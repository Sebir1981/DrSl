# DrSl/admin.py
from django.contrib import admin
from django.db import models
from django.shortcuts import redirect
from django.urls import reverse
from .widgets import RuDateWidget

# ✅ Меняем заголовки
admin.site.site_header = "🔐 Автошкола — Управление"
admin.site.site_title = "Админ-панель"
admin.site.index_title = "Выберите раздел"


class BaseAdmin(admin.ModelAdmin):
    """
    Базовая админка:
    1. Автоматически применяет RuDateWidget ко всем DateField
    2. После сохранения редиректит на фронтенд-список, а не в админку
    """
    formfield_overrides = {
        models.DateField: {'widget': RuDateWidget},
    }

    # 🗺️ Карта: модель -> имя фронтенд-URL
    _frontend_urls = {
        'groups.group': 'groups:group_list',
        'students.student': 'students:student_list',
        'classrooms.classroom': 'classrooms:classroom_list',
        'teachers.teacher': 'teachers:teacher_list',
        'vault.vaultentry': 'vault:vault_list',
        # Справочник оставляем в админке, т.к. там часто добавляют много записей подряд
    }

    def response_add(self, request, obj, post_url_continue=None):
        return self._try_redirect_to_frontend(request, obj) or \
            super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        return self._try_redirect_to_frontend(request, obj) or \
            super().response_change(request, obj)

    def _try_redirect_to_frontend(self, request, obj):
        # ✅ Если нажато "Сохранить и продолжить" или "Сохранить и добавить ещё" → остаёмся в админке
        if request.POST.get('_continue') or request.POST.get('_addanother'):
            return None

        key = f"{obj._meta.app_label}.{obj._meta.model_name}"
        url_name = self._frontend_urls.get(key)

        if url_name:
            try:
                return redirect(reverse(url_name))
            except Exception:
                pass
        return None