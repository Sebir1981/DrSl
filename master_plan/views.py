# master_plan/views.py

import json
import logging
from datetime import datetime, date, timedelta

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.db.models import Sum, F, Count, Q
from django.db.models.functions import TruncDate

from .models import (
    MasterPlanGroup,
    MasterPlanDistribution,
    StudentMasterAssignment,
    StudentReassignmentLog,
)
from groups.models import Group
from masters.models import MasterPouts
from students.models import Student

logger = logging.getLogger(__name__)


# =========================================================================
# 🔹 КОНСТАНТЫ
# =========================================================================

# 🔥 Соответствие: Student.gearbox_type → Car.transmission
GEARBOX_MAP = {
    'manual': 'MT',
    'auto': 'AT',
    'electric': 'ET',
}


# =========================================================================
# 🔹 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================================

def parse_date(date_str):
    """Универсальный парсер дат. Поддерживает ДД.ММ.ГГГГ и ГГГГ-ММ-ДД."""
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    try:
        return datetime.strptime(date_str, '%d.%m.%Y').date()
    except ValueError:
        pass
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        pass
    logger.warning(f"Неверный формат даты: {date_str}")
    return None


def fmt_date(date_obj):
    """Форматирование даты в ДД.ММ.ГГГГ."""
    if not date_obj:
        return ''
    return date_obj.strftime('%d.%m.%Y')


def _resolve_master_from_value(master_val):
    """Преобразует значение из платной услуги 'Мастер по вождению' в ID мастера."""
    if not master_val:
        return None

    s = str(master_val).strip()
    if s.isdigit():
        if MasterPouts.objects.filter(pk=int(s)).exists():
            return int(s)
        logger.warning(f"Мастер с ID={s} не найден")
        return None

    last_name = s.split()[0] if s.split() else s
    master_obj = MasterPouts.objects.filter(last_name__iexact=last_name).first()
    if master_obj:
        return master_obj.id
    master_obj = MasterPouts.objects.filter(last_name__icontains=last_name).first()
    if master_obj:
        return master_obj.id

    logger.warning(f"Мастер '{master_val}' не найден")
    return None


def _extract_master_id_from_values(values):
    """Извлекает ID мастера из values платной услуги."""
    if not values:
        return None

    candidate = None

    for key in ('master', 'master_id', 'master-id'):
        if key in values and values[key]:
            candidate = values[key]
            break

    if candidate is None:
        for key, val in values.items():
            if isinstance(key, str) and key.startswith('select-master-') and val:
                candidate = val
                break

    if candidate is None:
        for key, val in values.items():
            if isinstance(key, str) and 'master' in key.lower() and val:
                candidate = val
                break

    if candidate is None:
        return None

    return _resolve_master_from_value(candidate)


def _extract_car_brand_from_values(values):
    """Извлекает марку автомобиля из values платной услуги."""
    if not values:
        return None

    for key in ('car_brand', 'brand', 'car-brand'):
        if key in values and values[key]:
            return values[key]

    for key, val in values.items():
        if not isinstance(key, str) or not val:
            continue
        low = key.lower()
        if low.startswith('select-brand-') or low.startswith('select-car-'):
            return val

    for key, val in values.items():
        if not isinstance(key, str) or not val:
            continue
        low = key.lower()
        if 'brand' in low or 'car' in low or 'марк' in low:
            return val

    return None


def _extract_gender_from_values(values):
    """Извлекает пол мастера из values платной услуги."""
    if not values:
        return None

    for key in ('gender', 'master_gender', 'sex'):
        if key in values and values[key]:
            val = str(values[key]).lower()
            if val in ('male', 'female'):
                return val

    for key, val in values.items():
        if not isinstance(key, str) or not val:
            continue
        low = key.lower()
        if 'gender' in low or 'sex' in low:
            v = str(val).lower()
            if v in ('male', 'female'):
                return v

    return None


def _get_student_service_prefs(student):
    """Извлекает из activity_log ВСЕ платные услуги студента."""
    prefs = {
        'master_id': None,
        'car_brand': None,
        'master_gender': None,
        'services': []
    }

    if not student.activity_log:
        return prefs

    service_state = {}

    for entry in student.activity_log:
        if entry.get('type') in ('service_added', 'service_updated'):
            details = entry.get('details', {})
            service_name = details.get('service_name', '')
            values = details.get('values', {})

            if service_name:
                service_state[service_name] = values

    for service_name, values in service_state.items():
        service_values = [f"{v}" for v in values.values() if v]

        if service_values:
            prefs['services'].append({
                'name': service_name,
                'values': ', '.join(service_values),
            })

        if service_name == 'Мастер по вождению':
            prefs['master_id'] = _extract_master_id_from_values(values)
        elif service_name == 'Марка автомобиля':
            prefs['car_brand'] = _extract_car_brand_from_values(values)
        elif service_name == 'Пол мастера':
            prefs['master_gender'] = _extract_gender_from_values(values)

    return prefs


# =========================================================================
# 🔹 АВТОРАСПРЕДЕЛЕНИЕ И ПЕРЕСЧЁТ АГРЕГАТА
# =========================================================================

def _auto_assign_masters_from_services(plan_group, created_by=None):
    """
    Автоматически распределяет студентов по мастерам из платных услуг.
    Логирует первичное назначение в StudentReassignmentLog (reason='auto_service').
    """
    group = plan_group.group

    assigned_student_ids = set(
        StudentMasterAssignment.objects
        .filter(plan_group=plan_group)
        .values_list('student_id', flat=True)
    )

    students = (
        Student.objects
        .filter(group=group)
        .exclude(id__in=assigned_student_ids)
    )

    auto_assigned = 0

    for student in students:
        prefs = _get_student_service_prefs(student)
        master_id = prefs.get('master_id')

        if not master_id:
            continue

        master = MasterPouts.objects.filter(pk=int(master_id)).first()
        if not master:
            logger.warning(
                f"Студент {student.id}: мастер {master_id} из услуг "
                f"не найден в БД, пропущен"
            )
            continue

        StudentMasterAssignment.objects.update_or_create(
            student=student,
            plan_group=plan_group,
            defaults={
                'master': master,
                'is_auto': True,
            },
        )

        StudentReassignmentLog.objects.create(
            student=student,
            plan_group=plan_group,
            from_master=None,
            to_master=master,
            reason='auto_service',
            comment='Автоматически из платных услуг',
            created_by=created_by,
        )

        auto_assigned += 1

    _recalculate_distribution_aggregate(plan_group)
    return auto_assigned


def _recalculate_distribution_aggregate(plan_group):
    """Пересчитывает MasterPlanDistribution по фактическим StudentMasterAssignment."""
    counts = (
        StudentMasterAssignment.objects
        .filter(plan_group=plan_group)
        .values('master_id')
        .annotate(
            cnt=Count('id'),
            auto_cnt=Count('id', filter=Q(is_auto=True)),
        )
    )

    new_master_ids = {row['master_id'] for row in counts}

    MasterPlanDistribution.objects.filter(
        plan_group=plan_group
    ).exclude(master_id__in=new_master_ids).delete()

    for row in counts:
        all_auto = (row['auto_cnt'] == row['cnt']) and row['cnt'] > 0
        MasterPlanDistribution.objects.update_or_create(
            plan_group=plan_group,
            master_id=row['master_id'],
            defaults={
                'students_count': row['cnt'],
                'auto_assigned': all_auto,
            },
        )


# =========================================================================
# 🔹 DASHBOARD
# =========================================================================

@login_required
def master_plan_dashboard(request):
    """Главная страница генерального плана."""

    plan_groups_qs = (
        MasterPlanGroup.objects
        .filter(is_archived=False)
        .select_related('group', 'teacher', 'group__classroom')
        .prefetch_related('distributions__master', 'student_assignments')
    )

    plan_groups = sorted(
        plan_groups_qs,
        key=lambda pg: pg.group.exam_gai_date or date(9999, 12, 31)
    )

    masters = MasterPouts.objects.all().order_by('last_name', 'first_name')

    active_plan_group_ids = MasterPlanGroup.objects.filter(
        is_archived=False
    ).values_list('group_id', flat=True)

    all_groups = Group.objects.filter(
        status='active'
    ).exclude(
        pk__in=active_plan_group_ids
    ).order_by('group_number')

    total_groups = len(plan_groups)
    total_students = sum(pg.total_students for pg in plan_groups)
    total_hours = sum(pg.total_hours for pg in plan_groups)
    total_driven = sum(pg.driven_hours for pg in plan_groups)
    total_remaining = sum(pg.remaining_hours for pg in plan_groups)

    # ============================================================
    # СТАТИСТИКА ПО МАСТЕРАМ (с разбивкой по группам)
    # ============================================================
    masters_stats = []
    for master in masters:
        distributions = (
            master.distributions
            .filter(plan_group__in=plan_groups)
            .select_related('plan_group__group')
        )

        master_total_students = 0
        master_total_hours = 0
        master_driven_hours = 0

        groups_breakdown = []

        for dist in distributions:
            students_count = dist.students_count
            master_total_students += students_count

            hours_per_student = float(dist.plan_group.hours_per_student)
            group_hours = students_count * hours_per_student
            master_total_hours += group_hours

            driven_students = dist.completed_count
            master_driven_hours += driven_students * hours_per_student

            groups_breakdown.append({
                'group_number': dist.plan_group.group.group_number,
                'students_count': students_count,
            })

        assigned_ids = {d.plan_group_id for d in distributions}
        for pg in plan_groups:
            if pg.pk not in assigned_ids:
                groups_breakdown.append({
                    'group_number': pg.group.group_number,
                    'students_count': 0,
                })

        groups_breakdown.sort(key=lambda x: str(x['group_number']))

        master_remaining_hours = max(0, master_total_hours - master_driven_hours)

        masters_stats.append({
            'master': master,
            'total_students': master_total_students,
            'total_hours': master_total_hours,
            'driven_hours': master_driven_hours,
            'remaining_hours': master_remaining_hours,
            'groups_breakdown': groups_breakdown,
        })

    # ============================================================
    # РАСПРЕДЕЛЕНИЕ И ПРИЗНАК «ПОЛНОСТЬЮ РАСПРЕДЕЛЕНА»
    # ============================================================
    for pg in plan_groups:
        pg.distributed_count = (
            MasterPlanDistribution.objects
            .filter(plan_group=pg)
            .aggregate(total=Sum('students_count'))['total'] or 0
        )
        pg.distributed_count = min(pg.distributed_count, pg.total_students)

        pg.is_fully_distributed = (
            pg.total_students > 0
            and pg.distributed_count >= pg.total_students
        )

    # ============================================================
    # МАТРИЦА
    # ============================================================
    matrix_rows = []
    for master in masters:
        dist_dict = {d.plan_group_id: d for d in master.distributions.all()}
        row = {'master': master, 'cells': []}

        for plan_group in plan_groups:
            dist = dist_dict.get(plan_group.pk)

            row['cells'].append({
                'plan_group': plan_group,
                'dist': dist,
                'has_distribution': dist is not None,
                'auto_assigned': dist.auto_assigned if dist else False,
            })

        matrix_rows.append(row)

    context = {
        'plan_groups': plan_groups,
        'masters': masters,
        'all_groups': all_groups,
        'today': timezone.now().date(),
        'total_groups': total_groups,
        'total_students': total_students,
        'total_hours': total_hours,
        'total_driven': total_driven,
        'total_remaining': total_remaining,
        'masters_stats': masters_stats,
        'matrix_rows': matrix_rows,
    }
    return render(request, 'master_plan/dashboard.html', context)


# =========================================================================
# 🔹 ДОБАВЛЕНИЕ ГРУППЫ В ПЛАН
# =========================================================================

@login_required
@require_POST
@transaction.atomic
def add_group_to_plan(request):
    """Добавление группы в генеральный план + часы + автораспределение."""
    group_id = request.POST.get('group_id')
    hours_per_student = request.POST.get('hours_per_student', 56)
    status = request.POST.get('status', 'recruiting')

    dates = {
        'distribution_date': request.POST.get('distribution_date', '').strip(),
        'can_drive_from': request.POST.get('can_drive_from', '').strip(),
        'drive_until': request.POST.get('drive_until', '').strip(),
        'exam_internal_theory_date': request.POST.get('exam_internal_theory_date', '').strip(),
        'exam_internal_driving_date': request.POST.get('exam_internal_driving_date', '').strip(),
        'exam_gai_date': request.POST.get('exam_gai_date', '').strip(),
    }

    if not group_id:
        return JsonResponse({'error': 'Не выбрана группа'}, status=400)

    try:
        group = Group.objects.select_for_update().get(pk=group_id)
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Группа не найдена'}, status=404)

    parsed_dates = {key: parse_date(value) for key, value in dates.items()}
    hours_int = int(float(hours_per_student))

    try:
        plan_group = MasterPlanGroup.objects.filter(
            group=group, is_archived=False
        ).first()

        if plan_group is None:
            plan_group = MasterPlanGroup.objects.filter(group=group).first()
            if plan_group is None:
                plan_group = MasterPlanGroup(group=group)
            plan_group.is_archived = False

        plan_group.hours_per_student = hours_per_student
        plan_group.distribution_date = parsed_dates['distribution_date']
        plan_group.can_drive_from = parsed_dates['can_drive_from']
        plan_group.drive_until = parsed_dates['drive_until']
        plan_group.status = status
        plan_group.teacher = group.teacher
        plan_group.save()

        students_updated = Student.objects.filter(group=group).update(
            driving_hours_required=hours_int
        )

        auto_assigned = _auto_assign_masters_from_services(
            plan_group, created_by=request.user
        )

        group_updated = False
        for date_key, model_field in [
            ('exam_internal_theory_date', 'exam_internal_theory_date'),
            ('exam_internal_driving_date', 'exam_internal_driving_date'),
            ('exam_gai_date', 'exam_gai_date'),
        ]:
            if parsed_dates.get(date_key):
                setattr(group, model_field, parsed_dates[date_key])
                group_updated = True

        if group_updated:
            group.save()

        return JsonResponse({
            'success': True,
            'plan_group_id': plan_group.pk,
            'students_updated': students_updated,
            'auto_assigned': auto_assigned,
            'message': (
                f'Группа {group.group_number} добавлена. '
                f'Часы ({hours_int} ч.) установлены {students_updated} студентам. '
                f'Автоматически распределено: {auto_assigned}.'
            )
        })

    except IntegrityError as e:
        logger.error(f"Конфликт уникальности: {e}", exc_info=True)
        return JsonResponse({
            'error': 'Эта группа уже есть в генеральном плане'
        }, status=409)
    except Exception as e:
        logger.error(f"Ошибка при добавлении группы: {e}", exc_info=True)
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


# =========================================================================
# 🔹 ОБНОВЛЕНИЕ РАСПРЕДЕЛЕНИЯ (из матрицы)
# =========================================================================

@login_required
@require_POST
@transaction.atomic
def update_distribution(request):
    """Обновление агрегата распределения из матрицы (ручной input)."""
    master_id = request.POST.get('master_id')
    plan_group_id = request.POST.get('plan_group_id')
    students_count_str = request.POST.get('students_count', 0)

    if not master_id or not plan_group_id:
        return JsonResponse({'error': 'Не указаны мастер или группа'}, status=400)

    try:
        students_count = int(students_count_str)
        if students_count < 0:
            return JsonResponse({'error': 'Количество не может быть отрицательным'}, status=400)
    except ValueError:
        return JsonResponse({'error': 'Некорректное количество'}, status=400)

    try:
        master = MasterPouts.objects.get(pk=master_id)
        plan_group = MasterPlanGroup.objects.get(pk=plan_group_id)
    except (MasterPouts.DoesNotExist, MasterPlanGroup.DoesNotExist):
        return JsonResponse({'error': 'Мастер или группа не найдены'}, status=404)

    total_distributed = MasterPlanDistribution.objects.filter(
        plan_group=plan_group
    ).aggregate(total=Sum('students_count'))['total'] or 0

    existing_dist = MasterPlanDistribution.objects.filter(
        master=master, plan_group=plan_group
    ).first()
    old_count = existing_dist.students_count if existing_dist else 0

    new_total_distributed = (total_distributed - old_count) + students_count
    if new_total_distributed > plan_group.total_students:
        return JsonResponse({
            'error': f'Нельзя распределить больше {plan_group.total_students} студентов. '
                     f'Попытка: {new_total_distributed}'
        }, status=400)

    dist, created = MasterPlanDistribution.objects.update_or_create(
        master=master,
        plan_group=plan_group,
        defaults={
            'students_count': students_count,
            'auto_assigned': False,
        }
    )

    fully_driven_students_count = Student.objects.filter(
        group=plan_group.group,
        driving_hours_required__gt=0
    ).filter(
        driving_hours_completed__gte=F('driving_hours_required')
    ).count()

    is_fully_completed = (
        fully_driven_students_count >= plan_group.total_students
        and plan_group.total_students > 0
    )

    if is_fully_completed and not plan_group.is_archived:
        plan_group.is_archived = True
        plan_group.status = 'archived'
        plan_group.save(update_fields=['is_archived', 'status'])
        logger.info(
            f"📦 Группа {plan_group.group.group_number} автоматически заархивирована "
            f"(все {fully_driven_students_count} студентов выкатали часы)"
        )

    return JsonResponse({
        'success': True,
        'is_archived': plan_group.is_archived,
        'completed_count': dist.completed_count,
        'fully_driven_students': fully_driven_students_count,
        'total_students': plan_group.total_students,
        'message': 'Группа полностью выкатана и отправлена в архив'
                   if is_fully_completed else 'Распределение обновлено'
    })


# =========================================================================
# 🔹 ПОЛУЧЕНИЕ ДАННЫХ ГРУППЫ
# =========================================================================

@login_required
def get_group_data(request, group_id):
    """API: Получение данных группы для автозаполнения формы."""
    try:
        group = Group.objects.get(pk=group_id)
        plan_group = MasterPlanGroup.objects.filter(group=group, is_archived=False).first()

        data = {
            'group_number': group.group_number,
            'category': str(group.category) if group.category else '',
            'teacher': str(group.teacher) if group.teacher else '',
            'classroom': str(group.classroom) if group.classroom else '',
            'students_count': group.students.count(),
            'hours_per_student': float(plan_group.hours_per_student) if plan_group else 50,
            'status': plan_group.status if plan_group else 'recruiting',
            'distribution_date': fmt_date(plan_group.distribution_date) if plan_group else '',
            'can_drive_from': fmt_date(plan_group.can_drive_from) if plan_group else '',
            'drive_until': fmt_date(plan_group.drive_until) if plan_group else '',
            'exam_internal_theory_date': fmt_date(group.exam_internal_theory_date),
            'exam_internal_driving_date': fmt_date(group.exam_internal_driving_date),
            'exam_gai_date': fmt_date(group.exam_gai_date),
        }
        return JsonResponse(data)
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Группа не найдена'}, status=404)


# =========================================================================
# 🔹 ОБНОВЛЕНИЕ ГРУППЫ В ПЛАНЕ
# =========================================================================

@login_required
@require_POST
@transaction.atomic
def update_group_in_plan(request):
    """Обновление данных группы в генеральном плане + автораспределение."""
    plan_group_id = request.POST.get('plan_group_id', '').strip()
    group_id = request.POST.get('group_id', '').strip()

    if not plan_group_id or not group_id:
        return JsonResponse({'error': 'Не указаны обязательные параметры'}, status=400)

    try:
        plan_group = MasterPlanGroup.objects.get(pk=plan_group_id)
    except MasterPlanGroup.DoesNotExist:
        return JsonResponse({'error': 'Группа в плане не найдена'}, status=404)

    hours_per_student = request.POST.get('hours_per_student', 56)
    status = request.POST.get('status', 'recruiting')

    dates = {
        'distribution_date': request.POST.get('distribution_date', '').strip(),
        'can_drive_from': request.POST.get('can_drive_from', '').strip(),
        'drive_until': request.POST.get('drive_until', '').strip(),
        'exam_internal_theory_date': request.POST.get('exam_internal_theory_date', '').strip(),
        'exam_internal_driving_date': request.POST.get('exam_internal_driving_date', '').strip(),
        'exam_gai_date': request.POST.get('exam_gai_date', '').strip(),
    }
    parsed_dates = {key: parse_date(value) for key, value in dates.items()}

    try:
        old_hours = int(float(plan_group.hours_per_student))
        new_hours = int(float(hours_per_student))
        if old_hours != new_hours:
            Student.objects.filter(group=plan_group.group).update(
                driving_hours_required=new_hours
            )
            logger.info(
                f"⏱️ Часы на студента в группе {plan_group.group.group_number} "
                f"обновлены с {old_hours} на {new_hours}"
            )

        plan_group.hours_per_student = hours_per_student
        plan_group.distribution_date = parsed_dates['distribution_date']
        plan_group.can_drive_from = parsed_dates['can_drive_from']
        plan_group.drive_until = parsed_dates['drive_until']
        plan_group.status = status
        plan_group.save()

        auto_assigned = _auto_assign_masters_from_services(
            plan_group, created_by=request.user
        )

        group = plan_group.group
        group_updated = False
        for date_key, model_field in [
            ('exam_internal_theory_date', 'exam_internal_theory_date'),
            ('exam_internal_driving_date', 'exam_internal_driving_date'),
            ('exam_gai_date', 'exam_gai_date'),
        ]:
            if parsed_dates.get(date_key):
                setattr(group, model_field, parsed_dates[date_key])
                group_updated = True

        if group_updated:
            group.save()

        return JsonResponse({
            'success': True,
            'auto_assigned': auto_assigned,
            'message': f'Группа {group.group_number} обновлена. Автораспределено: {auto_assigned}.'
        })

    except Exception as e:
        logger.error(f"Ошибка при обновлении группы: {e}", exc_info=True)
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


# =========================================================================
# 🔹 УДАЛЕНИЕ ГРУППЫ ИЗ ПЛАНА
# =========================================================================

@login_required
@require_POST
@transaction.atomic
def delete_group_from_plan(request):
    """Удаление группы из генерального плана."""
    plan_group_id = request.POST.get('plan_group_id')

    if not plan_group_id:
        return JsonResponse({'error': 'Не указан ID группы'}, status=400)

    try:
        plan_group = MasterPlanGroup.objects.get(pk=plan_group_id)
        group_number = plan_group.group.group_number
        plan_group.delete()

        logger.info(f"🗑️ Группа {group_number} удалена из генерального плана")
        return JsonResponse({
            'success': True,
            'message': f'Группа {group_number} удалена из плана'
        })

    except MasterPlanGroup.DoesNotExist:
        return JsonResponse({'error': 'Группа в плане не найдена'}, status=404)
    except Exception as e:
        logger.error(f"Ошибка при удалении группы: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


# =========================================================================
# 🔹 МОДАЛЬНОЕ ОКНО РАСПРЕДЕЛЕНИЯ
# =========================================================================

@login_required
def open_distribution_modal(request, plan_group_id):
    """API: данные для модального окна распределения."""
    plan_group = get_object_or_404(MasterPlanGroup, pk=plan_group_id)

    assigned_student_ids = set(
        StudentMasterAssignment.objects
        .filter(plan_group=plan_group)
        .values_list('student_id', flat=True)
    )

    distributions = MasterPlanDistribution.objects.filter(
        plan_group=plan_group
    ).select_related('master')
    master_quotas = {dist.master_id: dist.students_count for dist in distributions}

    students = (
        Student.objects
        .filter(group=plan_group.group)
        .exclude(id__in=assigned_student_ids)
        .order_by('last_name', 'first_name')
    )

    if master_quotas:
        base_allowed_ids = list(master_quotas.keys())
        available_master_ids = set(master_quotas.keys())
    else:
        base_allowed_ids = list(MasterPouts.objects.values_list('id', flat=True))
        available_master_ids = set(base_allowed_ids)

    student_data = []
    for s in students:
        prefs = _get_student_service_prefs(s)
        master_id_pref = prefs.get('master_id')
        car_brand = prefs.get('car_brand')
        master_gender_pref = prefs.get('master_gender')

        allowed_master_ids = list(base_allowed_ids)
        brand_warning = None

        # 🔥 Жёсткий фильтр по марке
        if car_brand:
            allowed_masters_qs = MasterPouts.objects.filter(
                id__in=allowed_master_ids,
                car__make__iexact=car_brand,
            ).distinct()
            filtered_ids = list(allowed_masters_qs.values_list('id', flat=True))

            if filtered_ids:
                allowed_master_ids = filtered_ids
            else:
                allowed_master_ids = []
                brand_warning = (
                    f'Платная услуга: требуется марка «{car_brand}». '
                    f'Нет доступных мастеров с этой маркой для ручного выбора.'
                )

        # 🔥 Фильтр по КПП
        if s.gearbox_type:
            mapped = GEARBOX_MAP.get(s.gearbox_type.lower())
            if mapped:
                trans_qs = MasterPouts.objects.filter(
                    id__in=allowed_master_ids,
                    car__transmission=mapped,
                ).distinct()
                trans_ids = list(trans_qs.values_list('id', flat=True))
                if trans_ids:
                    allowed_master_ids = trans_ids
                else:
                    allowed_master_ids = []

        # 🔥 Фильтр по полу мастера
        if master_gender_pref:
            gender_qs = MasterPouts.objects.filter(
                id__in=allowed_master_ids,
                gender=master_gender_pref,
            ).distinct()
            gender_ids = list(gender_qs.values_list('id', flat=True))
            if gender_ids:
                allowed_master_ids = gender_ids
            else:
                allowed_master_ids = []

        # Предпочтительный мастер из услуг — добавляем, если он проходит фильтры
        if master_id_pref:
            pref_id = int(master_id_pref)
            pref_master = MasterPouts.objects.filter(pk=pref_id).first()

            if pref_master:
                if car_brand:
                    pref_has_brand = (
                        pref_master.car
                        and pref_master.car.make
                        and pref_master.car.make.lower() == car_brand.lower()
                    )
                    if not pref_has_brand:
                        brand_warning = (
                            f'⚠️ Конфликт: мастер «{pref_master.last_name}» '
                            f'из платной услуги не имеет марки «{car_brand}». '
                            f'Приоритет — за выбранным мастером.'
                        )

                if pref_id not in allowed_master_ids:
                    allowed_master_ids.append(pref_id)
                available_master_ids.add(pref_id)

        # Список мастеров, подходящих под марку
        brand_masters_names = []
        if car_brand:
            brand_masters_names = list(
                MasterPouts.objects.filter(
                    id__in=allowed_master_ids,
                    car__make__iexact=car_brand,
                ).values_list('last_name', flat=True)
            )

        student_data.append({
            'id': s.id,
            'full_name': s.full_name,
            'preferred_master_id': str(master_id_pref) if master_id_pref else None,
            'assigned_master_id': None,
            'car_brand': car_brand,
            'allowed_master_ids': allowed_master_ids,
            'is_locked': bool(master_id_pref),
            'services': prefs['services'],
            'brand_warning': brand_warning,
            'brand_masters': brand_masters_names,
        })

    masters_qs = MasterPouts.objects.filter(
        id__in=available_master_ids
    ).order_by('last_name', 'first_name')

    masters_data = [
        {
            'id': m.id,
            'name': f"{m.last_name} {m.first_name} {m.patronymic or ''}".strip(),
            'quota': master_quotas.get(m.id, 0)
        }
        for m in masters_qs
    ]

    return JsonResponse({
        'success': True,
        'group_name': plan_group.group.group_number,
        'students': student_data,
        'masters': masters_data,
        'master_quotas': master_quotas,
        'already_assigned': {
            row['master_id']: row['cnt']
            for row in (
                StudentMasterAssignment.objects
                .filter(plan_group=plan_group)
                .values('master_id')
                .annotate(cnt=Count('id'))
            )
        },
        'total_students': plan_group.total_students,
        'distributed_count': plan_group.total_students - len(student_data),
        'unassigned_count': len(student_data),
    })


# =========================================================================
# 🔹 СОХРАНЕНИЕ РАСПРЕДЕЛЕНИЯ (из модалки)
# =========================================================================

@login_required
@require_POST
@transaction.atomic
def save_distribution(request):
    """Сохраняет распределение студентов по мастерам из модалки."""
    try:
        data = json.loads(request.body)
        plan_group_id = data.get('plan_group_id')
        assignments = data.get('assignments', {})

        plan_group = get_object_or_404(MasterPlanGroup, pk=plan_group_id)

        quotas = {
            d.master_id: d.students_count
            for d in MasterPlanDistribution.objects.filter(plan_group=plan_group)
        }

        if not quotas:
            return JsonResponse({
                'success': False,
                'error': (
                    'В матрице не заданы квоты. Сначала распределите '
                    'число студентов по мастерам в матрице.'
                ),
            }, status=400)

        incoming_counts = {}
        for student_id, master_id in assignments.items():
            if not master_id:
                continue
            try:
                mid = int(master_id)
            except (TypeError, ValueError):
                continue
            incoming_counts[mid] = incoming_counts.get(mid, 0) + 1

        overflow = []
        for mid, cnt in incoming_counts.items():
            quota = quotas.get(mid, 0)
            if cnt > quota:
                master = MasterPouts.objects.filter(pk=mid).first()
                name = master.short_name if master else f'#{mid}'
                overflow.append(f'{name}: {cnt} из {quota}')

        if overflow:
            return JsonResponse({
                'success': False,
                'error': (
                    'Превышена квота мастеров:\n' +
                    '\n'.join('• ' + o for o in overflow)
                ),
                'overflow': True,
            }, status=400)

        for student_id, master_id in assignments.items():
            try:
                student_id_int = int(student_id)
            except (TypeError, ValueError):
                continue

            student_obj = Student.objects.filter(
                pk=student_id_int, group=plan_group.group
            ).first()
            if not student_obj:
                continue

            existing = StudentMasterAssignment.objects.filter(
                student_id=student_id_int,
                plan_group=plan_group
            ).select_related('master').first()
            from_master = existing.master if existing else None

            if master_id:
                new_master = MasterPouts.objects.filter(pk=int(master_id)).first()
                if not new_master:
                    continue

                if from_master and from_master.id == new_master.id:
                    continue

                StudentMasterAssignment.objects.update_or_create(
                    student_id=student_id_int,
                    plan_group=plan_group,
                    defaults={
                        'master_id': int(master_id),
                        'is_auto': False,
                    }
                )

                StudentReassignmentLog.objects.create(
                    student=student_obj,
                    plan_group=plan_group,
                    from_master=from_master,
                    to_master=new_master,
                    reason='manual' if from_master is None else 'reassign',
                    comment=(
                        'Назначено вручную'
                        if from_master is None
                        else 'Изменено через модалку распределения'
                    ),
                    created_by=request.user,
                )
            else:
                if existing:
                    StudentMasterAssignment.objects.filter(
                        student_id=student_id_int,
                        plan_group=plan_group
                    ).delete()

                    StudentReassignmentLog.objects.create(
                        student=student_obj,
                        plan_group=plan_group,
                        from_master=from_master,
                        to_master=None,
                        reason='reassign',
                        comment='Снято назначение',
                        created_by=request.user,
                    )

        _recalculate_distribution_aggregate(plan_group)

        total = StudentMasterAssignment.objects.filter(plan_group=plan_group).count()
        return JsonResponse({
            'success': True,
            'message': f'Распределение сохранено. Всего назначено: {total}'
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Некорректный JSON'}, status=400)
    except Exception as e:
        logger.error(f"Ошибка сохранения распределения: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# =========================================================================
# 🔹 АВТОРАСПРЕДЕЛЕНИЕ (кнопкой)
# =========================================================================

@login_required
@require_POST
@transaction.atomic
def auto_distribute_group(request, plan_group_id):
    """Ручной запуск автораспределения (кнопкой)."""
    plan_group = get_object_or_404(MasterPlanGroup, pk=plan_group_id)

    total_unassigned_before = (
        Student.objects
        .filter(group=plan_group.group)
        .exclude(
            id__in=StudentMasterAssignment.objects
            .filter(plan_group=plan_group)
            .values_list('student_id', flat=True)
        )
        .count()
    )

    auto_assigned = _auto_assign_masters_from_services(
        plan_group, created_by=request.user
    )
    manual_needed = total_unassigned_before - auto_assigned

    return JsonResponse({
        'success': True,
        'auto_assigned': auto_assigned,
        'manual_needed': manual_needed,
        'total_unassigned': total_unassigned_before,
        'message': (
            f'✅ Автоматически распределено: {auto_assigned} студентов. '
            f'Требуют ручного выбора: {manual_needed}'
        )
    })


# =========================================================================
# 🔹 API: СПИСОК СТУДЕНТОВ ЯЧЕЙКИ
# =========================================================================

@login_required
def get_cell_students(request, plan_group_id, master_id):
    """API: список студентов, назначенных мастеру в группе."""
    plan_group = get_object_or_404(MasterPlanGroup, pk=plan_group_id)

    assignments = (
        StudentMasterAssignment.objects
        .filter(plan_group=plan_group, master_id=master_id)
        .select_related('student')
        .order_by('student__last_name', 'student__first_name')
    )

    students_data = []
    for a in assignments:
        required = float(a.student.driving_hours_required or 0)
        completed = float(a.student.driving_hours_completed or 0)
        remaining = max(0.0, required - completed)

        percent = 0.0
        if required > 0:
            percent = min(100.0, round(completed / required * 100, 1))

        students_data.append({
            'id': a.student_id,
            'last_name': a.student.last_name,
            'first_name': a.student.first_name,
            'patronymic': a.student.patronymic or '',
            'full_name': a.student.full_name,
            'is_auto': a.is_auto,
            'hours_required': round(required, 1),
            'hours_completed': round(completed, 1),
            'hours_remaining': round(remaining, 1),
            'percent': percent,
        })

    master = MasterPouts.objects.filter(pk=master_id).values(
        'id', 'last_name', 'first_name', 'patronymic'
    ).first()

    return JsonResponse({
        'success': True,
        'group_number': plan_group.group.group_number,
        'master_name': (
            f"{master['last_name']} {master['first_name'][:1]}."
            if master else '—'
        ),
        'count': len(students_data),
        'students': students_data,
    })


# =========================================================================
# 🔹 API: ДАННЫЕ ДЛЯ МОДАЛКИ ПЕРЕРАСПРЕДЕЛЕНИЯ
# =========================================================================

@login_required
def get_reassignment_data(request, plan_group_id):
    """API: данные для модалки перераспределения."""
    plan_group = get_object_or_404(MasterPlanGroup, pk=plan_group_id)

    students_qs = (
        Student.objects
        .filter(group=plan_group.group)
        .order_by('last_name', 'first_name')
    )

    assignments = {
        a.student_id: a
        for a in StudentMasterAssignment.objects
            .filter(plan_group=plan_group)
            .select_related('master')
    }

    students_data = []
    for s in students_qs:
        a = assignments.get(s.id)
        students_data.append({
            'id': s.id,
            'full_name': s.full_name,
            'last_name': s.last_name,
            'first_name': s.first_name,
            'patronymic': s.patronymic or '',
            'current_master_id': str(a.master_id) if a and a.master_id else None,
            'current_master_name': (
                f"{a.master.last_name} {a.master.first_name[:1]}."
                if a and a.master else ''
            ),
        })

    masters_qs = MasterPouts.objects.all().order_by('last_name', 'first_name')
    masters_data = [
        {
            'id': m.id,
            'name': f"{m.last_name} {m.first_name} {m.patronymic or ''}".strip(),
        }
        for m in masters_qs
    ]

    reasons_data = [
        {'value': 'reassign', 'label': 'Перераспределить'},
        {'value': 'student_request', 'label': 'По требованию учащегося'},
        {'value': 'master_request', 'label': 'По требованию мастера'},
    ]

    return JsonResponse({
        'success': True,
        'group_id': plan_group.pk,
        'group_number': plan_group.group.group_number,
        'students': students_data,
        'masters': masters_data,
        'reasons': reasons_data,
    })


# =========================================================================
# 🔹 СОХРАНЕНИЕ ПЕРЕРАСПРЕДЕЛЕНИЯ
# =========================================================================

@login_required
@require_POST
@transaction.atomic
def save_reassignment(request):
    """Сохраняет перераспределения с журналом."""
    try:
        data = json.loads(request.body)
        plan_group_id = data.get('plan_group_id')
        reason = data.get('reason', 'reassign')
        comment = (data.get('comment') or '').strip()
        changes = data.get('changes', [])

        if reason not in dict(StudentReassignmentLog.REASON_CHOICES):
            return JsonResponse({
                'success': False,
                'error': 'Недопустимая причина перераспределения'
            }, status=400)

        plan_group = get_object_or_404(MasterPlanGroup, pk=plan_group_id)

        updated = 0
        log_created = 0

        for change in changes:
            try:
                student_id = int(change.get('student_id'))
            except (TypeError, ValueError):
                continue

            to_master_id = change.get('to_master_id')
            if to_master_id in ('', None):
                to_master_id = None
            else:
                try:
                    to_master_id = int(to_master_id)
                except (TypeError, ValueError):
                    continue

            if not Student.objects.filter(pk=student_id, group=plan_group.group).exists():
                continue

            current = StudentMasterAssignment.objects.filter(
                student_id=student_id,
                plan_group=plan_group
            ).select_related('master').first()

            from_master_id = current.master_id if current else None

            if from_master_id == to_master_id:
                continue

            if to_master_id is None:
                StudentMasterAssignment.objects.filter(
                    student_id=student_id,
                    plan_group=plan_group
                ).delete()
            else:
                if not MasterPouts.objects.filter(pk=to_master_id).exists():
                    continue
                StudentMasterAssignment.objects.update_or_create(
                    student_id=student_id,
                    plan_group=plan_group,
                    defaults={
                        'master_id': to_master_id,
                        'is_auto': False,
                    }
                )

            updated += 1

            StudentReassignmentLog.objects.create(
                student_id=student_id,
                plan_group=plan_group,
                from_master_id=from_master_id,
                to_master_id=to_master_id,
                reason=reason,
                comment=comment,
                created_by=request.user,
            )
            log_created += 1

        _recalculate_distribution_aggregate(plan_group)

        return JsonResponse({
            'success': True,
            'updated': updated,
            'logged': log_created,
            'message': f'Перераспределено студентов: {updated}. Записей в журнал: {log_created}.'
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Некорректный JSON'}, status=400)
    except Exception as e:
        logger.error(f"Ошибка сохранения перераспределения: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# =========================================================================
# 🔹 ОТЧЁТ ПО ПЕРЕРАСПРЕДЕЛЕНИЯМ
# =========================================================================

@login_required
def reassignment_report(request):
    """Отчёт по перераспределениям с фильтрами и агрегатами."""
    today = timezone.now().date()
    default_from = today - timedelta(days=30)

    date_from = parse_date(request.GET.get('date_from', '').strip()) or default_from
    date_to = parse_date(request.GET.get('date_to', '').strip()) or today
    reason_filter = request.GET.get('reason', '').strip()
    master_filter = request.GET.get('master', '').strip()
    group_filter = request.GET.get('group', '').strip()

    qs = (
        StudentReassignmentLog.objects
        .select_related(
            'student',
            'from_master', 'to_master',
            'plan_group__group',
            'created_by',
        )
        .filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        )
    )

    if reason_filter:
        qs = qs.filter(reason=reason_filter)

    if master_filter and master_filter.isdigit():
        m_id = int(master_filter)
        qs = qs.filter(Q(from_master_id=m_id) | Q(to_master_id=m_id))

    if group_filter and group_filter.isdigit():
        qs = qs.filter(plan_group_id=int(group_filter))

    total = qs.count()

    reason_labels = dict(StudentReassignmentLog.REASON_CHOICES)
    by_reason = [
        {
            'reason': row['reason'],
            'label': reason_labels.get(row['reason'], row['reason']),
            'cnt': row['cnt'],
        }
        for row in qs.values('reason').annotate(cnt=Count('id')).order_by('-cnt')
    ]

    top_to_masters = list(
        qs.exclude(to_master__isnull=True)
        .values(
            'to_master__last_name',
            'to_master__first_name',
            'to_master__patronymic',
        )
        .annotate(cnt=Count('id'))
        .order_by('-cnt')[:10]
    )

    top_from_masters = list(
        qs.exclude(from_master__isnull=True)
        .values(
            'from_master__last_name',
            'from_master__first_name',
            'from_master__patronymic',
        )
        .annotate(cnt=Count('id'))
        .order_by('-cnt')[:10]
    )

    top_students = list(
        qs.values(
            'student_id',
            'student__last_name',
            'student__first_name',
            'student__patronymic',
        )
        .annotate(cnt=Count('id'))
        .order_by('-cnt')[:10]
    )

    by_group = list(
        qs.values(
            'plan_group_id',
            'plan_group__group__group_number',
        )
        .annotate(cnt=Count('id'))
        .order_by('-cnt')
    )

    by_day = list(
        qs.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(cnt=Count('id'))
        .order_by('-day')[:30]
    )

    recent = list(qs.order_by('-created_at')[:50])

    all_masters = MasterPouts.objects.all().order_by('last_name', 'first_name')
    all_groups = (
        MasterPlanGroup.objects
        .filter(is_archived=False)
        .select_related('group')
        .order_by('group__group_number')
    )
    reasons = StudentReassignmentLog.REASON_CHOICES

    context = {
        'title': '📊 Отчёт по перераспределениям',
        'date_from': date_from,
        'date_to': date_to,
        'reason_filter': reason_filter,
        'master_filter': master_filter,
        'group_filter': group_filter,

        'total': total,
        'by_reason': by_reason,
        'top_to_masters': top_to_masters,
        'top_from_masters': top_from_masters,
        'top_students': top_students,
        'by_group': by_group,
        'by_day': by_day,
        'recent': recent,

        'all_masters': all_masters,
        'all_groups': all_groups,
        'reasons': reasons,
    }
    return render(request, 'master_plan/reports/reassignment_report.html', context)