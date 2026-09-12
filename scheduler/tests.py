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
        self.assertContains(res, "Faculty & Teacher Management")

    def test_add_teacher_api(self):
        res = self.client.post(reverse('api_add_teacher'), {
            'first_name': 'Gabriela',
            'last_name': 'Silang',
            'employee_id': 'T-TEST-999',
            'department_id': self.dept.id,
            'max_daily_hours': 6,
            'subject_ids': [self.subject.id],
        })
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(Teacher.objects.filter(employee_id='T-TEST-999').exists())
        t = Teacher.objects.get(employee_id='T-TEST-999')
        self.assertTrue(t.qualifications.filter(subject=self.subject).exists())
