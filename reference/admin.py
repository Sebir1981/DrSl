# reference/admin.py
from django.contrib import admin
from .models import GroupCategory, Credit


@admin.register(GroupCategory)
class GroupCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'description']
    search_fields = ['code', 'description']


@admin.register(Credit)
class CreditAdmin(admin.ModelAdmin):
    list_display = ['number', 'topic']
    ordering = ['number']
    search_fields = ['topic']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False