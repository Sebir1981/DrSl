# groups/views/__init__.py


from .dashboard import groups_dashboard
from .groups import group_list, group_detail, group_form
from .groups import group_list, group_detail
from .api import group_api_data, check_instructor_availability, get_teacher_schedules
from .credits import (
    credits_exams_dashboard,
    credits_exams_add,
    credits_report,
)
from .schedule_plans import (
    schedule_plans_list,
    schedule_plan_create,
    schedule_plan_ajax_update_day,
    schedule_plan_step2,
    schedule_plan_delete,  # 🔹 НОВОЕ: добавили экспорт
)
from .schedule_plans import (
    schedule_plans_list,
    schedule_plan_create,
    schedule_plan_ajax_update_day,
    schedule_plan_step2,
    schedule_plan_delete,
    schedule_plan_reset,  # ← Добавьте эту строку
)
from .api import group_api_data, check_instructor_availability

# 🔹 Явный список для IDE и линтеров
__all__ = [
    'groups_dashboard',
    'group_list',
    'group_detail',
    'group_form',
    'credits_exams_dashboard',
    'credits_exams_add',
    'credits_report',
    'schedule_plans_list',
    'schedule_plan_create',
    'schedule_plan_ajax_update_day',
    'schedule_plan_step2',
    'schedule_plan_delete',
    'group_api_data',
    'check_instructor_availability',
    'get_teacher_schedules',
]