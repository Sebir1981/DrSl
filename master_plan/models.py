# master_plan/models.py
from django.db import models
from django.db.models import Sum, F
from django.contrib.auth.models import User
from django.utils import timezone
from students.models import Student
from masters.models import MasterPouts


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
        "Статус",
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
        ordering = ['created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['group'],
                condition=models.Q(is_archived=False),
                name='unique_active_plan_group_per_group'
            ),
        ]

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
        """
        result = self.group.students.aggregate(
            total=Sum('driving_hours_completed')
        )['total']
        return float(result) if result else 0.0

    @property
    def driven_students_count(self):
        """Количество студентов, полностью выкатавших свои часы."""
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
    # 🔹 Пересчёт completed_count для всех распределений
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

        driven_students = self.driven_students_count

        for dist in distributions:
            if dist.students_count > 0:
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

    # 🔥 Флаг: распределение создано автоматически из платных услуг
    auto_assigned = models.BooleanField(
        "Автораспределение из услуг",
        default=False,
        help_text=(
            "True, если все студенты этого распределения назначены "
            "автоматически из платных услуг"
        )
    )

    class Meta:
        verbose_name = "Распределение"
        verbose_name_plural = "Распределения"
        unique_together = ['plan_group', 'master']

    def __str__(self):
        return f"{self.master} → {self.plan_group.group.group_number}: {self.students_count}"


class StudentMasterAssignment(models.Model):
    """
    Построчная привязка: какой студент к какому мастеру назначен
    в рамках конкретной группы генерального плана.
    """
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='master_assignments',
        verbose_name='Студент'
    )
    plan_group = models.ForeignKey(
        'MasterPlanGroup',
        on_delete=models.CASCADE,
        related_name='student_assignments',
        verbose_name='Группа в плане'
    )
    master = models.ForeignKey(
        MasterPouts,
        on_delete=models.CASCADE,
        related_name='student_assignments',
        verbose_name='Мастер'
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата назначения'
    )

    # 🔥 Флаг: назначение сделано автоматически из платной услуги
    is_auto = models.BooleanField(
        "Назначен автоматически",
        default=False,
        help_text="True, если назначение сделано из платной услуги"
    )

    class Meta:
        verbose_name = 'Назначение студента мастеру'
        verbose_name_plural = 'Назначения студентов мастерам'
        unique_together = ('student', 'plan_group')
        indexes = [
            models.Index(fields=['plan_group', 'master']),
            models.Index(fields=['student']),
        ]

    def __str__(self):
        return f"{self.student} → {self.master} ({self.plan_group})"

class StudentReassignmentLog(models.Model):
    """
    Журнал перераспределений студентов между мастерами.
    Используется для отчётов: кто, когда, кого, от кого к кому и почему.
    """
    REASON_CHOICES = [
        ('auto_service', 'Автоназначение из услуг'),
        ('manual', 'Первое назначение вручную'),
        ('reassign', 'Перераспределить'),
        ('student_request', 'По требованию учащегося'),
        ('master_request', 'По требованию мастера'),
    ]

    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='reassignment_logs',
        verbose_name='Студент'
    )
    plan_group = models.ForeignKey(
        'MasterPlanGroup',
        on_delete=models.CASCADE,
        related_name='reassignment_logs',
        verbose_name='Группа в плане'
    )
    from_master = models.ForeignKey(
        'masters.MasterPouts',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reassignments_from',
        verbose_name='От мастера'
    )
    to_master = models.ForeignKey(
        'masters.MasterPouts',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reassignments_to',
        verbose_name='К мастеру'
    )
    reason = models.CharField(
        'Причина',
        max_length=32,
        choices=REASON_CHOICES,
        default='reassign'
    )
    comment = models.TextField(
        'Комментарий',
        blank=True, default=''
    )
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reassignments_created',
        verbose_name='Кто выполнил'
    )
    created_at = models.DateTimeField(
        'Дата',
        auto_now_add=True
    )

    class Meta:
        verbose_name = 'Перераспределение студента'
        verbose_name_plural = 'Журнал перераспределений'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['plan_group', '-created_at']),
            models.Index(fields=['student', '-created_at']),
            models.Index(fields=['reason']),
        ]

    def __str__(self):
        return f"{self.student} : {self.from_master} → {self.to_master} ({self.get_reason_display()})"