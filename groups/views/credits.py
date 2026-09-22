# groups/views/credits.py
import json
import re
import csv
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect

from groups.models import Group, CreditResult, ExamResult
from reference.models import Credit
from students.models import Student
from teachers.models import Teacher


def _parse_credit_comment(comment):
    """Парсит комментарий: 'Попытка №2, Тип: paid | Текст'"""
    if not comment:
        return {'attempt_num': 0, 'attempt_type': 'free', 'user_comment': ''}

    parts = comment.split(' | ', 1)
    meta = parts[0]
    user_comment = parts[1] if len(parts) > 1 else ''

    match = re.search(r'Попытка №(\d+)', meta)
    attempt_num = int(match.group(1)) if match else 0
    attempt_type = 'paid' if 'Тип: paid' in meta else 'free'

    return {
        'attempt_num': attempt_num,
        'attempt_type': attempt_type,
        'user_comment': user_comment.strip()
    }


@login_required
def credits_exams_dashboard(request):
    """Матрица прогресса: студенты × зачёты + экзамены"""
    groups = Group.objects.filter(status='active').order_by('group_number')

    # 🔹 Фильтры
    group_id = request.GET.get('group', '')
    search = request.GET.get('search', '').strip()

    students_qs = Student.objects.select_related('group').order_by('last_name', 'first_name')
    if group_id and group_id.isdigit():
        students_qs = students_qs.filter(group_id=group_id)
    if search:
        students_qs = students_qs.filter(
            Q(last_name__icontains=search) | Q(first_name__icontains=search)
        )

    # 🔹 ДИНАМИЧЕСКИ получаем все зачёты и экзамены (без тематического контроля)
    all_credits = Credit.objects.exclude(credit_type='control').order_by('credit_type', 'number')

    # 🔹 РАЗДЕЛЯЕМ зачёты и экзамены по credit_type (строка, не boolean!)
    regular_credits = all_credits.filter(credit_type='credit')
    exam_credits = all_credits.filter(credit_type='exam')

    credit_numbers = [c.number for c in regular_credits]
    credit_topics = {c.number: c.topic for c in regular_credits}

    exam_numbers = [c.number for c in exam_credits]
    exam_topics = {c.number: c.topic for c in exam_credits}

    student_ids = list(students_qs.values_list('id', flat=True))
    if not student_ids:
        return render(request, 'groups/credits_exams.html', {
            'groups': groups,
            'students': [],
            'selected_group': group_id,
            'search': search,
            'credit_numbers': credit_numbers,
            'credit_topics': credit_topics,
            'exam_numbers': exam_numbers,
            'exam_topics': exam_topics,
        })

    # 🔹 Оптимизация: одна выборка всех попыток (только зачёты)
    all_attempts = CreditResult.objects.filter(
        student_id__in=student_ids,
        credit__number__in=credit_numbers
    ).select_related('credit').order_by('student_id', 'credit__number', 'credit_date', 'id')

    # Группировка в Python
    attempts_by_key = defaultdict(list)
    for att in all_attempts:
        attempts_by_key[(att.student_id, att.credit.number)].append(att)

    #  Получаем результаты экзаменов (тоже из CreditResult!)
    exam_results = {}
    all_exam_attempts = CreditResult.objects.filter(
        student_id__in=student_ids,
        credit__number__in=exam_numbers,
        credit__credit_type='exam'  # ← ВАЖНО: фильтруем только экзамены!
    ).select_related('credit').order_by('student_id', 'credit__number', 'credit_date', 'id')

    for att in all_exam_attempts:
        #  ИСПОЛЬЗУЕМ УНИКАЛЬНЫЙ КЛЮЧ С ТИПОМ
        key = (att.student_id, 'exam', att.credit.number)
        if key not in exam_results:
            exam_results[key] = []
        exam_results[key].append(att)

    # 🔹 Формирование данных для шаблона
    students_data = []
    for s in students_qs:
        # 🔹 Зачёты
        credits_status = []
        for num in credit_numbers:
            key = (s.id, num)
            attempts_list = attempts_by_key.get(key, [])
            topic = credit_topics.get(num, f'Зачёт №{num}')

            if attempts_list:
                last = attempts_list[-1]
                icon = '✅' if last.status == 'passed' else '❌'

                attempts_for_tooltip = []
                for att in attempts_list:
                    parsed = _parse_credit_comment(att.comment)
                    attempts_for_tooltip.append({
                        'num': parsed['attempt_num'],
                        'icon': '✅' if att.status == 'passed' else '❌',
                        'type': 'Платная' if parsed['attempt_type'] == 'paid' else 'Бесплатная',
                        'date': att.credit_date.strftime('%d.%m.%Y') if att.credit_date else '—'
                    })
                attempts_for_tooltip.sort(key=lambda x: x['num'])

                credits_status.append({
                    'num': num,
                    'status': last.status,
                    'icon': icon,
                    'topic': topic,
                    'attempts': attempts_for_tooltip
                })
            else:
                credits_status.append({
                    'num': num,
                    'status': 'none',
                    'icon': '—',
                    'topic': topic,
                    'attempts': []
                })

        #  Экзамены
        exams_status = []
        for num in exam_numbers:
            #  ИСПОЛЬЗУЕМ УНИКАЛЬНЫЙ КЛЮЧ: (student_id, 'exam', num)
            # Вместо (student_id, num), чтобы не путать с зачётами
            key = (s.id, 'exam', num)
            attempts_list = exam_results.get(key, [])
            topic = exam_topics.get(num, f'Экзамен №{num}')

            if attempts_list:
                last = attempts_list[-1]
                icon = '✅' if last.status == 'passed' else '❌'

                attempts_for_tooltip = []
                for att in attempts_list:
                    parsed = _parse_credit_comment(att.comment)
                    attempts_for_tooltip.append({
                        'num': parsed['attempt_num'],
                        'icon': '✅' if att.status == 'passed' else '❌',
                        'type': 'Платная' if parsed['attempt_type'] == 'paid' else 'Бесплатная',
                        'date': att.credit_date.strftime('%d.%m.%Y') if att.credit_date else '—'
                    })
                attempts_for_tooltip.sort(key=lambda x: x['num'])

                exams_status.append({
                    'num': num,
                    'status': last.status,
                    'icon': icon,
                    'topic': topic,
                    'attempts': attempts_for_tooltip
                })
            else:
                exams_status.append({
                    'num': num,
                    'status': 'none',
                    'icon': '—',
                    'topic': topic,
                    'attempts': []
                })
        students_data.append({
            'id': s.id,
            'full_name': s.full_name,
            'group_number': str(s.group) if s.group else '—',
            'group_id': s.group_id,
            'credits': credits_status,
            'exams': exams_status,
        })

    context = {
        'groups': groups,
        'students': students_data,
        'selected_group': group_id,
        'search': search,
        'credit_numbers': credit_numbers,
        'credit_topics': credit_topics,
        'exam_numbers': exam_numbers,
        'exam_topics': exam_topics,
    }
    return render(request, 'groups/credits_exams.html', context)


@login_required
def credits_exams_add(request):
    """Форма добавления результатов зачётов"""
    teachers = Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name')
    groups = Group.objects.filter(status='active').order_by('group_number')
    students = Student.objects.select_related('group').order_by('last_name', 'first_name')
    # Исключаем тематический контроль (он добавляется из путевого листа)
    credits = Credit.objects.select_related('category').exclude(credit_type='control').order_by('credit_type', 'number')

    # Предзагрузка количества попыток
    attempts_counts = CreditResult.objects.filter(
        student_id__in=[s.id for s in students],
        credit_id__in=[c.id for c in credits]
    ).values('student_id', 'credit_id').annotate(count=Count('id'))

    attempts_data = {s.id: {} for s in students}
    for row in attempts_counts:
        attempts_data[row['student_id']][row['credit_id']] = row['count']

    students_json = json.dumps([
        {'id': s.id, 'name': s.full_name, 'group_id': s.group_id, 'attempts': attempts_data.get(s.id, {})}
        for s in students
    ])

    # JSON с информацией о категориях тем зачётов (для фильтрации на клиенте)
    credits_categories_json = json.dumps([
        {'id': c.id, 'number': c.number, 'topic': c.topic, 'category_code': c.category.code if c.category else ''}
        for c in credits
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

                    attempt_num = CreditResult.objects.filter(
                        student_id=sid, credit_id=credit_id
                    ).count()

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

                    # Лог в activity_log
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
        'credits_categories_json': credits_categories_json,
        'title': 'Добавить результаты зачётов',
    }
    return render(request, 'groups/credits_exams_add.html', context)


@login_required
def credits_report(request):
    """Отчёт по зачётам с фильтрами и экспортом"""
    groups = Group.objects.filter(status='active').order_by('group_number')
    credits = Credit.objects.order_by('number')

    # Фильтры
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

    # Экспорт в CSV
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
            parsed = _parse_credit_comment(r.comment)
            members = [str(m) for m in [r.member1, r.member2, r.member3] if m]
            writer.writerow([
                r.credit_date.strftime('%d.%m.%Y'),
                r.student.group.group_number if r.student.group else '—',
                r.student.full_name,
                r.credit.number,
                r.credit.topic,
                parsed['attempt_num'],
                'Платная' if parsed['attempt_type'] == 'paid' else 'Бесплатная',
                '✅ Сдал' if r.status == 'passed' else '❌ Не сдал',
                str(r.chairman) if r.chairman else '—',
                ', '.join(members) if members else '—',
                parsed['user_comment'] or '—'
            ])
        return response

    # Данные для HTML-таблицы
    report_data = []
    for r in results:
        parsed = _parse_credit_comment(r.comment)
        report_data.append({
            'result': r,
            'attempt_num': parsed['attempt_num'],
            'attempt_type': parsed['attempt_type'],
            'user_comment': parsed['user_comment']
        })

    # Статистика
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