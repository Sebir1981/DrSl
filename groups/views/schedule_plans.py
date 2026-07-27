import json
from collections import defaultdict
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse

# ✅ ИМПОРТЫ МОДЕЛЕЙ
from groups.models import Group, SchedulePlan
from reference.models import GroupCategory, TrainingProgram
from groups.forms import SchedulePlanForm
from teachers.models import Teacher
from classrooms.models import Classroom


# =============================================================================
# 🔹 Вспомогательные функции
# =============================================================================
def _check_schedule_duplicates(group, date_start, date_end, exclude_plan_id=None):
    """Проверяет наличие пересекающихся план-графиков для той же группы."""
    duplicates = SchedulePlan.objects.filter(
        group=group,
        date_start__lte=date_end,
        date_end__gte=date_start,
    )
    if exclude_plan_id:
        duplicates = duplicates.exclude(pk=exclude_plan_id)
    return list(duplicates)


def _is_standard_schedule_day(date_str, schedule_type):
    """
    Проверяет, должен ли день быть в плане по стандартному алгоритму.
    Для 'even' и 'odd' учитываем, что выходные (сб-вс) автоматически исключаются.
    """
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
        weekday = d.weekday()  # 0=Пн, 1=Вт, ..., 5=Сб, 6=Вс

        if schedule_type == 'even':
            # Чётные дни, но ТОЛЬКО будние (пн-пт)
            return (d.day % 2 == 0) and (weekday < 5)

        if schedule_type == 'odd':
            # Нечётные дни, но ТОЛЬКО будние (пн-пт)
            return (d.day % 2 == 1) and (weekday < 5)

        if schedule_type == 'weekend':
            # Только выходные (сб=5, вс=6)
            return weekday >= 5

        return False  # custom/directed по умолчанию ничего не генерируют
    except Exception:
        return False


# =============================================================================
# 🔹 Список план-графиков
# =============================================================================
@login_required
def schedule_plans_list(request):
    plans = SchedulePlan.objects.select_related('group', 'teacher', 'created_by').all().order_by('-created_at')
    return render(request, 'groups/schedule_plans_list.html', {
        'plans': plans,
        'groups': Group.objects.filter(status='active').order_by('group_number'),
    })


# =============================================================================
# 🔹 Создание/редактирование план-графика (Шаг 1)
# =============================================================================
@login_required
def schedule_plan_create(request, plan_id=None):
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

            # 🔹 ПРОВЕРКА НА ДУБЛИКАТЫ
            duplicates = _check_schedule_duplicates(
                group=group, date_start=date_start, date_end=date_end,
                exclude_plan_id=plan.pk if plan else None
            )

            if duplicates:
                dup_info = [
                    f"{d.group.group_number} ({d.date_start.strftime('%d.%m.%Y')} — {d.date_end.strftime('%d.%m.%Y')})"
                    for d in duplicates]
                messages.error(request,
                               f'❌ План-график уже существует!\nДля группы {group.group_number} на период {date_start.strftime("%d.%m.%Y")} — {date_end.strftime("%d.%m.%Y")} уже есть план-график:\n{"; ".join(dup_info)}')
            else:
                schedule_plan = form.save(commit=False)
                if not plan:
                    schedule_plan.created_by = request.user

                # 🔥 СОХРАНЕНИЕ CLASS_DAYS + ДНЕЙ МЕДИЦИНЫ
                class_days_raw = request.POST.get('class_days', '{}')
                med_days = []
                final_class_days = {}

                if class_days_raw and class_days_raw != '{}':
                    try:
                        parsed_days = json.loads(class_days_raw)
                        for date_str, day_data in parsed_days.items():
                            try:
                                d_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                                if date_start <= d_obj <= date_end:
                                    final_class_days[date_str] = day_data
                                    if day_data.get('is_med') or day_data.get('med') or day_data.get('med_hours',
                                                                                                     0) > 0:
                                        med_days.append(date_str)
                            except (ValueError, TypeError):
                                continue
                    except json.JSONDecodeError:
                        final_class_days = {}

                schedule_plan.class_days = final_class_days

                if isinstance(schedule_plan.class_days, dict):
                    schedule_plan.class_days['_med_days'] = med_days

                # 👩‍⚕️ Преподаватель медицины
                med_teacher_id = request.POST.get('med_teacher')
                schedule_plan.med_teacher_id = int(
                    med_teacher_id) if med_teacher_id and med_teacher_id.isdigit() else None

                #  Время занятий
                time_slots = []
                if form.cleaned_data.get('time_morning'): time_slots.append('morning')
                if form.cleaned_data.get('time_day'): time_slots.append('day')
                if form.cleaned_data.get('time_evening'): time_slots.append('evening')
                schedule_plan.class_days['_time_slots'] = time_slots

                # 📅 УМНЫЙ РАСЧЁТ ИСКЛЮЧЁННЫХ/ДОПОЛНИТЕЛЬНЫХ ДНЕЙ
                # Мы игнорируем то, что прислал JS, и считаем сами на основе итогового календаря.

                # 📅 УМНЫЙ РАСЧЁТ ИСКЛЮЧЁННЫХ/ДОПОЛНИТЕЛЬНЫХ ДНЕЙ
                # Мы игнорируем то, что прислал JS, и считаем сами на основе итогового календаря.

                real_excluded = []
                real_additional = []

                # 🔹 Очищаем class_days от исключённых дней
                cleaned_class_days = {}
                for date_str, day_data in final_class_days.items():
                    if date_str.startswith('_'):
                        # Сохраняем служебные ключи
                        cleaned_class_days[date_str] = day_data
                        continue

                    # Проверяем, должен ли день быть по алгоритму
                    is_scheduled_by_algo = _is_standard_schedule_day(date_str, schedule_plan.schedule_type)

                    # 🔹 Если день есть в плане, но НЕ должен быть по алгоритму → это дополнение
                    if not is_scheduled_by_algo:
                        real_additional.append(date_str)
                        cleaned_class_days[date_str] = day_data
                    # 🔹 Если день должен быть по алгоритму → оставляем как есть
                    else:
                        cleaned_class_days[date_str] = day_data

                # 🔹 Теперь проверяем, какие дни ИЗ АЛГОРИТМА были удалены
                curr = date_start
                while curr <= date_end:
                    d_str = curr.strftime('%Y-%m-%d')
                    is_scheduled_by_algo = _is_standard_schedule_day(d_str, schedule_plan.schedule_type)
                    is_in_cleaned_plan = (d_str in cleaned_class_days)

                    # Если алгоритм сказал "ДА", а в плане "НЕТ" → Это исключение
                    if is_scheduled_by_algo and not is_in_cleaned_plan:
                        real_excluded.append(d_str)

                    curr += timedelta(days=1)

                schedule_plan.excluded_dates = real_excluded
                schedule_plan.additional_dates = real_additional
                schedule_plan.class_days = cleaned_class_days

                # 🔹 Сохраняем вычисленные списки в class_days для Шага 2
                schedule_plan.class_days['_additional_dates'] = schedule_plan.additional_dates
                schedule_plan.class_days['_excluded_dates'] = schedule_plan.excluded_dates

                schedule_plan.save()
                messages.success(request, '✅ План-график сохранён!')
                return redirect('groups:schedule_plan_step2', plan_id=schedule_plan.pk)
        else:
            messages.error(request, '❌ Ошибка в форме')
    else:
        initial = {}
        if plan:
            initial.update({
                'group': plan.group_id, 'teacher': plan.teacher_id,
                'date_start': plan.date_start, 'date_end': plan.date_end,
                'schedule_type': plan.schedule_type, 'location': plan.location,
                'med_teacher': plan.med_teacher_id,
            })
        elif request.GET.get('group'):
            try:
                g = Group.objects.get(pk=request.GET.get('group'), status='active')
                initial.update({'group': g.pk, 'teacher': g.teacher_id, 'date_start': g.contract_start,
                                'date_end': g.contract_end})
            except Group.DoesNotExist:
                pass
        form = SchedulePlanForm(instance=plan, initial=initial)

    # 🔹 ГЕНЕРАЦИЯ КАЛЕНДАРЯ
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
        cal_schedule_type = form.cleaned_data.get('schedule_type') if form.is_valid() else form.data.get(
            'schedule_type')
    else:
        cal_start = plan.date_start if plan else (form.initial.get('date_start') if form else None)
        cal_end = plan.date_end if plan else (form.initial.get('date_end') if form else None)
        cal_schedule_type = plan.schedule_type if plan else (form.initial.get('schedule_type') if form else 'custom')

    cal_class_days = plan.class_days if plan else {}

    # 🔹 Загружаем сохранённые списки исключений/дополнений
    excluded_dates_set = set(plan.excluded_dates or [])
    additional_dates_set = set(plan.additional_dates or [])

    if cal_start and cal_end:
        if isinstance(cal_start, str): cal_start = datetime.strptime(cal_start, '%Y-%m-%d').date()
        if isinstance(cal_end, str): cal_end = datetime.strptime(cal_end, '%Y-%m-%d').date()

        calendar_data = []
        current = cal_start
        while current <= cal_end:
            date_str = current.strftime('%Y-%m-%d')
            is_scheduled = False

            # 🔹 ШАГ 1: Проверяем базовый алгоритм
            if cal_schedule_type == 'even' and current.day % 2 == 0 and current.weekday() < 5:
                is_scheduled = True
            elif cal_schedule_type == 'odd' and current.day % 2 == 1 and current.weekday() < 5:
                is_scheduled = True
            elif cal_schedule_type == 'weekend' and current.weekday() >= 5:
                is_scheduled = True

            # 🔹 ШАГ 2: Применяем ручные дополнения (приоритет над алгоритмом)
            if date_str in additional_dates_set:
                is_scheduled = True

            # 🔹 ШАГ 3: Применяем ручные исключения (ВЫСШИЙ ПРИОРИТЕТ!)
            if date_str in excluded_dates_set:
                is_scheduled = False

            # 🔹 ШАГ 4: Проверяем class_days (НО ТОЛЬКО если не в исключениях!)
            if date_str in cal_class_days and not date_str.startswith('_'):
                if date_str not in excluded_dates_set:
                    is_scheduled = True
                else:
                    is_scheduled = False  # 🔥 Принудительно отключаем исключённые дни

            calendar_data.append({
                'date': date_str, 'day_name': current.strftime('%a'), 'day_num': current.day,
                'month': current.strftime('%B'), 'is_scheduled': is_scheduled,
                'is_weekend': current.weekday() >= 5, 'has_conflict': False,
            })
            current += timedelta(days=1)
        weeks = [calendar_data[i:i + 7] for i in range(0, len(calendar_data), 7)]

    classrooms = Classroom.objects.all().order_by('classroom_number')
    time_slots = []
    if plan and plan.class_days:
        cd = plan.class_days
        if isinstance(cd, str):
            try:
                cd = json.loads(cd)
            except json.JSONDecodeError:
                cd = {}
        time_slots = cd.get('_time_slots', [])
    elif form:
        if form.initial.get('time_morning'): time_slots.append('morning')
        if form.initial.get('time_day'): time_slots.append('day')
        if form.initial.get('time_evening'): time_slots.append('evening')

    calendar_slots = []
    if 'morning' in time_slots: calendar_slots.append('У')
    if 'day' in time_slots: calendar_slots.append('Д')
    if 'evening' in time_slots: calendar_slots.append('В')

    return render(request, 'groups/schedule_plan_form.html', {
        'form': form, 'plan': plan, 'weeks': weeks,
        'teachers': Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name'),
        'classrooms': classrooms,
        'title': 'Создание план-графика' if not plan else 'Редактирование план-графика',
        'weekdays': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
        'initial_location': plan.location if plan else (form.initial.get('location') if form else ''),
        'class_days_json': json.dumps(plan.class_days) if plan and plan.class_days else '{}',
        'time_morning_checked': 'morning' in time_slots,
        'time_day_checked': 'day' in time_slots,
        'time_evening_checked': 'evening' in time_slots,
        'calendar_time_slots': calendar_slots,
    })


# =============================================================================
# 🔹 AJAX: обновление дня в календаре
# =============================================================================
@login_required
def schedule_plan_ajax_update_day(request, plan_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    plan = get_object_or_404(SchedulePlan, pk=plan_id)
    try:
        data = json.loads(request.body)
        date_str, action = data.get('date'), data.get('action')
        class_days = plan.class_days or {}
        if isinstance(class_days, str): class_days = json.loads(class_days)

        if action == 'remove':
            class_days.pop(date_str, None)
        elif action in ['add', 'update'] and date_str:
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
    plan = get_object_or_404(SchedulePlan, pk=plan_id)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            topics_data = data.get('topics', {})
            med_teacher_val = data.get('med_teacher')

            class_days = plan.class_days or {}
            if isinstance(class_days, str):
                try:
                    class_days = json.loads(class_days)
                except json.JSONDecodeError:
                    class_days = {}

            # Сохраняем существующие метаданные
            med_days = class_days.get('_med_days', [])
            additional_dates = class_days.get('_additional_dates', [])
            excluded_dates = class_days.get('_excluded_dates', [])

            for date_str, subjects in topics_data.items():
                if not isinstance(date_str, str): continue
                if date_str not in class_days: class_days[date_str] = {}

                for subject, topic_map in subjects.items():
                    if not isinstance(topic_map, dict): continue
                    total = 0.0
                    cleaned = {}
                    for tid, h in topic_map.items():
                        try:
                            val = float(h)
                            if val > 0:
                                cleaned[str(tid)] = val
                                total += val
                        except (ValueError, TypeError):
                            continue
                    class_days[date_str][f'{subject}_topics'] = cleaned
                    class_days[date_str][subject] = total

            class_days['_category'] = data.get('category') or class_days.get('_category', '')
            class_days['_time_start'] = data.get('time_start') or class_days.get('_time_start', '09:00')
            class_days['_time_end'] = data.get('time_end') or class_days.get('_time_end', '17:00')
            class_days['_med_days'] = med_days
            class_days['_additional_dates'] = additional_dates
            class_days['_excluded_dates'] = excluded_dates

            # 🔹 Обновляем преподавателя ТОЛЬКО если значение явно передано
            if med_teacher_val is not None:
                if str(med_teacher_val).isdigit():
                    plan.med_teacher_id = int(med_teacher_val)
                else:
                    plan.med_teacher = None

            plan.class_days = class_days
            plan.save(update_fields=['class_days', 'med_teacher'])
            return JsonResponse({'success': True})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    # =========================================================================
    # GET
    # =========================================================================
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

    time_start = class_days.get('_time_start', '09:00')
    time_end = class_days.get('_time_end', '17:00')
    saved_category = class_days.get('_category', '') or (
        plan.group.category.code if plan.group and plan.group.category else '')

    med_days = class_days.get('_med_days', [])
    if not med_days:
        med_days = [d for d, data in class_days.items() if not d.startswith('_') and data.get('med', 0) > 0]

    selected_program_id = request.GET.get('program_id')
    training_program = None
    if selected_program_id:
        try:
            training_program = TrainingProgram.objects.get(pk=selected_program_id)
        except TrainingProgram.DoesNotExist:
            pass
    if not training_program and saved_category:
        training_program = TrainingProgram.objects.filter(categories__code=saved_category).prefetch_related(
            'subjects__subject').first()

    # 🔹 Формирование списка предметов
    program_subjects = []
    if training_program:
        exam_item = None
        other_subjects = []
        for ps in training_program.subjects.select_related('subject').order_by('subject__short_name'):
            item = {
                'code': ps.subject.short_name,
                'short_display': ps.subject.short_name_display or ps.subject.short_name.upper(),
                'full_name': ps.subject.name,
                'hours': float(ps.hours),
            }
            if ps.subject.short_name == 'exam':
                exam_item = item
            else:
                other_subjects.append(item)
        program_subjects = other_subjects + ([exam_item] if exam_item else [])

    # 🔹 Сбор всех дат для отображения
    all_dates = set()
    for d in class_days.keys():
        if isinstance(d, str) and not d.startswith('_'):
            all_dates.add(d)
    additional_dates = class_days.get('_additional_dates', [])
    if isinstance(additional_dates, list):
        all_dates.update(additional_dates)
    excluded_dates = class_days.get('_excluded_dates', [])
    if isinstance(excluded_dates, list):
        for d in excluded_dates:
            all_dates.discard(d)

    days_by_month = defaultdict(list)
    ru_months = {'January': 'Январь', 'February': 'Февраль', 'March': 'Март', 'April': 'Апрель', 'May': 'Май',
                 'June': 'Июнь', 'July': 'Июль', 'August': 'Август', 'September': 'Сентябрь', 'October': 'Октябрь',
                 'November': 'Ноябрь', 'December': 'Декабрь'}

    for date_str in sorted(list(all_dates)):
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            month_name = ru_months.get(date_obj.strftime('%B'), date_obj.strftime('%B'))
            day_data = class_days.get(date_str, {})
            day_info = {'day_num': date_obj.strftime('%d'), 'raw_date': date_str}
            for ps in program_subjects:
                day_info[ps['code']] = day_data.get(ps['code'], '')
            days_by_month[month_name].append(day_info)
        except (ValueError, TypeError):
            continue

    required_hours = float(training_program.total_hours) if training_program else float(plan.required_hours or 0)
    defaults = {item['code']: item['hours'] for item in program_subjects}
    subjects_list = [(item['code'], item['short_display']) for item in program_subjects]

    topics_state = {}
    for date_str, day_data in class_days.items():
        if not isinstance(date_str, str) or date_str.startswith('_'): continue
        for key, value in day_data.items():
            if key.endswith('_topics') and isinstance(value, dict):
                topics_state.setdefault(date_str, {})[key.replace('_topics', '')] = {str(k): float(v) for k, v in
                                                                                     value.items()}

    return render(request, 'groups/schedule_plan_step2.html', {
        'plan': plan, 'days_by_month': dict(days_by_month), 'plan_year': plan.date_start.year,
        'required_hours': required_hours, 'title': 'Подтверждение план-графика',
        'location': plan.location or '', 'med_teacher': plan.med_teacher,
        'time_start': time_start, 'time_end': time_end,
        'categories': list(GroupCategory.objects.values_list('code', 'description')),
        'current_category': saved_category, 'subjects': subjects_list, 'defaults': defaults,
        'topics_state_json': json.dumps(topics_state, default=str),
        'training_program': training_program, 'program_subjects': program_subjects,
        'available_programs': TrainingProgram.objects.all().order_by('name'),
        'training_program_id': training_program.id if training_program else None,
        'med_days': med_days,
    })


# =============================================================================
# 🔹 Удаление план-графика
# =============================================================================
@login_required
def schedule_plan_delete(request, plan_id):
    plan = get_object_or_404(SchedulePlan, pk=plan_id)
    if plan.created_by != request.user and not request.user.is_superuser:
        messages.error(request, ' У вас нет прав для удаления этого план-графика.')
        return redirect('groups:schedule_plans_list')
    group_number = plan.group.group_number
    plan.delete()
    messages.success(request, f'✅ План-график для группы "{group_number}" удалён.')
    return redirect('groups:schedule_plans_list')


# =============================================================================
# 🔹 Сброс таблицы распределения (Step 2)
# =============================================================================
@login_required
def schedule_plan_reset(request, plan_id):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    plan = get_object_or_404(SchedulePlan, pk=plan_id)
    if plan.created_by != request.user and not request.user.is_superuser:
        return JsonResponse({'error': 'Недостаточно прав'}, status=403)
    try:
        class_days = plan.class_days or {}
        if isinstance(class_days, str): class_days = json.loads(class_days)
        cleaned = {}
        for d, data in class_days.items():
            if d.startswith('_'):
                cleaned[d] = data
            elif isinstance(data, dict):
                cleaned[d] = {'scheduled': data.get('scheduled', False)}
        plan.class_days = cleaned
        plan.save(update_fields=['class_days'])
        return JsonResponse({'success': True, 'message': 'Часы очищены', 'action': 'hours_cleared'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=400)