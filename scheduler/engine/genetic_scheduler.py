import random
import copy
from collections import defaultdict
from scheduler.models import (
    TimeSlot, Room, Teacher, Subject, Section, 
    SectionSubjectRequirement, TeacherQualification, ScheduleItem
)

class Gene:
    def __init__(self, section_id, subject_id, teacher_id, room_id, timeslot_id, is_locked=False):
        self.section_id = section_id
        self.subject_id = subject_id
        self.teacher_id = teacher_id
        self.room_id = room_id
        self.timeslot_id = timeslot_id
        self.is_locked = is_locked

    def to_dict(self):
        return {
            'section_id': self.section_id,
            'subject_id': self.subject_id,
            'teacher_id': self.teacher_id,
            'room_id': self.room_id,
            'timeslot_id': self.timeslot_id,
            'is_locked': self.is_locked
        }

class Individual:
    def __init__(self, genes=None):
        self.genes = genes if genes is not None else []
        self.fitness = 0.0
        self.hard_conflicts = 0
        self.soft_conflicts = 0
        self.conflict_logs = []

class GeneticTimetableScheduler:
    def __init__(self, schedule, population_size=60, max_generations=150, elite_pct=0.1, mutation_rate=0.25):
        self.schedule = schedule
        self.population_size = population_size
        self.max_generations = max_generations
        self.elite_size = max(2, int(population_size * elite_pct))
        self.mutation_rate = mutation_rate

        # Reference data
        self.timeslots = list(TimeSlot.objects.filter(is_break=False))
        self.timeslot_ids = [ts.id for ts in self.timeslots]
        self.all_timeslots = {ts.id: ts for ts in TimeSlot.objects.all()}
        self.grade_timeslots = defaultdict(list)
        for ts in self.timeslots:
            self.grade_timeslots[ts.grade_level].append(ts.id)

        self.rooms = list(Room.objects.filter(is_active=True))
        self.rooms_by_id = {r.id: r for r in self.rooms}
        self.teachers = list(Teacher.objects.filter(is_active=True))
        self.teachers_by_id = {t.id: t for t in self.teachers}
        self.subjects = list(Subject.objects.all())
        self.subjects_by_id = {s.id: s for s in self.subjects}
        self.sections = list(Section.objects.filter(academic_year=schedule.academic_year))
        self.sections_by_id = {sec.id: sec for sec in self.sections}

        # Teacher qualifications
        self.teacher_qualifications = defaultdict(list)
        for tq in TeacherQualification.objects.select_related('teacher', 'subject'):
            self.teacher_qualifications[tq.subject_id].append(tq.teacher_id)

        # Requirements grouped by section
        self.section_requirements = defaultdict(list)
        self.locked_assigned_teachers = {}
        for req in SectionSubjectRequirement.objects.filter(section__in=self.sections).select_related('section', 'subject'):
            if req.assigned_teacher_id:
                self.locked_assigned_teachers[(req.section_id, req.subject_id)] = req.assigned_teacher_id
            for _ in range(int(round(req.subject.weekly_periods))):
                self.section_requirements[req.section_id].append({
                    'section_id': req.section_id,
                    'subject_id': req.subject_id,
                    'assigned_teacher': req.assigned_teacher_id,
                    'preferred_room': req.preferred_room_id or (req.section.homeroom_id if req.subject.room_type_needed == 'lecture' else None)
                })

        # Pre-calculate room compatibility
        self.rooms_by_type = defaultdict(list)
        for r in self.rooms:
            self.rooms_by_type[r.room_type].append(r.id)

    def get_slots_for_section(self, sec_id):
        sec = self.sections_by_id.get(sec_id)
        sec_grade = sec.grade_level if sec else 0
        if sec_grade in self.grade_timeslots and self.grade_timeslots[sec_grade]:
            return self.grade_timeslots[sec_grade]
        return self.grade_timeslots.get(0, self.timeslot_ids)

    def _get_valid_teacher(self, subject_id, assigned_teacher=None):
        if assigned_teacher and assigned_teacher in self.teachers_by_id:
            return assigned_teacher
        qualified = self.teacher_qualifications.get(subject_id, [])
        if qualified:
            return random.choice(qualified)
        return random.choice(self.teachers).id if self.teachers else None

    def _get_valid_room(self, subject_id, preferred_room=None):
        subject = self.subjects_by_id.get(subject_id)
        needed_type = subject.room_type_needed if subject else 'lecture'
        compatible = self.rooms_by_type.get(needed_type, [])
        if preferred_room and preferred_room in compatible:
            return preferred_room
        if compatible:
            return random.choice(compatible)
        # Fallback to standard lecture rooms or any room
        lectures = self.rooms_by_type.get('lecture', [])
        return random.choice(lectures) if lectures else (random.choice(self.rooms).id if self.rooms else None)

    def create_individual(self):
        genes = []
        for sec_id, reqs in self.section_requirements.items():
            num_reqs = len(reqs)
            sec_slots = self.get_slots_for_section(sec_id)
            if not sec_slots:
                sec_slots = self.timeslot_ids

            # Sample unique timeslots for this section (Permutation Model - zero self-collision)
            if num_reqs <= len(sec_slots):
                assigned_slots = random.sample(sec_slots, num_reqs)
            else:
                assigned_slots = [random.choice(sec_slots) for _ in range(num_reqs)]

            for i, req in enumerate(reqs):
                subj_id = req['subject_id']
                teacher_id = self._get_valid_teacher(subj_id, req.get('assigned_teacher'))
                room_id = self._get_valid_room(subj_id, req.get('preferred_room'))
                ts_id = assigned_slots[i]
                genes.append(Gene(sec_id, subj_id, teacher_id, room_id, ts_id))

        ind = Individual(genes)
        self.evaluate_fitness(ind)
        return ind

    def evaluate_fitness(self, individual):
        hard_penalties = 0
        soft_penalties = 0
        conflict_logs = []

        teacher_timeslot = defaultdict(list)
        room_timeslot = defaultdict(list)
        section_timeslot = defaultdict(list)
        teacher_day_intervals = defaultdict(list)
        room_day_intervals = defaultdict(list)
        teacher_daily_load = defaultdict(lambda: defaultdict(int))
        section_daily_subj = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

        for gene in individual.genes:
            ts = self.all_timeslots.get(gene.timeslot_id)
            if not ts:
                hard_penalties += 1000
                continue

            if ts.is_break:
                hard_penalties += 1000

            teacher_timeslot[(gene.teacher_id, gene.timeslot_id)].append(gene)
            room_timeslot[(gene.room_id, gene.timeslot_id)].append(gene)
            section_timeslot[(gene.section_id, gene.timeslot_id)].append(gene)

            day = ts.day_of_week
            teacher_day_intervals[(gene.teacher_id, day)].append((ts.start_time, ts.end_time, ts.id))
            room_day_intervals[(gene.room_id, day)].append((ts.start_time, ts.end_time, ts.id))
            teacher_daily_load[gene.teacher_id][day] += 1
            section_daily_subj[gene.section_id][day][gene.subject_id] += 1

            # Room type match constraint
            subj = self.subjects_by_id.get(gene.subject_id)
            room = self.rooms_by_id.get(gene.room_id)
            if subj and room and subj.room_type_needed != 'lecture' and room.room_type != subj.room_type_needed:
                hard_penalties += 500
                conflict_logs.append(f"Room mismatch: {subj.title} requires {subj.room_type_needed} but scheduled in {room.name}")

            # Soft constraint: Preferred vacant period
            teacher = self.teachers_by_id.get(gene.teacher_id)
            if teacher and teacher.preferred_vacant_period and ts.period_number == teacher.preferred_vacant_period:
                soft_penalties += 20

        # Check teacher double-booking (same timeslot)
        for (t_id, ts_id), glist in teacher_timeslot.items():
            if len(glist) > 1:
                hard_penalties += 1000 * (len(glist) - 1)
                t_name = self.teachers_by_id[t_id].full_name if t_id in self.teachers_by_id else f"Teacher #{t_id}"
                ts = self.all_timeslots.get(ts_id)
                conflict_logs.append(f"Teacher collision: {t_name} on {ts.get_day_of_week_display()} P{ts.period_number}")

        # Check teacher time overlap across different grade-level timeframes
        for (t_id, day), intervals in teacher_day_intervals.items():
            if len(intervals) > 1:
                intervals.sort(key=lambda x: x[0])
                for i in range(len(intervals) - 1):
                    s1, e1, ts1_id = intervals[i]
                    s2, e2, ts2_id = intervals[i+1]
                    if s2 < e1 and ts1_id != ts2_id:
                        hard_penalties += 1000
                        t_name = self.teachers_by_id[t_id].full_name if t_id in self.teachers_by_id else f"Teacher #{t_id}"
                        conflict_logs.append(f"Teacher clock overlap across grades: {t_name} on Day {day}")

        # Check room double-booking
        for (r_id, ts_id), glist in room_timeslot.items():
            if len(glist) > 1:
                hard_penalties += 1000 * (len(glist) - 1)
                r_name = self.rooms_by_id[r_id].name if r_id in self.rooms_by_id else f"Room #{r_id}"
                ts = self.all_timeslots.get(ts_id)
                conflict_logs.append(f"Room collision: {r_name} on {ts.get_day_of_week_display()} P{ts.period_number}")

        # Check room time overlap across different grade-level timeframes
        for (r_id, day), intervals in room_day_intervals.items():
            if len(intervals) > 1:
                intervals.sort(key=lambda x: x[0])
                for i in range(len(intervals) - 1):
                    s1, e1, ts1_id = intervals[i]
                    s2, e2, ts2_id = intervals[i+1]
                    if s2 < e1 and ts1_id != ts2_id:
                        hard_penalties += 1000
                        r_name = self.rooms_by_id[r_id].name if r_id in self.rooms_by_id else f"Room #{r_id}"
                        conflict_logs.append(f"Room clock overlap across grades: {r_name} on Day {day}")

        # Check section double-booking (if any)
        for (s_id, ts_id), glist in section_timeslot.items():
            if len(glist) > 1:
                hard_penalties += 1000 * (len(glist) - 1)
                s_name = self.sections_by_id[s_id].name if s_id in self.sections_by_id else f"Section #{s_id}"
                ts = self.all_timeslots.get(ts_id)
                conflict_logs.append(f"Section collision: {s_name} on {ts.get_day_of_week_display()} P{ts.period_number}")

        # Soft Constraint: DepEd DO 005 s. 2024 (max daily load)
        for t_id, days in teacher_daily_load.items():
            t = self.teachers_by_id.get(t_id)
            max_d = t.max_daily_hours if t else 6
            for day, count in days.items():
                if count > max_d:
                    soft_penalties += 40 * (count - max_d)

        # Soft Constraint: Subject Daily Clustering (max 2 per day)
        for s_id, days in section_daily_subj.items():
            for day, subjs in days.items():
                for sub_id, count in subjs.items():
                    if count > 2:
                        soft_penalties += 20 * (count - 2)

        total_penalty = hard_penalties + soft_penalties
        individual.fitness = max(0.0, 100.0 - (total_penalty / 100.0))
        individual.hard_conflicts = hard_penalties // 1000
        individual.soft_conflicts = soft_penalties // 20
        individual.conflict_logs = conflict_logs[:12]

    def selection(self, population):
        k = 3
        candidates = random.sample(population, k)
        return max(candidates, key=lambda x: x.fitness)

    def crossover(self, parent1, parent2):
        # Section-preserving crossover
        child_genes = []
        p1_by_sec = defaultdict(list)
        p2_by_sec = defaultdict(list)
        for g in parent1.genes:
            p1_by_sec[g.section_id].append(g)
        for g in parent2.genes:
            p2_by_sec[g.section_id].append(g)

        for sec_id in p1_by_sec.keys():
            donor = p1_by_sec if random.random() < 0.5 else p2_by_sec
            for g in donor[sec_id]:
                child_genes.append(copy.deepcopy(g))

        child = Individual(child_genes)
        return child

    def mutate(self, individual):
        genes_by_sec = defaultdict(list)
        for g in individual.genes:
            genes_by_sec[g.section_id].append(g)

        for sec_id, sec_genes in genes_by_sec.items():
            if random.random() < self.mutation_rate:
                # Pick two genes in this section and swap their timeslots
                if len(sec_genes) >= 2 and random.random() < 0.6:
                    g1, g2 = random.sample(sec_genes, 2)
                    if not g1.is_locked and not g2.is_locked:
                        g1.timeslot_id, g2.timeslot_id = g2.timeslot_id, g1.timeslot_id
                else:
                    # Move one gene to an unused timeslot for this section
                    used_ts = {g.timeslot_id for g in sec_genes}
                    sec_slots = self.get_slots_for_section(sec_id)
                    free_ts = [ts_id for ts_id in sec_slots if ts_id not in used_ts]
                    if free_ts:
                        g = random.choice(sec_genes)
                        if not g.is_locked:
                            g.timeslot_id = random.choice(free_ts)

                # Also mutate room or teacher
                if random.random() < 0.3:
                    target_gene = random.choice(sec_genes)
                    if not target_gene.is_locked:
                        if random.random() < 0.5:
                            # Only mutate teacher if not explicitly assigned by administrator
                            assigned_t = self.locked_assigned_teachers.get((target_gene.section_id, target_gene.subject_id))
                            if not assigned_t:
                                target_gene.teacher_id = self._get_valid_teacher(target_gene.subject_id)
                        else:
                            target_gene.room_id = self._get_valid_room(target_gene.subject_id)

    def run(self, progress_callback=None):
        if not self.section_requirements or not self.timeslot_ids:
            return None

        population = [self.create_individual() for _ in range(self.population_size)]
        population.sort(key=lambda x: x.fitness, reverse=True)

        best_individual = population[0]

        for gen in range(1, self.max_generations + 1):
            if best_individual.hard_conflicts == 0:
                # Zero hard collisions reached!
                break

            new_population = []
            for i in range(self.elite_size):
                new_population.append(copy.deepcopy(population[i]))

            while len(new_population) < self.population_size:
                p1 = self.selection(population)
                p2 = self.selection(population)
                child = self.crossover(p1, p2)
                self.mutate(child)
                self.evaluate_fitness(child)
                new_population.append(child)

            population = new_population
            population.sort(key=lambda x: x.fitness, reverse=True)

            if population[0].fitness > best_individual.fitness:
                best_individual = population[0]

            if progress_callback:
                progress_callback(gen, self.max_generations, best_individual.fitness, best_individual.hard_conflicts)

        self.evaluate_fitness(best_individual)
        return best_individual

    def apply_to_schedule(self, best_individual):
        ScheduleItem.objects.filter(schedule=self.schedule, is_locked=False).delete()

        # Deduplicate per (section, timeslot) just in case
        seen_sec_slot = set()
        items_to_create = []

        for g in best_individual.genes:
            if not g.is_locked:
                key = (g.section_id, g.timeslot_id)
                if key in seen_sec_slot:
                    continue
                seen_sec_slot.add(key)
                items_to_create.append(ScheduleItem(
                    schedule=self.schedule,
                    section_id=g.section_id,
                    subject_id=g.subject_id,
                    teacher_id=g.teacher_id,
                    room_id=g.room_id,
                    time_slot_id=g.timeslot_id,
                    is_locked=False
                ))

        ScheduleItem.objects.bulk_create(items_to_create)

        self.schedule.fitness_score = best_individual.fitness
        self.schedule.hard_conflicts_count = best_individual.hard_conflicts
        self.schedule.soft_conflicts_count = best_individual.soft_conflicts
        self.schedule.save()
        return len(items_to_create)
