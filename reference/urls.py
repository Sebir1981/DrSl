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

    # 📦 Наборы предметов (SubjectSet) - ЗАКОММЕНТИРОВАНО, т.к. функционал заменён на TrainingProgram
    # path('subject-sets/', views.subject_sets_list, name='subject_sets_list'),
    # path('subject-sets/create/', views.subject_set_create, name='subject_set_create'),
    # path('subject-sets/<int:pk>/edit/', views.subject_set_edit, name='subject_set_edit'),
    # path('subject-sets/<int:pk>/delete/', views.subject_set_delete, name='subject_set_delete'),
]