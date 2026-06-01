# masters/admin.py
from django.contrib import admin
from .models import Master
from .forms import MasterAdminForm
from DrSl.admin import BaseAdmin


@admin.register(Master)
class MasterAdmin(BaseAdmin):
    form = MasterAdminForm
    list_display = ('full_name', 'phone', 'license_number', 'license_expiry', 'medical_expiry')
    list_filter = ('license_categories', 'teaching_categories', 'license_expiry', 'medical_expiry')
    search_fields = ('last_name', 'first_name', 'phone', 'license_number')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('👤 Личные данные', {'fields': ('last_name', 'first_name', 'patronymic', 'birth_date', 'address', 'phone')}),
        ('🪂 Водительское удостоверение', {'fields': ('license_number', 'license_expiry', 'license_categories')}),
        ('🏥 Мед. справка', {'fields': ('medical_expiry',)}),
        ('🎓 Обучение', {'fields': ('teaching_categories',)}),
        ('🕒 Время работы', {'fields': ('work_time_start', 'work_time_end')}),
        ('📊 Системное', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse', 'extrapretty')}),
    )

    @admin.display(description="ФИО")
    def full_name(self, obj):
        return f"{obj.last_name} {obj.first_name} {obj.patronymic}".strip()