from django.urls import path
from . import views

app_name = 'cars'

urlpatterns = [
    path('', views.car_list, name='car_list'),
    path('add/', views.car_add, name='car_add'),
    path('<int:pk>/', views.car_detail, name='car_detail'),
    path('<int:pk>/edit/', views.car_edit, name='car_edit'),
    path('<int:pk>/documents/', views.car_documents, name='car_documents'),  # 🔹 НОВОЕ
    path('<int:pk>/delete/', views.car_delete, name='car_delete'),
]