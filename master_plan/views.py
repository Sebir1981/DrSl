# master_plan/views.py
import logging
from datetime import datetime, date

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, F
from django.core.exceptions import ValidationError

from .models import MasterPlanGroup, MasterPlanDistribution
from groups.models import Group
from masters.models import MasterPouts
from students.models import Student

logger = logging.getLogger(__name__)


def parse_date(date_str):
    """Универсальный парсер дат. Поддерживает ДД.ММ.ГГГГ и ГГГГ-ММ-ДД"""
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
    """Форматирование даты в ДД.ММ.ГГГГ"""
    if not date_obj:
        return ''
    return date_obj.strftime('%d.%m.%Y')


@login_required
def master_plan_dashboard(request):
    """Главная страница генерального плана."""

    # 1. Получаем все активные группы плана
    plan_groups_qs = (
        MasterPlanGroup.objects
        .filter(is_archived=False)
        .select_related('group', 'teacher', 'group__classroom')
        .prefetch_related('distributions__master')
    )

    # 2. 🔥 СОРТИРОВКА: Ближайшие даты Экзамена ГАИ слева, без даты — в конце
    # Используем datetime.date(9999, 12, 31) как "бесконечность" для групп без даты
    plan_groups = sorted(
        plan_groups_qs,
        key=lambda pg: pg.group.exam_gai_date or date(9999, 12, 31)
    )

    masters = MasterPouts.objects.all().order_by('last_name', 'first_name')
    all_groups = Group.objects.filter(status='active').order_by('group_number')

    # =======================================================================
    # 🔹 ФИЛЬТРАЦИЯ ГРУПП ДЛЯ ДОБАВЛЕНИЯ
    # =======================================================================

    # 1. Получаем ID групп, которые УЖЕ находятся в активном генеральном плане
    active_plan_group_ids = MasterPlanGroup.objects.filter(
        is_archived=False
    ).values_list('group_id', flat=True)

    # 2. Формируем итоговый список:
    # - Берем только активные группы (предполагаем, что у вас есть status='active')
    # - Исключаем те, чьи ID есть в списке active_plan_group_ids
    # - Если у модели Group есть поле is_archived, можно добавить .filter(is_archived=False)
    all_groups = Group.objects.filter(
        status='active'  # <-- Убедитесь, что это поле соответствует вашей модели Group
    ).exclude(
        pk__in=active_plan_group_ids
    ).order_by('group_number')

    # 💡 ПОДСКАЗКА: Если бизнес-логика требует исключить ВООБЩЕ ЛЮБЫЕ группы,
    # которые когда-либо были в плане (даже если они уже в архиве плана),
    # замените первую строку на:
    # existing_plan_group_ids = MasterPlanGroup.objects.values_list('group_id', flat=True)
    # и используйте existing_plan_group_ids в .exclude()

    # ============================================================
    # ОБЩАЯ СТАТИСТИКА
    # ============================================================
    total_groups = len(plan_groups)  # Используем len, так как теперь это список
    total_students = sum(pg.total_students for pg in plan_groups)
    total_hours = sum(pg.total_hours for pg in plan_groups)
    total_driven = sum(pg.driven_hours for pg in plan_groups)
    total_remaining = sum(pg.remaining_hours for pg in plan_groups)

    # ============================================================
    # СТАТИСТИКА ПО МАСТЕРАМ
    # ============================================================
    masters_stats = []
    for master in masters:
        distributions = master.distributions.filter(plan_group__in=plan_groups)

        master_total_students = 0
        master_total_hours = 0
        master_driven_hours = 0

        for dist in distributions:
            students_count = dist.students_count
            master_total_students += students_count

            hours_per_student = float(dist.plan_group.hours_per_student)
            group_hours = students_count * hours_per_student
            master_total_hours += group_hours

            driven_students = dist.completed_count
            master_driven_hours += driven_students * hours_per_student

        master_remaining_hours = max(0, master_total_hours - master_driven_hours)

        masters_stats.append({
            'master': master,
            'total_students': master_total_students,
            'total_hours': master_total_hours,
            'driven_hours': master_driven_hours,
            'remaining_hours': master_remaining_hours,
        })

    # ============================================================
    # ПОДГОТОВКА МАТРИЦЫ РАСПРЕДЕЛЕНИЯ
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
                'has_distribution': dist is not None
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


@login_required
@require_POST
@transaction.atomic
def add_group_to_plan(request):
    """Добавление группы в генеральный план + установка часов студентам."""
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
        group = Group.objects.get(pk=group_id)
    except Group.DoesNotExist:
        return JsonResponse({'error': 'Группа не найдена'}, status=404)

    parsed_dates = {key: parse_date(value) for key, value in dates.items()}
    hours_int = int(float(hours_per_student))

    try:
        plan_group, created = MasterPlanGroup.objects.get_or_create(
            group=group,
            defaults={
                'hours_per_student': hours_per_student,
                'distribution_date': parsed_dates['distribution_date'],
                'can_drive_from': parsed_dates['can_drive_from'],
                'drive_until': parsed_dates['drive_until'],
                'status': status,
                'teacher': group.teacher,
                'is_archived': False,
            }
        )

        if not created:
            plan_group.hours_per_student = hours_per_student
            plan_group.distribution_date = parsed_dates['distribution_date']
            plan_group.can_drive_from = parsed_dates['can_drive_from']
            plan_group.drive_until = parsed_dates['drive_until']
            plan_group.status = status
            plan_group.teacher = group.teacher
            plan_group.is_archived = False
            plan_group.save()

        # 🔥 УСТАНАВЛИВАЕМ ЧАСЫ ВСЕМ СТУДЕНТАМ ГРУППЫ
        students_updated = Student.objects.filter(group=group).update(
            driving_hours_required=hours_int
        )

        # Обновляем даты экзаменов в карточке группы
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
            'created': created,
            'students_updated': students_updated,
            'message': f'Группа {group.group_number} {"добавлена" if created else "обновлена"}. Часы ({hours_int} ч.) установлены {students_updated} студентам.'
        })

    except Exception as e:
        logger.error(f"Ошибка при добавлении группы: {e}", exc_info=True)
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


@login_required
@require_POST
@transaction.atomic
def update_distribution(request):
    """
    Обновление распределения студентов по мастерам.
    Архивация происходит ТОЛЬКО когда ВСЕ студенты группы выкатали свои часы.
    """
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

    # 1. Проверка лимита распределения
    total_distributed = MasterPlanDistribution.objects.filter(
        plan_group=plan_group
    ).aggregate(total=Sum('students_count'))['total'] or 0

    existing_dist = MasterPlanDistribution.objects.filter(master=master, plan_group=plan_group).first()
    old_count = existing_dist.students_count if existing_dist else 0

    new_total_distributed = (total_distributed - old_count) + students_count
    if new_total_distributed > plan_group.total_students:
        return JsonResponse({
            'error': f'Нельзя распределить больше {plan_group.total_students} студентов. Попытка: {new_total_distributed}'
        }, status=400)

    # 2. Сохранение распределения
    dist, created = MasterPlanDistribution.objects.update_or_create(
        master=master,
        plan_group=plan_group,
        defaults={'students_count': students_count}
    )

    # 3. 🔥 ПРОВЕРКА АРХИВАЦИИ ПО СТУДЕНТАМ
    fully_driven_students_count = Student.objects.filter(
        group=plan_group.group,
        driving_hours_required__gt=0
    ).filter(
        driving_hours_completed__gte=F('driving_hours_required')
    ).count()

    is_fully_completed = (fully_driven_students_count >= plan_group.total_students) and (plan_group.total_students > 0)

    if is_fully_completed and not plan_group.is_archived:
        plan_group.is_archived = True
        plan_group.status = 'archived'
        plan_group.save(update_fields=['is_archived', 'status'])
        logger.info(
            f"📦 Группа {plan_group.group.group_number} автоматически заархивирована (все {fully_driven_students_count} студентов выкатали часы)")

    return JsonResponse({
        'success': True,
        'is_archived': plan_group.is_archived,
        'completed_count': dist.completed_count,
        'fully_driven_students': fully_driven_students_count,
        'total_students': plan_group.total_students,
        'message': 'Группа полностью выкатана и отправлена в архив' if is_fully_completed else 'Распределение обновлено'
    })


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


@login_required
@require_POST
@transaction.atomic
def update_group_in_plan(request):
    """Обновление данных группы в генеральном плане."""
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
        # 🔥 Если изменилось количество часов, обновляем это у всех студентов группы
        old_hours = int(float(plan_group.hours_per_student))
        new_hours = int(float(hours_per_student))
        if old_hours != new_hours:
            Student.objects.filter(group=plan_group.group).update(
                driving_hours_required=new_hours
            )
            logger.info(
                f"⏱️ Часы на студента в группе {plan_group.group.group_number} обновлены с {old_hours} на {new_hours}")

        plan_group.hours_per_student = hours_per_student
        plan_group.distribution_date = parsed_dates['distribution_date']
        plan_group.can_drive_from = parsed_dates['can_drive_from']
        plan_group.drive_until = parsed_dates['drive_until']
        plan_group.status = status
        plan_group.save()

        # Обновляем даты в карточке группы
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

        return JsonResponse({'success': True, 'message': f'Группа {group.group_number} успешно обновлена'})

    except Exception as e:
        logger.error(f"Ошибка при обновлении группы: {e}", exc_info=True)
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


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

        # Каскадное удаление сработает автоматически благодаря on_delete=models.CASCADE в MasterPlanDistribution
        plan_group.delete()

        logger.info(f"🗑️ Группа {group_number} удалена из генерального плана")
        return JsonResponse({'success': True, 'message': f'Группа {group_number} удалена из плана'})

    except MasterPlanGroup.DoesNotExist:
        return JsonResponse({'error': 'Группа в плане не найдена'}, status=404)
    except Exception as e:
        logger.error(f"Ошибка при удалении группы: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)