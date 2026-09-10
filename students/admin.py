# students/admin.py
from django.contrib import admin
from django import forms
from django.db import models
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from .models import Student, StudentHistory
from DrSl.widgets import RuDateWidget


# =============================================================================
# 🔹 Форма студента (кастомные виджеты)
# =============================================================================
class StudentAdminForm(forms.ModelForm):
    class Meta:
        model = Student
        # ✅ Явный список полей вместо '__all__' (исправляет замечание SonarQube)
        fields = [
            'last_name', 'first_name', 'patronymic', 'phone',
            'birth_date', 'enrolled_date', 'graduated_date', 'transferred_date',
            'group', 'teacher', 'master',
            'place_of_birth', 'place_of_residence', 'place_of_registration',
            'work_study_place', 'position', 'gearbox_type',
        ]
        widgets = {
            'birth_date': RuDateWidget(),
            'enrolled_date': RuDateWidget(),
            'graduated_date': RuDateWidget(),
            'transferred_date': RuDateWidget(),
        }


# =============================================================================
# 🔹 Админка: Учащиеся
# =============================================================================
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    form = StudentAdminForm

    # 🔹 Список отображаемых колонок
    list_display = (
        'full_name', 'phone', 'group', 'teacher', 'master',
        'gearbox_type', 'enrolled_date', 'get_status_badge'
    )

    # 🔹 Фильтры справа
    list_filter = ('group', 'teacher', 'master', 'gearbox_type', 'enrolled_date', 'graduated_date')

    # 🔹 Поиск
    search_fields = ('last_name', 'first_name', 'patronymic', 'phone', 'group__group_number')

    # 🔹 Автодополнение
    autocomplete_fields = ('group', 'teacher', 'master')

    # 🔹 Поля только для чтения
    readonly_fields = ('created_at', 'updated_at', 'activity_log_display', 'full_name')

    # 🔹 Группировка полей в форме
    fieldsets = (
        ('👤 Личные данные', {
            'fields': ('last_name', 'first_name', 'patronymic', 'phone', 'birth_date', 'full_name')
        }),
        ('🏠 Адреса', {
            'fields': ('place_of_birth', 'place_of_residence', 'place_of_registration'),
            'classes': ('collapse',)
        }),
        ('💼 Работа/Учёба', {
            'fields': ('work_study_place', 'position'),
            'classes': ('collapse',)
        }),
        ('🔗 Привязка к учебному процессу', {
            'fields': ('group', 'teacher', 'master', 'gearbox_type')
        }),
        ('📅 Даты обучения', {
            'fields': ('enrolled_date', 'graduated_date', 'transferred_date')
        }),
        ('📜 История активности', {
            'fields': ('activity_log_display',),
            'description': '📋 Автоматический журнал событий (переводы, зачёты, экзамены, смены преподавателей)'
        }),
        ('⚙️ Системное', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse', 'extrapretty')
        }),
    )

    # 🔹 Метод для красивого отображения статуса
    @admin.display(description='Статус', ordering='graduated_date')
    def get_status_badge(self, obj):
        if obj.graduated_date:
            return '✅ Выпуск'
        if obj.activity_log:
            last_event = obj.activity_log[-1] if obj.activity_log else {}
            event_type = last_event.get('type', '')
            if event_type in ['dismissal', 'dismissed']:
                return '❌ Отчислен'
            if event_type in ['refusal', 'refused']:
                return '🚫 Отказ'
            if event_type in ['suspension', 'suspended']:
                return '⏸️ Приостановлен'
        return '🟢 Активен'

    # =====================================================================
    # 🔹 Вспомогательная функция: парсинг деталей события
    # =====================================================================
    def _parse_event_details(self, details, entry):
        """Разбирает details словарь на строку описания"""
        detail_parts = []

        if 'result_icon' in details and 'result' in details:
            detail_parts.append(f"{details['result_icon']} {details['result']}")

        if 'attempt_number' in details:
            detail_parts.append(f"Попытка №{details['attempt_number']}")

        if 'attempt_type' in details:
            type_label = 'Платная' if details['attempt_type'] == 'paid' else 'Бесплатная'
            detail_parts.append(type_label)

        if 'topic' in details:
            topic = details['topic']
            detail_parts.append(topic[:40] + ('…' if len(topic) > 40 else ''))

        if 'from_group' in details and 'to_group' in details:
            detail_parts.append(f"{details['from_group']} → {details['to_group']}")

        # Смена преподавателя
        if 'from' in details and 'to' in details and entry.get('type') == 'teacher_change':
            detail_parts.append(f"{details['from']} → {details['to']}")

        return ' • '.join(detail_parts) if detail_parts else ''

    # =====================================================================
    # 🔹 Вспомогательная функция: выбор цвета и иконки
    # =====================================================================
    def _get_event_style(self, event_type, details):
        """Возвращает кортеж (color, icon) для события"""
        if event_type in ['dismissal', 'dismissed', 'refusal', 'refused']:
            return '#dc2626', '❌'

        if event_type == 'credit_result':
            color = '#4facfe' if details.get('result') == 'passed' else '#f59e0b'
            return color, '📋'

        if event_type == 'transfer':
            return '#10b981', '🔄'

        if event_type == 'teacher_change':
            return '#8b5cf6', '👨‍🏫'

        return '#334155', '•'

    # =====================================================================
    # 🔹 Отображение JSON-лога в читаемом виде (Теперь КОРОТКАЯ)
    # =====================================================================
    @admin.display(description='📋 Журнал активности')
    def activity_log_display(self, obj):
        if not obj.activity_log:
            return mark_safe('<span style="color:#94a3b8;">— Записей нет —</span>')   # nosec B308

        log_items = []
        for entry in reversed(obj.activity_log[-20:]):
            date = entry.get('date', '—')
            title = entry.get('title', 'Событие')
            details = entry.get('details', {})
            event_type = entry.get('type', '')

            # Вызываем наши маленькие помощники
            detail_str = self._parse_event_details(details, entry)
            color, icon = self._get_event_style(event_type, details)

            log_items.append(format_html(
                '<div style="padding:6px 0; border-bottom:1px solid #f1f5f9; color:{};">'
                '<strong>[{}]</strong> {} {}<br>'
                '<span style="color:#64748b; margin-left:18px; font-size:11px;">{}</span>'
                '</div>',
                color, date, icon, title, detail_str
            ))

        return format_html(
            '<div style="max-height:300px; overflow-y:auto; font-size:12px; background:#f8fafc; padding:10px; border-radius:6px;">{}</div>',
            format_html('{}', *log_items)
        )

    # =====================================================================
    # 🔹 Отслеживание смены преподавателя и запись в activity_log
    # =====================================================================
    def save_model(self, request, obj, form, change):
        if change:  # Срабатывает только при редактировании существующей записи
            try:
                old_student = Student.objects.get(pk=obj.pk)
                if old_student.teacher_id != obj.teacher_id:
                    log_entry = {
                        'type': 'teacher_change',
                        'date': timezone.now().date().strftime('%Y-%m-%d'),
                        'title': 'Смена преподавателя',
                        'details': {
                            'from': str(old_student.teacher) if old_student.teacher else '—',
                            'to': str(obj.teacher) if obj.teacher else '—'
                        }
                    }
                    current_log = obj.activity_log or []
                    current_log.append(log_entry)
                    obj.activity_log = current_log
            except Student.DoesNotExist:
                pass
            obj.save(update_fields=['teacher', 'activity_log', 'updated_at'])
        super().save_model(request, obj, form, change)

    class Media:
        js = ('js/phone-mask.js?v=2',)


# =============================================================================
# 🔹 Админка: История событий (отдельная модель)
# =============================================================================
@admin.register(StudentHistory)
class StudentHistoryAdmin(admin.ModelAdmin):
    list_display = ('student', 'event_type', 'event_date', 'order_number', 'created_at')
    list_filter = ('event_type', 'event_date', 'created_at')
    search_fields = ('student__last_name', 'student__first_name', 'order_number')
    autocomplete_fields = ('student', 'created_by')

    fieldsets = (
        ('👤 Учащийся', {'fields': ('student',)}),
        ('📋 Событие', {'fields': ('event_type', 'event_date', 'comment')}),
        ('📄 Приказ', {'fields': ('order_number', 'order_date')}),
        ('⚙️ Системное', {'fields': ('created_by', 'created_at'), 'classes': ('collapse',)}),
    )

    def save_model(self, request, obj, form, change):
        """Автоматически заполняем кто создал запись"""
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)