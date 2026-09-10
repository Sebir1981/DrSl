import json
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from groups.models import Group, SchedulePlan

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