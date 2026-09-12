from django.test import TestCase, Client
from django.urls import reverse
from scheduler.models import (
    AcademicYear, Term, Department, Room, Subject, Teacher, 
    TeacherQualification, Section, TimeSlot, SectionSubjectRequirement, Schedule, ScheduleItem
)
from scheduler.engine.genetic_scheduler import GeneticTimetableScheduler

class ClassmateAITestSuite(TestCase):
    def setUp(self):
        self.client = Client()
        self.ay = AcademicYear.objects.create(name="2026-2027", is_active=True)
        self.term = Term.objects.create(academic_year=self.ay, name="Term 1 SSHS", term_type="shs_term_1", is_active=True)
        self.dept = Department.objects.create(code="SCI", name="Science")
        self.room = Room.objects.create(name="Room 101", room_type="lecture", capacity=45)
        self.subject = Subject.objects.create(
            code="SCI-7", title="Science 7", grade_level=7, cluster="jhs_core",
            department=self.dept, room_type_needed="lecture", weekly_periods=2
        )
        self.teacher = Teacher.objects.create(
            employee_id="T-001", first_name="Juan", last_name="Dela Cruz",
            department=self.dept, max_daily_hours=6, max_weekly_hours=30
        )
        TeacherQualification.objects.create(teacher=self.teacher, subject=self.subject)
        self.section = Section.objects.create(name="Grade 7 - Rizal", grade_level=7, cluster="jhs_core", homeroom=self.room, academic_year=self.ay)
        SectionSubjectRequirement.objects.create(section=self.section, subject=self.subject, assigned_teacher=self.teacher, preferred_room=self.room)

        # Create slots
        from datetime import time
        self.ts1 = TimeSlot.objects.create(day_of_week=1, period_number=1, start_time=time(7, 45), end_time=time(8, 45), label="P1", is_break=False)
        self.ts2 = TimeSlot.objects.create(day_of_week=1, period_number=2, start_time=time(8, 45), end_time=time(9, 45), label="P2", is_break=False)
        self.ts_break = TimeSlot.objects.create(day_of_week=1, period_number=3, start_time=time(9, 45), end_time=time(10, 0), label="Recess", is_break=True)

        self.schedule = Schedule.objects.create(name="Test Schedule", academic_year=self.ay, term=self.term)

    def test_dashboard_loads(self):
        res = self.client.get(reverse('dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "CLASSMATE")

    def test_timetable_loads(self):
        res = self.client.get(reverse('timetable'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Timetable Studio")

    def test_teacher_loads_matrix(self):
        res = self.client.get(reverse('teacher_loads'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Faculty Teaching Load")

    def test_room_utilization_loads(self):
        res = self.client.get(reverse('room_utilization'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Room 101")

    def test_sample_csv_download(self):
        res = self.client.get(reverse('download_sample', args=['teachers']))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/csv')

    def test_genetic_algorithm_optimizer(self):
        optimizer = GeneticTimetableScheduler(self.schedule, population_size=20, max_generations=20)
        best = optimizer.run()
        self.assertIsNotNone(best)
        self.assertEqual(best.hard_conflicts, 0)
        count = optimizer.apply_to_schedule(best)
        self.assertEqual(count, 2)
        self.assertEqual(ScheduleItem.objects.filter(schedule=self.schedule).count(), 2)

    def test_swap_api_blocks_break_period(self):
        item = ScheduleItem.objects.create(
            schedule=self.schedule, section=self.section, subject=self.subject,
            teacher=self.teacher, room=self.room, time_slot=self.ts1
        )
        res = self.client.post(reverse('api_swap_item'), {
            'item_id': item.id,
            'target_day': 1,
            'target_period': 3, # Recess
        })
        data = res.json()
        self.assertFalse(data['success'])
        self.assertIn('break', data['message'].lower())

    def test_teachers_view_loads(self):
        res = self.client.get(reverse('teachers'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Faculty & Workload Management")

    def test_add_teacher_api(self):
        res = self.client.post(reverse('api_add_teacher'), {
            'first_name': 'Gabriela',
            'last_name': 'Silang',
            'employee_id': 'T-TEST-999',
            'curriculum_level': 'jhs',
            'max_daily_hours': 6,
            'subject_ids': [self.subject.id],
        })
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(Teacher.objects.filter(employee_id='T-TEST-999').exists())
        t = Teacher.objects.get(employee_id='T-TEST-999')
        self.assertEqual(t.curriculum_level, 'jhs')
        self.assertTrue(t.qualifications.filter(subject=self.subject).exists())

    def test_subjects_view_loads(self):
        res = self.client.get(reverse('subjects'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Curriculum & Subject Management")
        self.assertContains(res, "Science 7")

    def test_add_subject_api(self):
        res = self.client.post(reverse('api_add_subject'), {
            'code': 'MATH-8',
            'title': 'Mathematics 8',
            'grade_level': 8,
            'cluster': 'jhs_core',
            'room_type_needed': 'lecture',
            'weekly_periods': 4,
        })
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(Subject.objects.filter(code='MATH-8').exists())
        subj = Subject.objects.get(code='MATH-8')
        self.assertEqual(subj.weekly_periods, 4)

    def test_add_timeslot_api(self):
        res = self.client.post(reverse('api_add_timeslot'), {
            'label': 'Late Afternoon Slot',
            'period_number': 9,
            'start_time': '16:00',
            'end_time': '17:00',
            'is_break': False,
        })
        data = res.json()
        self.assertTrue(data['success'])
        # Should have created slots for Monday to Friday (5 days)
        slots = TimeSlot.objects.filter(period_number=9)
        self.assertEqual(slots.count(), 5)
        self.assertEqual(slots.first().label, 'Late Afternoon Slot')

    def test_delete_subject_api(self):
        subj = Subject.objects.create(
            code="TEMP-1", title="Temporary Subject", grade_level=7,
            cluster="jhs_core", weekly_periods=1
        )
        res = self.client.post(reverse('api_delete_subject', args=[subj.id]))
        data = res.json()
        self.assertTrue(data['success'])
        self.assertFalse(Subject.objects.filter(id=subj.id).exists())

    def test_sections_view_loads(self):
        res = self.client.get(reverse('sections'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Sections & Advisory Desk")
        self.assertContains(res, "Grade 7 - Rizal")

    def test_get_subjects_by_grade_api(self):
        res = self.client.get(reverse('api_subjects_by_grade') + '?grade_level=7')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(any(s['code'] == 'SCI-7' for s in data['subjects']))

    def test_add_section_api_with_assigned_teachers(self):
        import json
        assignments = [
            {'subject_id': self.subject.id, 'teacher_id': self.teacher.id, 'room_id': self.room.id}
        ]
        res = self.client.post(reverse('api_add_section'), {
            'name': 'Grade 7 - Luna',
            'grade_level': 7,
            'cluster': 'jhs_core',
            'homeroom_id': self.room.id,
            'adviser_id': self.teacher.id,
            'assignments': json.dumps(assignments),
        })
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(Section.objects.filter(name='Grade 7 - Luna').exists())
        sec = Section.objects.get(name='Grade 7 - Luna')
        self.assertEqual(sec.adviser, self.teacher)
        req = sec.subject_requirements.filter(subject=self.subject).first()
        self.assertIsNotNone(req)
        self.assertEqual(req.assigned_teacher, self.teacher)

    def test_update_section_assignments_api(self):
        import json
        assignments = [
            {'subject_id': self.subject.id, 'teacher_id': self.teacher.id}
        ]
        res = self.client.post(reverse('api_update_section_assignments', args=[self.section.id]), {
            'name': 'Grade 7 - Rizal Updated',
            'assignments': json.dumps(assignments),
        })
        data = res.json()
        self.assertTrue(data['success'])
        self.section.refresh_from_db()
        self.assertEqual(self.section.name, 'Grade 7 - Rizal Updated')

    def test_add_and_delete_ancillary_duty_api(self):
        # Add duty
        res = self.client.post(reverse('api_add_ancillary_duty'), {
            'teacher_id': self.teacher.id,
            'title': 'School ICT Coordinator',
            'designation_type': 'ict_coordinator',
            'weekly_hours': '4.0',
            'description': 'Handles LIS system and campus ICT equipment.'
        })
        data = res.json()
        self.assertTrue(data['success'])
        duty_id = data['duty_id']
        self.assertTrue(self.teacher.ancillary_duties.filter(id=duty_id).exists())
        duty = self.teacher.ancillary_duties.get(id=duty_id)
        self.assertEqual(duty.weekly_hours, 4.0)

        # Delete duty
        res_del = self.client.post(reverse('api_delete_ancillary_duty', args=[duty_id]))
        self.assertTrue(res_del.json()['success'])
        self.assertFalse(self.teacher.ancillary_duties.filter(id=duty_id).exists())

    def test_delete_section_api(self):
        sec = Section.objects.create(name='Grade 8 - Del Pilar', grade_level=8, academic_year=self.ay)
        res = self.client.post(reverse('api_delete_section', args=[sec.id]))
        self.assertTrue(res.json()['success'])
        self.assertFalse(Section.objects.filter(id=sec.id).exists())


