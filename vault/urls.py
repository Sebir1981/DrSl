# vault/urls.py
from django.urls import path
from . import views

app_name = 'vault'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),  # ✅ Главная страница
    path('list/', views.vault_list, name='vault_list'),  # ✅ Список записей (было '')
    path('add/', views.add_entry, name='add_entry'),
]