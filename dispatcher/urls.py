from django.urls import path
from . import views

app_name = 'dispatcher'

urlpatterns = [
    path('', views.dispatcher_dashboard, name='dashboard'),
    path('individual-books/create/', views.individual_book_form, name='individual_book_create'),
    path('individual-books/<int:pk>/edit/', views.individual_book_form, name='individual_book_edit'),
    path('api/student-search/', views.student_search_api, name='student_search_api'),
    path('individual-books/<int:pk>/delete/', views.individual_book_delete, name='individual_book_delete'),
    path('api/book-search/', views.book_search_api, name='book_search_api'),
]