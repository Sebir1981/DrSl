from django.urls import path
from . import views
from groups.views.exports import export_schedule_to_excel, export_plan_graphic_to_excel

app_name = 'groups'

urlpatterns = [
    path('', views.groups_dashboard, name='dashboard'),
    path('list/', views.group_list, name='group_list'),
    path('add/', views.group_form, name='group_form'),
    path('<int:group_id>/edit/', views.group_form, name='group_edit'),
    path('<int:group_id>/', views.group_detail, name='group_detail'),

    path('credits-exams/', views.credits_exams_dashboard, name='credits_exams'),
    path('credits-exams/add/', views.credits_exams_add, name='credits_exams_add'),

    #  План-графики
    path('schedules/', views.schedule_plans_list, name='schedule_plans_list'),
    path('schedules/create/', views.schedule_plan_create, name='schedule_plan_create'),
    path('schedules/<int:plan_id>/edit/', views.schedule_plan_create, name='schedule_plan_edit'),
    path('schedules/<int:plan_id>/step2/', views.schedule_plan_step2, name='schedule_plan_step2'),
    path('schedules/<int:plan_id>/ajax/update-day/', views.schedule_plan_ajax_update_day,
         name='schedule_plan_ajax_update_day'),
    path('<int:plan_id>/clear-topics/', views.schedule_plans.clear_plan_topics, name='clear_plan_topics'),

    # 🔹 Удаление план-графика
    path('schedules/<int:plan_id>/delete/', views.schedule_plan_delete, name='schedule_plan_delete'),
    path('schedules/<int:plan_id>/delete-plan/', views.schedule_plan_reset, name='schedule_plan_reset'),


    # 🔹 API
    path('api/instructor/availability/', views.check_instructor_availability, name='check_instructor_availability'),
    path('api/groups/<int:group_id>/data/', views.group_api_data, name='group_api_data'),
    path('api/teacher-schedule/', views.get_teacher_schedules, name='get_teacher_schedules'),

    # 🔹 ЭКСПОРТ В EXCEL (два типа)
    path('schedules/<int:plan_id>/export/', export_schedule_to_excel, name='schedule_export'),
    path('schedules/<int:plan_id>/export-plan-graphic/', export_plan_graphic_to_excel, name='schedule_export_plan_graphic'),
]