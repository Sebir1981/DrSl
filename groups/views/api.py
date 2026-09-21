import json
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from groups.models import Group, SchedulePlan
from django.db.models import Q
from collections import defaultdict
from reference.models import Credit
from students.models import Student
from groups.models import CreditResult, ExamResult

logger = logging.getLogger(__name__)


@login_required
def group_api_data(request, group_id):
    """API: данные группы для автозаполнения форм"""
    group = get_object_or_404(Group, pk=group_id, status='active')

    data = {
        'teacher_id': group.teacher_id,
        'teacher_name': str(group.teacher) if group.teacher else None,
        'contract_start': group.contract_start.strftime('%Y-%m-%d') if group.contract_start else None,
        'contract_end': group.contract_end.strftime('%Y-%m-%d') if group.contract_end else None,
        'schedule_type': getattr(group, 'schedule_type', 'custom'),
        'location': group.classroom.address if group.classroom else '',
        'classroom_id': group.classroom_id if group.classroom else None,
        'category': str(group.category) if group.category else None,
        'category_id': group.category_id if group.category else None,
        'duration': group.get_duration_display() if group.duration else '—',
    }
    return JsonResponse(data)


@login_required
def check_instructor_availability(request):
    """API: проверка занятости преподавателя"""
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
    ).exclude(pk=exclude_plan_id if exclude_plan_id else None)

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


@login_required
def get_teacher_schedules(request):
    """Возвращает индикаторы занятости преподавателей (У/Д/В)"""
    teacher_id = request.GET.get('teacher_id')
    med_teacher_id = request.GET.get('med_teacher_id')
    date_start = request.GET.get('date_start')
    date_end = request.GET.get('date_end')
    exclude_plan_id = request.GET.get('exclude_plan_id')

    if not date_start or not date_end:
        return JsonResponse({})

    schedule_map = {}

    def process_plans(plans_qs, is_med_teacher=False, exclude_med_days=False):
        for plan in plans_qs:
            class_days = plan.class_days or {}
            if isinstance(class_days, str):
                try:
                    class_days = json.loads(class_days)
                except (json.JSONDecodeError, ValueError) as e:
                    # ✅ Логируем проблему и пропускаем битый план
                    logger.warning(
                        "План-график pk=%s содержит некорректный JSON в class_days: %s",
                        plan.pk, e
                    )
                    continue

            plan_time_slots = class_days.get('_time_slots', [])
            plan_indicators = []
            if 'morning' in plan_time_slots:
                plan_indicators.append('У')
            if 'day' in plan_time_slots:
                plan_indicators.append('Д')
            if 'evening' in plan_time_slots:
                plan_indicators.append('В')
            if not plan_indicators:
                plan_indicators = ['Д']

            for date_str, day_data in class_days.items():
                if date_str.startswith('_'):
                    continue
                if not (date_start <= date_str <= date_end):
                    continue

                # 🔹 Для мед. преподавателя: учитываем ТОЛЬКО дни с флагом med=true
                if is_med_teacher:
                    if not (isinstance(day_data, dict) and day_data.get('med')):
                        continue

                # 🔹 Для основного преподавателя: исключаем дни с флагом med=true
                if exclude_med_days:
                    if isinstance(day_data, dict) and day_data.get('med'):
                        continue

                final_indicators = []
                start_time = day_data.get('start', '') if isinstance(day_data, dict) else ''

                if start_time:
                    try:
                        h, m = map(int, start_time.split(':'))
                        minutes = h * 60 + m
                        if minutes < 810:
                            final_indicators = ['У']
                        elif minutes < 1050:
                            final_indicators = ['Д']
                        else:
                            final_indicators = ['В']
                    except (ValueError, AttributeError) as e:
                        # ✅ Логируем битое время и используем значение по умолчанию
                        logger.warning(
                            "Некорректное время '%s' в плане pk=%s на дату %s: %s. Используем 'Д'.",
                            start_time, plan.pk, date_str, e
                        )
                        final_indicators = ['Д']
                else:
                    final_indicators = plan_indicators

                if date_str not in schedule_map:
                    schedule_map[date_str] = []

                for ind in final_indicators:
                    existing = [
                        x for x in schedule_map.get(date_str, [])
                        if isinstance(x, dict) and x.get('ind') == ind
                    ]
                    if not existing:
                        schedule_map[date_str].append({
                            'ind': ind,
                            'group': str(plan.group) if plan.group else 'Не указано',
                            'location': plan.location or 'Не указано',
                            'is_med': is_med_teacher
                        })

    # 🔹 Ищем планы основного преподавателя (исключаем дни с мед. флагом)
    if teacher_id:
        qs = SchedulePlan.objects.filter(
            teacher_id=teacher_id,
            date_start__lte=date_end,
            date_end__gte=date_start
        )
        if exclude_plan_id and exclude_plan_id.isdigit():
            qs = qs.exclude(pk=int(exclude_plan_id))
        process_plans(qs, is_med_teacher=False, exclude_med_days=True)

    # 🔹 Ищем планы мед. преподавателя (только дни с мед. флагом)
    if med_teacher_id:
        qs = SchedulePlan.objects.filter(
            med_teacher_id=med_teacher_id,
            date_start__lte=date_end,
            date_end__gte=date_start
        )
        if exclude_plan_id and exclude_plan_id.isdigit():
            qs = qs.exclude(pk=int(exclude_plan_id))
        process_plans(qs, is_med_teacher=True, exclude_med_days=False)

    return JsonResponse(schedule_map)


@login_required
def live_search_students(request):
    """API для живого поиска учащихся с автоподсказками"""
    query = request.GET.get('q', '').strip()
    student_id = request.GET.get('id')
    group_id = request.GET.get('group', '')

    # Базовый queryset
    students_qs = Student.objects.select_related('group').order_by('last_name', 'first_name')

    # Фильтр по группе (если выбран)
    if group_id and group_id.isdigit():
        students_qs = students_qs.filter(group_id=group_id)

    # 🔹 Если передан ID — возвращаем отфильтрованные строки таблицы
    if student_id and student_id.isdigit():
        students_qs = students_qs.filter(pk=student_id)

        rows = []
        for s in students_qs:
            # Формируем HTML строки таблицы (упрощённо)
            row_html = f"""
            <tr>
                <td class="col-fio">
                    <div style="font-weight:600;color:#1e293b;">{s.full_name}</div>
                    <div style="font-size:11px;color:#64748b;margin-top:2px;">{s.group or '—'}</div>
                </td>
                <td colspan="{request.GET.get('colspan', 8)}" style="text-align:center;color:#64748b;">
                    Данные загружаются...
                </td>
            </tr>
            """
            rows.append(row_html)

        return JsonResponse({'rows': rows})

    # 🔹 Если передан запрос — возвращаем подсказки
    if query:
        students = students_qs.filter(
            Q(last_name__icontains=query) | Q(first_name__icontains=query)
        )[:10]  # Ограничение до 10 результатов

        suggestions = [
            {
                'id': s.id,
                'suggestion_text': f"{s.last_name} {s.first_name} {s.patronymic or ''} ({s.group or '—'})"
            }
            for s in students
        ]

        return JsonResponse({'suggestions': suggestions})

    return JsonResponse({'suggestions': []})

@login_required
def live_search_students(request):
    """API для живого поиска учащихся (совместимо с live_search.js)"""
    query = request.GET.get('q', '').strip()
    student_id = request.GET.get('id')
    group_id = request.GET.get('group', '')

    students_qs = Student.objects.select_related('group').order_by('last_name', 'first_name')
    if group_id and group_id.isdigit():
        students_qs = students_qs.filter(group_id=group_id)

    # 🔹 Если передан ID — возвращаем HTML строки таблицы
    if student_id and student_id.isdigit():
        students = list(students_qs.filter(pk=student_id))
        rows = []

        all_credits = Credit.objects.all().order_by('number')
        credit_numbers = [c.number for c in all_credits]
        credit_topics = {c.number: c.topic for c in all_credits}

        student_ids = [s.id for s in students]
        all_attempts = CreditResult.objects.filter(
            student_id__in=student_ids,
            credit__number__in=credit_numbers
        ).select_related('credit').order_by('student_id', 'credit__number', 'credit_date', 'id')

        attempts_by_key = defaultdict(list)
        for att in all_attempts:
            attempts_by_key[(att.student_id, att.credit.number)].append(att)

        for s in students:
            credits_status = []
            for num in credit_numbers:
                key = (s.id, num)
                attempts_list = attempts_by_key.get(key, [])
                topic = credit_topics.get(num, f'Зачёт №{num}')

                if attempts_list:
                    last = attempts_list[-1]
                    icon = '✅' if last.status == 'passed' else '❌'
                    credits_status.append({'num': num, 'status': last.status, 'icon': icon, 'topic': topic})
                else:
                    credits_status.append({'num': num, 'status': 'none', 'icon': '—', 'topic': topic})

            # Генерируем HTML строки
            html = f'<tr>'
            html += f'<td class="col-fio">'
            html += f'<div style="font-weight:600;color:#1e293b;">{s.full_name}</div>'
            html += f'<div style="font-size:11px;color:#64748b;margin-top:2px;">{s.group.group_number if s.group else "—"}</div>'
            html += f'</td>'

            for c in credits_status:
                html += f'<td>'
                if c['icon'] != '—':
                    html += f'<span class="indicator {c["status"]}" title="{c["topic"]}">{c["icon"]}</span>'
                else:
                    html += f'<span class="indicator none">—</span>'
                html += f'</td>'

            theory_exam = ExamResult.objects.filter(student=s, exam_type='theory').order_by('-exam_date').first()
            driving_exam = ExamResult.objects.filter(student=s, exam_type='driving').order_by('-exam_date').first()

            html += f'<td class="cell-exam">'
            if theory_exam:
                icon = '✅' if theory_exam.status == 'passed' else '❌'
                html += f'<span class="indicator {theory_exam.status}" title="Теория: {theory_exam.exam_date}">{icon}</span>'
            else:
                html += f'<span class="indicator none">—</span>'
            html += f'</td>'

            html += f'<td class="cell-exam">'
            if driving_exam:
                icon = '✅' if driving_exam.status == 'passed' else '❌'
                html += f'<span class="indicator {driving_exam.status}" title="Вождение: {driving_exam.exam_date}">{icon}</span>'
            else:
                html += f'<span class="indicator none">—</span>'
            html += f'</td>'

            html += f'</tr>'
            rows.append(html)

        return JsonResponse({'rows': rows})

    # 🔹 Если передан запрос q — возвращаем подсказки
    if query:
        students = students_qs.filter(
            Q(last_name__icontains=query) | Q(first_name__icontains=query)
        )[:10]

        suggestions = [
            {
                'id': s.id,
                'suggestion_text': f"{s.last_name} {s.first_name} {s.patronymic or ''} ({s.birth_date.year if s.birth_date else '—'}) ({s.group.group_number if s.group else '—'})"
            }
            for s in students
        ]
        return JsonResponse({'suggestions': suggestions})

    return JsonResponse({'suggestions': []})