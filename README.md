# CLASSMATE-AI 🎓

**CLASSMATE-AI: An AI-Assisted Classroom and Teaching Load Automated Scheduling System for Managed Assignments and Teacher Efficiency**

Developed as a Developmental Research / Design-and-Development solution to solve manual timetabling friction in Philippine high schools, fully compliant with **DepEd Order No. 005 s. 2024** and the new **Strengthened Senior High School (SSHS)** curriculum.

---

## 🌟 Key Features

1. **Genetic Algorithm (GA) Optimization Engine**:
   - Section-permutation chromosome representation for rapid convergence with zero self-collisions.
   - Enforces hard constraints: no teacher overlaps, no room collisions, no classes during recess/lunch, matching specialized science & computer laboratories.
   - Optimizes soft constraints: teacher availability, preferred vacant periods, uniform day distribution, and fatigue mitigation.

2. **DepEd Strengthened SHS (SSHS) & JHS Hybrid Architecture**:
   - Accommodates JHS MATATAG full-year curriculum alongside SSHS Trimestral (3-Term) block schedules.
   - Handles modern SSHS clusters: Core, STEM Cluster, Arts, Social Sciences & Humanities, Sports/Health/Wellness, and Tech-Pro (TVL) Electives.

3. **Faculty Teaching Load Management (SF7)**:
   - Tracks actual teaching hours against Magna Carta (RA 4670) and DO 005 s. 2024 (max 6h daily teaching + 2h prep).
   - Generates official printable **School Form 7 (SF7) Teacher's Individual Program**.

4. **Mobile-First DepEd Theme**:
   - DepEd brand palette (Navy `#0038A8`, Sun Gold `#FDDA24`, White).
   - Responsive day pills (`Mon`, `Tue`, `Wed`, `Thu`, `Fri`) allowing easy navigation on smartphones.

5. **Interactivity & Integration**:
   - In-place schedule slot adjustment & swap studio with real-time conflict validation.
   - Slot locking (`is_locked`) to protect manual edits from AI overwrite during subsequent runs.
   - CSV bulk import with downloadable sample templates for teachers and rooms.
   - One-click multi-sheet Excel timetable export.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+
- Django 5.x+
- `openpyxl`, `reportlab`, `django-cors-headers`

### 2. Installation
```bash
git clone https://github.com/codebyaxiom/classmate-ai.git
cd classmate-ai

python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_school_data
python manage.py runserver
```

Open `http://localhost:8000` in your browser.
