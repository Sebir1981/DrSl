from django.contrib import admin
from .models import GroupCategory, Credit, LessonTopic  # 🔹 Добавили LessonTopic


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


# 🔹 НОВОЕ: Админка для тем занятий
@admin.register(LessonTopic)
class LessonTopicAdmin(admin.ModelAdmin):
    list_display = ('category', 'topic_number', 'hours', 'content_preview')
    list_filter = ('category',)
    search_fields = ('content', 'topic_number')
    ordering = ('category', 'topic_number')

    def content_preview(self, obj):
        return obj.content[:60] + "..." if len(obj.content) > 60 else obj.content

    content_preview.short_description = "Содержание"