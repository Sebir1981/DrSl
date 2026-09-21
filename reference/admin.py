from django.contrib import admin
from .models import SubjectDictionary, GroupCategory, Credit, LessonTopic
from .models import PracticeCategory, PracticeExercise


@admin.register(SubjectDictionary)
class SubjectDictionaryAdmin(admin.ModelAdmin):
    list_display = ('short_name', 'name', 'description')
    search_fields = ('name', 'short_name')
    ordering = ('name',)


@admin.register(GroupCategory)
class GroupCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'description')
    search_fields = ('code', 'description')


@admin.register(Credit)
class CreditAdmin(admin.ModelAdmin):
    list_display = ('number', 'topic')
    search_fields = ('topic',)


@admin.register(LessonTopic)
class LessonTopicAdmin(admin.ModelAdmin):
    list_display = ('subject', 'topic_number', 'hours', 'content')
    list_filter = ('subject',)
    search_fields = ('content',)
    ordering = ('subject', 'topic_number')


@admin.register(PracticeCategory)
class PracticeCategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name')
    search_fields = ('code', 'name')


@admin.register(PracticeExercise)
class PracticeExerciseAdmin(admin.ModelAdmin):
    list_display = ('exercise_number', 'name', 'category', 'hours')
    list_filter = ('category',)
    search_fields = ('exercise_number', 'name')