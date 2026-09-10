# master_plan/apps.py
from django.apps import AppConfig


class MasterPlanConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'master_plan'
    verbose_name = '🗺️ Генеральный план'