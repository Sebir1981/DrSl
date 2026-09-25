from django.urls import path
from . import views

app_name = 'dispatcher'

urlpatterns = [
    path('', views.dispatcher_dashboard, name='dashboard'),
    path('route-sheets/', views.route_sheet_list, name='route_sheet_list'),
    path('route-sheets/add/', views.route_sheet_add, name='route_sheet_add'),
    path('route-sheets/<int:pk>/edit/', views.route_sheet_edit, name='route_sheet_edit'),
    path('route-sheets/<int:pk>/delete/', views.route_sheet_delete, name='route_sheet_delete'),
]