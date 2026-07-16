# students/urls.py
from django.urls import path
from . import views

app_name = 'students'

urlpatterns = [
    path('', views.students_dashboard, name='dashboard'),
    path('list/', views.student_list, name='student_list'),
    path('add/', views.student_add, name='student_add'),
    path('<int:student_id>/', views.student_detail, name='student_detail'),
    path('<int:student_id>/transfer/', views.transfer_student, name='transfer_student'),
    path('api/surname-suggestions/', views.surname_suggestions, name='surname_suggestions'),
    path('<int:student_id>/suspend/', views.student_suspension, name='student_suspend'),
    path('<int:student_id>/dismiss/', views.student_dismissal, name='student_dismissal'),
    path('<int:student_id>/refuse/', views.student_refusal, name='student_refuse'),
    path('<int:student_id>/activate/', views.student_activate, name='student_activate'),
    path('edit/<int:student_id>/', views.student_edit, name='student_edit'),
]