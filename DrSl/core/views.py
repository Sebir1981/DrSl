from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods  # <-- 1. Добавьте этот импорт

@login_required
@require_http_methods(["GET"])  # <-- 2. Добавьте этот декоратор
def dashboard(request):
    """Главная страница с боковым меню."""
    context = {
        'groups_count': 0,
        'students_count': 0,
        'teachers_count': 0,
        'instructors_count': 0,
    }
    return render(request, 'core/dashboard.html', context)