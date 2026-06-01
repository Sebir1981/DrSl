# core/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def dashboard(request):
    """Главная страница с боковым меню"""

    # Здесь позже добавим статистику из БД
    context = {
        'groups_count': 0,  # позже: Group.objects.count()
        'students_count': 0,  # позже: Student.objects.count()
        'teachers_count': 0,
        'instructors_count': 0,
        'cars_count': 0,
    }
    return render(request, 'core/dashboard.html', context)