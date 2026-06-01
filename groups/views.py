# groups/views.py
import json
import re
import csv
from collections import defaultdict
from datetime import datetime, timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.db import transaction
from django.http import HttpResponse, JsonResponse

from .models import Group, CreditResult, ExamResult, SchedulePlan
from .forms import SchedulePlanForm
from reference.models import GroupCategory, Credit
from students.models import Student
from teachers.models import Teacher
from classrooms.models import Classroom


# =============================================================================
# 🔹 Панель управления разделом "Группы"
# =============================================================================
@login_required
def groups_dashboard(request):
    context = {
        'total_groups': Group.objects.count(),
        'active_groups': Group.objects.filter(status='active').count(),
        'categories_count': GroupCategory.objects.count(),
    }
    return render(request, 'groups/dashboard.html', context)


# =============================================================================
# 🔹 Список групп
# =============================================================================
@login_required
def group_list(request):
    groups = Group.objects.select_related('category', 'classroom', 'teacher').all()
    search_query = request.GET.get('search', '').strip()
    if search_query:
        groups = groups.filter(
            Q(group_number__icontains=search_query) |
            Q(category__code__icontains=search_query) |
            Q(teacher__last_name__icontains=search_query)
        )
    category_filter = request.GET.get('category')
    if category_filter:
        groups = groups.filter(category_id=category_filter)
    status_filter = request.GET.get('status')
    if status_filter:
        groups = groups.filter(status=status_filter)
    groups = groups.order_by('group_number')
    categories = GroupCategory.objects.all().order_by('code')
    context = {
        'groups': groups, 'categories': categories,
        'selected_category': category_filter, 'selected_status': status_filter,
        'search_query': search_query,
    }
    return render(request, 'groups/group_list.html', context)


# =============================================================================
# 🔹 Карточка группы
# =============================================================================
@login_required
def group_detail(request, group_id):
    group = get_object_or_404(Group.objects.select_related('category', 'classroom', 'teacher'), pk=group_id)
    classrooms = Classroom.objects.all().order_by('classroom_number')
    teachers = Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name')

    if request.method == 'POST':
        if 'save_group' in request.POST:
            group.contract_start = request.POST.get('contract_start') or None
            group.contract_end = request.POST.get('contract_end') or None
            group.exam_internal_theory_date = request.POST.get('exam_internal_theory_date') or None
            group.exam_internal_driving_date = request.POST.get('exam_internal_driving_date') or None
            group.exam_gai_date = request.POST.get('exam_gai_date') or None
            group.status = request.POST.get('status', 'active')
            group.comments = request.POST.get('comments', '')

            classroom_id = request.POST.get('classroom')
            if classroom_id and classroom_id.isdigit():
                group.classroom = get_object_or_404(Classroom, pk=classroom_id)
            elif classroom_id == '':
                group.classroom = None

            teacher_id = request.POST.get('teacher')
            if teacher_id and teacher_id.isdigit():
                group.teacher = get_object_or_404(Teacher, pk=teacher_id)
            elif teacher_id == '':
                group.teacher = None

            group.save()
            messages.success(request, '✅ Данные группы сохранены.')
            return redirect('groups:group_detail', group_id=group.pk)

        elif 'add_student' in request.POST:
            student_id = request.POST.get('student_id')
            if student_id:
                student = get_object_or_404(Student, pk=student_id)
                if student.group == group:
                    messages.warning(request, 'Учащийся уже в группе.')
                else:
                    old_group = student.group
                    transfer_date = timezone.now().date()
                    transfer_log_entry = {
                        'type': 'transfer',
                        'date': transfer_date.strftime('%Y-%m-%d'),
                        'title': f"Перевод в группу {group.group_number}",
                        'details': {
                            'from_group': str(old_group) if old_group else '—',
                            'to_group': str(group.group_number),
                        }
                    }
                    current_log = student.activity_log or []
                    current_log.append(transfer_log_entry)
                    current_log.sort(key=lambda x: x.get('date', ''))
                    student.activity_log = current_log
                    student.transferred_date = transfer_date
                    student.group = group
                    student.save(update_fields=['group', 'transferred_date', 'activity_log', 'updated_at'])
                    messages.success(request, f'✅ {student.last_name} добавлен в группу.')
            return redirect('groups:group_detail', group_id=group.pk)

    current_students = Student.objects.filter(group=group).order_by('last_name', 'first_name')
    former_students_data = []
    all_students_no_group = Student.objects.exclude(group=group).order_by('last_name', 'first_name')
    for s in all_students_no_group:
        if s.activity_log:
            transfers = [entry for entry in s.activity_log if entry.get('type') == 'transfer']
            if transfers:
                last_transfer = transfers[-1]
                from_g = last_transfer.get('details', {}).get('from_group', '')
                if str(group.group_number) in str(from_g) or str(group) == str(from_g):
                    former_students_data.append({
                        'student': s,
                        'comment': last_transfer.get('details', {}).get('to_group', 'другую группу')
                    })

    available_students = Student.objects.exclude(group=group).order_by('last_name', 'first_name')
    context = {
        'group': group,
        'current_students': current_students,
        'former_students': former_students_data,
        'available_students': available_students,
        'classrooms': classrooms,
        'teachers': teachers,
    }
    return render(request, 'groups/group_detail.html', context)


# =============================================================================
# 🔹 Матрица прогресса: зачёты (ОПТИМИЗИРОВАНО)
# =============================================================================
@login_required
def credits_exams_dashboard(request):
    """Матрица прогресса: студенты × зачёты — показывает статус последней попытки + все попытки для подсказки"""

    groups = Group.objects.filter(status='active').order_by('group_number')

    group_id = request.GET.get('group', '')
    search = request.GET.get('search', '').strip()

    students_qs = Student.objects.select_related('group').order_by('last_name', 'first_name')

    if group_id and group_id.isdigit():
        students_qs = students_qs.filter(group_id=group_id)
    if search:
        students_qs = students_qs.filter(
            Q(last_name__icontains=search) | Q(first_name__icontains=search)
        )

    # 🔹 Оптимизация: загружаем ВСЕ попытки за ОДИН запрос
    student_ids = list(students_qs.values_list('id', flat=True))
    if not student_ids:
        return render(request, 'groups/credits_exams.html', {
            'groups': groups, 'students': [], 'selected_group': group_id, 'search': search
        })

    all_attempts = CreditResult.objects.filter(
        student_id__in=student_ids,
        credit__number__in=range(1, 7)
    ).select_related('credit').order_by('student_id', 'credit__number', 'credit_date', 'id')

    # 🔹 Группируем попытки в Python: (student_id, credit_number) -> [attempts]
    attempts_by_key = defaultdict(list)
    for att in all_attempts:
        attempts_by_key[(att.student_id, att.credit.number)].append(att)

    students_data = []
    for s in students_qs:
        credits_status = []
        for num in range(1, 7):
            key = (s.id, num)
            attempts_list = attempts_by_key.get(key, [])

            if attempts_list:
                # Последняя попытка (уже отсортировано по дате и ID)
                last_attempt = attempts_list[-1]
                icon = '✅' if last_attempt.status == 'passed' else '❌'

                # Собираем данные для подсказки
                attempts_for_tooltip = []
                for att in attempts_list:
                    attempt_num = 0
                    attempt_type = 'free'
                    if att.comment:
                        match = re.search(r'Попытка №(\d+)', att.comment)
                        if match:
                            attempt_num = int(match.group(1))
                        if 'Тип: paid' in att.comment:
                            attempt_type = 'paid'

                    attempts_for_tooltip.append({
                        'num': attempt_num,
                        'icon': '✅' if att.status == 'passed' else '❌',
                        'type': 'Платная' if attempt_type == 'paid' else 'Бесплатная',
                        'date': att.credit_date.strftime('%d.%m.%Y') if att.credit_date else '—'
                    })

                # Сортируем по номеру попытки для корректного отображения
                attempts_for_tooltip.sort(key=lambda x: x['num'])

                credits_status.append({
                    'num': num,
                    'status': last_attempt.status,
                    'icon': icon,
                    'attempts': attempts_for_tooltip
                })
            else:
                credits_status.append({'num': num, 'status': 'none', 'icon': '—', 'attempts': []})

        students_data.append({
            'id': s.id,
            'full_name': s.full_name,
            'group_number': str(s.group) if s.group else '—',
            'group_id': s.group_id,
            'credits': credits_status,
        })

    context = {
        'groups': groups,
        'students': students_data,
        'selected_group': group_id,
        'search': search,
    }
    return render(request, 'groups/credits_exams.html', context)


# =============================================================================
# 🔹 Форма добавления результатов зачётов (ОПТИМИЗИРОВАНО)
# =============================================================================
@login_required
def credits_exams_add(request):
    """Форма добавления результатов зачётов (с комиссией из 4 человек)"""

    teachers = Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name')
    groups = Group.objects.filter(status='active').order_by('group_number')
    students = Student.objects.select_related('group').order_by('last_name', 'first_name')
    credits = Credit.objects.order_by('number')

    # 🔹 Оптимизация: считаем попытки одним запросом
    attempts_counts = CreditResult.objects.filter(
        student_id__in=[s.id for s in students],
        credit_id__in=[c.id for c in credits]
    ).values('student_id', 'credit_id').annotate(count=Count('id'))

    attempts_data = {s.id: {} for s in students}
    for row in attempts_counts:
        attempts_data[row['student_id']][row['credit_id']] = row['count']

    students_json = json.dumps([
        {
            'id': s.id,
            'name': s.full_name,
            'group_id': s.group_id,
            'attempts': attempts_data.get(s.id, {})
        }
        for s in students
    ])

    if request.method == 'POST':
        credit_id = request.POST.get('credit_id')
        credit_date = request.POST.get('credit_date')
        chairman_id = request.POST.get('chairman')
        member1_id = request.POST.get('member1')
        member2_id = request.POST.get('member2')
        member3_id = request.POST.get('member3')
        global_comment = request.POST.get('global_comment', '').strip()

        student_pattern = re.compile(r'^student_(\d+)_type$')
        student_ids = {int(m.group(1)) for k in request.POST.keys() if (m := student_pattern.match(k))}

        if not student_ids:
            messages.error(request, '⚠️ В таблице нет учащихся для сохранения')
        elif not credit_date:
            messages.error(request, '⚠️ Укажите дату')
        elif not credit_id:
            messages.error(request, '⚠️ Выберите тему зачёта')
        elif not chairman_id:
            messages.error(request, '⚠️ Выберите председателя комиссии')
        else:
            saved = 0
            with transaction.atomic():
                credit_obj = Credit.objects.get(id=credit_id)

                for sid in student_ids:
                    prefix = f'student_{sid}'
                    status = request.POST.get(f'{prefix}_status')
                    attempt_type = request.POST.get(f'{prefix}_type', 'free')

                    if not status:
                        continue

                    attempt_num = CreditResult.objects.filter(student_id=sid, credit_id=credit_id).count()

                    result = CreditResult.objects.create(
                        student_id=sid,
                        credit_id=credit_id,
                        credit_date=credit_date,
                        status=status,
                        chairman_id=chairman_id or None,
                        member1_id=member1_id or None,
                        member2_id=member2_id or None,
                        member3_id=member3_id or None,
                        comment=f"Попытка №{attempt_num}, Тип: {attempt_type}" +
                                (f" | {global_comment}" if global_comment else "")
                    )

                    student = Student.objects.select_for_update().get(id=sid)
                    log_entry = {
                        'type': 'credit_result',
                        'date': credit_date,
                        'title': f"Зачёт №{credit_obj.number}: {credit_obj.topic}",
                        'details': {
                            'result': 'passed' if status == 'passed' else 'failed',
                            'result_icon': '✅' if status == 'passed' else '❌',
                            'attempt_number': attempt_num,
                            'attempt_type': attempt_type,
                        },
                        'commission': {
                            'chairman': str(result.chairman) if result.chairman else '—',
                            'members': [str(m) for m in [result.member1, result.member2, result.member3] if m]
                        },
                        'global_comment': global_comment or None
                    }

                    current_log = student.activity_log or []
                    current_log.append(log_entry)
                    current_log.sort(key=lambda x: x.get('date', ''))
                    student.activity_log = current_log
                    student.save(update_fields=['activity_log'])

                    saved += 1

            messages.success(request, f'✅ Сохранено зачётов: {saved}')
            return redirect('groups:credits_exams')

    context = {
        'teachers': teachers,
        'groups': groups,
        'students': students,
        'credits': credits,
        'students_json': students_json,
        'title': 'Добавить результаты зачётов',
    }
    return render(request, 'groups/credits_exams_add.html', context)


# =============================================================================
# 🔹 Отчёт по зачётам
# =============================================================================
@login_required
def credits_report(request):
    """Отчёт по зачётам с фильтрами и экспортом"""

    groups = Group.objects.filter(status='active').order_by('group_number')
    credits = Credit.objects.order_by('number')

    group_id = request.GET.get('group')
    credit_id = request.GET.get('credit')
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    results = CreditResult.objects.select_related(
        'student', 'student__group', 'credit', 'chairman', 'member1', 'member2', 'member3'
    ).order_by('-credit_date')

    if group_id and group_id.isdigit():
        results = results.filter(student__group_id=group_id)
    if credit_id and credit_id.isdigit():
        results = results.filter(credit_id=credit_id)
    if status and status in ['passed', 'failed']:
        results = results.filter(status=status)
    if date_from:
        results = results.filter(credit_date__gte=date_from)
    if date_to:
        results = results.filter(credit_date__lte=date_to)

    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="zachety_report.csv"'
        response.write('\ufeff'.encode('utf8'))

        writer = csv.writer(response, delimiter=';')
        writer.writerow([
            'Дата', 'Группа', 'ФИО учащегося', 'Зачёт №', 'Тема',
            'Попытка №', 'Тип', 'Статус', 'Председатель', 'Члены комиссии', 'Комментарий'
        ])

        for r in results:
            members = [str(m) for m in [r.member1, r.member2, r.member3] if m]
            members_str = ', '.join(members) if members else '—'

            comment_parts = r.comment.split(' | ', 1) if r.comment else ['', '']
            meta = comment_parts[0]
            user_comment = comment_parts[1] if len(comment_parts) > 1 else ''

            match = re.search(r'Попытка №(\d+)', meta)
            attempt_num = int(match.group(1)) if match else 0
            attempt_type = 'paid' if 'Тип: paid' in meta else 'free'

            writer.writerow([
                r.credit_date.strftime('%d.%m.%Y'),
                r.student.group.group_number if r.student.group else '—',
                r.student.full_name,
                r.credit.number,
                r.credit.topic,
                attempt_num,
                'Платная' if attempt_type == 'paid' else 'Бесплатная',
                '✅ Сдал' if r.status == 'passed' else '❌ Не сдал',
                str(r.chairman) if r.chairman else '—',
                members_str,
                user_comment or '—'
            ])

        return response

    report_data = []
    for r in results:
        comment_parts = r.comment.split(' | ', 1) if r.comment else ['', '']
        meta = comment_parts[0]
        user_comment = comment_parts[1] if len(comment_parts) > 1 else ''

        match = re.search(r'Попытка №(\d+)', meta)
        attempt_num = int(match.group(1)) if match else 0
        attempt_type = 'paid' if 'Тип: paid' in meta else 'free'

        report_data.append({
            'result': r,
            'attempt_num': attempt_num,
            'attempt_type': attempt_type,
            'user_comment': user_comment
        })

    total = len(report_data)
    passed = sum(1 for d in report_data if d['result'].status == 'passed')
    failed = sum(1 for d in report_data if d['result'].status == 'failed')
    success_rate = round(passed / total * 100) if total > 0 else 0

    context = {
        'groups': groups,
        'credits': credits,
        'results': report_data,
        'selected_group': group_id,
        'selected_credit': credit_id,
        'selected_status': status,
        'date_from': date_from,
        'date_to': date_to,
        'stats': {'total': total, 'passed': passed, 'failed': failed, 'success_rate': success_rate},
        'title': '📋 Отчёт по зачётам',
    }
    return render(request, 'reports/credits.html', context)


# =============================================================================
# 🔹 НОВОЕ: План-графики (Plan-Graphics)
# =============================================================================

@login_required
def schedule_plans_list(request):
    """Список всех план-графиков"""
    plans = SchedulePlan.objects.select_related('group', 'teacher', 'created_by').all().order_by('-created_at')
    context = {
        'plans': plans,
        'groups': Group.objects.filter(status='active').order_by('group_number'),
    }
    return render(request, 'groups/schedule_plans_list.html', context)


@login_required
def schedule_plan_create(request, plan_id=None):
    """Создание или редактирование план-графика (Шаг 1)"""
    plan = None
    if plan_id:
        plan = get_object_or_404(SchedulePlan, pk=plan_id)

    weeks = []  # 🔹 Инициализируем, чтобы избежать NameError

    if request.method == 'POST':
        form = SchedulePlanForm(request.POST, instance=plan)
        if form.is_valid():
            schedule_plan = form.save(commit=False)
            if not plan:
                schedule_plan.created_by = request.user

            class_days_raw = request.POST.get('class_days', '{}')
            if class_days_raw and class_days_raw != '{}':
                try:
                    import json
                    schedule_plan.class_days = json.loads(class_days_raw)
                except:
                    schedule_plan.class_days = {}
            else:
                schedule_plan.class_days = {}

            schedule_plan.save()
            return redirect('groups:schedule_plan_step2', plan_id=schedule_plan.pk)
    else:
        initial = {}
        if plan and plan.group:
            group = plan.group
            standard_time = group.standard_time_range if hasattr(group, 'standard_time_range') else None
            time_start = None
            time_end = None
            if standard_time and '–' in standard_time:
                try:
                    time_start, time_end = standard_time.split('–')
                except:
                    pass

            initial.update({
                'group': plan.group_id,
                'teacher': plan.teacher_id,
                'date_start': plan.date_start,
                'date_end': plan.date_end,
                'time_start': plan.time_start or time_start or (
                    group.time_start.strftime('%H:%M') if group and group.time_start else None),
                'time_end': plan.time_end or time_end or (
                    group.time_end.strftime('%H:%M') if group and group.time_end else None),
                'schedule_type': plan.schedule_type,
                'location': plan.location,
                'required_hours': plan.required_hours,
            })
        elif request.GET.get('group'):
            try:
                g = Group.objects.get(pk=request.GET.get('group'), status='active')
                standard_time = g.standard_time_range if hasattr(g, 'standard_time_range') else None
                time_start = None
                time_end = None
                if standard_time and '–' in standard_time:
                    try:
                        time_start, time_end = standard_time.split('–')
                    except:
                        pass

                initial.update({
                    'group': g.pk,
                    'teacher': g.teacher_id,
                    'date_start': g.contract_start,
                    'date_end': g.contract_end,
                    'schedule_type': getattr(g, 'schedule_type', 'custom'),
                    'location': g.classroom.address if g.classroom else '',
                    'time_start': time_start or (g.time_start.strftime('%H:%M') if g.time_start else None),
                    'time_end': time_end or (g.time_end.strftime('%H:%M') if g.time_end else None),
                })
            except Group.DoesNotExist:
                pass
        form = SchedulePlanForm(instance=plan, initial=initial)

    # 🔹 ГЕНЕРАЦИЯ КАЛЕНДАРЯ
    cal_start = (form.instance.date_start or form.initial.get('date_start'))
    cal_end = (form.instance.date_end or form.initial.get('date_end'))
    cal_schedule_type = (form.instance.schedule_type or form.initial.get('schedule_type', 'custom'))
    cal_class_days = form.instance.class_days if plan else {}

    if cal_start and cal_end:
        calendar_data = []
        current = cal_start
        while current <= cal_end:
            is_scheduled = False
            date_str = current.strftime('%Y-%m-%d')
            if cal_schedule_type == 'even' and current.day % 2 == 0:
                is_scheduled = True
            elif cal_schedule_type == 'odd' and current.day % 2 == 1:
                is_scheduled = True
            elif cal_schedule_type == 'weekend' and current.weekday() >= 5:
                is_scheduled = True
            elif cal_schedule_type == 'custom' and date_str in cal_class_days:
                is_scheduled = True

            day_info = cal_class_days.get(date_str, {})
            calendar_data.append({
                'date': date_str, 'day_name': current.strftime('%a'), 'day_num': current.day,
                'month': current.strftime('%B'), 'is_scheduled': is_scheduled,
                'time_start': day_info.get('start', ''), 'time_end': day_info.get('end', ''),
                'is_weekend': current.weekday() >= 5, 'has_conflict': False,
            })
            current += timedelta(days=1)
        weeks = [calendar_data[i:i + 7] for i in range(0, len(calendar_data), 7)]

    # 🔹 НОВОЕ: Получаем аудитории для dropdown
    classrooms = Classroom.objects.all().order_by('classroom_number')

    # 🔹 НОВОЕ: Безопасная передача location в шаблон
    initial_location = None
    if plan and plan.location:
        initial_location = plan.location
    elif form.initial.get('location'):
        initial_location = form.initial['location']

    context = {
        'form': form,
        'plan': plan,
        'weeks': weeks,
        'teachers': Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name'),
        'classrooms': classrooms,  # 🔹 Передаём аудитории в шаблон
        'title': 'Создание план-графика' if not plan else 'Редактирование план-графика',
        'weekdays': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
        'initial_location': initial_location,  # 🔹 Для безопасного доступа в шаблоне
    }
    return render(request, 'groups/schedule_plan_form.html', context)

    # 🔹 ГЕНЕРАЦИЯ КАЛЕНДАРЯ (ИСПРАВЛЕНО)
    # Приоритет источников данных:
    # 1. form.data (если POST с ошибками валидации)
    # 2. form.instance (если редактируем существующий план)
    # 3. form.initial (если новый план с автозаполнением)

    cal_start = (form.data.get('date_start') or
                 (form.instance.date_start if form.instance.pk else None) or
                 form.initial.get('date_start'))

    cal_end = (form.data.get('date_end') or
               (form.instance.date_end if form.instance.pk else None) or
               form.initial.get('date_end'))

    cal_schedule_type = (form.data.get('schedule_type') or
                         form.instance.schedule_type or
                         form.initial.get('schedule_type', 'custom'))

    cal_class_days = form.instance.class_days or {}

    # 🔹 Отладка
    print(f"DEBUG: cal_start={cal_start}, cal_end={cal_end}, type={type(cal_start)}")
    print(f"DEBUG: form.initial={form.initial}")
    print(f"DEBUG: form.instance.date_start={form.instance.date_start if form.instance else None}")

    weeks = []
    if cal_start and cal_end:
        calendar_data = []
        current = cal_start
        while current <= cal_end:
            is_scheduled = False
            if cal_schedule_type == 'even' and current.day % 2 == 0:
                is_scheduled = True
            elif cal_schedule_type == 'odd' and current.day % 2 == 1:
                is_scheduled = True
            elif cal_schedule_type == 'weekend' and current.weekday() >= 5:
                is_scheduled = True
            elif cal_schedule_type == 'custom':
                if current.strftime('%Y-%m-%d') in cal_class_days:
                    is_scheduled = True

            day_info = cal_class_days.get(current.strftime('%Y-%m-%d'), {})

            calendar_data.append({
                'date': current.strftime('%Y-%m-%d'),
                'day_name': current.strftime('%a'),
                'day_num': current.day,
                'month': current.strftime('%B'),
                'is_scheduled': is_scheduled,
                'time_start': day_info.get('start', ''),
                'time_end': day_info.get('end', ''),
                'is_weekend': current.weekday() >= 5,
                'has_conflict': False,
            })
            current += timedelta(days=1)

        # Группируем по неделям (7 дней)
        weeks = [calendar_data[i:i + 7] for i in range(0, len(calendar_data), 7)]
        print(f"DEBUG: weeks generated = {len(weeks)} weeks, {len(calendar_data)} days")
    else:
        print(f"WARNING: Calendar not generated - cal_start={cal_start}, cal_end={cal_end}")

    classrooms = Classroom.objects.all().order_by('classroom_number')

    context = {
        'form': form,
        'plan': plan,
        'weeks': weeks,
        'teachers': Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name'),
        'classrooms': classrooms,  # ✅ НОВОЕ: для dropdown мест проведения
        'title': 'Создание план-графика' if not plan else 'Редактирование план-графика',
        'weekdays': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
    }
    return render(request, 'groups/schedule_plan_form.html', context)


@login_required
def schedule_plan_ajax_update_day(request, plan_id):
    """AJAX: обновление дня в календаре"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    plan = get_object_or_404(SchedulePlan, pk=plan_id)
    try:
        data = json.loads(request.body)
        date_str = data.get('date')
        action = data.get('action')
        class_days = plan.class_days or {}

        if action == 'remove':
            if date_str in class_days:
                del class_days[date_str]
        elif action in ['add', 'update']:
            if data.get('time_start') and data.get('time_end'):
                class_days[date_str] = {'start': data.get('time_start'), 'end': data.get('time_end')}

        plan.class_days = class_days
        plan.save(update_fields=['class_days', 'updated_at'])
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def schedule_plan_step2(request, plan_id):
    """Шаг 2: Распределение часов по конкретным датам"""
    plan = get_object_or_404(SchedulePlan, pk=plan_id)

    # 🔹 ОБРАБОТКА POST-ЗАПРОСА (сохранение распределения)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            hours_data = data.get('hours', {})

            # Сохраняем распределение часов в class_days
            # Формат: {"2026-04-06": {"start": "08:40", "end": "13:30", "pdd": 4, "ua": 0, ...}}
            class_days = plan.class_days or {}

            # Собираем все уникальные даты из всех предметов
            all_dates = set()
            for subject, dates in hours_data.items():
                all_dates.update(dates.keys())

            # Обновляем class_days
            for date_str in all_dates:
                if date_str not in class_days:
                    class_days[date_str] = {}

                # Добавляем часы по каждому предмету
                for subject, dates in hours_data.items():
                    if date_str in dates:
                        class_days[date_str][subject] = dates[date_str]

            plan.class_days = class_days

            # Сохраняем преподавателя медицины (если выбран)
            med_teacher_id = data.get('med_teacher')
            if med_teacher_id and med_teacher_id.isdigit():
                plan.med_teacher_id = int(med_teacher_id)

            plan.save(update_fields=['class_days', 'med_teacher', 'updated_at'])

            return JsonResponse({'success': True, 'message': 'Распределение сохранено'})

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Неверный формат данных'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    # 🔹 GET-ЗАПРОС (отображение страницы)
    raw_days = plan.class_days
    if isinstance(raw_days, str):
        try:
            class_days = json.loads(raw_days)
        except:
            class_days = {}
    elif isinstance(raw_days, dict):
        class_days = raw_days
    else:
        class_days = {}

    plan_year = plan.date_start.year if plan.date_start else (next(iter(class_days))[:4] if class_days else '2026')

    days_by_month = defaultdict(list)
    ru_months = {
        'January': 'Январь', 'February': 'Февраль', 'March': 'Март',
        'April': 'Апрель', 'May': 'Май', 'June': 'Июнь',
        'July': 'Июль', 'August': 'Август', 'September': 'Сентябрь',
        'October': 'Октябрь', 'November': 'Ноябрь', 'December': 'Декабрь'
    }

    for date_str in sorted(class_days.keys()):
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            month_name = ru_months.get(date_obj.strftime('%B'), date_obj.strftime('%B'))

            duration = 0
            day_data = class_days.get(date_str, {})
            if day_data.get('start') and day_data.get('end'):
                try:
                    s = datetime.strptime(day_data['start'], '%H:%M')
                    e = datetime.strptime(day_data['end'], '%H:%M')
                    duration = round((e - s).seconds / 3600)
                except:
                    pass

            days_by_month[month_name].append({
                'day_num': date_obj.strftime('%d'),
                'raw_date': date_str,
                'duration': duration
            })
        except ValueError:
            continue

    context = {
        'plan': plan,
        'days_by_month': dict(days_by_month),
        'plan_year': plan_year,
        'required_hours': plan.required_hours,
        'title': 'Подтверждение план-графика',
        'pdd_default': 100,
        'ua_default': 6,
        'bd_default': 38,
        'podd_default': 8,
        'med_default': 16,
        'exam_default': 2,
        'time_start': plan.time_start.strftime('%H:%M') if plan.time_start else '08:40',
        'time_end': plan.time_end.strftime('%H:%M') if plan.time_end else '13:30',
        'location': plan.location or '',
        'teachers': Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name'),
        'med_teacher_id': getattr(plan, 'med_teacher_id', None),
    }

    return render(request, 'groups/schedule_plan_step2.html', context)


def calculate_duration(start, end):
    """Вычисляет продолжительность в часах"""
    if not start or not end:
        return 0
    try:
        start_time = datetime.strptime(start, '%H:%M')
        end_time = datetime.strptime(end, '%H:%M')
        delta = end_time - start_time
        return delta.seconds / 3600
    except:
        return 0

# =============================================================================
# 🔹 API: Данные группы для автозаполнения формы
# =============================================================================
@login_required
def group_api_data(request, group_id):
    """Возвращает данные группы в формате JSON для автозаполнения формы"""
    group = get_object_or_404(Group, pk=group_id, status='active')

    # 🔹 Вычисляем стандартное время (как в админке)
    standard_time = group.standard_time_range if hasattr(group, 'standard_time_range') else None
    time_start = None
    time_end = None

    if standard_time and '–' in standard_time:
        try:
            time_start, time_end = standard_time.split('–')
        except:
            pass

    data = {
        'teacher_id': group.teacher_id,
        'teacher_name': str(group.teacher) if group.teacher else None,
        'contract_start': group.contract_start.strftime('%Y-%m-%d') if group.contract_start else None,
        'contract_end': group.contract_end.strftime('%Y-%m-%d') if group.contract_end else None,
        'schedule_type': getattr(group, 'schedule_type', 'custom'),
        'location': group.classroom.address if group.classroom else '',
        'classroom_id': group.classroom_id if group.classroom else None,
        # 🔹 НОВОЕ: время из standard_time_range
        'time_start': time_start or (group.time_start.strftime('%H:%M') if group.time_start else '08:40'),
        'time_end': time_end or (group.time_end.strftime('%H:%M') if group.time_end else '13:30'),
        'standard_time_range': standard_time,  # 🔹 Для отладки
        'category': str(group.category) if group.category else None,
        'duration': group.get_duration_display() if group.duration else '—',
    }
    return JsonResponse(data)


# =============================================================================
# 🔹 API: Проверка занятости преподавателя
# =============================================================================
@login_required
def check_instructor_availability(request):
    """Проверка занятости преподавателя/мастера на конкретную дату и время"""
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    teacher_id = request.GET.get('teacher_id')
    date = request.GET.get('date')
    time_start = request.GET.get('time_start')
    time_end = request.GET.get('time_end')
    exclude_plan_id = request.GET.get('exclude_plan_id')

    if not all([teacher_id, date, time_start, time_end]):
        return JsonResponse({'available': False, 'reason': 'Не все параметры указаны'})

    conflicts = SchedulePlan.objects.filter(
        teacher_id=teacher_id,
        class_days__has_key=date
    ).exclude(
        pk=exclude_plan_id if exclude_plan_id else None
    )

    conflict_details = []
    for plan in conflicts:
        day_schedule = plan.class_days.get(date, {})
        existing_start = day_schedule.get('start', '')
        existing_end = day_schedule.get('end', '')

        if existing_start and existing_end:
            if not (time_end <= existing_start or time_start >= existing_end):
                conflict_details.append({
                    'group': str(plan.group),
                    'time': f"{existing_start}–{existing_end}",
                    'plan_id': plan.pk
                })

    if conflict_details:
        return JsonResponse({
            'available': False,
            'reason': 'Преподаватель занят',
            'conflicts': conflict_details
        })

    return JsonResponse({'available': True})