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


# =============================================================================
# 🔹 Вспомогательные функции
# =============================================================================

def parse_date_safe(value):
    """Безопасно парсит дату из строки 'DD.MM.YYYY' или 'YYYY-MM-DD'."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, '%d.%m.%Y').date()
    except ValueError:
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            return None


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
        # 🔹 Сохранение настроек группы
        if 'save_group' in request.POST:
            group.contract_start = parse_date_safe(request.POST.get('contract_start'))
            group.contract_end = parse_date_safe(request.POST.get('contract_end'))
            group.exam_internal_theory_date = parse_date_safe(request.POST.get('exam_internal_theory_date'))
            group.exam_internal_driving_date = parse_date_safe(request.POST.get('exam_internal_driving_date'))
            group.exam_gai_date = parse_date_safe(request.POST.get('exam_gai_date'))
            group.status = request.POST.get('status', 'active')
            group.schedule_type = request.POST.get('schedule_type', 'directed')
            group.duration = request.POST.get('duration', 'standard')
            group.comments = request.POST.get('comments', '')

            # Аудитория
            cid = request.POST.get('classroom')
            group.classroom = get_object_or_404(Classroom, pk=cid) if cid and cid.isdigit() else None

            # Преподаватель
            tid = request.POST.get('teacher')
            group.teacher = get_object_or_404(Teacher, pk=tid) if tid and tid.isdigit() else None

            group.save()
            messages.success(request, '✅ Данные группы сохранены.')
            return redirect('groups:group_detail', group_id=group.pk)

        # 🔹 Добавление учащегося
        if 'add_student' in request.POST:
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

    return render(request, 'groups/group_detail.html', {
        'group': group,
        'current_students': Student.objects.filter(group=group).order_by('last_name', 'first_name'),
        'available_students': Student.objects.exclude(group=group).order_by('last_name', 'first_name'),
        'classrooms': classrooms,
        'teachers': teachers,
    })


# =============================================================================
# 🔹 Создание / Редактирование группы
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
        # 🔹 Сбор и валидация данных
        group_number = request.POST.get('group_number', '').strip().upper()
        if not group_number:
            messages.error(request, '❌ Номер группы обязателен')
            return redirect('groups:group_form', group_id=group_id) if is_edit else redirect('groups:group_form')

        existing = Group.objects.filter(group_number=group_number)
        if group:
            existing = existing.exclude(pk=group.pk)
        if existing.exists():
            messages.error(request, f'❌ Группа "{group_number}" уже существует')
            return redirect('groups:group_form', group_id=group_id) if is_edit else redirect('groups:group_form')

        # 🔹 Инициализация или обновление объекта
        if not group:
            group = Group(created_at=timezone.now())

        group.group_number = group_number
        group.category_id = int(request.POST['category']) if request.POST.get('category', '').isdigit() else None
        group.classroom_id = int(request.POST['classroom']) if request.POST.get('classroom', '').isdigit() else None
        group.teacher_id = int(request.POST['teacher']) if request.POST.get('teacher', '').isdigit() else None

        # 🔹 Парсинг дат БЕЗОПАСНО (до сохранения)
        group.contract_start = parse_date_safe(request.POST.get('contract_start'))
        group.contract_end = parse_date_safe(request.POST.get('contract_end'))
        group.exam_internal_theory_date = parse_date_safe(request.POST.get('exam_internal_theory_date'))
        group.exam_internal_driving_date = parse_date_safe(request.POST.get('exam_internal_driving_date'))
        group.exam_gai_date = parse_date_safe(request.POST.get('exam_gai_date'))

        group.status = request.POST.get('status', 'active')
        group.schedule_type = request.POST.get('schedule_type', 'directed')
        group.duration = request.POST.get('duration', 'standard')
        group.comments = request.POST.get('comments', '').strip()
        group.updated_at = timezone.now()

        group.save()

        messages.success(request, f'✅ Группа "{group.group_number}" {"обновлена" if is_edit else "создана"}!')
        return redirect('groups:group_detail', group_id=group.pk)

    # 🔹 GET: подготовка контекста
    return render(request, 'groups/group_form.html', {
        'title': '✏️ Редактирование группы' if is_edit else '➕ Создание группы',
        'group': group,
        'categories': GroupCategory.objects.all().order_by('code'),
        'classrooms': Classroom.objects.all().order_by('classroom_number'),
        'teachers': Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name'),
        'is_edit': is_edit,
    })