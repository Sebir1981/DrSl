# reference/apps.py
from django.apps import AppConfig

class ReferenceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reference'
    verbose_name = '📖 Справочники'  # ✅ Имя папки в боковом меню