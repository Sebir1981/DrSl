# groups/admin.py
from django.contrib import admin
from django.db import models
from django import forms
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from reference.models import GroupCategory, Credit  # ✅ Импортируем для autocomplete_fields
from .models import Group, CreditResult, ExamResult
from DrSl.widgets import RuDateWidget


# =============================================================================
# 🔹 Базовый класс админки
# =============================================================================
class BaseAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.DateField: {'widget': RuDateWidget()},
        models.TimeField: {'widget': forms.TimeInput(attrs={
            'type': 'time', 'step': '60',
            'style': 'width: 90px; min-width: 90px; padding: 4px 6px;'
        })},
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
        for field_name in ['duration', 'schedule_type', 'time_session']:
            if field_name in self.fields:
                self.fields[field_name].choices = [
                    c for c in self.fields[field_name].choices if c[0] != ''
                ]
                if not self.instance.pk:
                    if field_name == 'duration': self.fields[field_name].initial = 'standard'
                    if field_name == 'schedule_type': self.fields[field_name].initial = 'directed'
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
    list_display = ('group_number', 'category', 'classroom', 'teacher', 'schedule_type', 'time_session', 'status',
                    'contract_period')
    list_filter = ('status', 'schedule_type', 'time_session', 'category')
    search_fields = ('group_number', 'category__code', 'teacher__last_name', 'classroom__classroom_number')
    autocomplete_fields = ('classroom', 'teacher')
    readonly_fields = ('created_at', 'updated_at', 'contract_section_header', 'standard_time_display')

    fieldsets = (
        ('🔢 Идентификаторы', {'fields': ('group_number', 'category', 'classroom', 'teacher')}),

        # 🔹 🔥 ОБНОВЛЕНО: Добавлены даты экзаменов в раздел Договора
        ('📅 Договор и экзамены', {
            'fields': (
                'contract_section_header',
                'contract_start',
                'contract_end',
                'status',
                # ✅ Новые поля дат экзаменов
                'exam_internal_theory_date',
                'exam_internal_driving_date',
                'exam_gai_date',
            ),
            'description': '📚 Даты внутренних экзаменов и сдачи в ГАИ'
        }),

        ('🗓️ Расписание', {
            'fields': ('schedule_type', 'time_session', 'duration', 'standard_time_display', 'time_start', 'time_end'),
            'classes': ('collapse',)
        }),
        ('📊 Системное', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse', 'extrapretty')
        }),
    )

    @admin.display(description="")
    def contract_section_header(self, obj):
        return mark_safe(
            '<div style="font-weight:600; color:#475569; margin-bottom:8px; padding-bottom:4px; border-bottom:2px solid #e2e8f0;">Действие договора</div>')

    @admin.display(description="⏱ Стандартное время")
    def standard_time_display(self, obj):
        sched = obj.schedule_type or ''
        sess = obj.time_session or ''
        if sched == 'weekend':
            time_str = '13:30–18:20'
        elif sess in ('morning', 'evening'):
            time_str = '08:40–13:30' if sess == 'morning' else '17:30–21:15'
        else:
            return mark_safe('<span style="color:#94a3b8;">Выберите Смену или Тип расписания</span>')
        start, end = time_str.split('–')
        return mark_safe(
            f'<strong>{time_str}</strong><button type="button" onclick="window.fillStandardTime(\'{start}\', \'{end}\')" style="margin-left:10px;padding:4px 10px;background:#4facfe;color:white;border:none;border-radius:4px;cursor:pointer;font-size:12px;">▶ Заполнить</button>')

    @admin.display(description="Период договора")
    def contract_period(self, obj):
        if obj.contract_start and obj.contract_end:
            return f"{obj.contract_start.strftime('%d.%m.%Y')} — {obj.contract_end.strftime('%d.%m.%Y')}"
        return "—"

    class Media:
        js = (
            'js/date-mask.js?v=3',
            'js/category-hint.js',
            'js/group-time-autofill.js?v=6',
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
    # ✅ autocomplete_fields для 'credit' будет работать, т.к. Credit зарегистрирован в reference/admin.py
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