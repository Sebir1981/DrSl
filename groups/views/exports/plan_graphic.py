import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from groups.models import SchedulePlan
from reference.models import TrainingProgram, ProgramSubject
from datetime import datetime, timedelta
from collections import defaultdict
import json
import re
from urllib.parse import quote

# 🔹 Принудительно русские месяца для заголовков таблицы
RU_MONTHS = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель', 5: 'Май', 6: 'Июнь',
    7: 'Июль', 8: 'Август', 9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
}


def _sanitize(name):
    """Очищает строку от недопустимых символов"""
    if not name:
        return ""
    return re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', str(name).strip()).replace(' ', '_')


def export_plan_graphic_to_excel(request, plan_id):
    """Экспорт План-графика (по дням, как на скриншоте)"""
    plan = get_object_or_404(SchedulePlan, pk=plan_id)
    group_category = getattr(plan.group, 'category', None)

    # --- Сбор данных ---
    class_days = plan.class_days or {}
    if isinstance(class_days, str):
        try:
            class_days = json.loads(class_days)
        except:
            class_days = {}

    # ✅ Берем из полей модели (ручные изменения через модальное окно)
    excluded_dates = plan.excluded_dates or []
    additional_dates = plan.additional_dates or []

    # Загрузка предметов (порядок: обычные по алфавиту + экзамен в конце)
    program_subjects = []
    program = TrainingProgram.objects.filter(categories=group_category).first() if group_category else None
    if program:
        exam_item = None
        other_subjects = []
        for ps in ProgramSubject.objects.filter(program=program, is_enabled=True).select_related('subject').order_by(
                'subject__short_name'):
            item = {
                'code': ps.subject.short_name.lower(),
                'display': ps.subject.short_name_display or ps.subject.short_name.upper(),
            }
            if ps.subject.short_name.lower() == 'exam':
                exam_item = item
            else:
                other_subjects.append(item)
        program_subjects = other_subjects + ([exam_item] if exam_item else [])

    # Диапазон дат
    days_in_schedule = []
    current_date = plan.date_start
    while current_date <= plan.date_end:
        days_in_schedule.append(current_date)
        current_date += timedelta(days=1)

    # --- Генерация Excel ---
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "План-график"

    font_small = Font(name='Arial Cyr', size=8)
    font_bold = Font(name='Arial Cyr', size=10, bold=True)
    font_title = Font(name='Arial Cyr', size=14, bold=True)
    thin_border = Border(left=Side('thin'), right=Side('thin'), top=Side('thin'), bottom=Side('thin'))
    align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    header_fill = PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid")

    # --- ШАПКА ---
    row = 1
    org_name = getattr(plan.group, 'organization_name', 'ООО "Своя автошкола"')
    ws.cell(row=row, column=1, value=org_name).font = font_bold

    ws.merge_cells(f'AB{row}:AM{row}')
    approve_cell = ws.cell(row=row, column=28, value='"УТВЕРЖДАЮ"')
    approve_cell.font = font_bold
    approve_cell.alignment = align_center
    row += 1

    ws.cell(row=row, column=28, value='Директор').font = font_bold
    row += 1
    ws.cell(row=row, column=28, value='_______________ В.В. Евтушков').font = font_bold
    row += 1

    ru_months_text = {1: 'января', 2: 'февраля', 3: 'марта', 4: 'апреля', 5: 'мая', 6: 'июня',
                      7: 'июля', 8: 'августа', 9: 'сентября', 10: 'октября', 11: 'ноября', 12: 'декабря'}
    date_str = f'"{plan.date_start.day:02d}" {ru_months_text[plan.date_start.month]} {plan.date_start.year} года'
    ws.cell(row=row, column=28, value=date_str).font = font_bold
    row += 2

    ws.merge_cells(f'A{row}:AM{row}')
    title_cell = ws.cell(row=row, column=1,
                         value='План - график выполнения единой программы подготовки водителей МТС категории "B"')
    title_cell.font = font_title
    title_cell.alignment = align_center
    row += 2

    ws.merge_cells(f'A{row}:AM{row}')
    group_num = getattr(plan.group, 'group_number', plan.group.id)
    ws.cell(row=row, column=1, value=f'учебная группа № {group_num}').font = font_bold
    ws.cell(row=row, column=1).alignment = align_center
    row += 2

    # --- Форматирование дат ---
    def format_dates_list(dates_list):
        if not dates_list: return "—"
        formatted = []
        for d in dates_list:
            try:
                val = datetime.strptime(d, '%Y-%m-%d').strftime('%d.%m.%Y') if isinstance(d, str) else d.strftime(
                    '%d.%m.%Y')
                formatted.append(val)
            except:
                pass
        return ', '.join(formatted) if formatted else "—"

    info_data = [
        ('Преподаватель', str(plan.teacher) if plan.teacher else '—'),
        ('Дни', str(plan.get_schedule_type_display())),
        ('Кроме', format_dates_list(excluded_dates)),
        ('Дополнительные дни', format_dates_list(additional_dates)),
        ('Время', f'{getattr(plan, "time_start", "09:00")} - {getattr(plan, "time_end", "17:00")}'),
        ('Место', getattr(plan, 'location', '—') or '—'),
    ]

    for label, value in info_data:
        ws.cell(row=row, column=1, value=label).font = font_bold
        ws.merge_cells(f'B{row}:AM{row}')
        val_cell = ws.cell(row=row, column=2, value=value)
        val_cell.font = font_small
        val_cell.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
        row += 1
    row += 1  # Отступ

    # --- ТАБЛИЦА ---
    months_data = defaultdict(list)
    month_order = []
    days_with_classes = []

    for d in days_in_schedule:
        date_key = d.strftime('%Y-%m-%d')
        if date_key not in class_days: continue

        day_data = class_days[date_key]
        # Сумма часов (исключая служебные поля и 'scheduled')
        day_sum = sum(v for k, v in day_data.items()
                      if not k.startswith('_') and not k.endswith('_topics') and k != 'scheduled'
                      and isinstance(v, (int, float)) and v > 0)

        if day_sum > 0:
            days_with_classes.append(d)
            m_label = f"{RU_MONTHS[d.month]} {d.year}"
            if m_label not in month_order: month_order.append(m_label)
            months_data[m_label].append(d)

    start_col = 1
    ws.cell(row=row, column=start_col, value='Дата/Тема').font = font_bold
    ws.cell(row=row, column=start_col).border = thin_border
    ws.cell(row=row, column=start_col).alignment = align_center

    current_col = start_col + 1
    col_map = {}

    for m_label in month_order:
        days = months_data[m_label]
        ws.merge_cells(start_row=row, start_column=current_col, end_row=row, end_column=current_col + len(days) - 1)
        month_cell = ws.cell(row=row, column=current_col, value=m_label)
        month_cell.font = font_bold
        month_cell.alignment = align_center
        month_cell.border = thin_border
        current_col += len(days)

    total_col_idx = current_col
    ws.cell(row=row, column=total_col_idx, value='ИТОГО').font = font_bold
    ws.cell(row=row, column=total_col_idx).alignment = align_center
    ws.cell(row=row, column=total_col_idx).border = thin_border
    row += 1

    # Дни
    current_col = start_col + 1
    for m_label in month_order:
        for d in months_data[m_label]:
            col_map[d] = current_col
            cell = ws.cell(row=row, column=current_col, value=d.day)
            cell.font = font_small
            cell.alignment = align_center
            cell.border = thin_border
            current_col += 1
    ws.cell(row=row, column=total_col_idx, value='').border = thin_border
    row += 1

    # Всего часов за день
    ws.cell(row=row, column=start_col, value='Всего').font = font_bold
    ws.cell(row=row, column=start_col).border = thin_border
    ws.cell(row=row, column=start_col).fill = header_fill

    for d in days_with_classes:
        if d in col_map:
            c_idx = col_map[d]
            day_sum = sum(v for k, v in class_days.get(d.strftime('%Y-%m-%d'), {}).items()
                          if not k.startswith('_') and not k.endswith('_topics') and k != 'scheduled'
                          and isinstance(v, (int, float)))
            cell = ws.cell(row=row, column=c_idx, value=int(day_sum) if day_sum == int(day_sum) else day_sum)
            cell.font = font_small
            cell.alignment = align_center
            cell.border = thin_border
            cell.fill = header_fill
    ws.cell(row=row, column=total_col_idx, value='').border = thin_border
    row += 1

    # Предметы
    for item in program_subjects:
        code, display_name = item['code'], item['display']
        ws.cell(row=row, column=start_col, value=display_name).font = font_small
        ws.cell(row=row, column=start_col).border = thin_border

        subject_total = 0
        for d in days_with_classes:
            if d in col_map:
                c_idx = col_map[d]
                h = class_days.get(d.strftime('%Y-%m-%d'), {}).get(code, 0)
                if not isinstance(h, (int, float)): h = 0

                cell = ws.cell(row=row, column=c_idx, value=int(h) if h > 0 and h == int(h) else (h if h > 0 else ''))
                cell.font = font_small
                cell.alignment = align_center
                cell.border = thin_border
                subject_total += h

        cell = ws.cell(row=row, column=total_col_idx,
                       value=int(subject_total) if subject_total == int(subject_total) else subject_total)
        cell.font = font_small
        cell.alignment = align_center
        cell.border = thin_border
        cell.fill = header_fill
        row += 1

    # --- Настройки печати ---
    ws.column_dimensions[get_column_letter(start_col)].width = 25
    for d in days_with_classes:
        if d in col_map: ws.column_dimensions[get_column_letter(col_map[d])].width = 4
    ws.column_dimensions[get_column_letter(total_col_idx)].width = 8

    ws.page_setup.orientation = 'landscape'
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_margins.left = ws.page_margins.right = ws.page_margins.top = ws.page_margins.bottom = 0.3

    # --- Имя файла ---
    t_name = _sanitize(str(plan.teacher)) if plan.teacher else "Без_преподавателя"
    location_raw = getattr(plan, 'location', '') or 'без_адреса'
    location_clean = _sanitize(location_raw) or 'без_адреса'
    sched_val = getattr(plan, 'schedule_type', None) or getattr(plan.group, 'schedule_type', None)
    sched_map = {'even': 'четная', 'odd': 'нечетная', 'evening': 'вечерняя', '1': 'четная', '2': 'нечетная',
                 '3': 'вечерняя'}
    sched_name = sched_map.get(str(sched_val).lower().strip(), "четная")

    filename = f"План-график_гр{_sanitize(group_num)}_{t_name}_{sched_name}_{location_clean}.xlsx"

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{quote(filename)}'
    wb.save(response)
    return response