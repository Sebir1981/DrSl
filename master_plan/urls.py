from django.urls import path
from . import views

app_name = 'master_plan'

urlpatterns = [
    path('', views.master_plan_dashboard, name='dashboard'),
    path('add-group/', views.add_group_to_plan, name='add_group'),
    path('update-group/', views.update_group_in_plan, name='update_group'),  # ← НОВОЕ
    path('delete-group/', views.delete_group_from_plan, name='delete_group'),  # ← НОВОЕ
    path('update-distribution/', views.update_distribution, name='update_distribution'),
    path('api/group/<int:group_id>/', views.get_group_data, name='get_group_data'),
]