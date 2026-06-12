# reference/urls.py
from django.urls import path
from . import views

app_name = 'reference'

urlpatterns = [
    path('', views.reference_dashboard, name='dashboard'),
    path('topics/', views.topic_list, name='topic_list'),
    path('delete/<int:topic_id>/', views.topic_delete, name='topic_delete'),
]