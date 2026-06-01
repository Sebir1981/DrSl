# teachers/admin.py
from django import forms
from django.contrib import admin
from .models import Teacher


class TeacherAdminForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = '__all__'
        widgets = {
            'phone': forms.TextInput(attrs={
                'id': 'id_phone',
                'placeholder': '+375 (__) ___-__-__',
                'maxlength': '19',
            }),
        }


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    form = TeacherAdminForm

    # ✅ Убрано: autocomplete_fields, classroom
    list_display = ('full_name', 'phone', 'vehicle_types', 'schedule_badges', 'is_active')
    list_filter = ('is_active', 'teaches_truck', 'teaches_car', 'schedule_morning', 'schedule_evening',
                   'schedule_weekend')
    search_fields = ('last_name', 'first_name', 'patronymic', 'phone')

    # ✅ Чистая разметка: ФИО в столбик, чекбоксы в строки
    fieldsets = (
        ('👤 Личные данные', {
            'fields': (
                'last_name',
                'first_name',
                'patronymic',
                'phone',
                'contract_main',
                'contract_part_time',
                ('schedule_morning', 'schedule_evening', 'schedule_weekend'),
                ('teaches_car', 'teaches_truck'),
                'is_active',
            ),
        }),
    )

    class Media:
        js = ('js/phone-mask.js',)
        css = {'all': ('css/admin-teacher.css',)}

    @admin.display(description="ФИО", ordering='last_name')
    def full_name(self, obj):
        return f"{obj.last_name} {obj.first_name} {obj.patronymic}".strip()

    @admin.display(description="Тип ТС")
    def vehicle_types(self, obj):
        b = []
        if obj.teaches_truck: b.append('🚛')
        if obj.teaches_car: b.append('🚗')
        return ' '.join(b) or '—'

    @admin.display(description="График")
    def schedule_badges(self, obj):
        b = []
        if obj.schedule_morning: b.append('🌅')
        if obj.schedule_evening: b.append('🌆')
        if obj.schedule_weekend: b.append('📅')
        return ' '.join(b) or '—'