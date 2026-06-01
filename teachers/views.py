# teachers/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Teacher


@login_required
def teacher_list(request):
    # ✅ Без classroom, без addresses — чистый запрос
    teachers = Teacher.objects.all()

    # 🔍 Поиск только по личным данным и телефону
    search_query = request.GET.get('search', '').strip()
    if search_query:
        teachers = teachers.filter(
            Q(last_name__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(patronymic__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    context = {
        'teachers': teachers,
        'search_query': search_query,
    }
    return render(request, 'teachers/teacher_list.html', context)