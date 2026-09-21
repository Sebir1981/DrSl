# students/views.py
import json
import random
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
from master_plan.models import MasterPlanGroup
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

            # 🔹 Наследуем преподавателя из группы при создании (если не задан вручную)
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
            # 🔹 Значение может быть номерм группы ИЛИ её ID — проверяем оба варианта
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
# ✅ 3. Карточка учащегося
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
    from groups.models import CreditResult, ExamResult
    from reference.models import Credit

    # Все зачёты студента
    credit_results = CreditResult.objects.filter(
        student=student
    ).select_related('credit').order_by('credit__number', '-credit_date')

    # Группируем по номерам зачётов
    # Все зачёты студента
    credit_results = CreditResult.objects.filter(
        student=student
    ).select_related('credit').order_by('credit__number', '-credit_date')

    # Группируем по номерам зачётов с распарсенными данными
    credits_by_number = defaultdict(list)
    for cr in credit_results:
        # Парсим комментарий для получения типа попытки
        attempt_type = 'Бесплатная'
        attempt_num = 0
        if cr.comment:
            # Ищем в комментарии маркеры типа попытки
            if 'платная' in cr.comment.lower() or 'paid' in cr.comment.lower():
                attempt_type = 'Платная'
            elif 'бесплатная' in cr.comment.lower() or 'free' in cr.comment.lower():
                attempt_type = 'Бесплатная'

            # Ищем номер попытки
            import re
            match = re.search(r'попытка\s*#?(\d+)', cr.comment.lower())
            if match:
                attempt_num = int(match.group(1))

        credits_by_number[cr.credit.number].append({
            'credit_date': cr.credit_date,
            'status': cr.status,
            'attempt_type': attempt_type,
            'attempt_num': attempt_num,
        })
    # Все экзамены студента
    exam_results = ExamResult.objects.filter(
        student=student
    ).order_by('exam_type', '-exam_date')

    theory_exams = exam_results.filter(exam_type='theory')
    driving_exams = exam_results.filter(exam_type='driving')

    # 🔹 Получаем все платные услуги и выбранные для студента
    from reference.models import PaidService
    all_services = PaidService.objects.all()

    # Получаем значения услуг для студента (из activity_log или отдельного поля)
    student_services = {}
    if student.activity_log:
        for entry in student.activity_log:
            if entry.get('type') == 'service_added':
                service_id = entry.get('details', {}).get('service_id')
                if service_id:
                    student_services[service_id] = True

    # 🔹 Получаем уникальные марки автомобилей из автопарка
    car_brands = Car.objects.values_list('make', flat=True).distinct().order_by('make')
    today = timezone.now().date()

    # 🔹 1. Расчёт часов ТЕОРИИ из план-графика
    theory_total = 0.0
    theory_distributed = 0.0

    if student.group:
        schedule_plan = SchedulePlan.objects.filter(group=student.group).order_by('-created_at').first()

        if schedule_plan:
            # 🔹 БЕРЁМ готовое значение "Итого" из план-графика
            theory_total = float(schedule_plan.required_hours or 0)

            # 🔹 Считаем только распределённые часы (прошедшие дни)
            if schedule_plan.class_days:
                class_days = schedule_plan.class_days
                if isinstance(class_days, str):
                    try:
                        class_days = json.loads(class_days)
                    except json.JSONDecodeError:
                        class_days = {}

                if isinstance(class_days, dict):
                    # Получаем список исключённых и дополнительных дней
                    excluded_dates = set(schedule_plan.excluded_dates or [])
                    additional_dates = set(schedule_plan.additional_dates or [])

                    for date_str, day_data in class_days.items():
                        # Пропускаем служебные ключи
                        if date_str.startswith('_') or not isinstance(day_data, dict):
                            continue

                        #  СТРОГАЯ ПРОВЕРКА: день должен быть активен
                        # Проверяем excluded_dates
                        if date_str in excluded_dates:
                            if settings.DEBUG:
                                print(f"SKIP (excluded): {date_str}")
                            continue

                        # Проверяем флаг scheduled
                        is_scheduled = day_data.get('scheduled', None)
                        if is_scheduled is False:
                            if settings.DEBUG:
                                print(f"SKIP (scheduled=False): {date_str}")
                            continue

                        # Если scheduled не установлен (None), проверяем по алгоритму
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

                                # Если день не должен быть по алгоритму и не в additional_dates
                                if not should_be_scheduled and date_str not in additional_dates:
                                    if settings.DEBUG:
                                        print(f"SKIP (not scheduled by algo): {date_str}")
                                    continue
                            except (ValueError, TypeError):
                                pass

                        try:
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                            # Суммируем только прошедшие дни (включая сегодня)
                            if date_obj <= today:
                                day_hours = 0.0
                                for k, v in day_data.items():
                                    # Пропускаем служебные ключи
                                    if k.startswith('_') or k.endswith('_topics'):
                                        continue
                                    if k in ['scheduled', 'manuallyRemoved', 'is_med', 'med', 'med_hours',
                                             'location', 'time_start', 'time_end', 'category']:
                                        continue
                                    # Суммируем только числа
                                    if isinstance(v, (int, float)):
                                        day_hours += float(v)
                                    elif isinstance(v, str):
                                        try:
                                            day_hours += float(v)
                                        except (ValueError, TypeError):
                                            pass

                                if day_hours > 0:
                                    theory_distributed += day_hours

                                    # Отладка
                                    if settings.DEBUG:
                                        print(f"✓ COUNT: {date_str} = {day_hours} ч. (всего: {theory_distributed})")
                        except (ValueError, TypeError) as e:
                            continue

    # Ограничиваем распределённые часы общим количеством
    theory_distributed = min(theory_distributed, theory_total)
    theory_remaining = max(0.0, theory_total - theory_distributed)
    theory_percent = round((theory_distributed / theory_total * 100), 1) if theory_total > 0 else 0.0

    # 🔹 2. Расчёт часов ПРАКТИКИ из генерального плана (с заглушкой)
    practice_total = 0.0
    practice_driven = 0.0

    if student.group:
        master_plan = MasterPlanGroup.objects.filter(group=student.group, is_archived=False).first()
        if master_plan:
            practice_total = float(master_plan.hours_per_student)
            # 🚧 ЗАГЛУШКА: рандомное число до 50, пока не реализован учёт из путевых листов
            practice_driven = min(random.randint(0, 50), practice_total)

    practice_remaining = max(0.0, practice_total - practice_driven)
    practice_percent = round((practice_driven / practice_total * 100), 1) if practice_total > 0 else 0.0

    # ✅ ИСПРАВЛЕННЫЙ ОТСТУП ЗДЕСЬ:
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
    }
    return render(request, 'students/student_detail.html', context)


# =============================================================================
# ✅ 4. Перевод в другую группу (с наследованием преподавателя)
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

        # 🔹 Назначаем новую группу и наследуем преподавателя
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
# ✅ 5. Отказ от обучения
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

            service = StudentStatusService(student)
            service.add_event(
                event_type='refusal',
                created_by=request.user,
                event_date=parsed_date,
                details={'comment': comment},
                comment=comment
            )

            messages.success(request, f"✅ Зафиксирован отказ: {student.last_name} {student.first_name}")
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
# ✅ 7. Отчисление учащегося
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

            service = StudentStatusService(student)
            service.add_event(
                event_type='dismissal',
                created_by=request.user,
                event_date=parsed_date,
                details={
                    'order_number': order_number if order_number else '—',
                    'comment': comment
                },
                comment=comment
            )

            messages.success(
                request,
                f"✅ {student.last_name} {student.first_name} отчислен. Приказ №{order_number if order_number else '—'}"
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
    """
    Обрабатывает смену группы: назначает группу, наследует преподавателя,
    записывает событие перевода. Возвращает True, если группа изменилась.
    """
    if new_group_id and new_group_id.isdigit():
        new_group_id = int(new_group_id)
        if new_group_id != old_group_id:
            target_group = get_object_or_404(Group, pk=new_group_id, status='active')
            old_group_number = student.group.group_number if student.group else '—'

            # 🔹 Назначаем новую группу и наследуем преподавателя
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
    """
    Обрабатывает РУЧНУЮ смену преподавателя.
    Вызывается только если группа НЕ менялась (иначе преподаватель унаследован).
    """
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

        # 1. Личные данные
        student.last_name = request.POST.get('last_name', '').strip()
        student.first_name = request.POST.get('first_name', '').strip()
        student.patronymic = request.POST.get('patronymic', '').strip()
        student.phone = request.POST.get('phone', '').strip()

        # 2. Даты
        student.birth_date = _parse_date_from_request(request, 'birth_date')
        student.enrolled_date = _parse_date_from_request(request, 'enrolled_date', None)

        # 3. Адреса и прочее
        student.place_of_birth = request.POST.get('place_of_birth', '').strip()
        student.place_of_residence = request.POST.get('place_of_residence', '').strip()
        student.place_of_registration = request.POST.get('place_of_registration', '').strip()
        student.work_study_place = request.POST.get('work_study_place', '').strip()
        student.position = request.POST.get('position', '').strip()
        student.gearbox_type = request.POST.get('gearbox_type', '')

        # 4. Обработка связей
        new_group_id = request.POST.get('group')
        new_teacher_id = request.POST.get('teacher')
        new_master_id = request.POST.get('master')

        # 🔹 Смена группы → преподаватель наследуется автоматически
        group_changed = _handle_group_change(student, new_group_id, old_group_id, request)

        # 🔹 Ручная смена преподавателя — только если группа НЕ менялась
        if not group_changed:
            _handle_teacher_change(student, new_teacher_id, old_teacher_id, request)

        # Мастер
        if new_master_id and new_master_id.isdigit():
            student.master = get_object_or_404(Master, pk=new_master_id)
        elif new_master_id is None or new_master_id == '':
            student.master = None

        # 5. Сохраняем и редиректим
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
# ✅ 12. Выбор платных услуг
# =============================================================================

@login_required
@require_http_methods(["POST"])
def update_service_value(request, student_id):
    """Обновление значения выбранной услуги для студента"""
    student = get_object_or_404(Student, pk=student_id)

    try:
        data = json.loads(request.body)
        service_id = data.get('service_id')
        field_type = data.get('field_type')
        value = data.get('value')

        from reference.models import PaidService
        service = get_object_or_404(PaidService, pk=service_id)

        # Добавляем запись в activity_log
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
    """Включение/выключение платной услуги для студента"""
    student = get_object_or_404(Student, pk=student_id)

    try:
        data = json.loads(request.body)
        service_id = data.get('service_id')
        enabled = data.get('enabled', False)

        from reference.models import PaidService
        service = get_object_or_404(PaidService, pk=service_id)

        # Добавляем запись в activity_log
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
# ✅ 14. Сохранение всех платных услуг для студента
# =============================================================================

@login_required
@require_http_methods(["POST"])
def save_services(request, student_id):
    """Сохранение всех выбранных платных услуг для студента"""
    student = get_object_or_404(Student, pk=student_id)

    try:
        data = json.loads(request.body)
        services = data.get('services', [])

        from reference.models import PaidService

        # Получаем текущий activity_log
        current_log = student.activity_log or []

        # Удаляем старые записи о услугах
        current_log = [entry for entry in current_log if entry.get('type') not in ['service_added', 'service_removed']]

        # Добавляем новые записи
        for service_data in services:
            service_id = service_data.get('service_id')
            service_name = service_data.get('service_name')
            values = service_data.get('values', {})

            log_entry = {
                'type': 'service_added',
                'date': timezone.now().date().isoformat(),
                'title': f"Добавлена услуга: {service_name}",
                'details': {
                    'service_id': service_id,
                    'service_name': service_name,
                    'enabled': True,
                    'values': values
                }
            }
            current_log.append(log_entry)

        student.activity_log = current_log
        student.save(update_fields=['activity_log'])

        return JsonResponse({'success': True, 'count': len(services)})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)