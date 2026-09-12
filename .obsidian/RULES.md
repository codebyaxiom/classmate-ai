# CLASSMATE-AI Architectural & Operational Guidelines

## 1. Absolute Candor & Anti-Sycophancy Rule
- **Never blindly agree with the user.** Do not be a 'yes-man' AI assistant.
- Always tell the unvarnished technical, architectural, and procedural truth.
- If a proposed step breaks relational integrity, violates data dependencies, or creates orphaned records, call it out proactively before executing.
- Prioritize what is objectively best for the stability, usability, and compliance of the school timetable platform.

---

## 2. Canonical School Setup Hierarchy (Data Dependency Order)
School scheduling relies on strict relational database parent-child relationships. The following sequence is mandatory for fresh or reset installations:

`
Step 1: Institutional Foundation (MUST BE FIRST)
  ├── 1.1 Active School Academic Year (e.g. S.Y. 2026–2027)
  ├── 1.2 Active Academic Term / Trimester (e.g. 1st Trimester)
  └── 1.3 School Profile & 5-Tier DepEd Signatories

Step 2: Physical Facilities & Bell Schedules
  ├── 2.1 Learning Spaces (Classrooms, Science Labs, Computer Labs, TVL Workshops)
  └── 2.2 Bell Schedules & Timeframes (Periods & protected breaks per grade level)

Step 3: Reference Catalogs
  ├── 3.1 Curriculum Clusters & Strands (JHS Core, SSHS STEM, TVL, HUMSS)
  └── 3.2 Ancillary Designation Catalog (Class Adviser, Coordinator, DRRM, etc.)

Step 4: Academic Roster
  ├── 4.1 Curriculum Subjects (Linked to Grade Level, Cluster, Facility Type)
  └── 4.2 Faculty Roster (Linked to Department, Qualifications, Ancillary Duties)

Step 5: Class Sections & Allocations
  ├── 5.1 Class Sections (Hard requirement: bound to Active Academic Year & Homeroom)
  └── 5.2 Section Subject Allocations (Binds Section + Subject + Qualified Teacher + Room)

Step 6: AI Timetable Engine & DepEd Outputs
  ├── 6.1 Genetic Algorithm Evolution (Generates collision-free master schedule)
  └── 6.2 Official DepEd Forms (SF7 Faculty Load, Classroom Programs, Room Heatmaps)
`

---

## 3. Single Source of Truth
- Catalogs (Clusters, Ancillary Designations, Facility Types) must live in the database, not hardcoded frontend fallbacks.
- When an entity is established or assigned anywhere in the application, it must synchronize with the Settings Hub catalog.
- Decimal values must be supported natively (as float/decimal) across periods, workload caps, and ancillary duties with clean integer formatting when whole (e.g., 5h instead of 5.0h, 1.5h when fractional).
