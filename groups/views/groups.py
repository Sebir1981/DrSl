# groups/views/groups.py

import re
from collections import defaultdict
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from groups.models import Group, CreditResult
from groups.forms import SchedulePlanForm, GroupForm
from reference.models import GroupCategory, Credit
from students.models import Student
from teachers.models import Teacher
from classrooms.models import Classroom


# =============================================================================
# 🔹 Список групп
# =============================================================================
@login_required
def group_list(request):
    """Список групп с фильтрами и поиском"""
    groups = Group.objects.select_related('category', 'classroom', 'teacher').all()

    search_query = request.GET.get('search', '').strip()
    if search_query:
        groups = groups.filter(
            Q(group_number__icontains=search_query) |
            Q(category__code__icontains=search_query) |
            Q(teacher__last_name__icontains=search_query)
        )

    if request.GET.get('category'):
        groups = groups.filter(category_id=request.GET.get('category'))
    if request.GET.get('status'):
        groups = groups.filter(status=request.GET.get('status'))

    groups = groups.order_by('group_number')
    categories = GroupCategory.objects.all().order_by('code')

    return render(request, 'groups/group_list.html', {
        'groups': groups,
        'categories': categories,
        'selected_category': request.GET.get('category'),
        'selected_status': request.GET.get('status'),
        'search_query': search_query,
    })


# =============================================================================
# 🔹 Карточка группы
# =============================================================================
@login_required
def group_detail(request, group_id):
    """Карточка группы: настройки, учащиеся, прогресс"""
    group = get_object_or_404(
        Group.objects.select_related('category', 'classroom', 'teacher'),
        pk=group_id
    )

    classrooms = Classroom.objects.all().order_by('classroom_number')
    teachers = Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name')

    if request.method == 'POST':
        # 🔹 Определяем, какая форма была отправлена
        action = request.POST.get('action')

        # 🔹 Сохранение настроек группы
        if action == 'save_group' or 'save_group' in request.POST:
            form = GroupForm(request.POST, instance=group)
            if form.is_valid():
                form.save()
                messages.success(request, '✅ Данные группы сохранены.')
                return redirect('groups:group_detail', group_id=group.pk)
            else:
                for field, errors in form.errors.items():
                    messages.error(request, f"⚠️ Ошибка в поле '{field}': {', '.join(errors)}")

        # 🔹 Массовое добавление выбранных учащихся
        elif action == 'add_selected_students':
            student_ids = request.POST.getlist('selected_students')
            if student_ids:
                count = 0
                for sid in student_ids:
                    try:
                        student = Student.objects.get(pk=sid)
                        if student.group != group:
                            transfer_log = {
                                'type': 'transfer',
                                'date': timezone.now().date().strftime('%Y-%m-%d'),
                                'title': f"Перевод в группу {group.group_number}",
                                'details': {
                                    'from_group': str(student.group) if student.group else '—',
                                    'to_group': str(group.group_number),
                                }
                            }
                            current_log = student.activity_log or []
                            current_log.append(transfer_log)
                            current_log.sort(key=lambda x: x.get('date', ''))

                            student.activity_log = current_log
                            student.transferred_date = timezone.now().date()
                            student.group = group
                            student.save(update_fields=['group', 'transferred_date', 'activity_log', 'updated_at'])
                            count += 1
                    except Student.DoesNotExist:
                        pass
                messages.success(request, f'✅ {count} учащихся добавлены в группу.')
            else:
                messages.warning(request, '⚠️ Не выбрано ни одного учащегося.')
            return redirect('groups:group_detail', group_id=group.pk)

        # 🔹 (Оставляем на случай, если кто-то использует старый путь)
        elif 'add_student' in request.POST:
            student_id = request.POST.get('student_id')
            if student_id:
                student = get_object_or_404(Student, pk=student_id)
                if student.group == group:
                    messages.warning(request, 'Учащийся уже в группе.')
                else:
                    transfer_log = {
                        'type': 'transfer',
                        'date': timezone.now().date().strftime('%Y-%m-%d'),
                        'title': f"Перевод в группу {group.group_number}",
                        'details': {
                            'from_group': str(student.group) if student.group else '—',
                            'to_group': str(group.group_number),
                        }
                    }
                    current_log = student.activity_log or []
                    current_log.append(transfer_log)
                    current_log.sort(key=lambda x: x.get('date', ''))

                    student.activity_log = current_log
                    student.transferred_date = timezone.now().date()
                    student.group = group
                    student.save(update_fields=['group', 'transferred_date', 'activity_log', 'updated_at'])
                    messages.success(request, f'✅ {student.last_name} добавлен в группу.')
            return redirect('groups:group_detail', group_id=group.pk)

    else:
        form = GroupForm(instance=group)

    return render(request, 'groups/group_detail.html', {
        'group': group,
        'form': form,
        'current_students': Student.objects.filter(group=group).order_by('last_name', 'first_name'),
        'available_students': Student.objects.exclude(group=group).order_by('last_name', 'first_name'),
        'unassigned_students': Student.objects.filter(group__isnull=True).order_by('last_name', 'first_name'),
        'classrooms': classrooms,
        'teachers': teachers,
    })


# =============================================================================
# 🔹 Создание / Редактирование группы (ИСПРАВЛЕНА НА ФОРМУ)
# =============================================================================
@login_required
def group_form(request, group_id=None):
    """Фронтенд-страница создания/редактирования группы"""
    group = None
    is_edit = False

    if group_id:
        group = get_object_or_404(Group, pk=group_id)
        is_edit = True

    if request.method == 'POST':
        form = GroupForm(request.POST, instance=group)

        # ВАЖНО: Дополнительная валидация уникальности номера группы
        if form.is_valid():
            # Проверяем, есть ли уже группа с таким номером (исключая текущую)
            group_number = form.cleaned_data['group_number']
            existing = Group.objects.filter(group_number=group_number)
            if group:
                existing = existing.exclude(pk=group.pk)

            if existing.exists():
                messages.error(request, f'❌ Группа "{group_number}" уже существует')
                return redirect('groups:group_form', group_id=group_id) if is_edit else redirect('groups:group_form')

            form.save()
            messages.success(request, f'✅ Группа "{form.instance.group_number}" {"обновлена" if is_edit else "создана"}!')
            return redirect('groups:group_detail', group_id=form.instance.pk)
        else:
            for field, errors in form.errors.items():
                messages.error(request, f"⚠️ Ошибка в поле '{field}': {', '.join(errors)}")

    else:
        form = GroupForm(instance=group)

    return render(request, 'groups/group_form.html', {
        'title': '✏️ Редактирование группы' if is_edit else '➕ Создание группы',
        'form': form,  # <--- Передаём форму в шаблон
        'categories': GroupCategory.objects.all().order_by('code'),
        'classrooms': Classroom.objects.all().order_by('classroom_number'),
        'teachers': Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name'),
        'is_edit': is_edit,
    })