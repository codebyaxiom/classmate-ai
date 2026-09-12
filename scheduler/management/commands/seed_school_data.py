from django.core.management.base import BaseCommand
from datetime import time
from scheduler.models import (
    AcademicYear, Term, Department, Room, Subject, Teacher, 
    TeacherQualification, Section, TimeSlot, SectionSubjectRequirement, Schedule
)

class Command(BaseCommand):
    help = "Seed realistic Philippine High School data (JHS MATATAG + Strengthened SHS 3-Term)"

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding school data...")

        # 1. Academic Year & Terms
        ay, _ = AcademicYear.objects.get_or_create(name="2026-2027", defaults={'is_active': True})

        term_jhs, _ = Term.objects.get_or_create(
            academic_year=ay, name="S.Y. 2026-2027 (JHS Full Year)",
            defaults={'term_type': 'jhs_full_year', 'is_active': True}
        )
        term_shs1, _ = Term.objects.get_or_create(
            academic_year=ay, name="Term 1 (SSHS Trimester)",
            defaults={'term_type': 'shs_term_1', 'is_active': True}
        )
        term_shs2, _ = Term.objects.get_or_create(
            academic_year=ay, name="Term 2 (SSHS Trimester)",
            defaults={'term_type': 'shs_term_2', 'is_active': False}
        )
        term_shs3, _ = Term.objects.get_or_create(
            academic_year=ay, name="Term 3 (SSHS Trimester)",
            defaults={'term_type': 'shs_term_3', 'is_active': False}
        )

        # 2. Departments
        depts_data = [
            ("SCI", "Science Department"),
            ("MATH", "Mathematics Department"),
            ("ENG", "English Department"),
            ("FIL", "Filipino Department"),
            ("AP", "Araling Panlipunan Department"),
            ("MAPEH", "MAPEH Department"),
            ("TVL", "Technical-Vocational & Livelihood (TVL/TLE)"),
            ("ESP", "Edukasyon sa Pagpapakatao (EsP)"),
        ]
        dept_map = {}
        for code, name in depts_data:
            d, _ = Department.objects.get_or_create(code=code, defaults={'name': name})
            dept_map[code] = d

        # 3. Rooms
        rooms_data = [
            ("Room 101", "lecture", 45, "Main Building G/F"),
            ("Room 102", "lecture", 45, "Main Building G/F"),
            ("Room 201", "lecture", 45, "Main Building 2/F"),
            ("Room 202", "lecture", 45, "Main Building 2/F"),
            ("Room 301", "lecture", 45, "Senior High Building 1/F"),
            ("Room 302", "lecture", 45, "Senior High Building 1/F"),
            ("Room 303", "lecture", 45, "Senior High Building 2/F"),
            ("Room 304", "lecture", 45, "Senior High Building 2/F"),
            ("Science Laboratory 1", "science_lab", 40, "Science Wing"),
            ("Science Laboratory 2", "science_lab", 40, "Science Wing"),
            ("Computer Laboratory A", "computer_lab", 50, "ICT Building"),
            ("TVL Workshop Center", "tvl_workshop", 35, "TVL Complex"),
            ("Gymnasium / Multi-Purpose Court", "gym", 120, "Sports Complex"),
        ]
        room_map = {}
        for name, rtype, cap, bld in rooms_data:
            r, _ = Room.objects.get_or_create(name=name, defaults={'room_type': rtype, 'capacity': cap, 'building': bld})
            room_map[name] = r

        # 4. TimeSlots (Monday-Friday)
        slots_def = [
            (1, time(7, 45), time(8, 45), "Period 1 (7:45 - 8:45 AM)", False),
            (2, time(8, 45), time(9, 45), "Period 2 (8:45 - 9:45 AM)", False),
            (3, time(9, 45), time(10, 0), "Morning Recess (9:45 - 10:00 AM)", True),
            (4, time(10, 0), time(11, 0), "Period 3 (10:00 - 11:00 AM)", False),
            (5, time(11, 0), time(12, 0), "Period 4 (11:00 - 12:00 PM)", False),
            (6, time(12, 0), time(13, 0), "Lunch Break (12:00 - 1:00 PM)", True),
            (7, time(13, 0), time(14, 0), "Period 5 (1:00 - 2:00 PM)", False),
            (8, time(14, 0), time(15, 0), "Period 6 (2:00 - 3:00 PM)", False),
            (9, time(15, 0), time(16, 0), "Period 7 (3:00 - 4:00 PM)", False),
        ]
        for day in range(1, 6):
            for period, st, et, label, is_brk in slots_def:
                TimeSlot.objects.get_or_create(
                    day_of_week=day, period_number=period,
                    defaults={'start_time': st, 'end_time': et, 'label': label, 'is_break': is_brk}
                )

        # 5. Subjects
        subjs_data = [
            # JHS Subjects
            ("ENG-G7", "English 7: Philippine Literature", 7, "jhs_core", dept_map["ENG"], "lecture", 4, 1, False),
            ("MATH-G7", "Mathematics 7: Foundational Algebra", 7, "jhs_core", dept_map["MATH"], "lecture", 4, 1, False),
            ("SCI-G7", "Science 7: General Integrated Science", 7, "jhs_core", dept_map["SCI"], "science_lab", 4, 2, True),
            ("FIL-G7", "Filipino 7: Ibong Adarna", 7, "jhs_core", dept_map["FIL"], "lecture", 4, 1, False),
            ("AP-G7", "Araling Panlipunan 7: Araling Asyano", 7, "jhs_core", dept_map["AP"], "lecture", 3, 1, False),
            ("MAPEH-G7", "MAPEH 7: Music, Arts, PE & Health", 7, "jhs_core", dept_map["MAPEH"], "gym", 4, 1, False),
            ("TLE-G7", "Technology & Livelihood Education 7", 7, "jhs_core", dept_map["TVL"], "tvl_workshop", 4, 2, True),
            ("ESP-G7", "Edukasyon sa Pagpapakatao 7", 7, "jhs_core", dept_map["ESP"], "lecture", 2, 1, False),

            ("ENG-G10", "English 10: World Literature", 10, "jhs_core", dept_map["ENG"], "lecture", 4, 1, False),
            ("MATH-G10", "Mathematics 10: Advanced Geometry & Stats", 10, "jhs_core", dept_map["MATH"], "lecture", 4, 1, False),
            ("SCI-G10", "Science 10: Chemistry & Physics Focus", 10, "jhs_core", dept_map["SCI"], "science_lab", 4, 2, True),
            ("FIL-G10", "Filipino 10: El Filibusterismo", 10, "jhs_core", dept_map["FIL"], "lecture", 4, 1, False),
            ("AP-G10", "Araling Panlipunan 10: Kontemporaryong Isyu", 10, "jhs_core", dept_map["AP"], "lecture", 3, 1, False),
            ("MAPEH-G10", "MAPEH 10: Active Recreation & Health", 10, "jhs_core", dept_map["MAPEH"], "gym", 4, 1, False),

            # Strengthened SHS Subjects (SSHS)
            ("SSHS-COMM11", "Effective Communication 1", 11, "shs_core", dept_map["ENG"], "lecture", 4, 1, False),
            ("SSHS-GMATH11", "General Mathematics 1", 11, "shs_core", dept_map["MATH"], "lecture", 4, 1, False),
            ("SSHS-GSCI11", "General Science 1", 11, "shs_core", dept_map["SCI"], "science_lab", 4, 2, True),
            ("SSHS-LCS11", "Life and Career Skills 1", 11, "shs_core", dept_map["ESP"], "lecture", 3, 1, False),
            ("SSHS-STEM-PRECALC", "Pre-Calculus (STEM Cluster)", 11, "shs_stem", dept_map["MATH"], "lecture", 4, 1, False),
            ("SSHS-STEM-DATA", "Fundamentals of Data Analytics", 11, "shs_stem", dept_map["TVL"], "computer_lab", 4, 2, True),
            ("SSHS-ARTS-LIT", "Contemporary Philippine Literature", 11, "shs_arts_ssh", dept_map["FIL"], "lecture", 4, 1, False),
            ("SSHS-ARTS-PHIL", "Introduction to Philosophy", 11, "shs_arts_ssh", dept_map["AP"], "lecture", 3, 1, False),
            ("SSHS-TVL-DBMS", "Database Management Systems (Tech-Pro)", 12, "shs_tech_pro", dept_map["TVL"], "computer_lab", 4, 2, True),
            ("SSHS-TVL-PROG", "Computer Programming & Robotics", 12, "shs_tech_pro", dept_map["TVL"], "computer_lab", 4, 2, True),
            ("SSHS-STEM-BCALC", "Basic Calculus (STEM Cluster)", 12, "shs_stem", dept_map["MATH"], "lecture", 4, 1, False),
            ("SSHS-STEM-PHYS", "Physics in Daily Life & Engineering", 12, "shs_stem", dept_map["SCI"], "science_lab", 4, 2, True),
        ]
        subj_map = {}
        for code, title, gr, clus, dept, rtype, wp, cp, is_lab in subjs_data:
            s, _ = Subject.objects.get_or_create(
                code=code,
                defaults={
                    'title': title, 'grade_level': gr, 'cluster': clus,
                    'department': dept, 'room_type_needed': rtype,
                    'weekly_periods': wp, 'consecutive_periods': cp, 'is_lab': is_lab
                }
            )
            subj_map[code] = s

        # 6. Teachers (DepEd Faculty)
        teachers_data = [
            ("T-2024-001", "Maria", "Santos", dept_map["MATH"], 6, 28, 4),
            ("T-2024-002", "Juan", "Dela Cruz", dept_map["MATH"], 6, 26, 5),
            ("T-2024-003", "Elena", "Reyes", dept_map["SCI"], 6, 28, 1),
            ("T-2024-004", "Ricardo", "Garcia", dept_map["SCI"], 6, 26, 2),
            ("T-2024-005", "Grace", "Tan", dept_map["ENG"], 6, 28, 7),
            ("T-2024-006", "Mark", "Villanueva", dept_map["ENG"], 6, 26, 8),
            ("T-2024-007", "Carmela", "Aquino", dept_map["FIL"], 6, 28, 4),
            ("T-2024-008", "Danilo", "Ramos", dept_map["FIL"], 6, 24, 2),
            ("T-2024-009", "Antonio", "Mendoza", dept_map["AP"], 6, 26, 5),
            ("T-2024-010", "Lourdes", "Fernandez", dept_map["AP"], 6, 24, 1),
            ("T-2024-011", "Jayson", "Bautista", dept_map["MAPEH"], 6, 28, 7),
            ("T-2024-012", "Rosanna", "Cruz", dept_map["MAPEH"], 6, 26, 8),
            ("T-2024-013", "Dennis", "Soriano", dept_map["TVL"], 6, 28, 4),
            ("T-2024-014", "Katherine", "Pascual", dept_map["TVL"], 6, 28, 2),
            ("T-2024-015", "Jose", "Mercado", dept_map["ESP"], 6, 22, 5),
            ("T-2024-016", "Theresa", "Navarro", dept_map["MATH"], 6, 26, 1),
            ("T-2024-017", "Ferdinand", "Castillo", dept_map["SCI"], 6, 28, 7),
            ("T-2024-018", "Aileen", "Salazar", dept_map["TVL"], 6, 26, 8),
        ]
        t_map = {}
        for emp_id, fn, ln, dept, max_d, max_w, pref_v in teachers_data:
            t, _ = Teacher.objects.get_or_create(
                employee_id=emp_id,
                defaults={
                    'first_name': fn, 'last_name': ln, 'department': dept,
                    'email': f"{fn.lower()}.{ln.lower()}@deped.gov.ph",
                    'max_daily_hours': max_d, 'max_weekly_hours': max_w,
                    'preferred_vacant_period': pref_v
                }
            )
            t_map[emp_id] = t

        # 7. Teacher Qualifications (Configurable subject matching)
        qual_mappings = [
            ("T-2024-001", ["MATH-G7", "MATH-G10", "SSHS-GMATH11"]),
            ("T-2024-002", ["MATH-G10", "SSHS-STEM-PRECALC", "SSHS-STEM-BCALC"]),
            ("T-2024-016", ["MATH-G7", "SSHS-GMATH11"]),
            ("T-2024-003", ["SCI-G7", "SCI-G10", "SSHS-GSCI11"]),
            ("T-2024-004", ["SCI-G10", "SSHS-STEM-PHYS"]),
            ("T-2024-017", ["SCI-G7", "SSHS-GSCI11"]),
            ("T-2024-005", ["ENG-G7", "SSHS-COMM11"]),
            ("T-2024-006", ["ENG-G10", "SSHS-COMM11"]),
            ("T-2024-007", ["FIL-G7", "SSHS-ARTS-LIT"]),
            ("T-2024-008", ["FIL-G10", "SSHS-ARTS-LIT"]),
            ("T-2024-009", ["AP-G7", "SSHS-ARTS-PHIL"]),
            ("T-2024-010", ["AP-G10", "SSHS-ARTS-PHIL"]),
            ("T-2024-011", ["MAPEH-G7", "MAPEH-G10"]),
            ("T-2024-012", ["MAPEH-G7", "MAPEH-G10"]),
            ("T-2024-013", ["TLE-G7", "SSHS-TVL-DBMS", "SSHS-TVL-PROG"]),
            ("T-2024-014", ["TLE-G7", "SSHS-STEM-DATA", "SSHS-TVL-DBMS"]),
            ("T-2024-018", ["SSHS-STEM-DATA", "SSHS-TVL-PROG"]),
            ("T-2024-015", ["ESP-G7", "SSHS-LCS11"]),
        ]
        for emp_id, codes in qual_mappings:
            teach = t_map[emp_id]
            for c in codes:
                if c in subj_map:
                    TeacherQualification.objects.get_or_create(teacher=teach, subject=subj_map[c])

        # 8. Sections (JHS + SSHS)
        sections_data = [
            ("Grade 7 - Rizal", 7, "jhs_core", room_map["Room 101"]),
            ("Grade 10 - Bonifacio", 10, "jhs_core", room_map["Room 201"]),
            ("Grade 11 - STEM Einstein", 11, "shs_stem", room_map["Room 301"]),
            ("Grade 11 - Arts & Humanities Plato", 11, "shs_arts_ssh", room_map["Room 302"]),
            ("Grade 12 - Tech-Pro Turing", 12, "shs_tech_pro", room_map["Room 303"]),
        ]
        sec_map = {}
        for name, gr, clus, hroom in sections_data:
            sec, _ = Section.objects.get_or_create(
                name=name, academic_year=ay,
                defaults={'grade_level': gr, 'cluster': clus, 'homeroom': hroom}
            )
            sec_map[name] = sec

        # 9. Section Subject Requirements
        sec_reqs = {
            "Grade 7 - Rizal": ["ENG-G7", "MATH-G7", "SCI-G7", "FIL-G7", "AP-G7", "MAPEH-G7", "TLE-G7", "ESP-G7"],
            "Grade 10 - Bonifacio": ["ENG-G10", "MATH-G10", "SCI-G10", "FIL-G10", "AP-G10", "MAPEH-G10"],
            "Grade 11 - STEM Einstein": ["SSHS-COMM11", "SSHS-GMATH11", "SSHS-GSCI11", "SSHS-STEM-PRECALC", "SSHS-STEM-DATA", "SSHS-LCS11"],
            "Grade 11 - Arts & Humanities Plato": ["SSHS-COMM11", "SSHS-GMATH11", "SSHS-GSCI11", "SSHS-ARTS-LIT", "SSHS-ARTS-PHIL", "SSHS-LCS11"],
            "Grade 12 - Tech-Pro Turing": ["SSHS-COMM11", "SSHS-GMATH11", "SSHS-TVL-DBMS", "SSHS-TVL-PROG", "SSHS-LCS11"],
        }
        for sec_name, scodes in sec_reqs.items():
            sec = sec_map[sec_name]
            for sc in scodes:
                if sc in subj_map:
                    SectionSubjectRequirement.objects.get_or_create(section=sec, subject=subj_map[sc])

        # 10. Initial Draft Schedule
        Schedule.objects.get_or_create(
            name="Official Master Timetable S.Y. 2026-2027 (Term 1 & JHS)",
            academic_year=ay,
            term=term_shs1,
            defaults={'status': 'draft', 'fitness_score': 0.0}
        )

        self.stdout.write(self.style.SUCCESS("Successfully seeded comprehensive Philippine school data!"))
