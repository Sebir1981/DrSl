from django.urls import path
from . import views

app_name = 'classrooms'
urlpatterns = [
    path('', views.classroom_list, name='classroom_list'),
]