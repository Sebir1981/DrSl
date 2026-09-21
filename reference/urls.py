# reference/urls.py
from django.urls import path
from . import views

app_name = 'reference'

urlpatterns = [
    # 🏠 Дашборд
    path('', views.reference_dashboard, name='dashboard'),

    #  Темы занятий
    path('topics/', views.topic_list, name='topic_list'),
    path('topics/delete/<int:topic_id>/', views.topic_delete, name='topic_delete'),  # ✅ Исправлено под фронтенд
    path('api/topics/', views.api_get_topics, name='api_get_topics'),
    path('api/topics/save/', views.api_save_topics, name='api_save_topics'),

    # 📚 Предметы (Справочник)
    path('subjects/', views.subject_list, name='subject_list'),
    path('subjects/<int:pk>/edit/', views.subject_edit, name='subject_edit'),
    path('subjects/delete/<int:pk>/', views.subject_delete, name='subject_delete'),

    # 📁 Категории и Программы обучения
    path('categories/', views.category_subjects_list, name='category_subjects_list'),
    # 🔹 Перенаправление "Настроить состав" -> Конструктор программ
    path('categories/<str:category_code>/subjects/', views.category_subjects_manage_redirect, name='category_subjects_manage'),

    # 🛠️ Конструктор программ (страница списка /programs/ удалена)
    path('programs/create/', views.training_program_builder, name='program_create'),
    path('programs/<int:pk>/edit/', views.training_program_builder, name='program_edit'),
    path('programs/save/', views.training_program_save, name='program_save'),
    path('programs/<int:pk>/delete/', views.training_program_delete, name='program_delete'),

    # 🔌 API
    path('api/subjects/by-category/', views.api_get_subjects_by_category, name='api_get_subjects_by_category'),
    path('api/subject-topics/', views.api_get_subject_topics, name='api_get_subject_topics'),

    # 🚗 Практические занятия
    # Должно быть только это:
    path('practice/', views.practice_exercise_list, name='practice_exercise_list'),
    path('practice/exercise/<int:exercise_id>/delete/', views.practice_exercise_delete, name='practice_exercise_delete'),
    path('practice/category/add/', views.practice_category_add, name='practice_category_add'),
    path('practice/category/<int:category_id>/delete/', views.practice_category_delete, name='practice_category_delete'),
    path('training-plan/create/', views.training_plan_create, name='training_plan_create'),

    # 💰 Платные услуги
    path('paid-services/', views.paid_service_list, name='paid_service_list'),
    path('paid-services/delete/<int:pk>/', views.paid_service_delete, name='paid_service_delete'),
    path('paid-services/update/<int:pk>/', views.paid_service_update, name='paid_service_update'),

# 🔹 Управление темами зачётов
    path('credits/', views.credit_list, name='credit_list'),
    path('credits/<int:credit_id>/edit/', views.credit_edit, name='credit_edit'),
    path('credits/<int:credit_id>/delete/', views.credit_delete, name='credit_delete'),
]