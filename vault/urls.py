# vault/urls.py
from django.urls import path
from . import views

app_name = 'vault'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),  # ✅ Главная страница
    path('list/', views.vault_list, name='vault_list'),  # ✅ Список записей (было '')
    path('detail/<int:entry_id>/', views.vault_detail, name='vault_detail'),
    path('add/', views.add_entry, name='add_entry'),  # было vault_add
    path('edit/<int:entry_id>/', views.edit_entry, name='edit_entry'),
    path('delete/<int:entry_id>/', views.delete_entry, name='delete_entry'),
    path('detail/<int:entry_id>/permissions/', views.manage_permissions, name='manage_permissions'),
    path('api/detail/<int:entry_id>/check-access/', views.check_access, name='check_access'),
]