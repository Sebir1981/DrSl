from django.urls import path
from . import views

app_name = 'teachers'
urlpatterns = [
    path('', views.teacher_list, name='teacher_list'),
    path('add/', views.teacher_add, name='teacher_add'),
    path('<int:pk>/edit/', views.teacher_edit, name='teacher_edit'),
    path('<int:pk>/delete/', views.teacher_delete, name='teacher_delete'),
    path('search-api/', views.teacher_search_api, name='teacher_search_api'),
]