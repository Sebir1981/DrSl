# reports/views.py
import csv
import re
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from groups.models import CreditResult
from reference.models import Credit
from groups.models import Group


def parse_credit_comment(comment):
    """Парсит комментарий вида 'Попытка №2, Тип: paid | Текст пользователя'"""
    if not comment:
        return {'attempt_num': 0, 'attempt_type': 'free', 'user_comment': ''}

    # Разделяем по ' | ' если есть пользовательский комментарий
    parts = comment.split(' | ', 1)
    meta = parts[0]  # "Попытка №2, Тип: paid"
    user_comment = parts[1] if len(parts) > 1 else ''

    # Извлекаем номер попытки
    match = re.search(r'Попытка №(\d+)', meta)
    attempt_num = int(match.group(1)) if match else 0

    # Извлекаем тип
    attempt_type = 'paid' if 'Тип: paid' in meta else 'free'

    return {
        'attempt_num': attempt_num,
        'attempt_type': attempt_type,
        'user_comment': user_comment.strip()
    }


@login_required
def reports_dashboard(request):
    """Панель отчётов — список доступных разделов"""
    context = {
        'title': '📊 Отчёты',
        'sections': [
            {
                'name': 'Зачёты',
                'url': 'reports:credits',
                'icon': '📋',
                'description': 'Статистика и детализация по сдаче зачётов'
            },
        ]
    }
    return render(request, 'reports/dashboard.html', context)


@login_required
def credits_report(request):
    """Отчёт по зачётам с фильтрами и экспортом"""

    groups = Group.objects.filter(status='active').order_by('group_number')
    credits = Credit.objects.order_by('number')

    # 🔹 Фильтры
    group_id = request.GET.get('group')
    credit_id = request.GET.get('credit')
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    # 🔹 Базовый запрос
    results = CreditResult.objects.select_related(
        'student', 'student__group', 'credit', 'chairman', 'member1', 'member2', 'member3'
    ).order_by('-credit_date')

    # 🔹 Применяем фильтры
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

    # 🔹 Экспорт в CSV
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="zachety_report.csv"'
        response.write('\ufeff'.encode('utf8'))  # BOM для Excel

        writer = csv.writer(response, delimiter=';')
        writer.writerow([
            'Дата', 'Группа', 'ФИО учащегося', 'Зачёт №', 'Тема',
            'Попытка №', 'Тип', 'Статус', 'Председатель', 'Члены комиссии', 'Комментарий'
        ])

        for r in results:
            parsed = parse_credit_comment(r.comment)
            members = [str(m) for m in [r.member1, r.member2, r.member3] if m]
            members_str = ', '.join(members) if members else '—'

            writer.writerow([
                r.credit_date.strftime('%d.%m.%Y'),
                r.student.group.group_number if r.student.group else '—',
                r.student.full_name,
                r.credit.number,
                r.credit.topic,
                parsed['attempt_num'],  # ✅ Реальный номер из записи
                'Платная' if parsed['attempt_type'] == 'paid' else 'Бесплатная',
                '✅ Сдал' if r.status == 'passed' else '❌ Не сдал',
                str(r.chairman) if r.chairman else '—',
                members_str,
                parsed['user_comment'] or '—'  # ✅ Только пользовательский комментарий
            ])

        return response

    # 🔹 Парсим комментарии для отображения в таблице
    report_data = []
    for r in results:
        parsed = parse_credit_comment(r.comment)
        report_data.append({
            'result': r,
            'attempt_num': parsed['attempt_num'],
            'attempt_type': parsed['attempt_type'],
            'user_comment': parsed['user_comment']
        })

    # 🔹 Статистика
    total = len(report_data)
    passed = sum(1 for d in report_data if d['result'].status == 'passed')
    failed = sum(1 for d in report_data if d['result'].status == 'failed')
    success_rate = round(passed / total * 100) if total > 0 else 0

    context = {
        'groups': groups,
        'credits': credits,
        'results': report_data,  # ✅ Передаём распарсенные данные
        'selected_group': group_id,
        'selected_credit': credit_id,
        'selected_status': status,
        'date_from': date_from,
        'date_to': date_to,
        'stats': {'total': total, 'passed': passed, 'failed': failed, 'success_rate': success_rate},
        'title': '📋 Отчёт по зачётам',
    }
    return render(request, 'reports/credits.html', context)