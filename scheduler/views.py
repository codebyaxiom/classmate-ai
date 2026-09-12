import csv
import io
import json
from collections import defaultdict
from datetime import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Count, Q
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from .models import (
    AcademicYear, Term, Department, Room, Subject, Teacher, TeacherQualification,
    Section, TimeSlot, SectionSubjectRequirement, Schedule, ScheduleItem, AuditLog,
    AncillaryDuty, SchoolProfile, CurriculumCluster, FacilityType, AncillaryDesignationCatalog
)
from .engine.genetic_scheduler import GeneticTimetableScheduler

def get_system_readiness_status():
    total_rooms = Room.objects.filter(is_active=True).count()
    active_ay = AcademicYear.objects.filter(is_active=True).exists()
    active_term = Term.objects.filter(is_active=True).exists()
    step1_done = (total_rooms > 0) and active_ay and active_term

    daily_periods_count = TimeSlot.objects.filter(day_of_week=1).count()
    step2_done = daily_periods_count > 0

    total_subjects = Subject.objects.count()
    step3_done = total_subjects > 0

    total_teachers = Teacher.objects.filter(is_active=True).count()
    total_quals = TeacherQualification.objects.count()
    step4_done = (total_teachers > 0) and (total_quals > 0)

    total_sections = Section.objects.count()
    assigned_requirements = SectionSubjectRequirement.objects.filter(assigned_teacher__isnull=False).count()
    step5_done = (total_sections > 0) and (assigned_requirements > 0)

    latest_schedule = Schedule.objects.order_by('-updated_at').first()
    total_scheduled = ScheduleItem.objects.filter(schedule=latest_schedule).count() if latest_schedule else 0
    step6_done = total_scheduled > 0

    steps = [
        {
            'step_num': 1,
            'code': 'facilities',
            'title': 'School & Facilities',
            'name': '1. School Profile & Facilities',
            'desc': 'Establish School Profile, active S.Y. & Term, and Room inventory (classrooms & laboratories).',
            'url': '/settings/#facilities',
            'icon': 'fa-solid fa-school',
            'is_completed': step1_done,
            'stat_badge': f"{total_rooms} Rooms" if total_rooms > 0 else "0 Rooms",
            'action_label': 'Manage Facilities' if step1_done else 'Set Up Facilities',
            'is_current': False,
        },
        {
            'step_num': 2,
            'code': 'timeframes',
            'title': 'Bell Schedules',
            'name': '2. Grade Bell Schedules',
            'desc': 'Define daily teaching periods, bell timeframes, and break intervals across JHS and SHS grade levels.',
            'url': '/timeframes/',
            'icon': 'fa-solid fa-clock',
            'is_completed': step2_done,
            'stat_badge': f"{daily_periods_count} Periods" if daily_periods_count > 0 else "Not Configured",
            'action_label': 'View Schedules' if step2_done else 'Create Bell Schedules',
            'is_current': False,
        },
        {
            'step_num': 3,
            'code': 'subjects',
            'title': 'Curriculum & Subjects',
            'name': '3. Curriculum & Subjects',
            'desc': 'Configure core, applied, and specialized subjects with weekly hours, lab room requirements, and clusters.',
            'url': '/subjects/',
            'icon': 'fa-solid fa-book-open-reader',
            'is_completed': step3_done,
            'stat_badge': f"{total_subjects} Subjects" if total_subjects > 0 else "0 Subjects",
            'action_label': 'Curriculum Hub' if step3_done else 'Add Subjects',
            'is_current': False,
        },
        {
            'step_num': 4,
            'code': 'teachers',
            'title': 'Faculty & Qualifications',
            'name': '4. Faculty Roster & Loads',
            'desc': 'Register teaching personnel, assign eligible subject qualifications, and log DepEd ancillary designations.',
            'url': '/teachers/',
            'icon': 'fa-solid fa-chalkboard-user',
            'is_completed': step4_done,
            'stat_badge': f"{total_teachers} Teachers" if total_teachers > 0 else "0 Teachers",
            'action_label': 'Faculty Desk' if step4_done else 'Add Teachers',
            'is_current': False,
        },
        {
            'step_num': 5,
            'code': 'sections',
            'title': 'Sections & Allocations',
            'name': '5. Class Sections & Allocations',
            'desc': 'Set up grade sections, designate homerooms, and allocate teacher loads to section subjects.',
            'url': '/sections/',
            'icon': 'fa-solid fa-people-roof',
            'is_completed': step5_done,
            'stat_badge': f"{total_sections} Sections" if total_sections > 0 else "0 Sections",
            'action_label': 'Manage Sections' if step5_done else 'Organize Sections',
            'is_current': False,
        },
        {
            'step_num': 6,
            'code': 'timetable',
            'title': 'AI Timetable Evolution',
            'name': '6. AI Timetable Evolution',
            'desc': 'Run the Genetic Algorithm to evolve collision-free schedules, review room utilization, and export SF7 matrices.',
            'url': '/timetable/',
            'icon': 'fa-solid fa-bolt',
            'is_completed': step6_done,
            'stat_badge': f"{total_scheduled} Bookings" if step6_done else "Ready to Run",
            'action_label': 'Timetable Studio' if step6_done else 'Run AI Optimizer',
            'is_current': False,
            'is_ai_action': True,
        }
    ]

    completed_count = sum(1 for s in steps if s['is_completed'])
    readiness_percentage = int(round((completed_count / len(steps)) * 100))

    next_step = None
    for s in steps:
        if not s['is_completed']:
            s['is_current'] = True
            next_step = s
            break
    if not next_step:
        steps[-1]['is_current'] = True
        next_step = steps[-1]

    return {
        'steps': steps,
        'completed_count': completed_count,
        'total_count': len(steps),
        'readiness_percentage': readiness_percentage,
        'next_step': next_step,
        'is_fully_ready': completed_count == len(steps),
    }

def dashboard_view(request):
    academic_year = AcademicYear.objects.filter(is_active=True).first()
    schedule = Schedule.objects.order_by('-updated_at').first()

    total_teachers = Teacher.objects.filter(is_active=True).count()
    total_sections = Section.objects.count()
    total_rooms = Room.objects.filter(is_active=True).count()
    total_subjects = Subject.objects.count()

    # Load statistics
    schedules = Schedule.objects.all().order_by('-created_at')
    
    # Conflict statistics
    hard_conflicts = schedule.hard_conflicts_count if schedule else 0
    soft_conflicts = schedule.soft_conflicts_count if schedule else 0
    fitness = schedule.fitness_score if schedule else 0.0

    # Section counts by grade
    jhs_sections = Section.objects.filter(grade_level__lte=10).count()
    shs_sections = Section.objects.filter(grade_level__gte=11).count()

    # Recent items
    total_scheduled_items = ScheduleItem.objects.filter(schedule=schedule).count() if schedule else 0

    readiness = get_system_readiness_status()

    context = {
        'academic_year': academic_year,
        'schedule': schedule,
        'schedules': schedules,
        'total_teachers': total_teachers,
        'total_sections': total_sections,
        'total_rooms': total_rooms,
        'total_subjects': total_subjects,
        'hard_conflicts': hard_conflicts,
        'soft_conflicts': soft_conflicts,
        'fitness': fitness,
        'jhs_sections': jhs_sections,
        'shs_sections': shs_sections,
        'total_scheduled_items': total_scheduled_items,
        'readiness': readiness,
    }
    return render(request, 'dashboard.html', context)

def timetable_view(request):
    schedules = Schedule.objects.all().order_by('-created_at')
    selected_schedule_id = request.GET.get('schedule_id')
    
    if selected_schedule_id:
        schedule = get_object_or_404(Schedule, id=selected_schedule_id)
    else:
        schedule = schedules.first()

    filter_type = request.GET.get('filter_type', 'section') # 'section', 'teacher', 'room'
    filter_id = request.GET.get('filter_id')

    sections = Section.objects.all().order_by('grade_level', 'name')
    teachers = Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name')
    rooms = Room.objects.filter(is_active=True).order_by('name')
    days = [(1, 'Monday'), (2, 'Tuesday'), (3, 'Wednesday'), (4, 'Thursday'), (5, 'Friday')]
    periods = list(range(1, 10))

    # Base query
    items = ScheduleItem.objects.none()
    current_entity_name = "All Classes"

    if schedule:
        qs = ScheduleItem.objects.filter(schedule=schedule).select_related('section', 'subject', 'teacher', 'room', 'time_slot')
        if filter_type == 'section':
            if not filter_id and sections.exists():
                filter_id = str(sections.first().id)
            if filter_id:
                qs = qs.filter(section_id=filter_id)
                sec = Section.objects.filter(id=filter_id).first()
                current_entity_name = f"Section: {sec.name}" if sec else "Section Schedule"
        elif filter_type == 'teacher':
            if not filter_id and teachers.exists():
                filter_id = str(teachers.first().id)
            if filter_id:
                qs = qs.filter(teacher_id=filter_id)
                t = Teacher.objects.filter(id=filter_id).first()
                current_entity_name = f"Teacher: {t.full_name}" if t else "Teacher Schedule"
        elif filter_type == 'room':
            if not filter_id and rooms.exists():
                filter_id = str(rooms.first().id)
            if filter_id:
                qs = qs.filter(room_id=filter_id)
                r = Room.objects.filter(id=filter_id).first()
                current_entity_name = f"Room: {r.name}" if r else "Room Schedule"
        items = qs

    # Build grid mapping: (day, period) -> item
    grid = {}
    for item in items:
        ts = item.time_slot
        grid[(ts.day_of_week, ts.period_number)] = item

    # Determine the target grade level for the timetable rows/axis
    view_grade = request.GET.get('view_grade')
    if view_grade:
        try:
            active_grade = int(view_grade)
        except ValueError:
            active_grade = 0
    elif filter_type == 'section' and filter_id:
        sec = Section.objects.filter(id=filter_id).first()
        active_grade = sec.grade_level if sec else 0
    elif filter_type == 'teacher' and filter_id:
        t = Teacher.objects.filter(id=filter_id).first()
        if t:
            advised = t.advised_sections.first()
            handled = SectionSubjectRequirement.objects.filter(assigned_teacher=t).first()
            sec = advised or (handled.section if handled else None)
            if sec:
                active_grade = sec.grade_level
            elif t.curriculum_level == 'shs':
                active_grade = 11
            elif t.curriculum_level == 'jhs':
                active_grade = 7
            else:
                active_grade = 0
        else:
            active_grade = 0
    else:
        active_grade = 0

    # Build structured timetable_rows for active grade level
    timeslots = TimeSlot.get_periods_for_grade(active_grade, day=1)
    timetable_rows = []
    for ts in timeslots:
        row = {
            'timeslot': ts,
            'is_break': ts.is_break,
            'days': []
        }
        for day_num, day_name in days:
            item = grid.get((day_num, ts.period_number))
            row['days'].append({
                'day_num': day_num,
                'day_name': day_name,
                'item': item,
            })
        timetable_rows.append(row)

    grade_dict = dict(TimeSlot.TIMEFRAME_GRADE_CHOICES)
    active_grade_label = grade_dict.get(active_grade, f"Grade {active_grade}")

    context = {
        'schedule': schedule,
        'schedules': schedules,
        'filter_type': filter_type,
        'filter_id': filter_id,
        'sections': sections,
        'teachers': teachers,
        'rooms': rooms,
        'days': days,
        'periods': periods,
        'grid': grid,
        'timeslots': timeslots,
        'timetable_rows': timetable_rows,
        'current_entity_name': current_entity_name,
        'active_grade': active_grade,
        'active_grade_label': active_grade_label,
        'grade_choices': TimeSlot.TIMEFRAME_GRADE_CHOICES,
    }
    return render(request, 'timetable.html', context)

def teacher_loads_view(request):
    schedule = Schedule.objects.order_by('-updated_at').first()
    teachers = Teacher.objects.filter(is_active=True).select_related('department').order_by('department__code', 'last_name')

    load_data = []
    if schedule:
        items = ScheduleItem.objects.filter(schedule=schedule).select_related('teacher', 'time_slot', 'subject', 'section')
        for t in teachers:
            t_items = [it for it in items if it.teacher_id == t.id]
            total_periods = len(t_items)
            
            # Group daily
            daily_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for it in t_items:
                daily_counts[it.time_slot.day_of_week] += 1

            max_day_load = max(daily_counts.values()) if daily_counts.values() else 0
            is_overloaded = max_day_load > t.max_daily_hours or total_periods > t.max_weekly_hours

            load_data.append({
                'teacher': t,
                'total_periods': total_periods,
                'daily_counts': daily_counts,
                'max_day_load': max_day_load,
                'is_overloaded': is_overloaded,
                'compliance_status': 'Overload Warning' if is_overloaded else 'DepEd Compliant',
                'items': t_items,
            })

    context = {
        'schedule': schedule,
        'load_data': load_data,
    }
    return render(request, 'teacher_loads.html', context)

def room_utilization_view(request):
    schedule = Schedule.objects.order_by('-updated_at').first()
    rooms = Room.objects.filter(is_active=True).order_by('room_type', 'name')
    timeslots = TimeSlot.objects.filter(day_of_week=1).order_by('period_number')
    days = [(1, 'Monday'), (2, 'Tuesday'), (3, 'Wednesday'), (4, 'Thursday'), (5, 'Friday')]

    # Calculate utilization percentage
    room_stats = []
    if schedule:
        total_schedulable_slots = TimeSlot.objects.filter(is_break=False).count()
        items = ScheduleItem.objects.filter(schedule=schedule)
        for r in rooms:
            occupied_count = items.filter(room=r).count()
            rate = (occupied_count / total_schedulable_slots * 100) if total_schedulable_slots > 0 else 0
            room_stats.append({
                'room': r,
                'occupied_count': occupied_count,
                'total_slots': total_schedulable_slots,
                'rate': round(rate, 1),
            })

    context = {
        'schedule': schedule,
        'rooms': rooms,
        'room_stats': room_stats,
        'days': days,
        'timeslots': timeslots,
    }
    return render(request, 'room_utilization.html', context)

@csrf_exempt
def run_genetic_algorithm(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    schedule_id = request.POST.get('schedule_id')
    if schedule_id:
        schedule = get_object_or_404(Schedule, id=schedule_id)
    else:
        schedule = Schedule.objects.order_by('-updated_at').first()
        if not schedule:
            ay = AcademicYear.objects.first()
            term = Term.objects.first()
            schedule = Schedule.objects.create(name="Automated S.Y. 2026-2027 Timetable", academic_year=ay, term=term)

    pop_size = int(request.POST.get('pop_size', 70))
    max_gens = int(request.POST.get('max_gens', 120))

    scheduler_engine = GeneticTimetableScheduler(schedule, population_size=pop_size, max_generations=max_gens)
    best_solution = scheduler_engine.run()

    if not best_solution:
        return JsonResponse({'success': False, 'message': 'Insufficient requirements or slots to generate timetable.'})

    saved_count = scheduler_engine.apply_to_schedule(best_solution)

    AuditLog.objects.create(
        action="Genetic Algorithm Timetable Generation",
        details=f"Generated {saved_count} items. Fitness: {best_solution.fitness:.2f}, Hard Conflicts: {best_solution.hard_conflicts}, Soft Conflicts: {best_solution.soft_conflicts}"
    )

    return JsonResponse({
        'success': True,
        'schedule_id': schedule.id,
        'schedule_name': schedule.name,
        'items_count': saved_count,
        'fitness': round(best_solution.fitness, 2),
        'hard_conflicts': best_solution.hard_conflicts,
        'soft_conflicts': best_solution.soft_conflicts,
        'conflict_logs': best_solution.conflict_logs,
    })

@csrf_exempt
def swap_item_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    item_id = request.POST.get('item_id')
    target_day = int(request.POST.get('target_day'))
    target_period = int(request.POST.get('target_period'))
    target_room_id = request.POST.get('target_room_id')
    target_teacher_id = request.POST.get('target_teacher_id')

    item = get_object_or_404(ScheduleItem, id=item_id)
    target_slot = get_object_or_404(TimeSlot, day_of_week=target_day, period_number=target_period)

    if target_slot.is_break:
        return JsonResponse({'success': False, 'message': 'Cannot schedule classes during designated break / lunch periods!'})

    # Collision Check
    target_room = Room.objects.get(id=target_room_id) if target_room_id else item.room
    target_teacher = Teacher.objects.get(id=target_teacher_id) if target_teacher_id else item.teacher

    # 1. Section collision
    sec_conflict = ScheduleItem.objects.filter(schedule=item.schedule, section=item.section, time_slot=target_slot).exclude(id=item.id).first()
    if sec_conflict:
        # Swap slots
        sec_conflict.time_slot = item.time_slot
        sec_conflict.save()

    # 2. Teacher collision
    t_conflict = ScheduleItem.objects.filter(schedule=item.schedule, teacher=target_teacher, time_slot=target_slot).exclude(id=item.id).first()
    if t_conflict and not sec_conflict:
        return JsonResponse({'success': False, 'message': f'Teacher {target_teacher.full_name} is already booked in section {t_conflict.section.name} at that time!'})

    # 3. Room collision
    r_conflict = ScheduleItem.objects.filter(schedule=item.schedule, room=target_room, time_slot=target_slot).exclude(id=item.id).first()
    if r_conflict and not sec_conflict:
        return JsonResponse({'success': False, 'message': f'Room {target_room.name} is already occupied by {r_conflict.section.name} at that time!'})

    # Update item
    item.time_slot = target_slot
    item.room = target_room
    item.teacher = target_teacher
    item.is_locked = True
    item.save()

    AuditLog.objects.create(
        action="Manual Timetable Adjustment",
        details=f"Adjusted {item.section.name} {item.subject.code} to {target_slot} (Room: {target_room.name}, Teacher: {target_teacher.full_name})"
    )

    return JsonResponse({'success': True, 'message': 'Schedule updated and slot locked!'})

@csrf_exempt
def toggle_lock_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    item_id = request.POST.get('item_id')
    item = get_object_or_404(ScheduleItem, id=item_id)
    item.is_locked = not item.is_locked
    item.save()
    return JsonResponse({'success': True, 'is_locked': item.is_locked})

def import_export_view(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        entity_type = request.POST.get('entity_type')
        csv_file = request.FILES['csv_file']
        decoded_file = csv_file.read().decode('utf-8-sig')
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)

        count = 0
        if entity_type == 'teachers':
            dept_sci = Department.objects.first()
            for row in reader:
                Teacher.objects.get_or_create(
                    employee_id=row['employee_id'].strip(),
                    defaults={
                        'first_name': row['first_name'].strip(),
                        'last_name': row['last_name'].strip(),
                        'email': row.get('email', '').strip(),
                        'department': dept_sci,
                        'max_daily_hours': int(row.get('max_daily_hours', 6)),
                    }
                )
                count += 1
            messages.success(request, f"Successfully imported {count} teachers!")

        elif entity_type == 'rooms':
            for row in reader:
                Room.objects.get_or_create(
                    name=row['name'].strip(),
                    defaults={
                        'room_type': row.get('room_type', 'lecture').strip(),
                        'capacity': int(row.get('capacity', 45)),
                        'building': row.get('building', '').strip(),
                    }
                )
                count += 1
            messages.success(request, f"Successfully imported {count} classrooms/laboratories!")

        return redirect('import_export')

    return render(request, 'import_export.html')

def download_sample_csv(request, template_type):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="sample_{template_type}.csv"'
    writer = csv.writer(response)

    if template_type == 'teachers':
        writer.writerow(['employee_id', 'first_name', 'last_name', 'email', 'max_daily_hours'])
        writer.writerow(['T-2026-101', 'Jose', 'Rizal', 'jose.rizal@deped.gov.ph', '6'])
        writer.writerow(['T-2026-102', 'Apolinario', 'Mabini', 'apolinario.mabini@deped.gov.ph', '6'])
    elif template_type == 'rooms':
        writer.writerow(['name', 'room_type', 'capacity', 'building'])
        writer.writerow(['Room 401', 'lecture', '45', 'Rizal Hall 4/F'])
        writer.writerow(['Science Lab 3', 'science_lab', '40', 'Science Complex'])
        writer.writerow(['Robotics Lab', 'computer_lab', '35', 'ICT Center'])

    return response

def export_excel(request):
    schedule = Schedule.objects.order_by('-updated_at').first()
    if not schedule:
        return HttpResponse("No schedule available to export.", status=404)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Master Timetable"

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0038A8", end_color="0038A8", fill_type="solid")
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    headers = ["Day", "Period", "Time Slot", "Grade & Section", "Subject Code", "Subject Title", "Teacher", "Room"]
    ws.append(headers)

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center

    items = ScheduleItem.objects.filter(schedule=schedule).select_related('section', 'subject', 'teacher', 'room', 'time_slot').order_by('time_slot__day_of_week', 'time_slot__period_number', 'section__name')

    for it in items:
        ws.append([
            it.time_slot.get_day_of_week_display(),
            f"Period {it.time_slot.period_number}",
            it.time_slot.label,
            it.section.name,
            it.subject.code,
            it.subject.title,
            it.teacher.full_name,
            it.room.name
        ])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="CLASSMATE_AI_{schedule.academic_year.name}_Schedule.xlsx"'
    wb.save(response)
    return response

def print_sf7_view(request, teacher_id=None):
    schedule = Schedule.objects.order_by('-updated_at').first()
    teacher = None
    items = []
    ancillary_duties = []
    ancillary_hours = 0.0
    if teacher_id:
        teacher = get_object_or_404(Teacher, id=teacher_id)
        if schedule:
            items = ScheduleItem.objects.filter(schedule=schedule, teacher=teacher).select_related('subject', 'section', 'room', 'time_slot').order_by('time_slot__day_of_week', 'time_slot__period_number')
        ancillary_duties = list(teacher.ancillary_duties.all())
        anc = sum(d.weekly_hours for d in ancillary_duties)
        ancillary_hours = int(anc) if anc == int(anc) else round(anc, 1)
    
    # Calculate weekly hours
    teaching_hours = len(items)
    tot = teaching_hours + ancillary_hours
    total_workload = int(tot) if tot == int(tot) else round(tot, 1)
    prep = max(0.0, 40.0 - total_workload) if total_workload > 0 else 0.0
    prep_hours = int(prep) if prep == int(prep) else round(prep, 1)

    context = {
        'schedule': schedule,
        'teacher': teacher,
        'items': items,
        'teaching_hours': teaching_hours,
        'total_hours': teaching_hours, # for backwards compatibility with existing template
        'ancillary_duties': ancillary_duties,
        'ancillary_hours': ancillary_hours,
        'total_workload': total_workload,
        'prep_hours': prep_hours,
        'profile': SchoolProfile.get_settings(),
    }
    return render(request, 'print_sf7.html', context)

def teachers_view(request):
    level_filter = request.GET.get('level')
    dept_filter = request.GET.get('dept')
    search_query = request.GET.get('q', '').strip()

    teachers = Teacher.objects.prefetch_related(
        'qualifications__subject',
        'ancillary_duties',
        'advised_sections'
    ).all().order_by('last_name')

    if level_filter:
        teachers = teachers.filter(curriculum_level=level_filter)
    if dept_filter:
        teachers = teachers.filter(department__code=dept_filter)
    if search_query:
        teachers = teachers.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(employee_id__icontains=search_query)
        )

    # Attach assigned sections and handled subjects
    teacher_assignments = defaultdict(list)
    for req in SectionSubjectRequirement.objects.filter(assigned_teacher__isnull=False).select_related('section', 'subject'):
        teacher_assignments[req.assigned_teacher_id].append(req)

    for t in teachers:
        t.handled_assignments = teacher_assignments.get(t.id, [])
        teach = sum(r.subject.weekly_periods for r in t.handled_assignments)
        t.teaching_hours = int(teach) if teach == int(teach) else round(teach, 1)
        t.duties_list = list(t.ancillary_duties.all())
        anc = sum(d.weekly_hours for d in t.duties_list)
        t.ancillary_hours = int(anc) if anc == int(anc) else round(anc, 1)
        tot = t.teaching_hours + t.ancillary_hours
        t.total_workload = int(tot) if tot == int(tot) else round(tot, 1)
        t.is_overload = (t.teaching_hours > t.max_weekly_hours) or (t.total_workload > 40)

    departments = Department.objects.all().order_by('name')
    subjects = Subject.objects.all().order_by('grade_level', 'code')
    timeframes = TimeSlot.objects.filter(day_of_week=1, is_break=False).order_by('grade_level', 'period_number')
    grouped_timeframes = defaultdict(list)
    for ts in timeframes:
        grade_lbl = dict(TimeSlot.TIMEFRAME_GRADE_CHOICES).get(ts.grade_level, f"Grade {ts.grade_level}")
        grouped_timeframes[grade_lbl].append(ts)

    common_designations = AncillaryDesignationCatalog.get_all_choices()

    context = {
        'teachers': teachers,
        'departments': departments,
        'subjects': subjects,
        'timeframes': timeframes,
        'grouped_timeframes': dict(grouped_timeframes),
        'common_designations': common_designations,
        'level_filter': level_filter,
        'dept_filter': dept_filter,
        'search_query': search_query,
    }
    return render(request, 'teachers.html', context)

@csrf_exempt
def add_teacher_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    emp_id = request.POST.get('employee_id', '').strip()
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    email = request.POST.get('email', '').strip()
    curriculum_level = request.POST.get('curriculum_level', 'both').strip()
    dept_id = request.POST.get('department_id')
    try:
        max_daily = float(request.POST.get('max_daily_hours', 6.0))
    except (ValueError, TypeError):
        max_daily = 6.0
    try:
        max_weekly = float(request.POST.get('max_weekly_hours', 30.0))
    except (ValueError, TypeError):
        max_weekly = 30.0
    pref_vacant = request.POST.get('preferred_vacant_period')
    subject_ids = request.POST.getlist('subject_ids')

    if not emp_id or not first_name or not last_name:
        return JsonResponse({'success': False, 'message': 'First Name, Last Name, and Employee ID are required.'})

    if Teacher.objects.filter(employee_id=emp_id).exists():
        return JsonResponse({'success': False, 'message': f'Employee ID {emp_id} is already registered.'})

    dept = Department.objects.filter(id=dept_id).first() if dept_id else None
    pref_v_int = int(pref_vacant) if pref_vacant and pref_vacant.isdigit() else None

    teacher = Teacher.objects.create(
        employee_id=emp_id,
        first_name=first_name,
        last_name=last_name,
        email=email or f"{first_name.lower()}.{last_name.lower()}@deped.gov.ph",
        curriculum_level=curriculum_level,
        department=dept,
        max_daily_hours=max_daily,
        max_weekly_hours=max_weekly,
        preferred_vacant_period=pref_v_int,
        is_active=True
    )

    for s_id in subject_ids:
        subj = Subject.objects.filter(id=s_id).first()
        if subj:
            TeacherQualification.objects.get_or_create(teacher=teacher, subject=subj)

    AuditLog.objects.create(
        action="Teacher Registered",
        details=f"Added faculty member {teacher.full_name} ({teacher.employee_id}, {teacher.get_curriculum_level_display()}) with {len(subject_ids)} qualified subjects."
    )

    return JsonResponse({
        'success': True,
        'message': f'Teacher {teacher.full_name} added successfully!',
        'teacher_id': teacher.id
    })


@csrf_exempt
def update_teacher_api(request, teacher_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    teacher = get_object_or_404(Teacher, id=teacher_id)
    emp_id = request.POST.get('employee_id', '').strip()
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    email = request.POST.get('email', '').strip()
    curriculum_level = request.POST.get('curriculum_level', 'both').strip()
    dept_id = request.POST.get('department_id')
    try:
        max_daily = float(request.POST.get('max_daily_hours', 6.0))
    except (ValueError, TypeError):
        max_daily = 6.0
    try:
        max_weekly = float(request.POST.get('max_weekly_hours', 30.0))
    except (ValueError, TypeError):
        max_weekly = 30.0
    pref_vacant = request.POST.get('preferred_vacant_period')
    subject_ids = request.POST.getlist('subject_ids')

    if not emp_id or not first_name or not last_name:
        return JsonResponse({'success': False, 'message': 'First Name, Last Name, and Employee ID are required.'})

    if Teacher.objects.filter(employee_id=emp_id).exclude(id=teacher.id).exists():
        return JsonResponse({'success': False, 'message': f'Employee ID {emp_id} is already in use by another teacher.'})

    dept = Department.objects.filter(id=dept_id).first() if dept_id else None
    pref_v_int = int(pref_vacant) if pref_vacant and pref_vacant.isdigit() else None

    old_name = teacher.full_name
    teacher.employee_id = emp_id
    teacher.first_name = first_name
    teacher.last_name = last_name
    teacher.email = email or f"{first_name.lower()}.{last_name.lower()}@deped.gov.ph"
    teacher.curriculum_level = curriculum_level
    teacher.department = dept
    teacher.max_daily_hours = max_daily
    teacher.max_weekly_hours = max_weekly
    teacher.preferred_vacant_period = pref_v_int
    teacher.save()

    # Update qualifications
    TeacherQualification.objects.filter(teacher=teacher).delete()
    for s_id in subject_ids:
        subj = Subject.objects.filter(id=s_id).first()
        if subj:
            TeacherQualification.objects.create(teacher=teacher, subject=subj)

    AuditLog.objects.create(
        action="Teacher Profile Updated",
        details=f"Updated faculty member {old_name} -> {teacher.full_name} ({teacher.employee_id}, {teacher.get_curriculum_level_display()}) with {len(subject_ids)} qualified subjects."
    )

    return JsonResponse({
        'success': True,
        'message': f'Teacher {teacher.full_name} updated successfully!',
        'teacher_id': teacher.id
    })


@csrf_exempt
def delete_teacher_api(request, teacher_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    teacher = get_object_or_404(Teacher, id=teacher_id)
    name = teacher.full_name
    teacher.delete()

    AuditLog.objects.create(
        action="Teacher Removed",
        details=f"Removed faculty member {name}."
    )

    return JsonResponse({'success': True, 'message': f'Faculty member {name} removed.'})



def subjects_view(request):
    grade_filter = request.GET.get('grade')
    cluster_filter = request.GET.get('cluster')
    search_query = request.GET.get('q', '').strip()

    subjects = Subject.objects.all().order_by('grade_level', 'code')
    if grade_filter:
        subjects = subjects.filter(grade_level=grade_filter)
    if cluster_filter:
        subjects = subjects.filter(cluster=cluster_filter)
    if search_query:
        subjects = subjects.filter(
            Q(code__icontains=search_query) |
            Q(title__icontains=search_query)
        )

    context = {
        'subjects': subjects,
        'grade_filter': grade_filter,
        'cluster_filter': cluster_filter,
        'search_query': search_query,
        'clusters': CurriculumCluster.get_all_choices(),
        'room_types': Room.ROOM_TYPES,
    }
    return render(request, 'subjects.html', context)

@csrf_exempt
def add_subject_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    code = request.POST.get('code', '').strip().upper()
    title = request.POST.get('title', '').strip()
    grade_level = int(request.POST.get('grade_level', 7))
    cluster = request.POST.get('cluster', 'jhs_core')
    room_type_needed = request.POST.get('room_type_needed', 'lecture')
    try:
        weekly_periods = float(request.POST.get('weekly_periods', 4.0))
    except (ValueError, TypeError):
        weekly_periods = 4.0
    consecutive_periods = int(request.POST.get('consecutive_periods', 1))
    is_lab = request.POST.get('is_lab') == 'true' or consecutive_periods > 1 or room_type_needed != 'lecture'

    if not code or not title:
        return JsonResponse({'success': False, 'message': 'Subject code and title are required.'})

    if Subject.objects.filter(code=code).exists():
        return JsonResponse({'success': False, 'message': f'Subject code {code} already exists.'})

    subj = Subject.objects.create(
        code=code,
        title=title,
        grade_level=grade_level,
        cluster=cluster,
        room_type_needed=room_type_needed,
        weekly_periods=weekly_periods,
        consecutive_periods=consecutive_periods,
        is_lab=is_lab
    )

    AuditLog.objects.create(
        action="Subject Registered",
        details=f"Added subject {subj.code} — {subj.title} (Grade {subj.grade_level}, {subj.cluster_display_name})."
    )

    return JsonResponse({
        'success': True,
        'message': f'Subject {subj.code} registered successfully!',
        'subject_id': subj.id
    })


@csrf_exempt
def update_subject_api(request, subject_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    subj = get_object_or_404(Subject, id=subject_id)
    code = request.POST.get('code', '').strip().upper()
    title = request.POST.get('title', '').strip()
    try:
        grade_level = int(request.POST.get('grade_level', subj.grade_level))
    except (ValueError, TypeError):
        grade_level = subj.grade_level
    cluster = request.POST.get('cluster', subj.cluster)
    room_type_needed = request.POST.get('room_type_needed', subj.room_type_needed)
    try:
        weekly_periods = float(request.POST.get('weekly_periods', subj.weekly_periods))
    except (ValueError, TypeError):
        weekly_periods = subj.weekly_periods
    try:
        consecutive_periods = int(request.POST.get('consecutive_periods', subj.consecutive_periods))
    except (ValueError, TypeError):
        consecutive_periods = subj.consecutive_periods
    is_lab = request.POST.get('is_lab') == 'true' or consecutive_periods > 1 or room_type_needed != 'lecture'

    if not code or not title:
        return JsonResponse({'success': False, 'message': 'Subject code and title are required.'})

    if Subject.objects.filter(code=code).exclude(id=subj.id).exists():
        return JsonResponse({'success': False, 'message': f'Subject code {code} is already used by another subject.'})

    old_code = subj.code
    subj.code = code
    subj.title = title
    subj.grade_level = grade_level
    subj.cluster = cluster
    subj.room_type_needed = room_type_needed
    subj.weekly_periods = weekly_periods
    subj.consecutive_periods = consecutive_periods
    subj.is_lab = is_lab
    subj.save()

    AuditLog.objects.create(
        action="Subject Updated",
        details=f"Updated subject {old_code} -> {subj.code} — {subj.title} (Grade {subj.grade_level}, {subj.cluster_display_name})."
    )

    return JsonResponse({
        'success': True,
        'message': f'Subject {subj.code} updated successfully!',
        'subject_id': subj.id
    })


@csrf_exempt
def delete_subject_api(request, subject_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    subj = get_object_or_404(Subject, id=subject_id)
    code = subj.code
    subj.delete()

    AuditLog.objects.create(
        action="Subject Removed",
        details=f"Deleted subject {code}."
    )

    return JsonResponse({'success': True, 'message': f'Subject {code} deleted.'})

@csrf_exempt
def add_timeslot_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    start_str = request.POST.get('start_time', '').strip() # e.g. "07:30"
    end_str = request.POST.get('end_time', '').strip()     # e.g. "08:30"
    label = request.POST.get('label', '').strip()
    is_break = request.POST.get('is_break') == 'true'

    if not start_str or not end_str:
        return JsonResponse({'success': False, 'message': 'Start and end times are required.'})

    try:
        st_parts = [int(p) for p in start_str.split(':')]
        et_parts = [int(p) for p in end_str.split(':')]
        from datetime import time as dt_time
        st = dt_time(st_parts[0], st_parts[1])
        et = dt_time(et_parts[0], et_parts[1])
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'Invalid time format. Use HH:MM.'})

    # Determine period_number
    req_period = request.POST.get('period_number')
    if req_period:
        try:
            next_period = int(req_period)
        except ValueError:
            existing_periods = TimeSlot.objects.filter(day_of_week=1).order_by('-period_number')
            next_period = (existing_periods.first().period_number + 1) if existing_periods.exists() else 1
    else:
        existing_periods = TimeSlot.objects.filter(day_of_week=1).order_by('-period_number')
        next_period = (existing_periods.first().period_number + 1) if existing_periods.exists() else 1
    
    if not label:
        label = f"{'Break' if is_break else 'Period'} {st.strftime('%I:%M %p')} - {et.strftime('%I:%M %p')}"

    # Create for Monday through Friday (days 1 to 5)
    created_count = 0
    for day in range(1, 6):
        TimeSlot.objects.update_or_create(
            day_of_week=day,
            period_number=next_period,
            defaults={
                'start_time': st,
                'end_time': et,
                'label': label,
                'is_break': is_break
            }
        )
        created_count += 1

    AuditLog.objects.create(
        action="Timeframe Added",
        details=f"Added custom timeframe {st.strftime('%I:%M %p')} - {et.strftime('%I:%M %p')} (Period {next_period}) across Mon-Fri."
    )

    return JsonResponse({
        'success': True,
        'message': f'Timeframe {st.strftime("%I:%M %p")} - {et.strftime("%I:%M %p")} added for Mon-Fri!',
        'period_number': next_period,
        'formatted_label': f"{st.strftime('%I:%M %p')} - {et.strftime('%I:%M %p')} (Period {next_period})"
    })


def sections_view(request):
    grade_filter = request.GET.get('grade')
    cluster_filter = request.GET.get('cluster')
    search_query = request.GET.get('q', '').strip()

    sections = Section.objects.select_related('homeroom', 'adviser', 'academic_year').prefetch_related(
        'subject_requirements__subject',
        'subject_requirements__assigned_teacher',
        'subject_requirements__preferred_room'
    ).all().order_by('grade_level', 'name')

    if grade_filter:
        sections = sections.filter(grade_level=grade_filter)
    if cluster_filter:
        sections = sections.filter(cluster=cluster_filter)
    if search_query:
        sections = sections.filter(name__icontains=search_query)

    for sec in sections:
        reqs = list(sec.subject_requirements.all())
        sec.total_subjects_count = len(reqs)
        sec.total_weekly_hours = sum(r.subject.weekly_periods for r in reqs)
        sec.assigned_faculty_count = sum(1 for r in reqs if r.assigned_teacher is not None)

    rooms = Room.objects.filter(is_active=True).order_by('name')
    teachers = Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name')
    subjects = Subject.objects.all().order_by('grade_level', 'code')
    clusters = CurriculumCluster.get_all_choices()
    grades = Subject.GRADE_CHOICES

    context = {
        'sections': sections,
        'rooms': rooms,
        'teachers': teachers,
        'subjects': subjects,
        'clusters': clusters,
        'grades': grades,
        'grade_filter': grade_filter,
        'cluster_filter': cluster_filter,
        'search_query': search_query,
    }
    return render(request, 'sections.html', context)


def get_subjects_by_grade_api(request):
    grade_level = request.GET.get('grade_level')
    cluster = request.GET.get('cluster')
    if not grade_level:
        return JsonResponse({'success': False, 'message': 'Grade level required'}, status=400)
    
    subjs = Subject.objects.filter(grade_level=grade_level)
    if cluster and cluster != 'all':
        subjs = subjs.filter(Q(cluster=cluster) | Q(cluster='shs_core') | Q(cluster='jhs_core'))

    subjs = subjs.order_by('code')
    
    qual_map = defaultdict(list)
    for q in TeacherQualification.objects.filter(subject__in=subjs).select_related('teacher'):
        qual_map[q.subject_id].append({'id': q.teacher.id, 'name': q.teacher.full_name})

    data = []
    for s in subjs:
        data.append({
            'id': s.id,
            'code': s.code,
            'title': s.title,
            'weekly_periods': s.weekly_periods,
            'room_type_needed': s.room_type_needed,
            'room_type_label': s.get_room_type_needed_display(),
            'qualified_teachers': qual_map.get(s.id, [])
        })

    return JsonResponse({'success': True, 'subjects': data})


@csrf_exempt
def add_section_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    name = request.POST.get('name', '').strip()
    grade_level = request.POST.get('grade_level')
    cluster = request.POST.get('cluster', 'jhs_core')
    homeroom_id = request.POST.get('homeroom_id')
    adviser_id = request.POST.get('adviser_id')

    if not name or not grade_level:
        return JsonResponse({'success': False, 'message': 'Section name and grade level are required.'})

    ay = AcademicYear.objects.filter(is_active=True).first()
    if not ay:
        ay = AcademicYear.objects.first()

    if Section.objects.filter(name=name, academic_year=ay).exists():
        return JsonResponse({'success': False, 'message': f'Section "{name}" already exists.'})

    homeroom = Room.objects.filter(id=homeroom_id).first() if homeroom_id else None
    adviser = Teacher.objects.filter(id=adviser_id).first() if adviser_id else None

    section = Section.objects.create(
        name=name,
        grade_level=int(grade_level),
        cluster=cluster,
        homeroom=homeroom,
        adviser=adviser,
        academic_year=ay
    )

    if adviser:
        AncillaryDuty.objects.get_or_create(
            teacher=adviser,
            title=f"Class Adviser ({section.name})",
            defaults={'designation_type': 'adviser', 'weekly_hours': 2.0}
        )

    assignments_json = request.POST.get('assignments')
    assigned_count = 0
    if assignments_json:
        try:
            assignments = json.loads(assignments_json)
            for item in assignments:
                subj_id = item.get('subject_id')
                teacher_id = item.get('teacher_id') or None
                room_id = item.get('room_id') or None

                subj = Subject.objects.filter(id=subj_id).first()
                if subj:
                    SectionSubjectRequirement.objects.create(
                        section=section,
                        subject=subj,
                        assigned_teacher_id=teacher_id if teacher_id else None,
                        preferred_room_id=room_id if room_id else None
                    )
                    assigned_count += 1
        except Exception:
            pass

    AuditLog.objects.create(
        action="Section Created",
        details=f"Created section {section.name} (Grade {section.grade_level}) with {assigned_count} subject assignments."
    )

    return JsonResponse({
        'success': True,
        'message': f'Section "{section.name}" created with {assigned_count} subjects established!',
        'section_id': section.id
    })


@csrf_exempt
def update_section_assignments_api(request, section_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    section = get_object_or_404(Section, id=section_id)
    name = request.POST.get('name', '').strip()
    homeroom_id = request.POST.get('homeroom_id')
    adviser_id = request.POST.get('adviser_id')

    if name:
        section.name = name
    if homeroom_id:
        section.homeroom = Room.objects.filter(id=homeroom_id).first()
    if adviser_id is not None:
        if adviser_id:
            adviser = Teacher.objects.filter(id=adviser_id).first()
            section.adviser = adviser
            if adviser:
                AncillaryDuty.objects.get_or_create(
                    teacher=adviser,
                    title=f"Class Adviser ({section.name})",
                    defaults={'designation_type': 'adviser', 'weekly_hours': 2.0}
                )
        else:
            section.adviser = None
    section.save()

    assignments_json = request.POST.get('assignments')
    if assignments_json:
        try:
            assignments = json.loads(assignments_json)
            existing_subjs = set()
            for item in assignments:
                subj_id = item.get('subject_id')
                teacher_id = item.get('teacher_id') or None
                room_id = item.get('room_id') or None

                subj = Subject.objects.filter(id=subj_id).first()
                if subj:
                    existing_subjs.add(subj.id)
                    SectionSubjectRequirement.objects.update_or_create(
                        section=section,
                        subject=subj,
                        defaults={
                            'assigned_teacher_id': teacher_id if teacher_id else None,
                            'preferred_room_id': room_id if room_id else None
                        }
                    )
            if request.POST.get('replace_all') == 'true':
                SectionSubjectRequirement.objects.filter(section=section).exclude(subject_id__in=existing_subjs).delete()
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error updating assignments: {str(e)}'})

    AuditLog.objects.create(
        action="Section Updated",
        details=f"Updated subject & teacher assignments for section {section.name}."
    )

    return JsonResponse({'success': True, 'message': f'Assignments for {section.name} updated successfully!'})


@csrf_exempt
def delete_section_api(request, section_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    section = get_object_or_404(Section, id=section_id)
    name = section.name
    section.delete()

    AuditLog.objects.create(
        action="Section Deleted",
        details=f"Deleted section {name} and its curriculum requirements."
    )

    return JsonResponse({'success': True, 'message': f'Section {name} deleted.'})


@csrf_exempt
def add_ancillary_duty_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    teacher_id = request.POST.get('teacher_id')
    title = request.POST.get('title', '').strip()
    designation_type = request.POST.get('designation_type', 'custom')
    weekly_hours_str = request.POST.get('weekly_hours', '2.0')
    description = request.POST.get('description', '').strip()

    if not teacher_id or not title:
        return JsonResponse({'success': False, 'message': 'Teacher and Designation title are required.'})

    teacher = get_object_or_404(Teacher, id=teacher_id)
    try:
        weekly_hours = float(weekly_hours_str)
    except ValueError:
        weekly_hours = 2.0

    duty = AncillaryDuty.objects.create(
        teacher=teacher,
        title=title,
        designation_type=designation_type,
        weekly_hours=weekly_hours,
        description=description
    )

    cat_code = designation_type if designation_type != 'custom' else title.lower().replace(' ', '_').replace('-', '_')[:50]
    AncillaryDesignationCatalog.objects.get_or_create(
        code=cat_code,
        defaults={
            'name': title,
            'default_weekly_hours': weekly_hours,
            'description': description or f"Auto-registered from faculty assignment ({title})"
        }
    )

    AuditLog.objects.create(
        action="Ancillary Designation Added",
        details=f"Assigned '{duty.title}' ({duty.weekly_hours}h/wk) to {teacher.full_name}."
    )

    return JsonResponse({
        'success': True,
        'message': f"Designation '{duty.title}' added to {teacher.full_name} ({duty.weekly_hours} hrs/wk).",
        'duty_id': duty.id,
        'title': duty.title,
        'weekly_hours': duty.weekly_hours,
    })


@csrf_exempt
def delete_ancillary_duty_api(request, duty_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    duty = get_object_or_404(AncillaryDuty, id=duty_id)
    teacher_name = duty.teacher.full_name
    title = duty.title
    duty.delete()

    AuditLog.objects.create(
        action="Ancillary Designation Removed",
        details=f"Removed designation '{title}' from {teacher_name}."
    )

    return JsonResponse({
        'success': True,
        'message': f"Designation '{title}' removed from {teacher_name}."
    })



def timeframes_view(request):
    try:
        selected_grade = int(request.GET.get('grade', 0))
    except (ValueError, TypeError):
        selected_grade = 0

    grade_choices = TimeSlot.TIMEFRAME_GRADE_CHOICES

    # Group counts of slots by grade level
    slot_counts = {}
    for g_val, _ in grade_choices:
        slot_counts[g_val] = TimeSlot.objects.filter(grade_level=g_val, day_of_week=1).count()

    # Get Monday slots as the canonical period definitions for this grade level
    periods = TimeSlot.objects.filter(grade_level=selected_grade, day_of_week=1).order_by('period_number')

    context = {
        'selected_grade': selected_grade,
        'grade_choices': grade_choices,
        'slot_counts': slot_counts,
        'periods': periods,
        'profile': SchoolProfile.get_settings(),
    }
    return render(request, 'timeframes.html', context)


@csrf_exempt
def add_timeframe_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    try:
        grade_level = int(request.POST.get('grade_level', 0))
        label = request.POST.get('label', '').strip()
        start_time_str = request.POST.get('start_time', '').strip()
        end_time_str = request.POST.get('end_time', '').strip()
        is_break = request.POST.get('is_break') in ['true', 'True', '1', 1, True]

        if not label or not start_time_str or not end_time_str:
            return JsonResponse({'success': False, 'message': 'Label, start time, and end time are required.'})

        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()

        period_number = request.POST.get('period_number')
        if period_number:
            period_number = int(period_number)
        else:
            existing = TimeSlot.objects.filter(grade_level=grade_level, day_of_week=1).order_by('-period_number').first()
            period_number = (existing.period_number + 1) if existing else 1

        for day in range(1, 6):
            TimeSlot.objects.update_or_create(
                day_of_week=day,
                period_number=period_number,
                grade_level=grade_level,
                defaults={
                    'label': label,
                    'start_time': start_time,
                    'end_time': end_time,
                    'is_break': is_break,
                }
            )

        AuditLog.objects.create(
            action="Timeframe Period Established",
            details=f"P{period_number} '{label}' ({start_time_str}-{end_time_str}) configured for Grade {grade_level} across Mon-Fri."
        )

        return JsonResponse({'success': True, 'message': f"Period P{period_number} ({label}) established successfully!"})

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@csrf_exempt
def delete_timeframe_api(request, period_number):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    try:
        grade_level = int(request.POST.get('grade_level', 0))
        deleted_count, _ = TimeSlot.objects.filter(period_number=period_number, grade_level=grade_level).delete()

        AuditLog.objects.create(
            action="Timeframe Period Deleted",
            details=f"Deleted P{period_number} for Grade {grade_level} ({deleted_count} slots removed)."
        )

        return JsonResponse({'success': True, 'message': f"Period P{period_number} removed."})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@csrf_exempt
def apply_preset_timeframes_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    preset_type = request.POST.get('preset_type', 'shs_sample')
    try:
        grade_level = int(request.POST.get('grade_level', 11))
    except (ValueError, TypeError):
        grade_level = 11

    # Clear existing periods for this grade level
    TimeSlot.objects.filter(grade_level=grade_level).delete()

    if preset_type == 'shs_sample':
        schedule_def = [
            (1, "Flag Ceremony", "07:00", "07:30", True),
            (2, "Period 1", "07:30", "08:30", False),
            (3, "Period 2", "08:30", "09:30", False),
            (4, "Morning Recess", "09:30", "09:45", True),
            (5, "Period 3", "09:45", "10:45", False),
            (6, "Period 4", "10:45", "11:45", False),
            (7, "Noon Break", "11:45", "13:00", True),
            (8, "Period 5 (Lab / Block)", "13:00", "14:30", False),
            (9, "Homeroom Guidance / Remediation", "14:30", "15:00", False),
            (10, "Period 6", "15:00", "16:00", False),
        ]
        label_preset = "Strengthened SHS Trimester Bell Schedule"
    elif preset_type == 'shs_immersion':
        schedule_def = [
            (1, "Flag Ceremony", "07:00", "07:30", True),
            (2, "Period 1 (Practicum Block)", "07:30", "09:00", False),
            (3, "Period 2 (Specialized Block)", "09:00", "10:30", False),
            (4, "Morning Recess", "10:30", "10:45", True),
            (5, "Period 3 (Applied Block)", "10:45", "12:15", False),
            (6, "Noon Break", "12:15", "13:15", True),
            (7, "Period 4 (Work Immersion / Research)", "13:15", "14:45", False),
            (8, "Period 5 (Culminating Activity)", "14:45", "16:15", False),
        ]
        label_preset = "Senior High Immersion & Block Schedule (90m Periods)"
    else:
        schedule_def = [
            (1, "Flag Ceremony", "07:15", "07:45", True),
            (2, "Period 1", "07:45", "08:45", False),
            (3, "Period 2", "08:45", "09:45", False),
            (4, "Morning Recess", "09:45", "10:00", True),
            (5, "Period 3", "10:00", "11:00", False),
            (6, "Period 4", "11:00", "12:00", False),
            (7, "Noon Break", "12:00", "13:00", True),
            (8, "Period 5", "13:00", "14:00", False),
            (9, "Period 6", "14:00", "15:00", False),
            (10, "Homeroom / Remediation", "15:00", "16:00", False),
        ]
        label_preset = "Standard JHS Bell Schedule"

    for p_num, lbl, s_str, e_str, is_brk in schedule_def:
        s_time = datetime.strptime(s_str, '%H:%M').time()
        e_time = datetime.strptime(e_str, '%H:%M').time()
        for day in range(1, 6):
            TimeSlot.objects.create(
                day_of_week=day,
                period_number=p_num,
                grade_level=grade_level,
                label=lbl,
                start_time=s_time,
                end_time=e_time,
                is_break=is_brk
            )

    AuditLog.objects.create(
        action="Applied Bell Schedule Preset",
        details=f"Loaded '{label_preset}' for Grade {grade_level} (10 periods)."
    )

    return JsonResponse({
        'success': True,
        'message': f"Successfully applied '{label_preset}' to Grade {grade_level}!"
    })


@csrf_exempt
def copy_grade_timeframes_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    try:
        source_grade = int(request.POST.get('source_grade'))
        target_grade = int(request.POST.get('target_grade'))
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'message': 'Valid source and target grade required.'}, status=400)

    if source_grade == target_grade:
        return JsonResponse({'success': False, 'message': 'Source and target grade must be different.'})

    source_slots = TimeSlot.objects.filter(grade_level=source_grade)
    if not source_slots.exists():
        return JsonResponse({'success': False, 'message': f'No timeframes found for Grade {source_grade} to copy from.'})

    TimeSlot.objects.filter(grade_level=target_grade).delete()

    created_count = 0
    for s in source_slots:
        TimeSlot.objects.create(
            day_of_week=s.day_of_week,
            period_number=s.period_number,
            start_time=s.start_time,
            end_time=s.end_time,
            label=s.label,
            is_break=s.is_break,
            grade_level=target_grade
        )
        created_count += 1

    grade_dict = dict(TimeSlot.TIMEFRAME_GRADE_CHOICES)
    src_name = grade_dict.get(source_grade, f"Grade {source_grade}")
    tgt_name = grade_dict.get(target_grade, f"Grade {target_grade}")

    AuditLog.objects.create(
        action="Timeframes Cloned",
        details=f"Copied schedule from {src_name} to {tgt_name} ({created_count} slots created)."
    )

    return JsonResponse({
        'success': True,
        'message': f'Successfully copied schedule from {src_name} to {tgt_name} ({created_count} slots)!'
    })


@csrf_exempt
def clear_grade_timeframes_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    try:
        grade_level = int(request.POST.get('grade_level'))
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'message': 'Valid grade level required.'}, status=400)

    deleted_count, _ = TimeSlot.objects.filter(grade_level=grade_level).delete()

    AuditLog.objects.create(
        action="Timeframes Cleared",
        details=f"Cleared all schedule periods for Grade {grade_level} ({deleted_count} slots deleted)."
    )

    return JsonResponse({
        'success': True,
        'message': f'Cleared all periods for Grade {grade_level}!'
    })


def settings_view(request):
    profile = SchoolProfile.get_settings()
    rooms = Room.objects.all().order_by('building', 'name')
    clusters = CurriculumCluster.objects.all().order_by('curriculum_level', 'name')
    facility_types = FacilityType.objects.all().order_by('name')
    ancillary_catalog = AncillaryDesignationCatalog.objects.all().order_by('name')
    academic_years = AcademicYear.objects.all().order_by('-name')
    terms = Term.objects.all().order_by('academic_year', 'name')
    departments = Department.objects.all().order_by('name')

    context = {
        'profile': profile,
        'rooms': rooms,
        'room_types': FacilityType.get_all_choices(),
        'facility_types': facility_types,
        'clusters': clusters,
        'cluster_levels': CurriculumCluster.LEVEL_CHOICES,
        'ancillary_catalog': ancillary_catalog,
        'academic_years': academic_years,
        'terms': terms,
        'term_types': Term.TERM_TYPES,
        'departments': departments,
    }
    return render(request, 'settings.html', context)


@csrf_exempt
def update_workload_policy_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    profile = SchoolProfile.get_settings()
    try:
        profile.max_daily_teaching_hours = float(request.POST.get('max_daily_teaching_hours', 6))
        profile.max_weekly_teaching_hours = float(request.POST.get('max_weekly_teaching_hours', 30))
        profile.standard_workweek_hours = float(request.POST.get('standard_workweek_hours', 40))
        profile.save()

        AuditLog.objects.create(
            action="Workload Policy Updated",
            details=f"Updated load caps: Max Daily {profile.max_daily_teaching_hours}h, Max Weekly {profile.max_weekly_teaching_hours}h, Workweek {profile.standard_workweek_hours}h."
        )

        return JsonResponse({'success': True, 'message': 'Workload & teaching policy rules successfully updated!'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)


@csrf_exempt
def add_facility_type_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    name = request.POST.get('name', '').strip()
    code = request.POST.get('code', '').strip().lower().replace(' ', '_').replace('-', '_')
    description = request.POST.get('description', '').strip()

    if not name:
        return JsonResponse({'success': False, 'message': 'Facility type name is required.'})

    if not code:
        code = name.lower().replace(' ', '_').replace('-', '_')

    if FacilityType.objects.filter(code=code).exists():
        return JsonResponse({'success': False, 'message': f'Facility type with code "{code}" already exists.'})

    ft = FacilityType.objects.create(code=code, name=name, description=description, is_active=True)

    AuditLog.objects.create(
        action="Facility Type Established",
        details=f"Added learning facility category '{ft.name}' ({ft.code})."
    )

    return JsonResponse({
        'success': True,
        'message': f'Facility category "{ft.name}" created successfully!',
        'id': ft.id,
        'code': ft.code,
        'name': ft.name,
    })


@csrf_exempt
def delete_facility_type_api(request, ft_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    ft = get_object_or_404(FacilityType, id=ft_id)
    name = ft.name
    ft.delete()

    AuditLog.objects.create(
        action="Facility Type Removed",
        details=f"Removed facility category '{name}'."
    )

    return JsonResponse({'success': True, 'message': f'Facility category "{name}" removed successfully!'})


@csrf_exempt
def add_academic_year_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    name = request.POST.get('name', '').strip()
    set_active = request.POST.get('set_active') == 'true'

    if not name:
        return JsonResponse({'success': False, 'message': 'Academic year name is required (e.g. 2025-2026).'})

    if AcademicYear.objects.filter(name=name).exists():
        return JsonResponse({'success': False, 'message': f'Academic year "{name}" already exists.'})

    if set_active:
        AcademicYear.objects.update(is_active=False)

    ay = AcademicYear.objects.create(name=name, is_active=set_active)

    if set_active:
        profile = SchoolProfile.get_settings()
        profile.active_academic_year = ay
        profile.save()

    AuditLog.objects.create(
        action="Academic Year Added",
        details=f"Created school year '{ay.name}' (Active: {ay.is_active})."
    )

    return JsonResponse({
        'success': True,
        'message': f'School Year "{ay.name}" established successfully!',
        'id': ay.id,
        'name': ay.name,
        'is_active': ay.is_active
    })


@csrf_exempt
def toggle_academic_year_api(request, ay_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    ay = get_object_or_404(AcademicYear, id=ay_id)
    AcademicYear.objects.update(is_active=False)
    ay.is_active = True
    ay.save()

    profile = SchoolProfile.get_settings()
    profile.active_academic_year = ay
    profile.save()

    AuditLog.objects.create(
        action="Active School Year Changed",
        details=f"Set '{ay.name}' as the active academic year."
    )

    return JsonResponse({
        'success': True,
        'message': f'School Year "{ay.name}" set as active across CLASSMATE-AI!'
    })


@csrf_exempt
def add_term_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    name = request.POST.get('name', '').strip()
    term_type = request.POST.get('term_type', 'shs_term_1')
    ay_id = request.POST.get('academic_year_id')
    set_active = request.POST.get('set_active') == 'true'

    if not name:
        return JsonResponse({'success': False, 'message': 'Term name is required (e.g. 1st Trimester).'})

    ay = AcademicYear.objects.filter(id=ay_id).first() or AcademicYear.objects.filter(is_active=True).first()
    if not ay:
        return JsonResponse({'success': False, 'message': 'Active academic year is required.'})

    if set_active:
        Term.objects.filter(academic_year=ay).update(is_active=False)

    term = Term.objects.create(academic_year=ay, name=name, term_type=term_type, is_active=set_active)

    if set_active:
        profile = SchoolProfile.get_settings()
        profile.active_term = term
        profile.save()

    AuditLog.objects.create(
        action="Academic Term Created",
        details=f"Added term '{term.name}' for {ay.name}."
    )

    return JsonResponse({
        'success': True,
        'message': f'Term "{term.name}" created successfully!',
        'id': term.id,
        'name': term.name,
    })


@csrf_exempt
def toggle_term_api(request, term_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    term = get_object_or_404(Term, id=term_id)
    Term.objects.filter(academic_year=term.academic_year).update(is_active=False)
    term.is_active = True
    term.save()

    profile = SchoolProfile.get_settings()
    profile.active_term = term
    profile.save()

    AuditLog.objects.create(
        action="Active Term Changed",
        details=f"Set '{term.name}' as the active term for {term.academic_year.name}."
    )

    return JsonResponse({
        'success': True,
        'message': f'Term "{term.name}" is now the active term!'
    })


@csrf_exempt
def add_ancillary_catalog_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    name = request.POST.get('name', '').strip()
    code = request.POST.get('code', '').strip().lower().replace(' ', '_').replace('-', '_')
    try:
        hours = float(request.POST.get('default_weekly_hours', 2.0))
    except (ValueError, TypeError):
        hours = 2.0
    description = request.POST.get('description', '').strip()

    if not name:
        return JsonResponse({'success': False, 'message': 'Designation name is required.'})

    if not code:
        code = name.lower().replace(' ', '_').replace('-', '_')

    if AncillaryDesignationCatalog.objects.filter(code=code).exists():
        return JsonResponse({'success': False, 'message': f'Designation with code "{code}" already exists.'})

    cat = AncillaryDesignationCatalog.objects.create(
        code=code, name=name, default_weekly_hours=hours, description=description, is_active=True
    )

    AuditLog.objects.create(
        action="Ancillary Designation Cataloged",
        details=f"Added '{cat.name}' ({hours}h/wk) to school designation catalog."
    )

    return JsonResponse({
        'success': True,
        'message': f'Designation "{cat.name}" added to catalog!',
        'id': cat.id,
        'name': cat.name,
        'hours': cat.default_weekly_hours,
    })


@csrf_exempt
def update_ancillary_catalog_api(request, cat_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    cat = get_object_or_404(AncillaryDesignationCatalog, id=cat_id)
    name = request.POST.get('name', '').strip()
    code = request.POST.get('code', '').strip().lower().replace(' ', '_').replace('-', '_')
    try:
        hours = float(request.POST.get('default_weekly_hours', cat.default_weekly_hours))
    except (ValueError, TypeError):
        hours = cat.default_weekly_hours
    description = request.POST.get('description', '').strip()

    if not name:
        return JsonResponse({'success': False, 'message': 'Designation name is required.'})
    if not code:
        code = name.lower().replace(' ', '_').replace('-', '_')

    if AncillaryDesignationCatalog.objects.filter(code=code).exclude(id=cat.id).exists():
        return JsonResponse({'success': False, 'message': f'Designation with code "{code}" already exists.'})

    old_name = cat.name
    cat.name = name
    cat.code = code
    cat.default_weekly_hours = hours
    cat.description = description
    cat.save()

    AuditLog.objects.create(
        action="Ancillary Designation Updated",
        details=f"Updated '{old_name}' -> '{cat.name}' ({hours}h/wk) in school designation catalog."
    )

    return JsonResponse({
        'success': True,
        'message': f'Designation "{cat.name}" updated successfully!',
        'id': cat.id,
        'name': cat.name,
        'hours': cat.default_weekly_hours,
    })


@csrf_exempt
def delete_ancillary_catalog_api(request, cat_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    cat = get_object_or_404(AncillaryDesignationCatalog, id=cat_id)
    name = cat.name
    cat.delete()

    AuditLog.objects.create(
        action="Ancillary Designation Removed",
        details=f"Removed '{name}' from designation catalog."
    )

    return JsonResponse({'success': True, 'message': f'Designation "{name}" removed from catalog!'})


@csrf_exempt
def add_cluster_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    name = request.POST.get('name', '').strip()
    code = request.POST.get('code', '').strip().lower().replace(' ', '_').replace('-', '_')
    curriculum_level = request.POST.get('curriculum_level', 'shs').strip()
    description = request.POST.get('description', '').strip()

    if not name:
        return JsonResponse({'success': False, 'message': 'Cluster name is required.'})

    if not code:
        code = name.lower().replace(' ', '_').replace('-', '_')

    if CurriculumCluster.objects.filter(code=code).exists():
        return JsonResponse({'success': False, 'message': f'Cluster with code "{code}" already exists.'})

    cluster = CurriculumCluster.objects.create(
        code=code,
        name=name,
        curriculum_level=curriculum_level,
        description=description,
        is_active=True
    )

    AuditLog.objects.create(
        action="Curriculum Cluster Established",
        details=f"Created cluster '{cluster.name}' ({cluster.code}) for {cluster.get_curriculum_level_display()}."
    )

    return JsonResponse({
        'success': True,
        'message': f'Curriculum Cluster "{cluster.name}" established successfully!',
        'cluster_id': cluster.id,
        'cluster_code': cluster.code,
        'cluster_name': cluster.name,
    })


@csrf_exempt
def update_cluster_api(request, cluster_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    cluster = get_object_or_404(CurriculumCluster, id=cluster_id)
    name = request.POST.get('name', '').strip()
    code = request.POST.get('code', '').strip().lower().replace(' ', '_').replace('-', '_')
    curriculum_level = request.POST.get('curriculum_level', cluster.curriculum_level).strip()
    description = request.POST.get('description', '').strip()

    if not name:
        return JsonResponse({'success': False, 'message': 'Cluster name is required.'})
    if not code:
        code = name.lower().replace(' ', '_').replace('-', '_')

    if CurriculumCluster.objects.filter(code=code).exclude(id=cluster.id).exists():
        return JsonResponse({'success': False, 'message': f'Cluster with code "{code}" already exists.'})

    old_name = cluster.name
    cluster.name = name
    cluster.code = code
    cluster.curriculum_level = curriculum_level
    cluster.description = description
    cluster.save()

    AuditLog.objects.create(
        action="Curriculum Cluster Updated",
        details=f"Updated cluster '{old_name}' -> '{cluster.name}' ({cluster.code}) for {cluster.get_curriculum_level_display()}."
    )

    return JsonResponse({
        'success': True,
        'message': f'Curriculum Cluster "{cluster.name}" updated successfully!',
        'cluster_id': cluster.id,
        'cluster_code': cluster.code,
        'cluster_name': cluster.name,
    })


@csrf_exempt
def delete_cluster_api(request, cluster_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    cluster = get_object_or_404(CurriculumCluster, id=cluster_id)
    name = cluster.name
    cluster.delete()

    AuditLog.objects.create(
        action="Curriculum Cluster Deleted",
        details=f"Removed curriculum cluster '{name}' from configuration."
    )

    return JsonResponse({
        'success': True,
        'message': f'Curriculum Cluster "{name}" deleted successfully!'
    })


@csrf_exempt
def add_room_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    name = request.POST.get('name', '').strip()
    room_type = request.POST.get('room_type', 'lecture').strip()
    building = request.POST.get('building', '').strip()
    try:
        capacity = int(request.POST.get('capacity', 45))
    except (ValueError, TypeError):
        capacity = 45

    if not name:
        return JsonResponse({'success': False, 'message': 'Classroom / Room name is required.'})

    if Room.objects.filter(name__iexact=name).exists():
        return JsonResponse({'success': False, 'message': f'Classroom "{name}" already exists.'})

    room = Room.objects.create(
        name=name,
        room_type=room_type,
        building=building,
        capacity=capacity,
        is_active=True
    )

    AuditLog.objects.create(
        action="Classroom Established",
        details=f"Added room '{room.name}' ({room.get_room_type_display()}, Capacity: {capacity}) in {building}."
    )

    return JsonResponse({
        'success': True,
        'message': f'Classroom "{room.name}" created successfully!',
        'room_id': room.id,
        'room_name': room.name,
    })


@csrf_exempt
def update_room_api(request, room_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    room = get_object_or_404(Room, id=room_id)
    name = request.POST.get('name', '').strip()
    room_type = request.POST.get('room_type', 'lecture').strip()
    building = request.POST.get('building', '').strip()
    try:
        capacity = int(request.POST.get('capacity', 45))
    except (ValueError, TypeError):
        capacity = 45

    if not name:
        return JsonResponse({'success': False, 'message': 'Classroom / Room name is required.'})

    if Room.objects.filter(name__iexact=name).exclude(id=room.id).exists():
        return JsonResponse({'success': False, 'message': f'Another classroom named "{name}" already exists.'})

    old_name = room.name
    room.name = name
    room.room_type = room_type
    room.building = building
    room.capacity = capacity
    room.save()

    AuditLog.objects.create(
        action="Classroom Updated",
        details=f"Updated room '{old_name}' -> '{room.name}' ({room.get_room_type_display()}, Capacity: {capacity}) in {building}."
    )

    return JsonResponse({
        'success': True,
        'message': f'Classroom "{room.name}" updated successfully!',
        'room_id': room.id,
        'room_name': room.name,
    })


@csrf_exempt
def delete_room_api(request, room_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    room = get_object_or_404(Room, id=room_id)
    name = room.name
    room.delete()

    AuditLog.objects.create(
        action="Classroom Deleted",
        details=f"Removed classroom '{name}' from inventory."
    )

    return JsonResponse({
        'success': True,
        'message': f'Classroom "{name}" removed successfully!'
    })


@csrf_exempt
def update_settings_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    profile = SchoolProfile.get_settings()
    profile.school_name = request.POST.get('school_name', profile.school_name).strip()
    profile.school_id = request.POST.get('school_id', profile.school_id).strip()
    profile.region = request.POST.get('region', profile.region).strip()
    profile.division = request.POST.get('division', profile.division).strip()
    profile.district = request.POST.get('district', profile.district).strip()

    profile.prepared_by_name = request.POST.get('prepared_by_name', profile.prepared_by_name).strip()
    profile.prepared_by_title = request.POST.get('prepared_by_title', profile.prepared_by_title).strip()

    profile.reviewed_by_name = request.POST.get('reviewed_by_name', profile.reviewed_by_name).strip()
    profile.reviewed_by_title = request.POST.get('reviewed_by_title', profile.reviewed_by_title).strip()

    profile.verified_by_name = request.POST.get('verified_by_name', profile.verified_by_name).strip()
    profile.verified_by_title = request.POST.get('verified_by_title', profile.verified_by_title).strip()

    profile.recommending_name = request.POST.get('recommending_name', profile.recommending_name).strip()
    profile.recommending_title = request.POST.get('recommending_title', profile.recommending_title).strip()

    profile.approved_by_name = request.POST.get('approved_by_name', profile.approved_by_name).strip()
    profile.approved_by_title = request.POST.get('approved_by_title', profile.approved_by_title).strip()

    profile.save()

    AuditLog.objects.create(
        action="Institutional Profile & Signatories Updated",
        details=f"Updated settings for {profile.school_name}."
    )

    return JsonResponse({
        'success': True,
        'message': 'School profile and official signatories successfully updated!'
    })


@csrf_exempt
def reset_settings_api(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST required'}, status=405)

    profile = SchoolProfile.get_settings()
    profile.school_name = "ISABELA NATIONAL HIGH SCHOOL"
    profile.school_id = "300582"
    profile.region = "REGION II – CAGAYAN VALLEY"
    profile.division = "SCHOOLS DIVISION OF ISABELA"
    profile.district = "District II"

    profile.prepared_by_name = "VILMA L. VILLADOR, PhD"
    profile.prepared_by_title = "Principal II"

    profile.reviewed_by_name = "JOVITO M. CADIZ, PhD"
    profile.reviewed_by_title = "Principal IV, District-in-Charge"

    profile.verified_by_name = "MARIETESS B. BAQUIRAN, PhD"
    profile.verified_by_title = "Chief, Curriculum Instruction Division"

    profile.recommending_name = "MARY JULIE A. TRUS, PhD, CESO VI"
    profile.recommending_title = "Assistant Schools Division Superintendent"

    profile.approved_by_name = "RACHEL R. LLANA, PhD, CESO V"
    profile.approved_by_title = "Schools Division Superintendent"

    profile.save()

    return JsonResponse({
        'success': True,
        'message': 'Reset signatories and header to official DepEd Region II defaults.'
    })


def print_classroom_program_view(request, section_id):
    section = get_object_or_404(Section, id=section_id)
    schedule = Schedule.objects.order_by('-updated_at').first()
    profile = SchoolProfile.get_settings()

    # Get slots specifically for this section's grade level, fallback to universal
    slots = TimeSlot.objects.filter(grade_level=section.grade_level)
    if not slots.exists():
        slots = TimeSlot.objects.filter(grade_level=0)

    # Distinct canonical periods (using Monday day 1)
    canonical_periods = slots.filter(day_of_week=1).order_by('period_number')
    if not canonical_periods.exists():
        canonical_periods = TimeSlot.objects.filter(day_of_week=1).order_by('period_number')

    # Query schedule items for this section
    schedule_items = {}
    if schedule:
        for item in ScheduleItem.objects.filter(schedule=schedule, section=section).select_related('subject', 'teacher', 'time_slot'):
            schedule_items[(item.time_slot.day_of_week, item.time_slot.period_number)] = item

    rows = []
    for cp in canonical_periods:
        days_cells = []
        for day in range(1, 6):
            ts = slots.filter(day_of_week=day, period_number=cp.period_number).first() or cp
            if ts.is_break:
                days_cells.append({
                    'type': 'break',
                    'label': ts.label
                })
            else:
                item = schedule_items.get((day, cp.period_number))
                if item:
                    t_initial = f"{item.teacher.first_name[0]}. {item.teacher.last_name.upper()}" if item.teacher.first_name else item.teacher.last_name.upper()
                    days_cells.append({
                        'type': 'subject',
                        'subject_code': item.subject.code,
                        'subject_title': item.subject.title.upper(),
                        'teacher_name': t_initial
                    })
                else:
                    label = "REMEDIATION / STUDY" if cp.period_number >= 8 else "STUDY PERIOD"
                    days_cells.append({
                        'type': 'vacant',
                        'label': label
                    })

        is_uniform_break = cp.is_break
        break_label = cp.label if cp.is_break else ""

        rows.append({
            'period_number': cp.period_number,
            'time_range': f"{cp.start_time.strftime('%I:%M').lstrip('0')}-{cp.end_time.strftime('%I:%M').lstrip('0')}",
            'is_break': is_uniform_break,
            'break_label': break_label,
            'days': days_cells,
        })

    adviser_name = section.adviser.full_name.upper() if section.adviser else "UNASSIGNED"

    context = {
        'section': section,
        'schedule': schedule,
        'profile': profile,
        'adviser_name': adviser_name,
        'rows': rows,
    }
    return render(request, 'print_classroom_program.html', context)


def print_teacher_program_view(request, teacher_id):
    teacher = get_object_or_404(Teacher, id=teacher_id)
    schedule = Schedule.objects.order_by('-updated_at').first()
    profile = SchoolProfile.get_settings()

    advised_sec = teacher.advised_sections.first()
    adviser_tag = advised_sec.name.upper() if advised_sec else "N/A"

    duties = list(teacher.ancillary_duties.all())
    ancillary_title = duties[0].title.upper() if duties else ""

    teacher_items = ScheduleItem.objects.filter(schedule=schedule, teacher=teacher).select_related('subject', 'section', 'time_slot') if schedule else []
    
    teaches_shs = any(it.section.grade_level in [11, 12] for it in teacher_items) or teacher.curriculum_level in ['shs', 'both']
    preferred_grade = 11 if teaches_shs else 7

    slots = TimeSlot.objects.filter(grade_level=preferred_grade)
    if not slots.exists():
        slots = TimeSlot.objects.filter(grade_level=0)
    
    canonical_periods = slots.filter(day_of_week=1).order_by('period_number')
    if not canonical_periods.exists():
        canonical_periods = TimeSlot.objects.filter(day_of_week=1).order_by('period_number')

    item_map = {}
    for it in teacher_items:
        item_map[(it.time_slot.day_of_week, it.time_slot.period_number)] = it

    rows = []
    for cp in canonical_periods:
        duration = cp.duration_minutes
        days_cells = []
        for day in range(1, 6):
            ts = slots.filter(day_of_week=day, period_number=cp.period_number).first() or cp
            if ts.is_break:
                days_cells.append({
                    'type': 'break',
                    'label': ts.label
                })
            else:
                it = item_map.get((day, cp.period_number))
                if it:
                    days_cells.append({
                        'type': 'class',
                        'subject_title': it.subject.title.upper(),
                        'section_name': it.section.name,
                    })
                elif advised_sec and cp.period_number == 9 and (day in [1, 5]):
                    days_cells.append({
                        'type': 'homeroom',
                        'subject_title': 'HOMEROOM GUIDANCE',
                        'section_name': advised_sec.name,
                    })
                else:
                    days_cells.append({
                        'type': 'prep',
                        'subject_title': 'Preparation of Instructional Materials / Lesson Planning / Recording of Formative Assessment',
                        'section_name': '',
                    })

        rows.append({
            'period_number': cp.period_number,
            'time_range': f"{cp.start_time.strftime('%I:%M').lstrip('0')}-{cp.end_time.strftime('%I:%M').lstrip('0')}",
            'duration_minutes': duration,
            'is_break': cp.is_break,
            'break_label': cp.label if cp.is_break else "",
            'days': days_cells,
        })

    major = "MATHEMATICS"
    quals = teacher.qualifications.select_related('subject')
    if quals.exists():
        major = quals.first().subject.cluster.replace('_', ' ').upper()

    context = {
        'teacher': teacher,
        'major': major,
        'adviser_tag': adviser_tag,
        'ancillary_title': ancillary_title,
        'schedule': schedule,
        'profile': profile,
        'rows': rows,
    }
    return render(request, 'print_teacher_program.html', context)
