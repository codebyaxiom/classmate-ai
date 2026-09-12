from django.test import TestCase, Client
from django.urls import reverse
from scheduler.models import (
    AcademicYear, Term, Department, Room, Subject, Teacher, 
    TeacherQualification, Section, TimeSlot, SchoolProfile, SectionSubjectRequirement, Schedule, ScheduleItem,
    CurriculumCluster
)
from scheduler.engine.genetic_scheduler import GeneticTimetableScheduler
from scheduler.views import get_system_readiness_status

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

    def test_copy_and_clear_grade_timeframes_api(self):
        # 1. Apply preset to Grade 11
        res_preset = self.client.post(reverse('api_apply_preset_timeframes'), {
            'preset_type': 'shs_sample',
            'grade_level': 11,
        })
        self.assertTrue(res_preset.json()['success'])
        self.assertEqual(TimeSlot.objects.filter(grade_level=11).count(), 50)

        # 2. Copy schedule from Grade 11 to Grade 12
        res_copy = self.client.post(reverse('api_copy_grade_timeframes'), {
            'source_grade': 11,
            'target_grade': 12,
        })
        self.assertTrue(res_copy.json()['success'])
        self.assertEqual(TimeSlot.objects.filter(grade_level=12).count(), 50)

        # 3. Clear schedule for Grade 12
        res_clear = self.client.post(reverse('api_clear_grade_timeframes'), {
            'grade_level': 12,
        })
        self.assertTrue(res_clear.json()['success'])
        self.assertEqual(TimeSlot.objects.filter(grade_level=12).count(), 0)
        # Grade 11 remains intact
        self.assertEqual(TimeSlot.objects.filter(grade_level=11).count(), 50)

    def test_shs_immersion_90min_preset(self):
        res = self.client.post(reverse('api_apply_preset_timeframes'), {
            'preset_type': 'shs_immersion',
            'grade_level': 12,
        })
        self.assertTrue(res.json()['success'])
        slots = TimeSlot.objects.filter(grade_level=12)
        # 8 periods x 5 days = 40 slots
        self.assertEqual(slots.count(), 40)
        p1 = TimeSlot.objects.filter(grade_level=12, period_number=1, day_of_week=1).first()
        self.assertEqual(p1.duration_minutes, 30) # Flag ceremony
        p2 = TimeSlot.objects.filter(grade_level=12, period_number=2, day_of_week=1).first()
        self.assertEqual(p2.duration_minutes, 90) # 90m block

    def test_facility_type_and_classroom_apis(self):
        # Add facility type
        res_ft = self.client.post(reverse('api_add_facility_type'), {
            'name': 'Speech & Audio Lab',
            'code': 'speech_audio_lab',
            'description': 'Audio consoles for language proficiency'
        })
        data_ft = res_ft.json()
        self.assertTrue(data_ft['success'])
        ft_id = data_ft['id']

        # Add room using this facility type
        res_rm = self.client.post(reverse('api_add_room'), {
            'name': 'Lab 301',
            'room_type': 'speech_audio_lab',
            'capacity': 40,
            'building': 'East Wing'
        })
        data_rm = res_rm.json()
        self.assertTrue(data_rm['success'])
        room = Room.objects.get(id=data_rm['room_id'])
        self.assertEqual(room.room_type_display_name, 'Speech & Audio Lab')

        # Delete facility type
        res_ft_del = self.client.post(reverse('api_delete_facility_type', args=[ft_id]))
        self.assertTrue(res_ft_del.json()['success'])

    def test_academic_year_and_term_management_apis(self):
        # Add S.Y.
        res_ay = self.client.post(reverse('api_add_academic_year'), {
            'name': '2028-2029',
            'set_active': 'true'
        })
        data_ay = res_ay.json()
        self.assertTrue(data_ay['success'])
        new_ay_id = data_ay['id']
        self.assertTrue(AcademicYear.objects.get(id=new_ay_id).is_active)

        # Add Term
        res_term = self.client.post(reverse('api_add_term'), {
            'academic_year_id': new_ay_id,
            'name': '1st Trimester 2028',
            'term_type': 'tri1',
            'set_active': 'true'
        })
        data_term = res_term.json()
        self.assertTrue(data_term['success'])
        term_id = data_term['id']
        self.assertTrue(Term.objects.get(id=term_id).is_active)

        # Toggle back to original S.Y.
        res_toggle = self.client.post(reverse('api_toggle_academic_year', args=[self.ay.id]))
        self.assertTrue(res_toggle.json()['success'])
        self.assertTrue(AcademicYear.objects.get(id=self.ay.id).is_active)
        self.assertFalse(AcademicYear.objects.get(id=new_ay_id).is_active)

    def test_ancillary_catalog_and_workload_policy_apis(self):
        # Add catalog item
        res_cat = self.client.post(reverse('api_add_ancillary_catalog'), {
            'name': 'Disaster Risk Reduction Coordinator',
            'code': 'drrm_coord',
            'default_weekly_hours': 3.5,
            'description': 'Campus safety and emergency readiness.'
        })
        data_cat = res_cat.json()
        self.assertTrue(data_cat['success'])
        cat_id = data_cat['id']

        # Update workload policy caps
        res_pol = self.client.post(reverse('api_update_workload_policy'), {
            'max_daily_teaching_hours': 5,
            'max_weekly_teaching_hours': 28,
            'standard_workweek_hours': 40
        })
        self.assertTrue(res_pol.json()['success'])
        prof = SchoolProfile.get_settings()
        self.assertEqual(prof.max_daily_teaching_hours, 5)
        self.assertEqual(prof.max_weekly_teaching_hours, 28)

        # Delete catalog item
        res_cat_del = self.client.post(reverse('api_delete_ancillary_catalog', args=[cat_id]))
        self.assertTrue(res_cat_del.json()['success'])

    def test_timetable_grade_adaptive_switching(self):
        # Create G11 section
        sec11 = Section.objects.create(name='Grade 11 - STEM Einstein', grade_level=11, academic_year=self.ay)
        # Apply SHS schedule to Grade 11
        self.client.post(reverse('api_apply_preset_timeframes'), {'preset_type': 'shs_sample', 'grade_level': 11})

        # View Section 11 timetable
        res11 = self.client.get(reverse('timetable') + f'?filter_type=section&filter_id={sec11.id}')
        self.assertEqual(res11.status_code, 200)
        self.assertEqual(res11.context['active_grade'], 11)
        self.assertContains(res11, 'Grade 11 (SHS)')

        # View Section 7 timetable (from setUp)
        res7 = self.client.get(reverse('timetable') + f'?filter_type=section&filter_id={self.section.id}')
        self.assertEqual(res7.status_code, 200)
        self.assertEqual(res7.context['active_grade'], 7)
        self.assertContains(res7, 'Grade 7 (JHS)')

    def test_readiness_calculation_and_stepper(self):
        # With setUp data (1 room, 1 ay, 1 term, 3 slots, 1 subject, 1 teacher+qual, 1 section+req, 0 schedule items)
        status = get_system_readiness_status()
        self.assertEqual(status['completed_count'], 5)
        self.assertEqual(status['total_count'], 6)
        self.assertEqual(status['readiness_percentage'], 83)
        self.assertFalse(status['is_fully_ready'])
        self.assertEqual(status['next_step']['step_num'], 6)
        self.assertEqual(status['next_step']['code'], 'timetable')

        # Create schedule item to complete step 6
        ScheduleItem.objects.create(
            schedule=self.schedule, section=self.section, subject=self.subject,
            teacher=self.teacher, room=self.room, time_slot=self.ts1
        )
        status_complete = get_system_readiness_status()
        self.assertEqual(status_complete['completed_count'], 6)
        self.assertEqual(status_complete['readiness_percentage'], 100)
        self.assertTrue(status_complete['is_fully_ready'])

    def test_readiness_empty_state(self):
        # Clear out rooms and check step 1 is pending
        Room.objects.all().delete()
        status = get_system_readiness_status()
        step1 = status['steps'][0]
        self.assertFalse(step1['is_completed'])
        self.assertEqual(status['next_step']['step_num'], 1)

    def test_dashboard_renders_readiness_stepper_and_categorized_nav(self):
        res = self.client.get(reverse('dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('readiness', res.context)
        # Check stepper elements
        self.assertContains(res, "DepEd School Setup & Timetable Readiness Guide")
        self.assertContains(res, "Guided Setup Sequence")
        self.assertContains(res, "School &amp; Facilities")
        self.assertContains(res, "Bell Schedules")
        self.assertContains(res, "Curriculum &amp; Subjects")
        self.assertContains(res, "Faculty &amp; Qualifications")
        self.assertContains(res, "Sections &amp; Allocations")
        self.assertContains(res, "AI Timetable Evolution")

        # Check categorized navbar links & dropdowns
        self.assertContains(res, "Academic Setup")
        self.assertContains(res, "Faculty & Classes")
        self.assertContains(res, "Timetable & Reports")
        self.assertContains(res, "Run AI Optimizer")
        self.assertContains(res, reverse('timeframes'))
        self.assertContains(res, reverse('subjects'))
        self.assertContains(res, reverse('teachers'))
        self.assertContains(res, reverse('sections'))
        self.assertContains(res, reverse('teacher_loads'))
        self.assertContains(res, reverse('timetable'))
        self.assertContains(res, reverse('room_utilization'))
        self.assertContains(res, reverse('import_export'))
        self.assertContains(res, reverse('settings'))

    def test_in_context_prerequisite_banners(self):
        # Delete subjects and check teachers page shows recommendation banner
        Subject.objects.all().delete()
        res_t = self.client.get(reverse('teachers'))
        self.assertEqual(res_t.status_code, 200)
        self.assertContains(res_t, "Setup Sequence Recommendation: Create Curriculum Subjects First")

        # Check sections page shows recommendation banner
        res_s = self.client.get(reverse('sections'))
        self.assertEqual(res_s.status_code, 200)
        self.assertContains(res_s, "Setup Sequence Recommendation: Complete Prerequisites First")


