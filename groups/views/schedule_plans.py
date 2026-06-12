# groups/views/schedule_plans.py
import json
from collections import defaultdict
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse

from groups.models import Group, SchedulePlan
from groups.forms import SchedulePlanForm
from teachers.models import Teacher
from classrooms.models import Classroom


# =============================================================================
# 🔹 Вспомогательная функция: проверка на дубликаты
# =============================================================================
def _check_schedule_duplicates(group, date_start, date_end, exclude_plan_id=None):
    """
    Проверяет наличие пересекающихся план-графиков для той же группы.
    Возвращает список дубликатов или пустой список.
    """
    duplicates = SchedulePlan.objects.filter(
        group=group,
        date_start__lte=date_end,
        date_end__gte=date_start,
    )

    if exclude_plan_id:
        duplicates = duplicates.exclude(pk=exclude_plan_id)

    return list(duplicates)


# =============================================================================
# 🔹 Список план-графиков
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


# =============================================================================
# 🔹 Создание/редактирование план-графика (Шаг 1)
# =============================================================================
@login_required
def schedule_plan_create(request, plan_id=None):
    """Шаг 1: Создание или редактирование план-графика"""
    plan = None
    if plan_id:
        plan = get_object_or_404(SchedulePlan, pk=plan_id)

    weeks = []
    form = None

    if request.method == 'POST':
        form = SchedulePlanForm(request.POST, instance=plan)
        if form.is_valid():
            group = form.cleaned_data['group']
            date_start = form.cleaned_data['date_start']
            date_end = form.cleaned_data['date_end']
            schedule_type = form.cleaned_data.get('schedule_type', 'custom')

            # 🔹 ПРОВЕРКА НА ДУБЛИКАТЫ
            duplicates = _check_schedule_duplicates(
                group=group,
                date_start=date_start,
                date_end=date_end,
                exclude_plan_id=plan.pk if plan else None
            )

            if duplicates:
                dup_info = []
                for dup in duplicates:
                    dup_info.append(
                        f"{dup.group.group_number} ({dup.date_start.strftime('%d.%m.%Y')} — "
                        f"{dup.date_end.strftime('%d.%m.%Y')})"
                    )

                messages.error(
                    request,
                    f'❌ План-график уже существует!\n\n'
                    f'Для группы {group.group_number} на период '
                    f'{date_start.strftime("%d.%m.%Y")} — {date_end.strftime("%d.%m.%Y")} '
                    f'уже есть план-график:\n'
                    f'{"; ".join(dup_info)}\n\n'
                    f'Измените даты или удалите существующий план-график.'
                )
            else:
                schedule_plan = form.save(commit=False)
                if not plan:
                    schedule_plan.created_by = request.user

                # 🔥 СОХРАНЕНИЕ CLASS_DAYS ИЗ POST
                class_days_raw = request.POST.get('class_days', '{}')
                if class_days_raw and class_days_raw != '{}':
                    try:
                        parsed_days = json.loads(class_days_raw)
                        schedule_plan.class_days = {}
                        for date_str, day_data in parsed_days.items():
                            try:
                                d_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                                if date_start <= d_obj <= date_end:
                                    schedule_plan.class_days[date_str] = day_data
                            except (ValueError, TypeError):
                                continue
                    except json.JSONDecodeError as e:
                        print(f" Ошибка JSON class_days: {e}")
                        schedule_plan.class_days = {}
                else:
                    schedule_plan.class_days = {}

                # 🔹 Сохранение преподавателя медицины
                med_teacher_id = request.POST.get('med_teacher')
                if med_teacher_id and med_teacher_id.isdigit():
                    schedule_plan.med_teacher_id = int(med_teacher_id)
                else:
                    schedule_plan.med_teacher = None

                # 🔥 СОХРАНЕНИЕ ВРЕМЕНИ ЗАНЯТИЙ (Утро/День/Вечер)
                time_slots = []
                if form.cleaned_data.get('time_morning'): time_slots.append('morning')
                if form.cleaned_data.get('time_day'): time_slots.append('day')
                if form.cleaned_data.get('time_evening'): time_slots.append('evening')

                if isinstance(schedule_plan.class_days, dict):
                    schedule_plan.class_days['_time_slots'] = time_slots
                else:
                    schedule_plan.class_days = {'_time_slots': time_slots}

                # 🔹 🔥 🔥 НОВОЕ: СОХРАНЕНИЕ ЛОГОВ ДАТ (Исключенные / Дополнительные) 🔥 🔥 🔥
                excluded_raw = request.POST.get('excluded_dates', '[]')
                additional_raw = request.POST.get('additional_dates', '[]')

                try:
                    schedule_plan.excluded_dates = json.loads(excluded_raw) if excluded_raw else []
                except json.JSONDecodeError:
                    schedule_plan.excluded_dates = []

                try:
                    schedule_plan.additional_dates = json.loads(additional_raw) if additional_raw else []
                except json.JSONDecodeError:
                    schedule_plan.additional_dates = []

                schedule_plan.save()

                messages.success(request, '✅ План-график сохранён!')
                return redirect('groups:schedule_plan_step2', plan_id=schedule_plan.pk)
        else:
            print(f" Ошибки формы: {form.errors}")
            messages.error(request, '❌ Ошибка в форме')
    else:
        # GET-запрос
        initial = {}
        if plan:
            initial.update({
                'group': plan.group_id,
                'teacher': plan.teacher_id,
                'date_start': plan.date_start,
                'date_end': plan.date_end,
                'schedule_type': plan.schedule_type,
                'location': plan.location,
                'med_teacher': plan.med_teacher_id,
            })
        elif request.GET.get('group'):
            try:
                g = Group.objects.get(pk=request.GET.get('group'), status='active')
                initial.update({
                    'group': g.pk,
                    'teacher': g.teacher_id,
                    'date_start': g.contract_start,
                    'date_end': g.contract_end,
                })
            except Group.DoesNotExist:
                pass

        form = SchedulePlanForm(instance=plan, initial=initial)

    # 🔹 ГЕНЕРАЦИЯ КАЛЕНДАРЯ (для отображения в GET)
    def _get_date_value(source, key):
        val = source.get(key) if isinstance(source, dict) else getattr(source, key, None)
        if isinstance(val, str):
            try:
                return datetime.strptime(val, '%Y-%m-%d').date()
            except ValueError:
                return None
        return val

    if request.method == 'POST' and form and form.is_bound:
        cal_start = form.cleaned_data.get('date_start') if form.is_valid() else _get_date_value(form.data, 'date_start')
        cal_end = form.cleaned_data.get('date_end') if form.is_valid() else _get_date_value(form.data, 'date_end')
        cal_schedule_type = form.cleaned_data.get('schedule_type') if form.is_valid() else form.data.get('schedule_type')
    else:
        cal_start = plan.date_start if plan else (form.initial.get('date_start') if form else None)
        cal_end = plan.date_end if plan else (form.initial.get('date_end') if form else None)
        cal_schedule_type = plan.schedule_type if plan else (form.initial.get('schedule_type') if form else 'custom')

    cal_class_days = plan.class_days if plan else {}

    if cal_start and cal_end:
        if isinstance(cal_start, str):
            cal_start = datetime.strptime(cal_start, '%Y-%m-%d').date()
        if isinstance(cal_end, str):
            cal_end = datetime.strptime(cal_end, '%Y-%m-%d').date()

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
                'date': date_str,
                'day_name': current.strftime('%a'),
                'day_num': current.day,
                'month': current.strftime('%B'),
                'is_scheduled': is_scheduled,
                'is_weekend': current.weekday() >= 5,
                'has_conflict': False,
            })
            current += timedelta(days=1)
        weeks = [calendar_data[i:i + 7] for i in range(0, len(calendar_data), 7)]

    classrooms = Classroom.objects.all().order_by('classroom_number')
    initial_location = plan.location if plan else (form.initial.get('location') if form else '')

    class_days_json = '{}'
    if plan and plan.class_days:
        if isinstance(plan.class_days, dict):
            class_days_json = json.dumps(plan.class_days)
        elif isinstance(plan.class_days, str):
            class_days_json = plan.class_days

    # 🔹 Извлекаем время занятий для отображения в чекбоксах И для календаря
    time_slots = []
    if plan and plan.class_days:
        class_days = plan.class_days
        if isinstance(class_days, str):
            try:
                class_days = json.loads(class_days)
            except json.JSONDecodeError:
                class_days = {}
        time_slots = class_days.get('_time_slots', [])
    elif form:
        if form.initial.get('time_morning'): time_slots.append('morning')
        if form.initial.get('time_day'): time_slots.append('day')
        if form.initial.get('time_evening'): time_slots.append('evening')

    # 🔹 Преобразуем morning/day/evening в У/Д/В для календаря
    calendar_slots = []
    if 'morning' in time_slots: calendar_slots.append('У')
    if 'day' in time_slots: calendar_slots.append('Д')
    if 'evening' in time_slots: calendar_slots.append('В')

    context = {
        'form': form,
        'plan': plan,
        'weeks': weeks,
        'teachers': Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name'),
        'classrooms': classrooms,
        'title': 'Создание план-графика' if not plan else 'Редактирование план-графика',
        'weekdays': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
        'initial_location': initial_location,
        'class_days_json': class_days_json,
        'time_morning_checked': 'morning' in time_slots,
        'time_day_checked': 'day' in time_slots,
        'time_evening_checked': 'evening' in time_slots,
        'calendar_time_slots': calendar_slots,
    }
    return render(request, 'groups/schedule_plan_form.html', context)


# =============================================================================
# 🔹 AJAX: обновление дня в календаре
# =============================================================================
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
        if isinstance(class_days, str):
            class_days = json.loads(class_days)

        if action == 'remove':
            class_days.pop(date_str, None)
        elif action in ['add', 'update']:
            if date_str:
                class_days[date_str] = {'scheduled': True}

        plan.class_days = class_days
        plan.save(update_fields=['class_days', 'updated_at'])
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# =============================================================================
# 🔹 Шаг 2: Распределение часов
# =============================================================================
@login_required
def schedule_plan_step2(request, plan_id):
    """Шаг 2: Распределение часов по датам"""
    plan = get_object_or_404(SchedulePlan, pk=plan_id)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            hours_data = data.get('hours', {})

            class_days = plan.class_days or {}
            if isinstance(class_days, str):
                class_days = json.loads(class_days)

            for subject, dates in hours_data.items():
                for date_str, val in dates.items():
                    if date_str not in class_days:
                        class_days[date_str] = {}
                    class_days[date_str][subject] = val

            plan.class_days = class_days
            plan.save(update_fields=['class_days'])
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    raw_days = plan.class_days
    if isinstance(raw_days, str):
        try:
            class_days = json.loads(raw_days)
        except json.JSONDecodeError:
            class_days = {}
    elif isinstance(raw_days, dict):
        class_days = raw_days
    else:
        class_days = {}

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
            day_data = class_days.get(date_str, {})

            day_info = {
                'day_num': date_obj.strftime('%d'),
                'raw_date': date_str,
                'pdd': day_data.get('pdd', ''),
                'ua': day_data.get('ua', ''),
                'bd': day_data.get('bd', ''),
                'podd': day_data.get('podd', ''),
                'med': day_data.get('med', ''),
                'exam': day_data.get('exam', ''),
            }
            days_by_month[month_name].append(day_info)
        except ValueError:
            continue

    context = {
        'plan': plan,
        'days_by_month': dict(days_by_month),
        'plan_year': plan.date_start.year,
        'required_hours': plan.required_hours,
        'title': 'Подтверждение план-графика',
        'pdd_default': 100, 'ua_default': 6, 'bd_default': 38,
        'podd_default': 8, 'med_default': 16, 'exam_default': 2,
        'location': plan.location or '',
        'teachers': Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name'),
        'med_teacher_id': getattr(plan, 'med_teacher_id', None),
    }
    return render(request, 'groups/schedule_plan_step2.html', context)


# =============================================================================
# 🔹 Удаление план-графика
# =============================================================================
@login_required
def schedule_plan_delete(request, plan_id):
    """Удаление план-графика"""
    plan = get_object_or_404(SchedulePlan, pk=plan_id)

    if plan.created_by != request.user and not request.user.is_superuser:
        messages.error(request, '❌ У вас нет прав для удаления этого план-графика.')
        return redirect('groups:schedule_plans_list')

    group_number = plan.group.group_number
    plan.delete()

    messages.success(request, f'✅ План-график для группы "{group_number}" удалён.')
    return redirect('groups:schedule_plans_list')