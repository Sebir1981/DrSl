# teachers/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Teacher
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404, redirect
from django.http import JsonResponse
from django.template.loader import render_to_string
from .forms import TeacherForm

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


@login_required
def teacher_add(request):
    """Добавление преподавателя"""
    if request.method == 'POST':
        form = TeacherForm(request.POST)
        if form.is_valid():
            teacher = form.save()
            messages.success(request, f'✅ Преподаватель {teacher.full_name} добавлен!')
            return redirect('teachers:teacher_list')
    else:
        form = TeacherForm()

    return render(request, 'teachers/teacher_form.html', {
        'form': form,
        'title': 'Добавить преподавателя',
        'is_edit': False
    })


@login_required
def teacher_edit(request, pk):
    """Редактирование преподавателя"""
    teacher = get_object_or_404(Teacher, pk=pk)

    if request.method == 'POST':
        form = TeacherForm(request.POST, instance=teacher)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ Данные преподавателя {teacher.full_name} обновлены!')
            return redirect('teachers:teacher_list')
    else:
        form = TeacherForm(instance=teacher)

    return render(request, 'teachers/teacher_form.html', {
        'form': form,
        'title': 'Редактировать преподавателя',
        'is_edit': True,
        'teacher': teacher
    })

@login_required
@require_http_methods(["POST"])
def teacher_delete(request, pk):
    """Удаление преподавателя через модальное окно"""
    teacher = get_object_or_404(Teacher, pk=pk)
    full_name = f"{teacher.last_name} {teacher.first_name} {teacher.patronymic}".strip()
    teacher.delete()
    messages.success(request, f'🗑️ Преподаватель {full_name} удалён')
    return redirect('/teachers/')


def teacher_search_api(request):
    """API для живого поиска преподавателей с учётом фильтров"""
    query = request.GET.get('q', '').strip()
    item_id = request.GET.get('id', '').strip()

    # Берём активные фильтры
    vehicles = request.GET.getlist('vehicle')
    schedules = request.GET.getlist('schedule')

    teachers = Teacher.objects.all()

    # Применяем фильтры
    if 'truck' in vehicles:
        teachers = teachers.filter(teaches_truck=True)
    if 'car' in vehicles:
        teachers = teachers.filter(teaches_car=True)
    if 'morning' in schedules:
        teachers = teachers.filter(schedule_morning=True)
    if 'evening' in schedules:
        teachers = teachers.filter(schedule_evening=True)
    if 'weekend' in schedules:
        teachers = teachers.filter(schedule_weekend=True)

    # Поиск
    if item_id:
        teachers = teachers.filter(pk=int(item_id))
    elif query:
        teachers = teachers.filter(
            Q(last_name__icontains=query) |
            Q(first_name__icontains=query) |
            Q(patronymic__icontains=query) |
            Q(phone__icontains=query)
        )[:10]

    # Формируем подсказки
    suggestions = []
    for t in teachers:
        full_name = f"{t.last_name} {t.first_name} {t.patronymic}".strip()
        suggestions.append({
            'id': t.pk,
            'suggestion_text': f"👨‍🏫 {full_name} • 📞 {t.phone}"
        })

    # Формируем строки таблицы
    rows = []
    for idx, t in enumerate(teachers, start=1):
        row_html = render_to_string(
            'teachers/_teacher_row.html',
            {'t': t, 'forloop': {'counter': idx}},
            request=request
        )
        rows.append(row_html)

    return JsonResponse({
        'suggestions': suggestions,
        'rows': rows
    })