from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('timetable/', views.timetable_view, name='timetable'),
    path('teacher-loads/', views.teacher_loads_view, name='teacher_loads'),
    path('room-utilization/', views.room_utilization_view, name='room_utilization'),
    path('import-export/', views.import_export_view, name='import_export'),
    path('download-sample/<str:template_type>/', views.download_sample_csv, name='download_sample'),
    path('export-excel/', views.export_excel, name='export_excel'),
    path('print-sf7/<int:teacher_id>/', views.print_sf7_view, name='print_sf7'),
    
    path('teachers/', views.teachers_view, name='teachers'),
    path('api/teachers/add/', views.add_teacher_api, name='api_add_teacher'),
    path('api/teachers/delete/<int:teacher_id>/', views.delete_teacher_api, name='api_delete_teacher'),
    path('api/ancillary/add/', views.add_ancillary_duty_api, name='api_add_ancillary_duty'),
    path('api/ancillary/delete/<int:duty_id>/', views.delete_ancillary_duty_api, name='api_delete_ancillary_duty'),
    
    path('sections/', views.sections_view, name='sections'),
    path('api/sections/add/', views.add_section_api, name='api_add_section'),
    path('api/sections/<int:section_id>/update/', views.update_section_assignments_api, name='api_update_section_assignments'),
    path('api/sections/<int:section_id>/delete/', views.delete_section_api, name='api_delete_section'),
    path('api/curriculum/subjects-by-grade/', views.get_subjects_by_grade_api, name='api_subjects_by_grade'),
    
    path('subjects/', views.subjects_view, name='subjects'),
    path('api/subjects/add/', views.add_subject_api, name='api_add_subject'),
    path('api/subjects/delete/<int:subject_id>/', views.delete_subject_api, name='api_delete_subject'),
    path('api/timeslots/add/', views.add_timeslot_api, name='api_add_timeslot'),
    
    # API endpoints
    path('api/run-ga/', views.run_genetic_algorithm, name='api_run_ga'),
    path('api/swap-item/', views.swap_item_api, name='api_swap_item'),
    path('api/toggle-lock/', views.toggle_lock_api, name='api_toggle_lock'),
]
