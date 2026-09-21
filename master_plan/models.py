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
        "Статус",  # 🔥 Исправлено: было "Ситуация"
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
        ordering = ['created_at']  # 🔥 Порядок добавления, а не по номеру

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
        Выкатано часов — сумма driving_hours_completed по всем студентам группы.
        Работает корректно, когда у студентов заполнено driving_hours_completed.
        """
        result = self.group.students.aggregate(
            total=Sum('driving_hours_completed')
        )['total']
        return float(result) if result else 0.0

    @property
    def driven_students_count(self):
        """
        Количество студентов, которые полностью выкатали свои часы.
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
        """Все ли студенты группы полностью выкатали часы"""
        return (self.driven_students_count >= self.total_students) and (self.total_students > 0)

    @property
    def days_until_drive_deadline(self):
        """Сколько дней осталось до даты 'Выкатать до'"""
        if not self.drive_until:
            return None
        return (self.drive_until - timezone.now().date()).days

    @property
    def drive_until_status(self):
        """Цветовой статус даты 'Выкатать до'"""
        days = self.days_until_drive_deadline
        if days is None:
            return 'none'
        if days <= 7:
            return 'danger'
        if days <= 14:
            return 'warning'
        return 'normal'

    # =========================================================
    # 🔹 НОВЫЙ МЕТОД: Пересчёт completed_count для всех распределений
    # =========================================================
    def recalculate_distribution_completed(self):
        """
        Пересчитывает completed_count для всех распределений этой группы.
        Распределяет выкатанных студентов пропорционально students_count.
        """
        distributions = self.distributions.all()
        total_distributed = sum(d.students_count for d in distributions)

        if total_distributed == 0:
            distributions.update(completed_count=0)
            return

        # Получаем реально выкатанных студентов в этой группе
        driven_students = self.driven_students_count

        for dist in distributions:
            if dist.students_count > 0:
                # Пропорциональное распределение
                ratio = dist.students_count / total_distributed
                dist.completed_count = round(driven_students * ratio)
                dist.save(update_fields=['completed_count'])


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