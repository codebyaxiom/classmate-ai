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
    
    # API endpoints
    path('api/run-ga/', views.run_genetic_algorithm, name='api_run_ga'),
    path('api/swap-item/', views.swap_item_api, name='api_swap_item'),
    path('api/toggle-lock/', views.toggle_lock_api, name='api_toggle_lock'),
]
