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
from groups.forms import SchedulePlanForm
from reference.models import GroupCategory, Credit
from students.models import Student
from teachers.models import Teacher
from classrooms.models import Classroom


@login_required
def group_list(request):
    """Список групп с фильтрами и поиском"""
    groups = Group.objects.select_related('category', 'classroom', 'teacher').all()

    # 🔹 Поиск
    search_query = request.GET.get('search', '').strip()
    if search_query:
        groups = groups.filter(
            Q(group_number__icontains=search_query) |
            Q(category__code__icontains=search_query) |
            Q(teacher__last_name__icontains=search_query)
        )

    # 🔹 Фильтры
    if request.GET.get('category'):
        groups = groups.filter(category_id=request.GET.get('category'))
    if request.GET.get('status'):
        groups = groups.filter(status=request.GET.get('status'))

    groups = groups.order_by('group_number')
    categories = GroupCategory.objects.all().order_by('code')

    context = {
        'groups': groups,
        'categories': categories,
        'selected_category': request.GET.get('category'),
        'selected_status': request.GET.get('status'),
        'search_query': search_query,
    }
    return render(request, 'groups/group_list.html', context)


@login_required
def group_detail(request, group_id):
    """Карточка группы: настройки, учащиеся, прогресс"""
    group = get_object_or_404(
        Group.objects.select_related('category', 'classroom', 'teacher'),
        pk=group_id
    )

    classrooms = Classroom.objects.all().order_by('classroom_number')
    teachers = Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name')

    # 🔹 Обработка POST: сохранение настроек группы
    if request.method == 'POST' and 'save_group' in request.POST:
        group.contract_start = request.POST.get('contract_start') or None
        group.contract_end = request.POST.get('contract_end') or None
        group.exam_internal_theory_date = request.POST.get('exam_internal_theory_date') or None
        group.exam_internal_driving_date = request.POST.get('exam_internal_driving_date') or None
        group.exam_gai_date = request.POST.get('exam_gai_date') or None
        group.status = request.POST.get('status', 'active')
        group.comments = request.POST.get('comments', '')

        # Аудитория
        classroom_id = request.POST.get('classroom')
        if classroom_id and classroom_id.isdigit():
            group.classroom = get_object_or_404(Classroom, pk=classroom_id)
        elif classroom_id == '':
            group.classroom = None

        # Преподаватель
        teacher_id = request.POST.get('teacher')
        if teacher_id and teacher_id.isdigit():
            group.teacher = get_object_or_404(Teacher, pk=teacher_id)
        elif teacher_id == '':
            group.teacher = None

        group.save()
        messages.success(request, '✅ Данные группы сохранены.')
        return redirect('groups:group_detail', group_id=group.pk)

    # 🔹 Добавление учащегося в группу
    if request.method == 'POST' and 'add_student' in request.POST:
        student_id = request.POST.get('student_id')
        if student_id:
            student = get_object_or_404(Student, pk=student_id)
            if student.group == group:
                messages.warning(request, 'Учащийся уже в группе.')
            else:
                # 🔹 Лог перевода
                old_group = student.group
                transfer_date = timezone.now().date()
                transfer_log = {
                    'type': 'transfer',
                    'date': transfer_date.strftime('%Y-%m-%d'),
                    'title': f"Перевод в группу {group.group_number}",
                    'details': {
                        'from_group': str(old_group) if old_group else '—',
                        'to_group': str(group.group_number),
                    }
                }
                current_log = student.activity_log or []
                current_log.append(transfer_log)
                current_log.sort(key=lambda x: x.get('date', ''))

                student.activity_log = current_log
                student.transferred_date = transfer_date
                student.group = group
                student.save(update_fields=['group', 'transferred_date', 'activity_log', 'updated_at'])

                messages.success(request, f'✅ {student.last_name} добавлен в группу.')
        return redirect('groups:group_detail', group_id=group.pk)

    # 🔹 Подготовка данных для шаблона
    current_students = Student.objects.filter(group=group).order_by('last_name', 'first_name')
    available_students = Student.objects.exclude(group=group).order_by('last_name', 'first_name')

    context = {
        'group': group,
        'current_students': current_students,
        'available_students': available_students,
        'classrooms': classrooms,
        'teachers': teachers,
    }
    return render(request, 'groups/group_detail.html', context)