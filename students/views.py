# students/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Q
from django.http import JsonResponse

from .models import Student, StudentHistory
from groups.models import Group
from teachers.models import Teacher
from .forms import DismissalForm, RefusalForm, SuspensionForm
from masters.models import Master

# ✅ 0. Создание карточки учащегося
@login_required
def student_add(request):
    """Фронтенд-страница добавления учащегося"""

    if request.method == 'POST':
        # 🔹 Сбор данных из формы
        last_name = request.POST.get('last_name', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        patronymic = request.POST.get('patronymic', '').strip()
        phone = request.POST.get('phone', '').strip()
        birth_date = request.POST.get('birth_date') or None
        place_of_birth = request.POST.get('place_of_birth', '').strip()
        place_of_residence = request.POST.get('place_of_residence', '').strip()
        place_of_registration = request.POST.get('place_of_registration', '').strip()
        work_study_place = request.POST.get('work_study_place', '').strip()
        position = request.POST.get('position', '').strip()

        # 🔹 Связи
        group_id = request.POST.get('group')
        teacher_id = request.POST.get('teacher')
        master_id = request.POST.get('master')
        gearbox_type = request.POST.get('gearbox_type', '')
        enrolled_date = request.POST.get('enrolled_date') or timezone.now().date()

        # 🔹 Валидация
        if not last_name or not first_name:
            messages.error(request, '❌ Фамилия и имя обязательны для заполнения')
            return redirect('students:student_add')

        # 🔹 Создание записи
        student = Student.objects.create(
            last_name=last_name,
            first_name=first_name,
            patronymic=patronymic,
            phone=phone,
            birth_date=birth_date,
            place_of_birth=place_of_birth,
            place_of_residence=place_of_residence,
            place_of_registration=place_of_registration,
            work_study_place=work_study_place,
            position=position,
            group_id=group_id if group_id and group_id.isdigit() else None,
            teacher_id=teacher_id if teacher_id and teacher_id.isdigit() else None,
            master_id=master_id if master_id and master_id.isdigit() else None,
            gearbox_type=gearbox_type,
            enrolled_date=enrolled_date,
        )

        # 🔹 Лог в activity_log
        log_entry = {
            'type': 'enrollment',
            'date': enrolled_date.strftime('%d.%m.%Y') if enrolled_date else timezone.now().date().strftime('%d.%m.%Y'),
            'title': 'Зачисление в автошколу',
            'details': {
                'group': str(student.group) if student.group else '—',
                'teacher': str(student.teacher) if student.teacher else '—',
            }
        }
        student.activity_log = [log_entry]
        student.save(update_fields=['activity_log'])

        messages.success(request, f'✅ Учащийся {last_name} {first_name} добавлен!')
        return redirect('students:student_detail', student_id=student.pk)

    # 🔹 GET-запрос: подготовка данных для формы
    groups = Group.objects.filter(status='active').order_by('group_number')
    teachers = Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name')
    masters = Master.objects.all().order_by('last_name', 'first_name')

    context = {
        'title': '➕ Добавить учащегося',
        'groups': groups,
        'teachers': teachers,
        'masters': masters,
        'today': timezone.now().date(),
    }
    return render(request, 'students/student_add.html', context)


# ✅ 1. Панель управления разделом "Учащиеся"
@login_required
def students_dashboard(request):
    context = {'total_students': Student.objects.count()}
    return render(request, 'students/dashboard.html', context)


# ✅ 2. Список учащихся с фильтрами и поиском
@login_required
def student_list(request):
    students = Student.objects.select_related('group', 'teacher', 'master').all()

    search_query = request.GET.get('search', '').strip()
    if search_query:
        students = students.filter(
            Q(last_name__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(patronymic__icontains=search_query)
        )

    group_filter = request.GET.get('group')
    if group_filter:
        if group_filter.isdigit():
            students = students.filter(group_id=group_filter)
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

    # 🔹 Подготовка данных для шаблона
    students_data = []
    for s in students:
        # 🔹 Статус: только Активен/Приостановлен/Отказ/Отчислен/Выпуск (без "Переведён")
        status = 'Активен'
        status_color = '#16a34a'  # зелёный

        if s.graduated_date:
            status = 'Выпуск'
            status_color = '#0ea5e9'  # голубой
        elif s.activity_log:
            # Ищем последнее событие, влияющее на статус (transfer НЕ считается)
            for event in reversed(s.activity_log):
                etype = event.get('type', '')
                if etype in ['dismissal', 'dismissed']:
                    status = 'Отчислен'
                    status_color = '#dc2626'  # красный
                    break
                elif etype in ['refusal', 'refused']:
                    status = 'Отказ'
                    status_color = '#f59e0b'  # оранжевый
                    break
                elif etype in ['suspension', 'suspended']:
                    status = 'Приостановлен'
                    status_color = '#7c3aed'  # фиолетовый
                    break
                # 🔹 transfer, activation и другие — не меняют статус, просто пропускаем

        # 🔹 ФИО преподавателя (короткий формат)
        teacher_name = '—'
        if s.teacher:
            teacher_name = f"{s.teacher.last_name} {s.teacher.first_name[:1]}."
            if s.teacher.patronymic:
                teacher_name += f"{s.teacher.patronymic[:1]}."

        students_data.append({
            'student': s,
            'status': status,
            'status_color': status_color,
            'teacher_name': teacher_name,
        })

    context = {
        'students': students_data,  # ✅ Передаём подготовленные данные
        'groups': groups,
        'teachers': teachers,
        'selected_group': group_filter,
        'selected_teacher': teacher_filter,
        'search_query': search_query,
        'debug': True,
    }
    return render(request, 'students/student_list.html', context)


# ✅ 3. Карточка учащегося
@login_required
def student_detail(request, student_id):
    student = get_object_or_404(
        Student.objects.select_related('group', 'group__category', 'teacher', 'master'),
        pk=student_id
    )
    activity_log = student.activity_log or []

    # 🔹 НОРМАЛИЗАЦИЯ ДАТ: приводим все даты к формату дд.мм.гггг
    for entry in activity_log:
        date_str = entry.get('date', '')
        # Если дата в формате 'YYYY-MM-DD' (старые записи)
        if date_str and len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
            parts = date_str.split('-')
            entry['date'] = f"{parts[2]}.{parts[1]}.{parts[0]}"  # → 'дд.мм.гггг'

    # 🔹 Подготовка данных по ВСЕМ 6 зачётам
    credits_data = []
    for num in range(1, 7):
        attempts = []
        for entry in activity_log:
            if entry.get('type') == 'credit_result':
                title = entry.get('title', '')
                if f'Зачёт №{num}' in title or f'Зачёт №{num}:' in title:
                    attempts.append({
                        'date': entry.get('date'),  # ✅ Уже в формате дд.мм.гггг
                        'icon': entry['details'].get('result_icon', '—'),
                        'status': entry['details'].get('result', ''),
                        'attempt_num': entry['details'].get('attempt_number', 0),
                        'type': entry['details'].get('attempt_type', '')
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

    # 🔹 Последний перевод
    last_transfer = None
    for entry in reversed(activity_log):
        if entry.get('type') == 'transfer':
            last_transfer = entry
            break

    # 🔹 История изменений для выпадающего меню
    change_history = []
    for entry in reversed(activity_log):
        etype = entry.get('type')
        if etype == 'transfer':
            change_history.append({
                'date': entry.get('date'),  # ✅ Уже в формате дд.мм.гггг
                'field': 'Группа',
                'old': entry['details'].get('from_group'),
                'new': entry['details'].get('to_group')
            })
        elif etype == 'teacher_change':
            change_history.append({
                'date': entry.get('date'),  # ✅ Уже в формате дд.мм.гггг
                'field': 'Преподаватель',
                'old': entry['details'].get('from'),
                'new': entry['details'].get('to')
            })

    context = {
        'student': student,
        'activity_log': activity_log,
        'credits_data': credits_data,
        'last_transfer': last_transfer,
        'change_history': change_history,
        'title': f'🎓 {student.full_name}',
    }
    return render(request, 'students/student_detail.html', context)

# ✅ 4. Перевод в другую группу
@login_required
def transfer_student(request, student_id):
    student = get_object_or_404(Student.objects.select_related('group'), pk=student_id)
    groups = Group.objects.filter(status='active').order_by('group_number')

    if request.method == 'POST':
        target_group_id = request.POST.get('target_group')
        if not target_group_id:
            messages.error(request, 'Выберите группу для перевода.')
        else:
            target_group = get_object_or_404(Group, pk=target_group_id)
            if target_group == student.group:
                messages.warning(request, 'Учащийся уже находится в этой группе.')
            else:
                old_group = student.group
                transfer_date = timezone.now().date()

                student.group = target_group
                student.transferred_date = transfer_date

                transfer_log_entry = {
                    'type': 'transfer',
                    'date': transfer_date.strftime('%d.%m.%Y'),
                    'title': f"Перевод в группу {target_group.group_number}",
                    'details': {
                        'from_group': str(old_group) if old_group else '—',
                        'to_group': str(target_group.group_number),
                    }
                }

                current_log = student.activity_log or []
                current_log.append(transfer_log_entry)
                current_log.sort(key=lambda x: x.get('date', ''))
                student.activity_log = current_log

                student.save(update_fields=['group', 'transferred_date', 'activity_log', 'updated_at'])

                messages.success(request, f'✅ Учащийся успешно переведён в группу {target_group.group_number}.')
                return redirect('students:student_detail', student_id=student.pk)

    return render(request, 'students/transfer_student.html', {
        'student': student,
        'groups': groups,
        'today': timezone.now().date()
    })


# ✅ 5. Отказ от обучения
@login_required
def student_refusal(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    if request.method == 'POST':
        form = RefusalForm(request.POST)
        refusal_date = request.POST.get('refusal_date')

        if not refusal_date:
            messages.error(request, '⚠️ Укажите дату отказа.')
        elif form.is_valid():
            history = form.save(commit=False)
            history.student = student
            history.event_type = 'refused'
            history.created_by = request.user
            history.event_date = parse_date(refusal_date)
            history.save()

            refusal_entry = {
                'type': 'refusal',
                'date': history.event_date.strftime(
                    '%d.%m.%Y') if history.event_date else timezone.now().date().strftime('%d.%m.%Y'),
                'title': 'Отказ от обучения',
                'details': {'comment': history.comment or ''}
            }
            current_log = student.activity_log or []
            current_log.append(refusal_entry)
            current_log.sort(key=lambda x: x.get('date', ''))
            student.activity_log = current_log
            student.save(update_fields=['activity_log', 'updated_at'])

            messages.success(request, f"✅ Зафиксирован отказ: {student.last_name} {student.first_name}")
            return redirect('students:student_detail', student_id=student.id)
    else:
        form = RefusalForm()

    return render(request, 'students/student_refusal.html', {
        'student': student,
        'form': form,
        'title': 'Отказ от обучения'
    })


# ✅ 6. Приостановка обучения
@login_required
def student_suspension(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    if request.method == 'POST':
        form = SuspensionForm(request.POST)
        if form.is_valid():
            history = form.save(commit=False)
            history.student = student
            history.event_type = 'suspended'
            history.created_by = request.user
            history.event_date = form.cleaned_data.get('suspension_start')

            end_date = form.cleaned_data.get('suspension_end')
            if end_date:
                if history.comment:
                    history.comment = f"{history.comment} [до {end_date.strftime('%d.%m.%Y')}]".strip()
                else:
                    history.comment = f"До {end_date.strftime('%d.%m.%Y')}"
            history.save()

            suspension_entry = {
                'type': 'suspension',
                'date': history.event_date.strftime(
                    '%d.%m.%Y') if history.event_date else timezone.now().date().strftime('%d.%m.%Y'),
                'title': 'Приостановка обучения',
                'details': {
                    'comment': history.comment or '',
                    'end_date': end_date.strftime('%d.%m.%Y') if end_date else None,
                }
            }
            current_log = student.activity_log or []
            current_log.append(suspension_entry)
            current_log.sort(key=lambda x: x.get('date', ''))
            student.activity_log = current_log
            student.save(update_fields=['activity_log', 'updated_at'])

            messages.success(request, f"✅ Обучение приостановлено: {student.last_name} {student.first_name}")
            return redirect('students:student_detail', student_id=student.id)
    else:
        form = SuspensionForm()

    return render(request, 'students/student_suspension.html', {
        'student': student,
        'form': form,
        'title': 'Приостановка обучения'
    })


# ✅ 7. Отчисление учащегося
@login_required
def student_dismissal(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    if request.method == 'POST':
        form = DismissalForm(request.POST)
        if form.is_valid():
            history = form.save(commit=False)
            history.student = student
            history.event_type = 'dismissed'
            history.created_by = request.user
            history.save()

            dismissal_entry = {
                'type': 'dismissal',
                'date': history.event_date.strftime(
                    '%d.%m.%Y') if history.event_date else timezone.now().date().strftime('%d.%m.%Y'),
                'title': f"Отчисление: приказ №{history.order_number or '—'}",
                'details': {
                    'order_number': history.order_number,
                    'comment': history.comment or '',
                }
            }
            current_log = student.activity_log or []
            current_log.append(dismissal_entry)
            current_log.sort(key=lambda x: x.get('date', ''))
            student.activity_log = current_log
            student.save(update_fields=['activity_log', 'updated_at'])

            messages.success(request,
                             f"✅ {student.last_name} {student.first_name} отчислен. Приказ №{history.order_number}")
            return redirect('students:student_detail', student_id=student.id)
    else:
        form = DismissalForm()

    return render(request, 'students/student_dismissal.html', {
        'student': student,
        'form': form,
        'title': 'Отчисление учащегося'
    })


# ✅ 8. Активация учащегося
@login_required
def student_activate(request, student_id):
    student = get_object_or_404(Student, pk=student_id)

    StudentHistory.objects.create(
        student=student,
        event_type='activated',
        event_date=timezone.now().date(),
        comment='Возврат в активное состояние',
        created_by=request.user
    )

    activation_entry = {
        'type': 'activation',
        'date': timezone.now().date().strftime('%d.%m.%Y'),
        'title': 'Активация учащегося',
        'details': {'comment': 'Возврат в активное состояние'}
    }
    current_log = student.activity_log or []
    current_log.append(activation_entry)
    current_log.sort(key=lambda x: x.get('date', ''))
    student.activity_log = current_log
    student.save(update_fields=['activity_log', 'updated_at'])

    messages.success(request, f"✅ {student.last_name} {student.first_name} активирован")
    return redirect('students:student_detail', student_id=student.id)


# ✅ 9. AJAX: Автоподсказки по фамилии
@login_required
def surname_suggestions(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'suggestions': []})

    suggestions = Student.objects.filter(
        last_name__istartswith=query
    ).values_list('last_name', flat=True).distinct()[:10]

    return JsonResponse({'suggestions': list(suggestions)})


# students/views.py (добавить в конец)

@login_required
def student_edit(request, student_id):
    """Фронтенд-страница редактирования учащегося"""
    student = get_object_or_404(Student, pk=student_id)

    if request.method == 'POST':
        # Обновляем поля из формы
        student.last_name = request.POST.get('last_name', '').strip()
        student.first_name = request.POST.get('first_name', '').strip()
        student.patronymic = request.POST.get('patronymic', '').strip()
        student.phone = request.POST.get('phone', '').strip()

        # Даты и адреса
        student.birth_date = request.POST.get('birth_date') or None
        student.place_of_birth = request.POST.get('place_of_birth', '').strip()
        student.place_of_residence = request.POST.get('place_of_residence', '').strip()
        student.place_of_registration = request.POST.get('place_of_registration', '').strip()
        student.work_study_place = request.POST.get('work_study_place', '').strip()
        student.position = request.POST.get('position', '').strip()

        # Связи
        group_id = request.POST.get('group')
        teacher_id = request.POST.get('teacher')
        master_id = request.POST.get('master')

        student.group_id = group_id if group_id and group_id.isdigit() else None
        student.teacher_id = teacher_id if teacher_id and teacher_id.isdigit() else None
        student.master_id = master_id if master_id and master_id.isdigit() else None

        student.gearbox_type = request.POST.get('gearbox_type', '')
        student.enrolled_date = request.POST.get('enrolled_date') or None

        student.save()
        messages.success(request, f'✅ Данные учащегося {student.last_name} обновлены!')
        return redirect('students:student_detail', student_id=student.pk)

    # GET-запрос: подготовка данных для формы
    groups = Group.objects.filter(status='active').order_by('group_number')
    teachers = Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name')
    masters = Master.objects.all().order_by('last_name', 'first_name')

    context = {
        'title': '✏️ Редактирование учащегося',
        'student': student,  # Передаем ученика, чтобы заполнить поля
        'groups': groups,
        'teachers': teachers,
        'masters': masters,
    }
    return render(request, 'students/student_edit.html', context)