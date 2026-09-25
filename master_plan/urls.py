from django.urls import path
from . import views

app_name = 'master_plan'

urlpatterns = [
    path('', views.master_plan_dashboard, name='dashboard'),
    path('add-group/', views.add_group_to_plan, name='add_group'),
    path('update-group/', views.update_group_in_plan, name='update_group'),
    path('delete-group/', views.delete_group_from_plan, name='delete_group'),
    path('update-distribution/', views.update_distribution, name='update_distribution'),
    path('api/group/<int:group_id>/', views.get_group_data, name='get_group_data'),

    # 🔹 НОВЫЕ URL для модального окна распределения
    path('api/distribute/<int:plan_group_id>/', views.open_distribution_modal, name='open_distribution_modal'),
    path('save-distribution/', views.save_distribution, name='save_distribution'),
    path('auto-distribute/<int:plan_group_id>/', views.auto_distribute_group, name='auto_distribute_group'),
    path('api/cell-students/<int:plan_group_id>/<int:master_id>/', views.get_cell_students, name='get_cell_students',),
    path('api/reassignment/group/<int:plan_group_id>/', views.get_reassignment_data, name='get_reassignment_data',),
    path('save-reassignment/', views.save_reassignment, name='save_reassignment',),
]