import csv
import io
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
    Section, TimeSlot, SectionSubjectRequirement, Schedule, ScheduleItem, AuditLog
)
from .engine.genetic_scheduler import GeneticTimetableScheduler

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

    # Build structured timetable_rows for seamless template rendering
    timeslots = TimeSlot.objects.filter(day_of_week=1).order_by('period_number')
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
    if teacher_id:
        teacher = get_object_or_404(Teacher, id=teacher_id)
        if schedule:
            items = ScheduleItem.objects.filter(schedule=schedule, teacher=teacher).select_related('subject', 'section', 'room', 'time_slot').order_by('time_slot__day_of_week', 'time_slot__period_number')
    
    # Calculate weekly hours
    total_hours = len(items)
    prep_hours = max(0, 40 - total_hours) if total_hours > 0 else 0

    context = {
        'schedule': schedule,
        'teacher': teacher,
        'items': items,
        'total_hours': total_hours,
        'prep_hours': prep_hours,
    }
    return render(request, 'print_sf7.html', context)

def teachers_view(request):
    level_filter = request.GET.get('level')
    dept_filter = request.GET.get('dept')
    search_query = request.GET.get('q', '').strip()

    teachers = Teacher.objects.prefetch_related('qualifications__subject').all().order_by('last_name')
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

    departments = Department.objects.all().order_by('name')
    subjects = Subject.objects.all().order_by('grade_level', 'code')

    context = {
        'teachers': teachers,
        'departments': departments,
        'subjects': subjects,
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
    max_daily = int(request.POST.get('max_daily_hours', 6))
    max_weekly = int(request.POST.get('max_weekly_hours', 30))
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
