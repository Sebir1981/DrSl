# groups/admin.py
from django.contrib import admin
from django.db import models
from django import forms
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from reference.models import GroupCategory, Credit
from .models import Group, CreditResult, ExamResult
from DrSl.widgets import RuDateWidget


# =============================================================================
# 🔹 Базовый класс админки
# =============================================================================
class BaseAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.DateField: {'widget': RuDateWidget()},
    }


# =============================================================================
# 🔹 Форма для группы
# =============================================================================
class GroupAdminForm(forms.ModelForm):
    contract_start = forms.DateField(
        label="Действие договора",
        input_formats=['%d.%m.%Y'],
        widget=RuDateWidget(attrs={'placeholder': 'дд.мм.гггг'}),
        required=False,
    )
    contract_end = forms.DateField(
        label="",
        input_formats=['%d.%m.%Y'],
        widget=RuDateWidget(attrs={'placeholder': 'дд.мм.гггг'}),
        required=False,
    )

    class Meta:
        model = Group
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ['duration', 'schedule_type']:
            if field_name in self.fields:
                self.fields[field_name].choices = [
                    c for c in self.fields[field_name].choices if c[0] != ''
                ]
        if not self.instance.pk:
            if 'duration' in self.fields:
                self.fields['duration'].initial = 'standard'
            if 'schedule_type' in self.fields:
                self.fields['schedule_type'].initial = 'directed'
        if 'category' in self.fields:
            field = self.fields['category']
            field.widget.attrs['class'] = 'category-with-hint'
            hints = {
                str(cat.id): cat.hint.replace('"', '&quot;').replace("'", "&#39;")
                for cat in GroupCategory.objects.exclude(hint__exact='')
            }
            if hints:
                field.widget.attrs['data-hints'] = format_html(
                    '{{{}}}',
                    ', '.join(f'"{k}":"{v}"' for k, v in hints.items())
                )


# =============================================================================
# 🔹 Админка: Группы
# =============================================================================
@admin.register(Group)
class GroupAdmin(BaseAdmin):
    form = GroupAdminForm

    # ✅ Убраны time_session, time_start, time_end
    list_display = (
        'group_number', 'category', 'classroom', 'teacher',
        'schedule_type', 'status', 'contract_period'
    )

    # ✅ Убран time_session
    list_filter = ('status', 'schedule_type', 'category')

    search_fields = ('group_number', 'category__code', 'teacher__last_name', 'classroom__classroom_number')
    autocomplete_fields = ('classroom', 'teacher')

    # ✅ Убран standard_time_display
    readonly_fields = ('created_at', 'updated_at', 'contract_section_header')

    fieldsets = (
        ('🔢 Идентификаторы', {
            'fields': ('group_number', 'category', 'classroom', 'teacher')
        }),
        ('📅 Договор и экзамены', {
            'fields': (
                'contract_section_header',
                'contract_start',
                'contract_end',
                'status',
                'exam_internal_theory_date',
                'exam_internal_driving_date',
                'exam_gai_date',
            ),
            'description': '📚 Даты внутренних экзаменов и сдачи в ГАИ'
        }),
        # ✅ Убрано время из расписания
        ('🗓️ Расписание', {
            'fields': ('schedule_type', 'duration'),
            'classes': ('collapse',)
        }),
        ('📊 Системное', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse', 'extrapretty')
        }),
    )

    @admin.display(description="")
    def contract_section_header(self, obj):
        return mark_safe( # nosec B308
            '<div style="font-weight:600; color:#475569; margin-bottom:8px; '
            'padding-bottom:4px; border-bottom:2px solid #e2e8f0;">Действие договора</div>')

    @admin.display(description="Период договора")
    def contract_period(self, obj):
        if obj.contract_start and obj.contract_end:
            return f"{obj.contract_start.strftime('%d.%m.%Y')} — {obj.contract_end.strftime('%d.%m.%Y')}"
        return "—"

    class Media:
        js = (
            'js/date-mask.js?v=3',
            'js/category-hint.js',
        )
        css = {'all': ('css/date-fields.css',)}


# =============================================================================
# 🔹 Админка: Результаты зачётов
# =============================================================================
@admin.register(CreditResult)
class CreditResultAdmin(admin.ModelAdmin):
    list_display = ['student', 'credit', 'credit_date', 'chairman']
    list_filter = ['credit', 'chairman', 'student__group']
    search_fields = ['student__last_name', 'student__first_name', 'chairman__last_name']
    autocomplete_fields = ['student', 'credit', 'chairman', 'member1', 'member2', 'member3']
    date_hierarchy = 'credit_date'


# =============================================================================
# 🔹 Админка: Результаты экзаменов
# =============================================================================
@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = ['student', 'exam_type', 'attempt_type', 'status', 'exam_date', 'examiner']
    list_filter = ['exam_type', 'attempt_type', 'status', 'examiner', 'student__group']
    search_fields = ['student__last_name', 'student__first_name']
    autocomplete_fields = ['student', 'examiner']
    date_hierarchy = 'exam_date'
    list_editable = ['status']