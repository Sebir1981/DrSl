# master_plan/admin.py
from django.contrib import admin
from .models import MasterPlanGroup, MasterPlanDistribution


class DistributionInline(admin.TabularInline):
    model = MasterPlanDistribution
    extra = 1


@admin.register(MasterPlanGroup)
class MasterPlanGroupAdmin(admin.ModelAdmin):
    list_display = [
        'group', 'status', 'hours_per_student',
        'can_drive_from', 'drive_until', 'teacher', 'is_archived'
    ]
    list_filter = ['status', 'is_archived']
    search_fields = ['group__group_number']
    inlines = [DistributionInline]


@admin.register(MasterPlanDistribution)
class MasterPlanDistributionAdmin(admin.ModelAdmin):
    list_display = ['plan_group', 'master', 'students_count', 'completed_count']
    list_filter = ['plan_group__status']