# master_plan/models.py
from django.db import models
from django.db.models import Sum
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
    archived_at = models.DateTimeField(
        "Дата архивации",
        null=True,
        blank=True,
        help_text="Заполняется автоматически при архивации"
    )
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
    # 🔹 БАЗОВЫЕ ЦИФРЫ
    # =========================================================

    @property
    def total_students(self):
        """Общее количество студентов в группе."""
        return self.group.students.count()

    @property
    def total_hours(self):
        """Всего положенных часов = студенты × часов на человека."""
        return round(self.total_students * float(self.hours_per_student), 1)

    @property
    def driving_threshold(self):
        """
        Порог «вождение выкатано» = plan − 1 ч (экзамен).
        При hours_per_student=50 порог = 49 ч.
        """
        t = float(self.hours_per_student) - 1.0
        return max(0.0, t)

    # =========================================================
    # 🔹 ПЛАН: ВОЖДЕНИЕ + ЭКЗАМЕН
    # =========================================================

    @property
    def driving_hours_plan(self):
        """Часов на вождение = порог × студентов (без экзамена)."""
        return round(self.total_students * self.driving_threshold, 1)

    @property
    def exam_hours_plan(self):
        """Часов на экзамен = 1 ч × количество студентов."""
        return round(1.0 * self.total_students, 1)

    # =========================================================
    # 🔹 РЕАЛЬНО ВЫКАТАННЫЕ ЧАСЫ И УЧЕНИКИ
    # =========================================================

    @property
    def driven_hours(self):
        """
        Реально выкатанные часы — сумма duration_hours_cache
        из всех BookEntry студентов этой группы.
        Экзамен сюда НЕ входит.
        """
        from dispatcher.models import BookEntry

        result = (
            BookEntry.objects
            .filter(book__group_id=self.group_id)
            .aggregate(total=Sum('duration_hours_cache'))
            .get('total')
        )
        return round(float(result or 0), 1)

    def _student_hours_map(self):
        """
        Возвращает {student_id: сумма_часов_из_BookEntry}.
        Кэшируется на объекте, чтобы не делать N запросов.
        """
        cache_key = '_student_hours_map_cache'
        if hasattr(self, cache_key):
            return getattr(self, cache_key)

        from dispatcher.models import BookEntry

        rows = (
            BookEntry.objects
            .filter(book__group_id=self.group_id)
            .values('book__student_id')
            .annotate(total=Sum('duration_hours_cache'))
        )
        result = {
            row['book__student_id']: round(float(row['total'] or 0), 1)
            for row in rows
        }
        setattr(self, cache_key, result)
        return result

    @property
    def driven_students_count(self):
        """
        Сколько студентов группы полностью выкатали вождение.
        Читаем часы из BookEntry, а не из Student.driving_hours_completed.
        """
        threshold = self.driving_threshold
        hours_map = self._student_hours_map()

        count = 0
        for s in self.group.students.all():
            if hours_map.get(s.id, 0.0) >= threshold:
                count += 1
        return count

    @property
    def remaining_students(self):
        """Осталось докатать учеников в группе."""
        return max(0, self.total_students - self.driven_students_count)

    def driven_students_for_master(self, master_id):
        """
        Сколько учеников КОНКРЕТНОГО мастера в этой группе выкатали.
        Читаем часы из BookEntry.
        """
        threshold = self.driving_threshold
        hours_map = self._student_hours_map()

        student_ids = list(
            self.student_assignments
            .filter(master_id=master_id)
            .values_list('student_id', flat=True)
        )

        count = 0
        for sid in student_ids:
            if hours_map.get(sid, 0.0) >= threshold:
                count += 1
        return count

    def assigned_students_for_master(self, master_id):
        """Сколько учеников закреплено за конкретным мастером в этой группе."""
        return self.student_assignments.filter(master_id=master_id).count()

    # =========================================================
    # 🔹 ОСТАТКИ (в часах)
    # =========================================================

    @property
    def driving_remaining(self):
        """Осталось выкатать вождение в часах (без экзамена)."""
        return round(max(0.0, self.driving_hours_plan - self.driven_hours), 1)

    @property
    def remaining_hours(self):
        """Общий остаток по плану = план − выкатано."""
        return round(max(0.0, self.total_hours - self.driven_hours), 1)

    @property
    def remaining_hours_with_exam(self):
        """Алиас для remaining_hours."""
        return self.remaining_hours

    # =========================================================
    # 🔹 ЭКЗАМЕН
    # =========================================================

    @property
    def exam_available(self):
        """Экзамен доступен, когда всё вождение выкатано."""
        return self.driving_remaining <= 0 and self.total_students > 0

    @property
    def exam_hours(self):
        """Часы на экзамен, если группа дошла до экзамена, иначе 0."""
        if self.exam_available:
            return self.exam_hours_plan
        return 0.0

    # =========================================================
    # 🔹 СТАТУСЫ И ФЛАГИ
    # =========================================================

    @property
    def is_completed(self):
        """Все ли студенты группы полностью выкатали вождение."""
        return (
            self.total_students > 0
            and self.driven_students_count >= self.total_students
        )

    @property
    def progress_percent(self):
        """Процент выкатанного вождения."""
        if self.driving_hours_plan <= 0:
            return 0.0
        return min(100.0, round(self.driven_hours / self.driving_hours_plan * 100, 1))

    @property
    def days_until_drive_deadline(self):
        """Сколько дней осталось до даты 'Выкатать до'."""
        if not self.drive_until:
            return None
        return (self.drive_until - timezone.now().date()).days

    @property
    def drive_until_status(self):
        """Цветовой статус даты 'Выкатать до'."""
        days = self.days_until_drive_deadline
        if days is None:
            return 'none'
        if days <= 7:
            return 'danger'
        if days <= 14:
            return 'warning'
        return 'normal'

    # =========================================================
    # 🔹 ПЕРЕСЧЁТ РАСПРЕДЕЛЕНИЙ
    # =========================================================

    def recalculate_distribution_completed(self):
        """
        Пересчитывает completed_count для всех распределений этой группы
        пропорционально students_count.
        """
        distributions = list(self.distributions.all())
        total_distributed = sum(d.students_count for d in distributions)

        if total_distributed == 0:
            for d in distributions:
                if d.completed_count != 0:
                    d.completed_count = 0
                    d.save(update_fields=['completed_count'])
            return

        driven_students = self.driven_students_count

        for dist in distributions:
            if dist.students_count > 0:
                ratio = dist.students_count / total_distributed
                new_completed = round(driven_students * ratio)
                if dist.completed_count != new_completed:
                    dist.completed_count = new_completed
                    dist.save(update_fields=['completed_count'])

    # =========================================================
    # 🔹 АРХИВАЦИЯ
    # =========================================================

    def check_and_archive(self, save=True):
        """
        Проверяет: все ли студенты выкатали вождение (порог).
        Если да — помечает группу как архивную и ставит дату архивации.
        Возвращает True, если группа была только что заархивирована.
        """
        if self.is_archived:
            return False

        if self.total_students <= 0:
            return False

        if self.driven_students_count >= self.total_students:
            self.is_archived = True
            self.status = 'archived'
            self.archived_at = timezone.now()
            if save:
                # 🔥 Используем self.save() с update_fields — super() здесь не работает,
                # потому что метод внутри класса, а не модуля.
                self.save(update_fields=['is_archived', 'status', 'archived_at'])
            return True

        return False


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

    @property
    def driven_students(self):
        """
        Сколько учеников ЭТОГО мастера в ЭТОЙ группе выкатали.
        Считаем через BookEntry (единый источник истины).
        """
        return self.plan_group.driven_students_for_master(self.master_id)

    @property
    def remaining_students(self):
        """Сколько ещё не выкатали из закреплённых за мастером."""
        return max(0, self.students_count - self.driven_students)


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