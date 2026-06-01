# reports/urls.py
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.reports_dashboard, name='dashboard'),
    path('credits/', views.credits_report, name='credits'),
    # В будущем можно добавить: path('exams/', views.exams_report, name='exams'),
]