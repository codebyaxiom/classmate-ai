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

    # Timeframes & Bell Schedules Desk
    path('timeframes/', views.timeframes_view, name='timeframes'),
    path('api/timeframes/add/', views.add_timeframe_api, name='api_add_timeframe'),
    path('api/timeframes/delete/<int:period_number>/', views.delete_timeframe_api, name='api_delete_timeframe'),
    path('api/timeframes/apply-preset/', views.apply_preset_timeframes_api, name='api_apply_preset_timeframes'),
    path('api/timeframes/copy/', views.copy_grade_timeframes_api, name='api_copy_grade_timeframes'),
    path('api/timeframes/clear/', views.clear_grade_timeframes_api, name='api_clear_grade_timeframes'),

    # Institutional Settings & Official DepEd Signatories
    path('settings/', views.settings_view, name='settings'),
    path('api/settings/update/', views.update_settings_api, name='api_update_settings'),
    path('api/settings/reset/', views.reset_settings_api, name='api_reset_settings'),
    path('api/settings/policy/', views.update_workload_policy_api, name='api_update_workload_policy'),
    path('api/rooms/add/', views.add_room_api, name='api_add_room'),
    path('api/rooms/update/<int:room_id>/', views.update_room_api, name='api_update_room'),
    path('api/rooms/delete/<int:room_id>/', views.delete_room_api, name='api_delete_room'),
    path('api/facility-types/add/', views.add_facility_type_api, name='api_add_facility_type'),
    path('api/facility-types/delete/<int:ft_id>/', views.delete_facility_type_api, name='api_delete_facility_type'),
    path('api/clusters/add/', views.add_cluster_api, name='api_add_cluster'),
    path('api/clusters/delete/<int:cluster_id>/', views.delete_cluster_api, name='api_delete_cluster'),
    path('api/academic-years/add/', views.add_academic_year_api, name='api_add_academic_year'),
    path('api/academic-years/<int:ay_id>/toggle/', views.toggle_academic_year_api, name='api_toggle_academic_year'),
    path('api/terms/add/', views.add_term_api, name='api_add_term'),
    path('api/terms/<int:term_id>/toggle/', views.toggle_term_api, name='api_toggle_term'),
    path('api/ancillary-catalog/add/', views.add_ancillary_catalog_api, name='api_add_ancillary_catalog'),
    path('api/ancillary-catalog/delete/<int:cat_id>/', views.delete_ancillary_catalog_api, name='api_delete_ancillary_catalog'),

    # Official DepEd Printouts
    path('print/classroom-program/<int:section_id>/', views.print_classroom_program_view, name='print_classroom_program'),
    path('print/teacher-program/<int:teacher_id>/', views.print_teacher_program_view, name='print_teacher_program'),

    # API endpoints
    path('api/run-ga/', views.run_genetic_algorithm, name='api_run_ga'),
    path('api/swap-item/', views.swap_item_api, name='api_swap_item'),
    path('api/toggle-lock/', views.toggle_lock_api, name='api_toggle_lock'),
]
