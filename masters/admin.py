from django.contrib import admin
from .models import MasterPouts


@admin.register(MasterPouts)
class MasterPoutsAdmin(admin.ModelAdmin):
    list_display = ['last_name', 'first_name', 'patronymic', 'license_number', 'phone', 'car']
    list_filter = ['car']
    search_fields = ['last_name', 'first_name', 'patronymic', 'phone']
    ordering = ['last_name', 'first_name']