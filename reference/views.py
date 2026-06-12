# reference/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from .models import LessonTopic
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from classrooms.models import Classroom
from teachers.models import Teacher
from masters.models import Master


@login_required
def topic_list(request):
    category = request.GET.get('category', 'pdd')
    valid_categories = dict(LessonTopic.CATEGORY_CHOICES).keys()
    if category not in valid_categories:
        category = 'pdd'

    topics = LessonTopic.objects.filter(category=category).order_by('topic_number')

    #  ПОДСЧЁТ ЗАПИСЕЙ ДЛЯ ВСЕХ КАТЕГОРИЙ (чтобы badge не были 0)
    categories_with_counts = []
    for code, name in LessonTopic.CATEGORY_CHOICES:
        count = LessonTopic.objects.filter(category=code).count()
        categories_with_counts.append({'code': code, 'name': name, 'count': count})

    if request.method == 'POST':
        if 'topic_number' in request.POST:
            try:
                LessonTopic.objects.create(
                    category=category,
                    topic_number=int(request.POST['topic_number']),
                    hours=float(request.POST['hours']),
                    content=request.POST['content']
                )
                messages.success(request, '✅ Тема добавлена')
            except Exception as e:
                messages.error(request, f'❌ Ошибка: {e}')
            return redirect(f'{reverse("reference:topic_list")}?category={category}')

    context = {
        'topics': topics,
        'current_category': category,
        'categories_with_counts': categories_with_counts,  # 🔹 Передаём готовый список
        'title': 'Темы занятий'
    }
    return render(request, 'reference/topic_list.html', context)


@login_required
def topic_delete(request, topic_id):
    topic = get_object_or_404(LessonTopic, pk=topic_id)
    category = topic.category
    topic.delete()
    messages.success(request, '🗑️ Тема удалена')
    return redirect(f'{reverse("reference:topic_list")}?category={category}')

@login_required
def reference_dashboard(request):
    """Дашборд раздела Справочники"""
    context = {
        'classrooms_count': Classroom.objects.count(),
        'teachers_count': Teacher.objects.count(),
        'masters_count': Master.objects.count(),
    }
    return render(request, 'reference/dashboard.html', context)