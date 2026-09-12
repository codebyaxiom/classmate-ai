from django.test import TestCase, Client
from django.urls import reverse
from scheduler.models import (
    AcademicYear, Term, Department, Room, Subject, Teacher, 
    TeacherQualification, Section, TimeSlot, SchoolProfile, SectionSubjectRequirement, Schedule, ScheduleItem,
    CurriculumCluster
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

    def test_school_profile_default_and_update_api(self):
        # Check settings view loads
        res = self.client.get(reverse('settings'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "School Profile, Signatories & Classrooms")

        # Update settings
        res = self.client.post(reverse('api_update_settings'), {
            'school_name': 'CAGAYAN VALLEY HIGH SCHOOL',
            'school_id': '300999',
            'region': 'REGION II',
            'division': 'DIVISION OF ILAGAN',
            'district': 'District 1',
            'prepared_by_name': 'DR. JUAN DELA CRUZ',
            'prepared_by_title': 'Principal I',
            'reviewed_by_name': 'DR. MARIA SANTOS',
            'reviewed_by_title': 'PSDS',
            'verified_by_name': 'DR. PEDRO REYES',
            'verified_by_title': 'CID Chief',
            'recommending_name': 'DR. ANA LIM',
            'recommending_title': 'ASDS',
            'approved_by_name': 'DR. CARLOS TAN',
            'approved_by_title': 'SDS',
        })
        data = res.json()
        self.assertTrue(data['success'])

        profile = SchoolProfile.get_settings()
        self.assertEqual(profile.school_name, 'CAGAYAN VALLEY HIGH SCHOOL')
        self.assertEqual(profile.prepared_by_name, 'DR. JUAN DELA CRUZ')

        # Reset to defaults
        res_reset = self.client.post(reverse('api_reset_settings'))
        self.assertTrue(res_reset.json()['success'])
        profile.refresh_from_db()
        self.assertEqual(profile.school_name, 'ISABELA NATIONAL HIGH SCHOOL')

    def test_add_and_delete_room_api(self):
        res = self.client.post(reverse('api_add_room'), {
            'name': 'Science Lab Delta',
            'room_type': 'science_lab',
            'building': 'Science Wing',
            'capacity': 50,
        })
        data = res.json()
        self.assertTrue(data['success'])
        room_id = data['room_id']
        self.assertTrue(Room.objects.filter(id=room_id).exists())

        # Delete room
        res_del = self.client.post(reverse('api_delete_room', args=[room_id]))
        self.assertTrue(res_del.json()['success'])
        self.assertFalse(Room.objects.filter(id=room_id).exists())

    def test_timeframes_view_and_add_delete_api(self):
        res = self.client.get(reverse('timeframes') + '?grade=11')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Bell Schedules & Timeframes")

        # Add custom period for Grade 11
        res_add = self.client.post(reverse('api_add_timeframe'), {
            'grade_level': 11,
            'period_number': 8,
            'label': 'Afternoon Practicum Block',
            'start_time': '13:00',
            'end_time': '14:30',
            'is_break': False,
        })
        self.assertTrue(res_add.json()['success'])
        slots = TimeSlot.objects.filter(grade_level=11, period_number=8)
        self.assertEqual(slots.count(), 5) # Mon-Fri
        self.assertEqual(slots.first().duration_minutes, 90)

        # Delete period
        res_del = self.client.post(reverse('api_delete_timeframe', args=[8]), {
            'grade_level': 11,
        })
        self.assertTrue(res_del.json()['success'])
        self.assertEqual(TimeSlot.objects.filter(grade_level=11, period_number=8).count(), 0)

    def test_apply_preset_timeframes_api(self):
        res = self.client.post(reverse('api_apply_preset_timeframes'), {
            'preset_type': 'shs_sample',
            'grade_level': 11,
        })
        data = res.json()
        self.assertTrue(data['success'])
        slots = TimeSlot.objects.filter(grade_level=11)
        self.assertEqual(slots.count(), 50) # 10 periods x 5 days

    def test_print_classroom_program_view(self):
        res = self.client.get(reverse('print_classroom_program', args=[self.section.id]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "CLASSROOM PROGRAM")
        self.assertContains(res, self.section.name)
        self.assertContains(res, "Prepared by:")
        self.assertContains(res, "APPROVED:")

    def test_print_teacher_program_view(self):
        res = self.client.get(reverse('print_teacher_program', args=[self.teacher.id]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "TEACHER'S PROGRAM")
        self.assertContains(res, self.teacher.full_name)
        self.assertContains(res, "NO. OF MINS")
        self.assertContains(res, "APPROVED:")

    def test_add_and_delete_curriculum_cluster_api(self):
        # Add a custom cluster
        res = self.client.post(reverse('api_add_cluster'), {
            'name': 'Robotics and Automation Track',
            'code': 'robotics_auto',
            'curriculum_level': 'shs',
            'description': 'Advanced robotics and hardware engineering.'
        })
        data = res.json()
        self.assertTrue(data['success'])
        cluster_id = data['cluster_id']
        self.assertTrue(CurriculumCluster.objects.filter(id=cluster_id).exists())
        cluster = CurriculumCluster.objects.get(id=cluster_id)
        self.assertEqual(cluster.code, 'robotics_auto')
        self.assertEqual(cluster.name, 'Robotics and Automation Track')

        # Verify cluster appears in sections and subjects views
        res_sec = self.client.get(reverse('sections'))
        self.assertEqual(res_sec.status_code, 200)
        self.assertContains(res_sec, 'Robotics and Automation Track')

        res_subj = self.client.get(reverse('subjects'))
        self.assertEqual(res_subj.status_code, 200)
        self.assertContains(res_subj, 'Robotics and Automation Track')

        # Test cluster_display_name on Section and Subject
        sec_custom = Section.objects.create(
            name='Grade 11 - Robotics Alpha',
            grade_level=11,
            cluster='robotics_auto',
            academic_year=self.ay
        )
        self.assertEqual(sec_custom.cluster_display_name, 'Robotics and Automation Track')

        subj_custom = Subject.objects.create(
            code='ROBOT-11',
            title='Intro to Mechatronics',
            grade_level=11,
            cluster='robotics_auto',
            weekly_periods=4
        )
        self.assertEqual(subj_custom.cluster_display_name, 'Robotics and Automation Track')

        # Delete cluster
        res_del = self.client.post(reverse('api_delete_cluster', args=[cluster_id]))
        self.assertTrue(res_del.json()['success'])
        self.assertFalse(CurriculumCluster.objects.filter(id=cluster_id).exists())
