from django.urls import path
from . import views

app_name = 'masters'

urlpatterns = [
    path('', views.master_pouts_list, name='master_pouts_list'),
    path('add/', views.master_pouts_add, name='master_pouts_add'),
    path('<int:pk>/edit/', views.master_pouts_edit, name='master_pouts_edit'),
    path('<int:pk>/delete/', views.master_pouts_delete, name='master_pouts_delete'),
    path('search-api/', views.master_pouts_search_api, name='master_pouts_search_api'),
]