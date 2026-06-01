# vault/apps.py
from django.apps import AppConfig  # ✅ Обязательный импорт

class VaultConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'vault'