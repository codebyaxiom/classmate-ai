from django.db import models
from django.contrib.auth.models import User

class AcademicYear(models.Model):
    name = models.CharField(max_length=50, unique=True, help_text="e.g. 2026-2027")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Term(models.Model):
    TERM_TYPES = [
        ('jhs_full_year', 'JHS - Full School Year (4 Quarters)'),
        ('shs_term_1', 'SSHS - Term 1 (Trimester)'),
        ('shs_term_2', 'SSHS - Term 2 (Trimester)'),
        ('shs_term_3', 'SSHS - Term 3 (Trimester)'),
    ]
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='terms')
    name = models.CharField(max_length=100)
    term_type = models.CharField(max_length=30, choices=TERM_TYPES, default='shs_term_1')
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('academic_year', 'name')

    def __str__(self):
        return f"{self.academic_year.name} - {self.name}"

class Department(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.code})"

class FacilityType(models.Model):
    code = models.CharField(max_length=50, unique=True, help_text="e.g. lecture, science_lab, speech_lab, avr")
    name = models.CharField(max_length=150, help_text="e.g. Standard Classroom, Science Laboratory")
    description = models.CharField(max_length=255, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @classmethod
    def get_all_choices(cls):
        custom = list(cls.objects.filter(is_active=True).order_by('name'))
        if not custom:
            return [
                ('lecture', 'Standard Classroom / Homeroom'),
                ('science_lab', 'Science Laboratory'),
                ('computer_lab', 'Computer / Mac Lab'),
                ('tvl_workshop', 'TVL / TLE Workshop'),
                ('gym', 'Gymnasium / Open Court'),
            ]
        return [(ft.code, ft.name) for ft in custom]

class Room(models.Model):
    ROOM_TYPES = [
        ('lecture', 'Standard Classroom / Homeroom'),
        ('science_lab', 'Science Laboratory'),
        ('computer_lab', 'Computer Laboratory'),
        ('tvl_workshop', 'TVL / TLE Workshop'),
        ('gym', 'Gymnasium / Open Court'),
    ]
    name = models.CharField(max_length=100, unique=True)
    room_type = models.CharField(max_length=60, default='lecture')
    capacity = models.IntegerField(default=45)
    building = models.CharField(max_length=100, blank=True, default='')
    is_active = models.BooleanField(default=True)

    @property
    def room_type_display_name(self):
        ft = FacilityType.objects.filter(code=self.room_type).first()
        if ft:
            return ft.name
        dict_choices = dict(self.ROOM_TYPES)
        if self.room_type in dict_choices:
            return dict_choices[self.room_type]
        return self.room_type.replace('_', ' ').title()

    def get_room_type_display(self):
        return self.room_type_display_name

    def __str__(self):
        return f"{self.name} [{self.room_type_display_name}]"

class CurriculumCluster(models.Model):
    LEVEL_CHOICES = [
        ('jhs', 'Junior High School (JHS)'),
        ('shs', 'Senior High School (SHS)'),
        ('both', 'Both JHS & SHS'),
    ]
    code = models.CharField(max_length=50, unique=True, help_text="e.g. pure_academic, stem, humss, jhs_core")
    name = models.CharField(max_length=150, help_text="e.g. Pure Academic, STEM Cluster, Humanities")
    curriculum_level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='shs')
    description = models.CharField(max_length=255, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_curriculum_level_display()})"

    @classmethod
    def get_all_choices(cls):
        clusters = list(cls.objects.filter(is_active=True).order_by('curriculum_level', 'name'))
        if not clusters:
            return [
                ('pure_academic', 'Pure Academic'),
                ('jhs_core', 'JHS MATATAG Curriculum Core'),
                ('shs_core', 'SSHS Core Subject'),
                ('shs_stem', 'SSHS Academic - STEM Cluster'),
                ('shs_arts_ssh', 'SSHS Academic - Arts, Social Sciences & Humanities'),
                ('shs_sports_health', 'SSHS Academic - Sports, Health & Wellness'),
                ('shs_tech_pro', 'SSHS Tech-Pro (TVL) Elective'),
            ]
        return [(c.code, c.name) for c in clusters]


class Subject(models.Model):
    GRADE_CHOICES = [
        (7, 'Grade 7 (JHS)'),
        (8, 'Grade 8 (JHS)'),
        (9, 'Grade 9 (JHS)'),
        (10, 'Grade 10 (JHS)'),
        (11, 'Grade 11 (SHS)'),
        (12, 'Grade 12 (SHS)'),
    ]
    CLUSTER_CHOICES = [
        ('pure_academic', 'Pure Academic (SSHS)'),
        ('jhs_core', 'JHS MATATAG Curriculum Core'),
        ('shs_core', 'SSHS Core Subject'),
        ('shs_stem', 'SSHS Academic - STEM Cluster'),
        ('shs_arts_ssh', 'SSHS Academic - Arts, Social Sciences & Humanities'),
        ('shs_sports_health', 'SSHS Academic - Sports, Health & Wellness'),
        ('shs_tech_pro', 'SSHS Tech-Pro (TVL) Elective'),
    ]
    code = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=150)
    grade_level = models.IntegerField(choices=GRADE_CHOICES)
    cluster = models.CharField(max_length=60, default='jhs_core')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='subjects')
    room_type_needed = models.CharField(max_length=60, default='lecture')
    weekly_periods = models.FloatField(default=4.0, help_text="Number of 1-hour periods per week (supports decimals like 1.5, 4.5)")
    consecutive_periods = models.IntegerField(default=1, help_text="1 for standard, 2 for double-period lab/workshop")
    is_lab = models.BooleanField(default=False)

    @property
    def room_type_display_name(self):
        ft = FacilityType.objects.filter(code=self.room_type_needed).first()
        if ft:
            return ft.name
        dict_choices = dict(Room.ROOM_TYPES)
        if self.room_type_needed in dict_choices:
            return dict_choices[self.room_type_needed]
        return self.room_type_needed.replace('_', ' ').title()

    @property
    def cluster_display_name(self):
        c = CurriculumCluster.objects.filter(code=self.cluster).first()
        if c:
            return c.name
        dict_choices = dict(self.CLUSTER_CHOICES)
        if self.cluster in dict_choices:
            return dict_choices[self.cluster]
        return self.cluster.replace('_', ' ').upper()

    def get_room_type_needed_display(self):
        return self.room_type_display_name

    def get_cluster_display(self):
        return self.cluster_display_name

    def __str__(self):
        return f"{self.code} - {self.title} (G{self.grade_level})"

class Teacher(models.Model):
    CURRICULUM_LEVEL_CHOICES = [
        ('jhs', 'Junior High School (Grades 7–10)'),
        ('shs', 'Senior High School (Grades 11–12)'),
        ('both', 'Both JHS & SHS (Integrated)'),
    ]
    employee_id = models.CharField(max_length=30, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(blank=True, default='')
    curriculum_level = models.CharField(max_length=20, choices=CURRICULUM_LEVEL_CHOICES, default='both')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='teachers')
    max_daily_hours = models.FloatField(default=6.0, help_text="DepEd DO 005 s. 2024 (max 6h actual teaching)")
    max_weekly_hours = models.FloatField(default=30.0)
    preferred_vacant_period = models.IntegerField(null=True, blank=True, help_text="Preferred vacant period (1-8)")
    is_active = models.BooleanField(default=True)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return f"{self.full_name} ({self.department.code})"

class TeacherQualification(models.Model):
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='qualifications')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='qualified_teachers')

    class Meta:
        unique_together = ('teacher', 'subject')

    def __str__(self):
        return f"{self.teacher.full_name} -> {self.subject.code}"

class Section(models.Model):
    name = models.CharField(max_length=100)
    grade_level = models.IntegerField(choices=Subject.GRADE_CHOICES)
    cluster = models.CharField(max_length=60, default='jhs_core')
    homeroom = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='homeroom_sections')
    adviser = models.ForeignKey('Teacher', on_delete=models.SET_NULL, null=True, blank=True, related_name='advised_sections')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='sections')

    class Meta:
        unique_together = ('name', 'academic_year')

    @property
    def cluster_display_name(self):
        c = CurriculumCluster.objects.filter(code=self.cluster).first()
        if c:
            return c.name
        dict_choices = dict(Subject.CLUSTER_CHOICES)
        if self.cluster in dict_choices:
            return dict_choices[self.cluster]
        return self.cluster.replace('_', ' ').upper()

    def get_cluster_display(self):
        return self.cluster_display_name

    def __str__(self):
        return f"{self.name} (G{self.grade_level})"

class AncillaryDesignationCatalog(models.Model):
    code = models.CharField(max_length=50, unique=True, help_text="e.g. ict_coordinator, property_custodian")
    name = models.CharField(max_length=150, help_text="e.g. School ICT / LIS Coordinator")
    default_weekly_hours = models.FloatField(default=2.0)
    description = models.CharField(max_length=255, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.default_weekly_hours}h/wk)"

    @classmethod
    def get_all_choices(cls):
        custom = list(cls.objects.filter(is_active=True).order_by('name'))
        if not custom:
            return AncillaryDuty.COMMON_DESIGNATIONS
        return [(d.code, f"{d.name} ({d.default_weekly_hours}h/wk)") for d in custom]


class AncillaryDuty(models.Model):
    COMMON_DESIGNATIONS = [
        ('adviser', 'Class Advisory (Adviser)'),
        ('ict_coordinator', 'School ICT / LIS Coordinator'),
        ('drrm_coordinator', 'Disaster Risk Reduction (DRRM) Coordinator'),
        ('school_paper', 'School Paper / Campus Journalism Adviser'),
        ('scout_coordinator', 'BSP / GSP Scout Coordinator'),
        ('dept_coordinator', 'Department / Grade Level Coordinator'),
        ('guidance_designate', 'Guidance Counselor Designate'),
        ('canteen_manager', 'Canteen / Feeding Program Manager'),
        ('property_custodian', 'Property Custodian / Supply Designate'),
        ('sports_coach', 'Sports / Athletic Club Coach'),
        ('reading_coordinator', 'Reading / Remediation Coordinator'),
        ('custom', 'Other Special Designation'),
    ]
    teacher = models.ForeignKey('Teacher', on_delete=models.CASCADE, related_name='ancillary_duties')
    title = models.CharField(max_length=150, help_text="Designation or Ancillary Title")
    designation_type = models.CharField(max_length=50, choices=COMMON_DESIGNATIONS, default='custom')
    weekly_hours = models.FloatField(default=2.0, help_text="Credited hours/week under DepEd DO 005 s. 2024")
    description = models.CharField(max_length=255, blank=True, default='')

    def __str__(self):
        return f"{self.teacher.full_name} - {self.title} ({self.weekly_hours}h/wk)"


class TimeSlot(models.Model):
    DAY_CHOICES = [
        (1, 'Monday'),
        (2, 'Tuesday'),
        (3, 'Wednesday'),
        (4, 'Thursday'),
        (5, 'Friday'),
    ]
    TIMEFRAME_GRADE_CHOICES = [
        (0, 'All / Universal'),
        (7, 'Grade 7 (JHS)'),
        (8, 'Grade 8 (JHS)'),
        (9, 'Grade 9 (JHS)'),
        (10, 'Grade 10 (JHS)'),
        (11, 'Grade 11 (SHS)'),
        (12, 'Grade 12 (SHS)'),
    ]
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    period_number = models.IntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    label = models.CharField(max_length=50)
    is_break = models.BooleanField(default=False, help_text="Flag Ceremony, Recess, or Lunch Break")
    grade_level = models.IntegerField(default=0, choices=TIMEFRAME_GRADE_CHOICES, help_text="Grade level this timeframe applies to (0 for Universal)")

    @property
    def duration_minutes(self):
        start_m = self.start_time.hour * 60 + self.start_time.minute
        end_m = self.end_time.hour * 60 + self.end_time.minute
        return max(0, end_m - start_m)

    @classmethod
    def get_periods_for_grade(cls, grade_level, day=1):
        slots = cls.objects.filter(day_of_week=day, grade_level=grade_level).order_by('period_number')
        if not slots.exists():
            slots = cls.objects.filter(day_of_week=day, grade_level=0).order_by('period_number')
        return slots

    class Meta:
        unique_together = ('day_of_week', 'period_number', 'grade_level')
        ordering = ['grade_level', 'day_of_week', 'period_number']

    def __str__(self):
        grade_tag = f" [G{self.grade_level}]" if self.grade_level else ""
        return f"{self.get_day_of_week_display()} P{self.period_number}{grade_tag} ({self.label})"


class SchoolProfile(models.Model):
    school_name = models.CharField(max_length=200, default="ISABELA NATIONAL HIGH SCHOOL")
    school_id = models.CharField(max_length=50, default="300582", blank=True)
    region = models.CharField(max_length=150, default="REGION II – CAGAYAN VALLEY")
    division = models.CharField(max_length=150, default="SCHOOLS DIVISION OF ISABELA")
    district = models.CharField(max_length=100, default="District II", blank=True)

    # 5 Official DepEd Signatories matching official document format
    prepared_by_name = models.CharField(max_length=150, default="VILMA L. VILLADOR, PhD")
    prepared_by_title = models.CharField(max_length=150, default="Principal II")

    reviewed_by_name = models.CharField(max_length=150, default="JOVITO M. CADIZ, PhD")
    reviewed_by_title = models.CharField(max_length=150, default="Principal IV, District-in-Charge")

    verified_by_name = models.CharField(max_length=150, default="MARIETESS B. BAQUIRAN, PhD")
    verified_by_title = models.CharField(max_length=150, default="Chief, Curriculum Instruction Division")

    recommending_name = models.CharField(max_length=150, default="MARY JULIE A. TRUS, PhD, CESO VI")
    recommending_title = models.CharField(max_length=150, default="Assistant Schools Division Superintendent")

    approved_by_name = models.CharField(max_length=150, default="RACHEL R. LLANA, PhD, CESO V")
    approved_by_title = models.CharField(max_length=150, default="Schools Division Superintendent")

    # Academic cycle configuration
    active_academic_year = models.ForeignKey('AcademicYear', on_delete=models.SET_NULL, null=True, blank=True)
    active_term = models.ForeignKey('Term', on_delete=models.SET_NULL, null=True, blank=True)

    # Workload Policy Limits (DepEd DO 005 s. 2024 / RA 4670)
    max_daily_teaching_hours = models.FloatField(default=6.0, help_text="Max actual classroom teaching hours per day")
    max_weekly_teaching_hours = models.FloatField(default=30.0, help_text="Max actual classroom teaching hours per week")
    standard_workweek_hours = models.FloatField(default=40.0, help_text="Total official weekly work hours")

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.school_name} Profile"

    @classmethod
    def get_settings(cls):
        profile, created = cls.objects.get_or_create(id=1)
        if not profile.active_academic_year:
            profile.active_academic_year = AcademicYear.objects.filter(is_active=True).first() or AcademicYear.objects.first()
        if not profile.active_term:
            profile.active_term = Term.objects.filter(is_active=True).first() or Term.objects.first()
        if created:
            profile.save()
        return profile

class SectionSubjectRequirement(models.Model):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='subject_requirements')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='section_requirements')
    assigned_teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True)
    preferred_room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('section', 'subject')

    def __str__(self):
        return f"{self.section.name} - {self.subject.code}"

class Schedule(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft (Editing / Work-in-Progress)'),
        ('published', 'Official Published Timetable'),
        ('archived', 'Archived'),
    ]
    name = models.CharField(max_length=150)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='schedules')
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='schedules')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    fitness_score = models.FloatField(default=0.0)
    hard_conflicts_count = models.IntegerField(default=0)
    soft_conflicts_count = models.IntegerField(default=0)
    generation_iterations = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} [{self.get_status_display()}]"

class ScheduleItem(models.Model):
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='items')
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='schedule_items')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='schedule_items')
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='schedule_items')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='schedule_items')
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='schedule_items')
    is_locked = models.BooleanField(default=False, help_text="Preserve manual swap during re-generation")

    class Meta:
        unique_together = ('schedule', 'section', 'time_slot')

    def __str__(self):
        return f"{self.section.name} - {self.subject.code} @ {self.time_slot}"

class AuditLog(models.Model):
    action = models.CharField(max_length=150)
    details = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {self.action}"
