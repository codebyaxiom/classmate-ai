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

class Room(models.Model):
    ROOM_TYPES = [
        ('lecture', 'Standard Classroom / Homeroom'),
        ('science_lab', 'Science Laboratory'),
        ('computer_lab', 'Computer Laboratory'),
        ('tvl_workshop', 'TVL / TLE Workshop'),
        ('gym', 'Gymnasium / Open Court'),
    ]
    name = models.CharField(max_length=100, unique=True)
    room_type = models.CharField(max_length=30, choices=ROOM_TYPES, default='lecture')
    capacity = models.IntegerField(default=45)
    building = models.CharField(max_length=100, blank=True, default='')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} [{self.get_room_type_display()}]"

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
    cluster = models.CharField(max_length=30, choices=CLUSTER_CHOICES, default='jhs_core')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='subjects')
    room_type_needed = models.CharField(max_length=30, choices=Room.ROOM_TYPES, default='lecture')
    weekly_periods = models.IntegerField(default=4, help_text="Number of 1-hour periods per week")
    consecutive_periods = models.IntegerField(default=1, help_text="1 for standard, 2 for double-period lab/workshop")
    is_lab = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.code} - {self.title} (G{self.grade_level})"

class Teacher(models.Model):
    employee_id = models.CharField(max_length=30, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(blank=True, default='')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='teachers')
    max_daily_hours = models.IntegerField(default=6, help_text="DepEd DO 005 s. 2024 (max 6h actual teaching)")
    max_weekly_hours = models.IntegerField(default=30)
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
    cluster = models.CharField(max_length=30, choices=Subject.CLUSTER_CHOICES, default='jhs_core')
    homeroom = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='homeroom_sections')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='sections')

    class Meta:
        unique_together = ('name', 'academic_year')

    def __str__(self):
        return f"{self.name} (G{self.grade_level})"

class TimeSlot(models.Model):
    DAY_CHOICES = [
        (1, 'Monday'),
        (2, 'Tuesday'),
        (3, 'Wednesday'),
        (4, 'Thursday'),
        (5, 'Friday'),
    ]
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    period_number = models.IntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    label = models.CharField(max_length=50)
    is_break = models.BooleanField(default=False, help_text="Flag Ceremony, Recess, or Lunch Break")

    class Meta:
        unique_together = ('day_of_week', 'period_number')
        ordering = ['day_of_week', 'period_number']

    def __str__(self):
        return f"{self.get_day_of_week_display()} P{self.period_number} ({self.label})"

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
