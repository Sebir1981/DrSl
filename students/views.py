# students/views.py
import json
import random
import re
from datetime import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.template.loader import render_to_string
from django.conf import settings

from .forms import DismissalForm, RefusalForm, SuspensionForm, ContractExtensionForm, StudentPublicAddForm
from teachers.models import Teacher
from masters.models import Master
from .services import StudentStatusService
from .models import Student
from collections import defaultdict
from groups.models import Group, SchedulePlan
from master_plan.models import MasterPlanGroup, StudentReassignmentLog
from cars.models import Car

# =============================================================================
# 🔹 КОНСТАНТЫ
# =============================================================================
REDIRECT_STUDENT_DETAIL = 'students:student_detail'
TODAY = timezone.now().date()
TEMPLATE_TRANSFER_STUDENT = 'students/transfer_student.html'


# =============================================================================
# 🔹 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================
def _parse_date_from_request(request, field_name, default_date=None):
    """Парсит дату из POST-запроса в формате дд.мм.гггг. Возвращает объект date."""
    raw = request.POST.get(field_name, '').strip()
    if not raw:
        return default_date
    try:
        import datetime
        day, month, year = map(int, raw.split('.'))
        return datetime.date(year, month, day)
    except (ValueError, AttributeError):
        return default_date


def _parse_int_or_none(request, field_name):
    """Парсит ID из запроса, возвращает int или None"""
    val = request.POST.get(field_name, '').strip()
    if val and val.isdigit():
        return int(val)
    return None


def _format_date_for_display(date_str):
    """Возвращает дату в формате дд.мм.гггг."""
    if len(date_str) == 10 and date_str[4] == '-':
        parts = date_str.split('-')
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return date_str


def _prepare_credits_data(activity_log):
    """Генерирует данные по зачетам для отображения."""
    credits_data = []
    for num in range(1, 7):
        attempts = []
        for entry in activity_log:
            if entry.get('type') == 'credit_result':
                details = entry.get('details') or {}
                date_str = entry.get('date', '')
                display_date = _format_date_for_display(date_str)

                attempts.append({
                    'date': display_date,
                    'icon': details.get('result_icon', '—'),
                    'status': details.get('result', ''),
                    'attempt_num': details.get('attempt_number', 0),
                    'type': details.get('attempt_type', '')
                })
        attempts.sort(key=lambda x: x['attempt_num'])

        if attempts:
            last = attempts[-1]
            display_icon = last['icon']
            display_status = last['status']
        else:
            display_icon = '—'
            display_status = 'none'

        credits_data.append({
            'num': num,
            'attempts': attempts,
            'display_icon': display_icon,
            'display_status': display_status
        })
    return credits_data


def _prepare_change_history(activity_log, author_name):
    """Генерирует историю изменений для выпадающего меню."""
    change_history = []
    for entry in reversed(activity_log):
        etype = entry.get('type')
        details = entry.get('details') or {}

        if etype == 'transfer':
            change_history.append({
                'date': entry.get('date'),
                'field': 'Группа',
                'old': details.get('from_group', '—'),
                'new': details.get('to_group', '—'),
                'author': author_name
            })
        elif etype == 'teacher_change':
            change_history.append({
                'date': entry.get('date'),
                'field': 'Преподаватель',
                'old': details.get('from', '—'),
                'new': details.get('to', '—'),
                'author': author_name
            })
    return change_history


def _resolve_master_id(master_val):
    """
    Преобразует значение из услуги 'Мастер по вождению' в ID мастера.
    Поддерживает:
      - int / строка из цифр → ID
      - ФИО ('Иванов И.И.' / 'Иванов') → поиск по last_name
    """
    if not master_val:
        return None

    s = str(master_val).strip()
    if s.isdigit():
        if Master.objects.filter(pk=int(s)).exists():
            return int(s)
        return None

    last_name = s.split()[0] if s.split() else s
    m = Master.objects.filter(last_name__iexact=last_name).first()
    if m:
        return m.id
    m = Master.objects.filter(last_name__icontains=last_name).first()
    if m:
        return m.id
    return None


def _extract_master_id_from_values(values):
    """Извлекает ID мастера из values платной услуги."""
    if not values:
        return None

    candidate = None
    for key in ('master', 'master_id', 'master-id'):
        if key in values and values[key]:
            candidate = values[key]
            break

    if candidate is None:
        for key, val in values.items():
            if isinstance(key, str) and key.startswith('select-master-') and val:
                candidate = val
                break

    if candidate is None:
        for key, val in values.items():
            if isinstance(key, str) and 'master' in key.lower() and val:
                candidate = val
                break

    if candidate is None:
        return None

    return _resolve_master_id(candidate)


def _extract_car_brand_from_values(values):
    """Извлекает марку автомобиля из values платной услуги."""
    if not values:
        return None

    for key in ('car_brand', 'brand', 'car-brand'):
        if key in values and values[key]:
            return values[key]

    for key, val in values.items():
        if not isinstance(key, str) or not val:
            continue
        low = key.lower()
        if low.startswith('select-brand-') or low.startswith('select-car-'):
            return val

    for key, val in values.items():
        if not isinstance(key, str) or not val:
            continue
        low = key.lower()
        if 'brand' in low or 'car' in low or 'марк' in low:
            return val

    return None

def _extract_gender_from_values(values):
    """Извлекает пол мастера из values платной услуги."""
    if not values:
        return None

    for key in ('gender', 'master_gender', 'sex'):
        if key in values and values[key]:
            val = str(values[key]).lower()
            if val in ('male', 'female'):
                return val

    for key, val in values.items():
        if not isinstance(key, str) or not val:
            continue
        low = key.lower()
        if 'gender' in low or 'sex' in low:
            v = str(val).lower()
            if v in ('male', 'female'):
                return v

    return None

def _validate_master_brand_compatibility(master_id, car_brand):
    """
    Проверяет, что у мастера есть машина с указанной маркой.
    У MasterPouts ОДНА машина (FK `car`), не M2M.
    """
    if not master_id or not car_brand:
        return True, None

    master = Master.objects.filter(pk=int(master_id)).first()
    if not master:
        return True, None

    # У мастера нет машины
    if not master.car:
        return False, (
            f'Мастер {master.last_name} {master.first_name} '
            f'не имеет закреплённого автомобиля. '
            f'Назначьте машину или выберите другого мастера.'
        )

    master_make = (master.car.make or '').strip().lower()
    if master_make != car_brand.strip().lower():
        return False, (
            f'Мастер {master.last_name} закреплён за маркой '
            f'«{master.car.make}», а услуга требует «{car_brand}». '
            f'Выберите другого мастера или измените марку.'
        )

    return True, None


# =============================================================================
# ✅ 0. Создание карточки учащегося
# =============================================================================
@login_required
@require_http_methods(["GET", "POST"])
def student_add(request):
    if request.method == 'POST':
        form = StudentPublicAddForm(request.POST)
        if form.is_valid():
            student = form.save()

            if student.group and student.group.teacher and not student.teacher_id:
                student.teacher = student.group.teacher
                student.save()

            service = StudentStatusService(student)
            service.add_event(
                event_type='enrollment',
                created_by=request.user,
                event_date=student.enrolled_date if student.enrolled_date else TODAY,
                details={}
            )

            messages.success(request, f'✅ Учащийся {student.last_name} {student.first_name} добавлен!')
            return redirect(REDIRECT_STUDENT_DETAIL, student_id=student.pk)
        else:
            for field, errors in form.errors.items():
                messages.error(request, f"⚠️ Ошибка в поле '{field}': {', '.join(errors)}")
    else:
        form = StudentPublicAddForm()

    groups = Group.objects.filter(status='active').order_by('group_number')
    teachers = Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name')
    masters = Master.objects.all().order_by('last_name', 'first_name')

    context = {
        'title': '➕ Добавить учащегося',
        'form': form,
        'groups': groups,
        'teachers': teachers,
        'masters': masters,
        'today': TODAY,
    }
    return render(request, 'students/student_add.html', context)


# =============================================================================
# ✅ 1. Панель управления разделом "Учащиеся"
# =============================================================================
@login_required
@require_http_methods(["GET"])
def students_dashboard(request):
    context = {'total_students': Student.objects.count()}
    return render(request, 'students/dashboard.html', context)


# =============================================================================
# ✅ 2. Список учащихся с фильтрами и поиском
# =============================================================================
@login_required
@require_http_methods(["GET"])
def student_list(request):
    students = Student.objects.select_related('group', 'teacher', 'master').all()

    highlight_mode = request.GET.get('highlight')
    search_query = request.GET.get('search', '').strip()
    if search_query:
        students = students.filter(
            Q(last_name__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(patronymic__icontains=search_query)
        )

    group_filter = request.GET.get('group', '').strip()
    if group_filter:
        if group_filter.isdigit():
            students = students.filter(
                Q(group__group_number=group_filter) | Q(group_id=group_filter)
            )
        else:
            students = students.filter(group__group_number__icontains=group_filter)

    teacher_filter = request.GET.get('teacher')
    if teacher_filter:
        students = students.filter(
            Q(teacher__last_name__icontains=teacher_filter) |
            Q(teacher__first_name__icontains=teacher_filter)
        )

    students = students.order_by('last_name', 'first_name')

    groups = Group.objects.filter(status='active').order_by('group_number')
    teachers = Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name')

    students_data = []
    for s in students:
        service = StudentStatusService(s)
        status_data = service.get_current_status()

        teacher_name = '—'
        if s.teacher:
            teacher_name = f"{s.teacher.last_name} {s.teacher.first_name[:1]}."
            if s.teacher.patronymic:
                teacher_name += f"{s.teacher.patronymic[:1]}."

        students_data.append({
            'student': s,
            'status': status_data['status'],
            'status_color': status_data['color'],
            'teacher_name': teacher_name,
        })

    context = {
        'students': students_data,
        'groups': groups,
        'teachers': teachers,
        'selected_group': group_filter,
        'selected_teacher': teacher_filter,
        'search_query': search_query,
        'highlight_mode': highlight_mode,
        'debug': True,
    }
    return render(request, 'students/student_list.html', context)


# =============================================================================
# ✅ 3. Карточка учащегося (с Историей)
# =============================================================================
@login_required
@require_http_methods(["GET"])
def student_detail(request, student_id):
    student = get_object_or_404(
        Student.objects.select_related('group', 'group__category', 'teacher', 'master'),
        pk=student_id
    )

    activity_log = student.activity_log or []
    credits_data = _prepare_credits_data(activity_log)

    last_transfer = None
    for entry in reversed(activity_log):
        if entry.get('type') == 'transfer':
            last_transfer = entry
            break

    author_name = request.user.get_full_name() or request.user.username
    change_history = _prepare_change_history(activity_log, author_name)

    # 🔹 Получаем результаты зачётов и экзаменов
    from groups.models import CreditResult
    from reference.models import PaidService

    def parse_comment(comment):
        if not comment:
            return {'attempt_num': 1, 'attempt_type': 'free'}
        match = re.search(r'Попытка №(\d+)', comment)
        attempt_num = int(match.group(1)) if match else 1
        attempt_type = 'paid' if 'Тип: paid' in comment else 'free'
        return {'attempt_num': attempt_num, 'attempt_type': attempt_type}

    # 1. Все ЗАЧЁТЫ студента (строго credit_type='credit')
    credit_results = CreditResult.objects.filter(
        student=student,
        credit__credit_type='credit'
    ).select_related('credit').order_by('credit__number', '-credit_date')

    credits_by_number = defaultdict(list)
    for cr in credit_results:
        parsed = parse_comment(cr.comment)
        credits_by_number[cr.credit.number].append({
            'credit_date': cr.credit_date,
            'status': cr.status,
            'attempt_type': 'Платная' if parsed['attempt_type'] == 'paid' else 'Бесплатная',
            'attempt_num': parsed['attempt_num'],
        })

    # 2. Все ЭКЗАМЕНЫ студента (строго credit_type='exam')
    exam_results_qs = CreditResult.objects.filter(
        student=student,
        credit__credit_type='exam'
    ).select_related('credit').order_by('credit__number', '-credit_date')

    theory_exams = []
    driving_exams = []

    for er in exam_results_qs:
        parsed = parse_comment(er.comment)
        exam_data = {
            'exam_date': er.credit_date,
            'status': er.status,
            'attempt_type': 'paid' if parsed['attempt_type'] == 'paid' else 'free',
        }

        topic_lower = er.credit.topic.lower() if er.credit.topic else ''
        if er.credit.number == 1 or 'теоретич' in topic_lower or 'пдд' in topic_lower:
            theory_exams.append(exam_data)
        elif er.credit.number == 2 or 'практич' in topic_lower or 'вожден' in topic_lower:
            driving_exams.append(exam_data)
        else:
            theory_exams.append(exam_data)

    # 🔹 Платные услуги — собираем состояние (включено + значения)
    all_services = PaidService.objects.all()
    student_services = {}  # service_id -> True (включено)
    student_service_values = {}  # service_id -> {field_type: value}

    if student.activity_log:
        for entry in student.activity_log:
            if entry.get('type') == 'service_added':
                details = entry.get('details', {})
                service_id = details.get('service_id')
                if not service_id:
                    continue

                # Флаг: услуга была включена
                student_services[service_id] = True

                # Значения: словарь вида {'master': '6'} или {'car_brand': 'Hyundai'}
                values = details.get('values', {})
                if values:
                    # Объединяем: если несколько записей по одной услуге — берём последнюю
                    student_service_values.setdefault(service_id, {}).update(values)

    car_brands = Car.objects.values_list('make', flat=True).distinct().order_by('make')
    today = timezone.now().date()

    # 🔹 1. Расчёт часов ТЕОРИИ
    theory_total = 0.0
    theory_distributed = 0.0

    if student.group:
        schedule_plan = SchedulePlan.objects.filter(group=student.group).order_by('-created_at').first()
        if schedule_plan:
            theory_total = float(schedule_plan.required_hours or 0)
            if schedule_plan.class_days:
                class_days = schedule_plan.class_days
                if isinstance(class_days, str):
                    try:
                        class_days = json.loads(class_days)
                    except json.JSONDecodeError:
                        class_days = {}

                if isinstance(class_days, dict):
                    excluded_dates = set(schedule_plan.excluded_dates or [])
                    additional_dates = set(schedule_plan.additional_dates or [])

                    for date_str, day_data in class_days.items():
                        if date_str.startswith('_') or not isinstance(day_data, dict):
                            continue
                        if date_str in excluded_dates:
                            continue

                        is_scheduled = day_data.get('scheduled', None)
                        if is_scheduled is False:
                            continue

                        if is_scheduled is None:
                            try:
                                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                                weekday = date_obj.weekday()
                                schedule_type = schedule_plan.schedule_type
                                should_be_scheduled = False

                                if schedule_type == 'even' and date_obj.day % 2 == 0 and weekday < 5:
                                    should_be_scheduled = True
                                elif schedule_type == 'odd' and date_obj.day % 2 == 1 and weekday < 5:
                                    should_be_scheduled = True
                                elif schedule_type == 'weekend' and weekday >= 5:
                                    should_be_scheduled = True
                                elif schedule_type == 'everyday':
                                    should_be_scheduled = True

                                if not should_be_scheduled and date_str not in additional_dates:
                                    continue
                            except (ValueError, TypeError):
                                pass

                        try:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                            if date_obj <= today:
                                day_hours = 0.0
                                for k, v in day_data.items():
                                    if k.startswith('_') or k.endswith('_topics'):
                                        continue
                                    if k in ['scheduled', 'manuallyRemoved', 'is_med', 'med', 'med_hours',
                                             'location', 'time_start', 'time_end', 'category']:
                                        continue
                                    if isinstance(v, (int, float)):
                                        day_hours += float(v)
                                    elif isinstance(v, str):
                                        try:
                                            day_hours += float(v)
                                        except (ValueError, TypeError):
                                            pass
                                if day_hours > 0:
                                    theory_distributed += day_hours
                        except (ValueError, TypeError):
                            continue

    theory_distributed = min(theory_distributed, theory_total)
    theory_remaining = max(0.0, theory_total - theory_distributed)
    theory_percent = f"{(theory_distributed / theory_total * 100):.1f}" if theory_total > 0 else "0.0"

    # 🔹 2. Расчёт часов ПРАКТИКИ
    practice_total = 0.0
    practice_driven = 0.0

    if student.group:
        master_plan = MasterPlanGroup.objects.filter(group=student.group, is_archived=False).first()
        if master_plan:
            practice_total = float(master_plan.hours_per_student)
            practice_driven = min(random.randint(0, 50), practice_total)

    practice_remaining = max(0.0, practice_total - practice_driven)
    practice_percent = f"{(practice_driven / practice_total * 100):.1f}" if practice_total > 0 else "0.0"

    # 🔹 3. Формирование ОБЩЕЙ ИСТОРИИ (Таймлайн)
    history_timeline = []
    EVENT_ICONS = {
        'enrollment': '🎓', 'transfer': '🔄', 'credit_result': '📝',
        'service_added': '💰', 'service_removed': '❌', 'refusal': '🚫',
        'dismissal': '🚪', 'suspension': '⏸️', 'contract_extension': '📄',
        'teacher_change': '👨‍🏫', 'activated': '✅',
    }
    EVENT_TITLES = {
        'enrollment': 'Зачисление', 'transfer': 'Перевод в группу',
        'credit_result': 'Результат зачёта', 'service_added': 'Добавлена услуга',
        'service_removed': 'Удалена услуга', 'refusal': 'Отказ от обучения',
        'dismissal': 'Отчисление', 'suspension': 'Приостановка',
        'contract_extension': 'Продление договора', 'teacher_change': 'Смена преподавателя',
        'activated': 'Активация',
    }

    for entry in activity_log:
        entry_type = entry.get('type', 'other')
        entry_date = entry.get('date', '')
        details = entry.get('details', {})

        display_date = entry_date
        if entry_date and len(entry_date) == 10 and entry_date[4] == '-':
            parts = entry_date.split('-')
            display_date = f"{parts[2]}.{parts[1]}.{parts[0]}"

        description = entry.get('title', EVENT_TITLES.get(entry_type, entry_type))
        extra_info = ''
        if entry_type == 'transfer':
            extra_info = f"{details.get('from_group', '—')} → {details.get('to_group', '—')}"
        elif entry_type == 'credit_result':
            extra_info = f"Попытка №{details.get('attempt_number', 0)} {details.get('result_icon', '')}"
        elif entry_type == 'dismissal':
            extra_info = f"Приказ №{details.get('order_number', '—')}"
        elif entry_type == 'refusal':
            from_group = details.get('from_group', '')
            if from_group:
                extra_info = f"из группы {from_group}"

        history_timeline.append({
            'date': display_date,
            'date_raw': entry_date,
            'type': entry_type,
            'icon': EVENT_ICONS.get(entry_type, '📌'),
            'title': description,
            'extra': extra_info,
        })

    history_timeline.sort(key=lambda x: x['date_raw'], reverse=True)

    reassignment_history = (
        StudentReassignmentLog.objects
        .filter(student=student)
        .select_related('from_master', 'to_master', 'created_by', 'plan_group__group')
        .order_by('-created_at')
    )

    context = {
        'student': student,
        'activity_log': activity_log,
        'credits_data': credits_data,
        'last_transfer': last_transfer,
        'change_history': change_history,
        'title': f'🎓 {student.full_name}',
        'credits_by_number': credits_by_number,
        'theory_exams': theory_exams,
        'driving_exams': driving_exams,
        'all_services': all_services,
        'student_services': student_services,
        'masters': Master.objects.all().order_by('last_name', 'first_name'),
        'teachers': Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name'),
        'car_brands': car_brands,
        'theory_total': round(theory_total, 1),
        'theory_distributed': round(theory_distributed, 1),
        'theory_remaining': round(theory_remaining, 1),
        'theory_percent': theory_percent,
        'practice_total': round(practice_total, 1),
        'practice_driven': round(practice_driven, 1),
        'practice_remaining': round(practice_remaining, 1),
        'practice_percent': practice_percent,
        'history_timeline': history_timeline,
        'reassignment_history': reassignment_history,
        'student_service_values': student_service_values,
    }
    return render(request, 'students/student_detail.html', context)


# =============================================================================
# ✅ 4. Перевод в другую группу
# =============================================================================
@login_required
@require_http_methods(["GET", "POST"])
def transfer_student(request, student_id):
    student = get_object_or_404(Student.objects.select_related('group'), pk=student_id)
    groups = Group.objects.filter(status='active').order_by('group_number')

    if request.method == 'POST':
        target_group_id = request.POST.get('target_group')
        if not target_group_id:
            messages.error(request, 'Выберите группу для перевода.')
            return render(request, TEMPLATE_TRANSFER_STUDENT, {'student': student, 'groups': groups})

        target_group = get_object_or_404(Group, pk=target_group_id, status='active')

        if target_group == student.group:
            messages.warning(request, 'Учащийся уже находится в этой группе.')
            return render(request, TEMPLATE_TRANSFER_STUDENT, {'student': student, 'groups': groups})

        old_group_number = student.group.group_number if student.group else '—'

        service = StudentStatusService(student)
        service.add_event(
            event_type='transfer',
            created_by=request.user,
            event_date=TODAY,
            details={
                'from_group': old_group_number,
                'to_group_id': target_group.id,
                'to_group': target_group.group_number
            }
        )

        student.group = target_group
        if target_group.teacher:
            student.teacher = target_group.teacher
        student.save()

        messages.success(request, f'✅ Учащийся успешно переведён в группу {target_group.group_number}.')
        return redirect(REDIRECT_STUDENT_DETAIL, student_id=student.pk)

    return render(request, TEMPLATE_TRANSFER_STUDENT, {
        'student': student,
        'groups': groups,
        'today': TODAY
    })


# =============================================================================
# ✅ 5. Отказ от обучения (с исключением из группы)
# =============================================================================
@login_required
@require_http_methods(["GET", "POST"])
def student_refusal(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    if request.method == 'POST':
        form = RefusalForm(request.POST)

        if form.is_valid():
            comment = form.cleaned_data.get('comment', '')
            parsed_date = _parse_date_from_request(request, 'refusal_date') or TODAY

            old_group = student.group.group_number if student.group else '—'

            service = StudentStatusService(student)
            service.add_event(
                event_type='refusal',
                created_by=request.user,
                event_date=parsed_date,
                details={
                    'comment': comment,
                    'from_group': old_group
                },
                comment=comment
            )

            student.group = None
            student.save(update_fields=['group'])

            messages.success(request,
                             f"✅ Зафиксирован отказ: {student.last_name} {student.first_name}. Исключён из группы {old_group}.")
            return redirect(REDIRECT_STUDENT_DETAIL, student_id=student.id)
        else:
            for field, errors in form.errors.items():
                messages.error(request, f"⚠️ Ошибка в поле '{field}': {', '.join(errors)}")
                break
    else:
        form = RefusalForm()

    return render(request, 'students/student_refusal.html', {
        'student': student,
        'form': form,
        'title': 'Отказ от обучения'
    })


# =============================================================================
# ✅ 6. Приостановка обучения
# =============================================================================
@login_required
@require_http_methods(["GET", "POST"])
def student_suspension(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    if request.method == 'POST':
        form = SuspensionForm(request.POST)
        if form.is_valid():
            suspension_start = form.cleaned_data.get('suspension_start')
            suspension_end = form.cleaned_data.get('suspension_end')
            comment = form.cleaned_data.get('comment', '')

            details = {'comment': comment}
            if suspension_end:
                details['end_date'] = suspension_end.strftime('%d.%m.%Y')

            service = StudentStatusService(student)
            service.add_event(
                event_type='suspension',
                created_by=request.user,
                event_date=suspension_start,
                details=details,
                comment=comment
            )

            messages.success(request, f"✅ Обучение приостановлено: {student.last_name} {student.first_name}")
            return redirect(REDIRECT_STUDENT_DETAIL, student_id=student.id)
    else:
        form = SuspensionForm()

    return render(request, 'students/student_suspension.html', {
        'student': student,
        'form': form,
        'title': 'Приостановка обучения'
    })


# =============================================================================
# ✅ 7. Отчисление учащегося (с исключением из группы)
# =============================================================================
@login_required
@require_http_methods(["GET", "POST"])
def student_dismissal(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    if request.method == 'POST':
        form = DismissalForm(request.POST)

        if form.is_valid():
            order_number = form.cleaned_data.get('order_number')
            comment = form.cleaned_data.get('comment', '')
            parsed_date = _parse_date_from_request(request, 'event_date') or TODAY

            old_group = student.group.group_number if student.group else '—'

            service = StudentStatusService(student)
            service.add_event(
                event_type='dismissal',
                created_by=request.user,
                event_date=parsed_date,
                details={
                    'order_number': order_number if order_number else '—',
                    'comment': comment,
                    'from_group': old_group
                },
                comment=comment
            )

            student.group = None
            student.save(update_fields=['group'])

            messages.success(
                request,
                f"✅ {student.last_name} {student.first_name} отчислен. Приказ №{order_number if order_number else '—'}. Исключён из группы {old_group}."
            )
            return redirect(REDIRECT_STUDENT_DETAIL, student_id=student.id)
        else:
            for field, errors in form.errors.items():
                messages.error(request, f"⚠️ Ошибка в поле '{field}': {', '.join(errors)}")
                break
    else:
        form = DismissalForm()

    return render(request, 'students/student_dismissal.html', {
        'student': student,
        'form': form,
        'title': 'Отчисление учащегося'
    })


# =============================================================================
# ✅ 8. Продление договора
# =============================================================================
@login_required
@require_POST
def contract_extension(request, student_id):
    student = get_object_or_404(Student.objects.select_related('group'), pk=student_id)

    if request.method == 'POST':
        form = ContractExtensionForm(request.POST)

        if form.is_valid():
            new_contract_number = form.cleaned_data['new_contract_number']
            new_start_date = form.cleaned_data['new_start_date']
            new_end_date = form.cleaned_data['new_end_date']
            is_paid = form.cleaned_data['is_paid'] == 'paid'
            comment = form.cleaned_data['comment']

            service = StudentStatusService(student)
            service.add_event(
                event_type='contract_extension',
                created_by=request.user,
                event_date=new_start_date,
                details={
                    'new_contract_number': new_contract_number,
                    'new_start_date': new_start_date.strftime('%d.%m.%Y'),
                    'new_end_date': new_end_date.strftime('%d.%m.%Y'),
                    'is_paid': 'Платное' if is_paid else 'Бесплатное',
                    'comment': comment
                },
                comment=comment
            )

            messages.success(request, f'✅ Договор продлён! Новый номер: {new_contract_number}')
            return redirect(REDIRECT_STUDENT_DETAIL, student_id=student.id)
        else:
            for field, errors in form.errors.items():
                messages.error(request, f"⚠️ Ошибка в поле '{field}': {', '.join(errors)}")
            return render(request, 'students/contract_extension.html', {'student': student, 'form': form})

    form = ContractExtensionForm()
    return render(request, 'students/contract_extension.html', {'student': student, 'form': form})


# =============================================================================
# ✅ 9. AJAX: Автоподсказки по фамилии
# =============================================================================
@login_required
@require_http_methods(["GET"])
def surname_suggestions(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'suggestions': []})

    suggestions = Student.objects.filter(
        last_name__istartswith=query
    ).values_list('last_name', flat=True).distinct()[:10]

    return JsonResponse({'suggestions': list(suggestions)})


# =============================================================================
# 🔹 Вспомогательные функции для student_edit
# =============================================================================
def _handle_group_change(student, new_group_id, old_group_id, request):
    if new_group_id and new_group_id.isdigit():
        new_group_id = int(new_group_id)
        if new_group_id != old_group_id:
            target_group = get_object_or_404(Group, pk=new_group_id, status='active')
            old_group_number = student.group.group_number if student.group else '—'

            student.group = target_group
            if target_group.teacher:
                student.teacher = target_group.teacher

            service = StudentStatusService(student)
            service.add_event(
                event_type='transfer',
                created_by=request.user,
                details={
                    'from_group': old_group_number,
                    'to_group_id': target_group.id,
                    'to_group': target_group.group_number
                }
            )
            return True
    elif new_group_id is None or new_group_id == '':
        student.group = None
    return False


def _handle_teacher_change(student, new_teacher_id, old_teacher_id, request):
    if new_teacher_id and new_teacher_id.isdigit():
        new_teacher_id = int(new_teacher_id)
        if new_teacher_id != student.teacher_id:
            old_teacher = student.teacher
            target_teacher = get_object_or_404(Teacher, pk=new_teacher_id, is_active=True)
            student.teacher = target_teacher

            service = StudentStatusService(student)
            service.add_event(
                event_type='teacher_change',
                created_by=request.user,
                details={
                    'from': str(old_teacher) if old_teacher else '—',
                    'to': f"{target_teacher.last_name} {target_teacher.first_name[:1]}.",
                    'to_teacher_id': target_teacher.id,
                }
            )
    elif new_teacher_id is None or new_teacher_id == '':
        student.teacher = None


# =============================================================================
# ✅ 10. Редактирование учащегося
# =============================================================================
@login_required
@require_http_methods(["GET", "POST"])
def student_edit(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    if request.method == 'POST':
        old_group_id = student.group_id
        old_teacher_id = student.teacher_id

        student.last_name = request.POST.get('last_name', '').strip()
        student.first_name = request.POST.get('first_name', '').strip()
        student.patronymic = request.POST.get('patronymic', '').strip()
        student.phone = request.POST.get('phone', '').strip()

        student.birth_date = _parse_date_from_request(request, 'birth_date')
        student.enrolled_date = _parse_date_from_request(request, 'enrolled_date', None)

        student.place_of_birth = request.POST.get('place_of_birth', '').strip()
        student.place_of_residence = request.POST.get('place_of_residence', '').strip()
        student.place_of_registration = request.POST.get('place_of_registration', '').strip()
        student.work_study_place = request.POST.get('work_study_place', '').strip()
        student.position = request.POST.get('position', '').strip()
        student.gearbox_type = request.POST.get('gearbox_type', '')

        new_group_id = request.POST.get('group')
        new_teacher_id = request.POST.get('teacher')
        new_master_id = request.POST.get('master')

        group_changed = _handle_group_change(student, new_group_id, old_group_id, request)

        if not group_changed:
            _handle_teacher_change(student, new_teacher_id, old_teacher_id, request)

        if new_master_id and new_master_id.isdigit():
            student.master = get_object_or_404(Master, pk=new_master_id)
        elif new_master_id is None or new_master_id == '':
            student.master = None

        student.save()
        messages.success(request, f'✅ Данные учащегося {student.last_name} обновлены!')
        return redirect(REDIRECT_STUDENT_DETAIL, student_id=student.pk)

    groups = Group.objects.filter(status='active').order_by('group_number')
    teachers = Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name')
    masters = Master.objects.all().order_by('last_name', 'first_name')

    context = {
        'title': '✏️ Редактирование учащегося',
        'student': student,
        'groups': groups,
        'teachers': teachers,
        'masters': masters,
    }
    return render(request, 'students/student_edit.html', context)


# =============================================================================
# ✅ 11. API для живого поиска (Live Search)
# =============================================================================
@login_required
@require_http_methods(["GET"])
def get_students_api(request):
    query = request.GET.get('q', '').strip()
    student_id = request.GET.get('student_id')

    qs = Student.objects.select_related('group', 'teacher', 'master')

    if student_id:
        students = qs.filter(id=student_id)
    else:
        if len(query) == 0:
            students = qs.all()
        else:
            students = qs.filter(
                Q(last_name__istartswith=query) |
                Q(first_name__istartswith=query) |
                Q(patronymic__istartswith=query)
            ).order_by('last_name', 'first_name')

    rows_html = []
    suggestions_list = []

    for s in students[:50]:
        service = StudentStatusService(s)
        status_data = service.get_current_status()
        row_html = render_to_string('students/includes/student_table_row.html', {
            'student': s,
            'status_color': status_data['color'],
        })
        rows_html.append(row_html)

        full_name = f"{s.last_name} {s.first_name}"
        if s.patronymic:
            full_name += f" {s.patronymic}"

        birth_str = s.birth_date.strftime('%d.%m.%Y') if s.birth_date else ''
        group_str = f"(гр. {s.group.group_number})" if s.group else ''
        display_text = f"{full_name} {birth_str} {group_str}".strip()

        suggestions_list.append({
            'id': s.id,
            'suggestion_text': display_text
        })

    return JsonResponse({'rows': rows_html, 'suggestions': suggestions_list})


# =============================================================================
# ✅ 12. Обновление значения платной услуги
# =============================================================================
@login_required
@require_http_methods(["POST"])
def update_service_value(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    try:
        data = json.loads(request.body)
        service_id = data.get('service_id')
        field_type = data.get('field_type')
        value = data.get('value')

        from reference.models import PaidService
        service = get_object_or_404(PaidService, pk=service_id)

        log_entry = {
            'type': 'service_value_updated',
            'date': timezone.now().date().isoformat(),
            'title': f"Обновлено значение услуги: {service.name}",
            'details': {
                'service_id': service.id,
                'service_name': service.name,
                'field_type': field_type,
                'value': value
            }
        }

        current_log = student.activity_log or []
        current_log.append(log_entry)
        student.activity_log = current_log
        student.save(update_fields=['activity_log', 'updated_at'])

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# =============================================================================
# ✅ 13. Включение/выключение платной услуги
# =============================================================================
@login_required
@require_http_methods(["POST"])
def toggle_service(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    try:
        data = json.loads(request.body)
        service_id = data.get('service_id')
        enabled = data.get('enabled', False)

        from reference.models import PaidService
        service = get_object_or_404(PaidService, pk=service_id)

        log_entry = {
            'type': 'service_added' if enabled else 'service_removed',
            'date': timezone.now().date().isoformat(),
            'title': f"{'Добавлена' if enabled else 'Удалена'} услуга: {service.name}",
            'details': {
                'service_id': service.id,
                'service_name': service.name,
                'enabled': enabled
            }
        }

        current_log = student.activity_log or []
        current_log.append(log_entry)
        student.activity_log = current_log
        student.save(update_fields=['activity_log'])

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# =============================================================================
# ✅ 14. Сохранение всех платных услуг с проверкой совместимости
# =============================================================================
@login_required
@require_http_methods(["POST"])
def save_services(request, student_id):
    """
    Сохраняет все платные услуги студента.

    🔥 Проверки совместимости:
      - Если указан «Мастер по вождению» и «Марка автомобиля» —
        мастер ОБЯЗАН иметь машину этой марки.
      - Если марка не совпадает — возвращаем 400 с описанием конфликта,
        НЕ сохраняем.
    """
    student = get_object_or_404(Student, pk=student_id)

    try:
        data = json.loads(request.body)
        services = data.get('services', [])

        from reference.models import PaidService

        # 🔥 1. Сначала соберём финальные значения услуг
        #     (не пишем в БД, пока не прошли все проверки)
        final_master_id = None
        final_car_brand = None
        final_master_gender = None
        prepared_entries = []

        for service_data in services:
            service_id = service_data.get('service_id')
            service_name = service_data.get('service_name')
            values = service_data.get('values', {})

            # Извлекаем мастера / марку
            if service_name == 'Мастер по вождению':
                final_master_id = _extract_master_id_from_values(values)
            elif service_name == 'Марка автомобиля':
                final_car_brand = _extract_car_brand_from_values(values)
            elif service_name == 'Пол мастера':
                final_master_gender = _extract_gender_from_values(values)

            prepared_entries.append({
                'service_id': service_id,
                'service_name': service_name,
                'values': values,
            })

        # 🔥 2. Проверяем совместимость мастера и марки
        ok, err = _validate_master_brand_compatibility(final_master_id, final_car_brand)
        if not ok:
            return JsonResponse({
                'success': False,
                'error': err,
                'conflict': True,
                'master_id': final_master_id,
                'car_brand': final_car_brand,
            }, status=400)

        # 🔥 2б. Если указан мастер и пол — проверяем, что пол мастера совпадает
        if final_master_id and final_master_gender:
            master = Master.objects.filter(pk=int(final_master_id)).first()
            if master and master.gender and master.gender != final_master_gender:
                return JsonResponse({
                    'success': False,
                    'error': (
                        f'Мастер {master.last_name} {master.first_name} '
                        f'не соответствует полу из услуги. '
                        f'Выберите другого мастера или уберите «Пол мастера».'
                    ),
                    'conflict': True,
                    'master_id': final_master_id,
                    'master_gender': final_master_gender,
                }, status=400)

        # 🔥 2в. Если указан мастер и у студента задана коробка —
        #        проверяем, что КПП машины мастера совпадает
        if final_master_id and student.gearbox_type:
            GEARBOX_MAP = {
                'manual': 'MT',
                'auto': 'AT',
                'electric': 'ET',
            }
            required_transmission = GEARBOX_MAP.get(student.gearbox_type.lower())
            master = Master.objects.filter(pk=int(final_master_id)).first()
            if (required_transmission and master and master.car
                    and master.car.transmission != required_transmission):
                return JsonResponse({
                    'success': False,
                    'error': (
                        f'Мастер {master.last_name} {master.first_name} '
                        f'закреплён за машиной с КПП «{master.car.get_transmission_display()}», '
                        f'а учащемуся нужна «{student.get_gearbox_type_display()}». '
                        f'Выберите другого мастера.'
                    ),
                    'conflict': True,
                    'master_id': final_master_id,
                }, status=400)

        # 🔥 3. Все проверки прошли — сохраняем услуги
        current_log = student.activity_log or []
        current_log = [
            entry for entry in current_log
            if entry.get('type') not in ['service_added', 'service_removed']
        ]

        for entry in prepared_entries:
            log_entry = {
                'type': 'service_added',
                'date': timezone.now().date().isoformat(),
                'title': f"Добавлена услуга: {entry['service_name']}",
                'details': {
                    'service_id': entry['service_id'],
                    'service_name': entry['service_name'],
                    'enabled': True,
                    'values': entry['values'],
                }
            }
            current_log.append(log_entry)

        student.activity_log = current_log
        student.save(update_fields=['activity_log'])

        return JsonResponse({'success': True, 'count': len(prepared_entries)})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)