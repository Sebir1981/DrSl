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
                added_count = 0
                skipped_count = 0

                for sid in student_ids:
                    try:
                        student = Student.objects.get(pk=sid)
                        if student.group == group:
                            skipped_count += 1
                            continue

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
                        added_count += 1
                    except Student.DoesNotExist:
                        pass

                if added_count > 0:
                    messages.success(request, f'✅ {added_count} учащихся добавлены в группу.')
                if skipped_count > 0:
                    messages.warning(request, f'⚠️ {skipped_count} учащихся уже были в группе и пропущены.')
                if added_count == 0 and skipped_count == 0:
                    messages.warning(request, '️ Не удалось добавить ни одного учащегося.')
            else:
                messages.warning(request, '⚠️ Не выбрано ни одного учащегося.')

            return redirect('groups:group_detail', group_id=group.pk)

        # 🔹 Старый путь добавления одного учащегося (оставляем для совместимости)
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
# 🔹 Создание / Редактирование группы
# =============================================================================
@login_required
def group_form(request, group_id=None):
    """Фронтенд-страница создания/редактирования группы.

    Валидация уникальности номера группы выполняется внутри формы
    (метод clean_group_number в GroupForm), поэтому здесь дублировать её не нужно.
    """
    group = None
    is_edit = False

    if group_id:
        group = get_object_or_404(Group, pk=group_id)
        is_edit = True

    if request.method == 'POST':
        form = GroupForm(request.POST, instance=group)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'✅ Группа "{form.instance.group_number}" {"обновлена" if is_edit else "создана"}!'
            )
            return redirect('groups:group_detail', group_id=form.instance.pk)
        else:
            # Форма сама добавит ошибки валидации (включая уникальность номера)
            for field, errors in form.errors.items():
                field_label = field.replace('_', ' ').title()
                messages.error(request, f"⚠️ {field_label}: {', '.join(errors)}")
    else:
        form = GroupForm(instance=group)

    return render(request, 'groups/group_form.html', {
        'title': '✏️ Редактирование группы' if is_edit else '➕ Создание группы',
        'form': form,
        'categories': GroupCategory.objects.all().order_by('code'),
        'classrooms': Classroom.objects.all().order_by('classroom_number'),
        'teachers': Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name'),
        'is_edit': is_edit,
    })


# =============================================================================
# 🔹 Удаление групп (массовое)
# =============================================================================
@login_required
def delete_groups(request):
    """Удаление выбранных групп"""
    if request.method == 'POST':
        group_ids = request.POST.getlist('group_ids')

        if not group_ids:
            messages.warning(request, '️ Не выбрано ни одной группы для удаления.')
            return redirect('groups:group_list')

        deleted_count = 0
        for group_id in group_ids:
            try:
                group = Group.objects.get(pk=group_id)
                group.delete()
                deleted_count += 1
            except Group.DoesNotExist:
                pass

        messages.success(request, f'✅ Удалено групп: {deleted_count}')
        return redirect('groups:group_list')

    return redirect('groups:group_list')