# DrSl/management/commands/create_roles.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from vault.models import VaultEntry
from groups.models import Group as DrGroup, SchedulePlan
from students.models import Student
from teachers.models import Teacher
from masters.models import Master
from classrooms.models import Classroom
from reference.models import GroupCategory, LessonTopic


class Command(BaseCommand):
    help = 'Создаёт роли: Админ, Пользователь, Гость'

    def handle(self, *args, **options):
        # 🔹 1. АДМИН — полный доступ
        admin_group, _ = Group.objects.get_or_create(name='admin')
        admin_group.permissions.set(Permission.objects.all())
        self.stdout.write(self.style.SUCCESS('✅ Создана роль: Админ'))

        # 🔹 2. ПОЛЬЗОВАТЕЛЬ — доступ ко всему, кроме админки и удаления
        user_group, _ = Group.objects.get_or_create(name='user')

        # Разрешаем: view, add, change (но НЕ delete) для всех моделей
        perms = []
        for model in [VaultEntry, DrGroup, SchedulePlan, Student, Teacher, Master, Classroom, GroupCategory,
                      LessonTopic]:
            ct = ContentType.objects.get_for_model(model)
            for codename in ['view_%s' % model._meta.model_name,
                             'add_%s' % model._meta.model_name,
                             'change_%s' % model._meta.model_name]:
                try:
                    perm = Permission.objects.get(content_type=ct, codename=codename)
                    perms.append(perm)
                except Permission.DoesNotExist:
                    pass
        user_group.permissions.set(perms)
        self.stdout.write(self.style.SUCCESS('✅ Создана роль: Пользователь'))

        # 🔹 3. ГОСТЬ — только просмотр
        guest_group, _ = Group.objects.get_or_create(name='guest')

        guest_perms = []
        for model in [DrGroup, Student, Teacher, Master, Classroom, GroupCategory, LessonTopic]:
            ct = ContentType.objects.get_for_model(model)
            try:
                perm = Permission.objects.get(
                    content_type=ct,
                    codename='view_%s' % model._meta.model_name
                )
                guest_perms.append(perm)
            except Permission.DoesNotExist:
                pass
        guest_group.permissions.set(guest_perms)
        self.stdout.write(self.style.SUCCESS('✅ Создана роль: Гость'))

        self.stdout.write(self.style.SUCCESS('\n🎉 Все роли созданы!'))
        self.stdout.write(
            'Теперь назначьте пользователям группы в админке: Пользователи → Выберите пользователя → Группы')