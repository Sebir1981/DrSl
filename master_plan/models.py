# master_plan/models.py
from django.db import models
from django.db.models import Sum, F
from django.contrib.auth.models import User
from django.utils import timezone


class MasterPlanGroup(models.Model):
    """Группа в генеральном плане"""
    STATUS_CHOICES = [
        ('recruiting', 'В наборе'),
        ('active', 'Занимается'),
        ('archived', 'В архиве'),
    ]

    group = models.ForeignKey(
        'groups.Group',
        on_delete=models.CASCADE,
        verbose_name="Учебная группа",
        related_name='master_plan_groups'
    )
    hours_per_student = models.DecimalField(
        "Часов на человека",
        max_digits=5,
        decimal_places=1,
        default=50
    )
    distribution_date = models.DateField(
        "Дата раздачи",
        null=True,
        blank=True
    )
    can_drive_from = models.DateField(
        "Можно катать с",
        null=True,
        blank=True
    )
    drive_until = models.DateField(
        "Выкатать до",
        null=True,
        blank=True
    )
    status = models.CharField(
        "Ситуация",
        max_length=20,
        choices=STATUS_CHOICES,
        default='recruiting'
    )
    teacher = models.ForeignKey(
        'teachers.Teacher',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Преподаватель"
    )
    is_archived = models.BooleanField("В архиве", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Группа в плане"
        verbose_name_plural = "Группы в плане"
        ordering = ['group__group_number']

    def __str__(self):
        return f"{self.group.group_number} ({self.get_status_display()})"

    # =========================================================
    # 🔹 Свойства для расчёта статистики
    # =========================================================
    @property
    def total_students(self):
        """Общее количество студентов в группе"""
        return self.group.students.count()

    @property
    def total_hours(self):
        """Всего положенных часов = студенты × часов на человека"""
        return self.total_students * float(self.hours_per_student)

    @property
    def driven_hours(self):
        """
        Выкатано часов.

        СЕЙЧАС: Заглушка 36 (для тестирования)
        ПОЗЖЕ: Будет рассчитываться из путевых листов (когда реализуем эту модель)

        Пример будущей реализации:
        return self.group.students.aggregate(
            total=Sum('driving_hours_completed')
        )['total'] or 0
        """
        return 36  # TODO: Заменить на расчёт из путевых листов

    @property
    def driven_students_count(self):
        """
        Количество студентов, которые полностью выкатали свои часы.
        Считается по полю driving_hours_completed у каждого студента.

        ПОЗЖЕ: driving_hours_completed будет заполняться автоматически
        из путевых листов (сумма часов по всем поездкам студента).
        """
        return self.group.students.filter(
            driving_hours_required__gt=0,
            driving_hours_completed__gte=F('driving_hours_required')
        ).count()

    @property
    def remaining_hours(self):
        """Осталось выкатать часов (общее)"""
        return max(0, self.total_hours - self.driven_hours)

    @property
    def is_completed(self):
        """
        Все ли студенты группы полностью выкатали часы.
        Группа готова к архивации, когда это свойство == True.

        ПОКА НЕ РАБОТАЕТ: так как driven_hours = 36 (заглушка)
        Будет работать после реализации путевых листов.
        """
        return (self.driven_students_count >= self.total_students) and (self.total_students > 0)

    @property
    def days_until_drive_deadline(self):
        """Сколько дней осталось до даты 'Выкатать до'"""
        if not self.drive_until:
            return None
        return (self.drive_until - timezone.now().date()).days

    @property
    def drive_until_status(self):
        """Цветовой статус даты 'Выкатать до':
        normal  — больше 14 дней
        warning — 14 дней и меньше (оранжевая)
        danger  — 7 дней и меньше (красная)
        none    — дата не задана
        """
        days = self.days_until_drive_deadline
        if days is None:
            return 'none'
        if days <= 7:
            return 'danger'
        if days <= 14:
            return 'warning'
        return 'normal'


class MasterPlanDistribution(models.Model):
    """Распределение мастеров по группам"""
    plan_group = models.ForeignKey(
        MasterPlanGroup,
        on_delete=models.CASCADE,
        related_name='distributions',
        verbose_name="Группа"
    )
    master = models.ForeignKey(
        'masters.MasterPouts',
        on_delete=models.CASCADE,
        related_name='distributions',
        verbose_name="Мастер"
    )
    students_count = models.IntegerField("Количество человек", default=0)
    completed_count = models.IntegerField("Выкатано человек", default=0)

    class Meta:
        verbose_name = "Распределение"
        verbose_name_plural = "Распределения"
        unique_together = ['plan_group', 'master']

    def __str__(self):
        return f"{self.master} → {self.plan_group.group.group_number}: {self.students_count}"