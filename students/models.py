# students/models.py
from django.db import models
from django.core.validators import RegexValidator

# =============================================================================
#  Валидатор телефона
# =============================================================================
PHONE_VALIDATOR = RegexValidator(
    regex=r'^\+375\s?\(\d{2}\)\s?\d{3}-\d{2}-\d{2}$',
    message="Формат: +375 (29) 123-45-67"
)


# =============================================================================
# 🔹 Модель учащегося
# =============================================================================
class Student(models.Model):
    """
    Модель учащегося автошколы.
    """

    # =========================================================
    # Личные данные
    # =========================================================
    last_name = models.CharField("Фамилия", max_length=100)
    first_name = models.CharField("Имя", max_length=100)
    patronymic = models.CharField("Отчество", max_length=100, blank=True)

    phone = models.CharField(
        "Телефон",
        max_length=25,
        validators=[PHONE_VALIDATOR],
        help_text="Формат: +375 (29) 123-45-67"
    )

    birth_date = models.DateField("Дата рождения", null=True, blank=True)
    place_of_birth = models.CharField("Место рождения", max_length=255, blank=True)
    place_of_residence = models.CharField("Место проживания", max_length=255, blank=True)
    place_of_registration = models.CharField("Место регистрации", max_length=255, blank=True)

    # =========================================================
    # Работа / учёба
    # =========================================================
    work_study_place = models.CharField("Место работы/учёбы", max_length=255, blank=True)
    position = models.CharField("Должность", max_length=100, blank=True)

    # =========================================================
    # Связи
    # =========================================================
    group = models.ForeignKey(
        'groups.Group',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Группа",
        related_name='students'
    )

    teacher = models.ForeignKey(
        'teachers.Teacher',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Преподаватель"
    )

    master = models.ForeignKey(
        'masters.MasterPouts',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Мастер вождения"
    )

    GEARBOX_CHOICES = [
        ('manual', 'Механическая'),
        ('auto', 'Автоматическая'),
        ('electric', 'Электромобиль'),
    ]
    gearbox_type = models.CharField(
        "Тип КПП",
        max_length=50,
        choices=GEARBOX_CHOICES,
        default='',
        blank=True,
        help_text="Выберите тип коробки передач для обучения"
    )

    # =========================================================
    # Даты обучения
    # =========================================================
    enrolled_date = models.DateField("Дата зачисления", null=True, blank=True)
    graduated_date = models.DateField("Дата выпуска", null=True, blank=True)

    # =========================================================
    # 🔹 Учёт часов вождения
    # =========================================================
    driving_hours_required = models.IntegerField(
        "Положено часов вождения",
        default=0,
        help_text="Устанавливается при добавлении группы в генплан"
    )

    driving_hours_completed = models.IntegerField(
        "Выкатано часов",
        default=0,
        help_text="Заполняется из путевых листов"
    )

    # =========================================================
    # 🔹 ЕДИНЫЙ журнал активности (переводы, зачёты, статусы)
    # =========================================================
    activity_log = models.JSONField(
        "Журнал активности",
        default=list,
        blank=True,
        help_text="Общий журнал: переводы, зачёты, изменения статусов (сортируется по дате)"
    )

    transferred_date = models.DateField("Дата последнего перевода", null=True, blank=True)

    # =========================================================
    # Системные поля
    # =========================================================
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    def save(self, *args, **kwargs):
        """
        Автоматически наследует преподавателя из группы
        при смене группы (или при создании учащегося).
        """
        if self.group_id:
            old_group_id = None
            if self.pk:
                old_group_id = (
                    Student.objects.filter(pk=self.pk)
                    .values_list('group_id', flat=True)
                    .first()
                )
            # Группа изменилась (или студент создаётся) → наследуем преподавателя
            if old_group_id != self.group_id and self.group.teacher_id:
                self.teacher_id = self.group.teacher_id
        super().save(*args, **kwargs)

    # =========================================================
    # Свойства
    # =========================================================
    @property
    def full_name(self):
        """Возвращает полное ФИО"""
        return f"{self.last_name} {self.first_name} {self.patronymic}".strip()

    @property
    def is_fully_driven(self):
        """Студент полностью выкатал часы"""
        return self.driving_hours_completed >= self.driving_hours_required and self.driving_hours_required > 0

    @property
    def remaining_hours(self):
        """Осталось выкатать часов"""
        return max(0, self.driving_hours_required - self.driving_hours_completed)

    # =========================================================
    # Строковое представление
    # =========================================================
    def __str__(self):
        return self.full_name

    # =========================================================
    # Meta
    # =========================================================
    class Meta:
        verbose_name = "Учащийся"
        verbose_name_plural = "🎓 Учащиеся"
        ordering = ['last_name', 'first_name']


# =============================================================================
# 🔹 Модель истории событий учащегося (отдельная таблица для сложных событий)
# =============================================================================
class StudentHistory(models.Model):
    """
    Журнал событий учащегося:
    - переводы, отчисления, уведомления
    - приостановки, продления договора, активации
    """

    # =========================================================
    # Типы событий (константы)
    # =========================================================
    EVENT_DISMISSED = 'dismissed'
    EVENT_TRANSFERRED = 'transferred'
    EVENT_CONTRACT_EXTENDED = 'contract_extended'
    EVENT_NOTIFIED = 'notified'
    EVENT_SUSPENDED = 'suspended'
    EVENT_REFUSED = 'refused'
    EVENT_ACTIVATED = 'activated'
    EVENT_OTHER = 'other'

    EVENT_CHOICES = [
        (EVENT_DISMISSED, '❌ Отчислен'),
        (EVENT_TRANSFERRED, ' Переведён'),
        (EVENT_CONTRACT_EXTENDED, '📄 Продление договора'),
        (EVENT_NOTIFIED, '🔔 Уведомление'),
        (EVENT_SUSPENDED, '⏸️ Приостановка'),
        (EVENT_REFUSED, '🚫 Отказ от обучения'),
        (EVENT_ACTIVATED, '✅ Активирован'),
        (EVENT_OTHER, '📝 Другое'),
    ]

    # =========================================================
    # Основные поля
    # =========================================================
    student = models.ForeignKey(
        'Student',
        on_delete=models.CASCADE,
        verbose_name="Учащийся",
        related_name='history'
    )

    event_type = models.CharField(
        "Тип события",
        max_length=30,
        choices=EVENT_CHOICES
    )

    event_date = models.DateField(
        "Дата события",
        blank=True,
        null=True
    )

    # =========================================================
    # Приказы
    # =========================================================
    order_number = models.CharField(
        "№ приказа",
        max_length=50,
        blank=True,
        help_text="Заполняется для отчислений"
    )

    order_date = models.DateField(
        "Дата приказа",
        null=True,
        blank=True
    )

    # =========================================================
    # Дополнительная информация
    # =========================================================
    comment = models.TextField(
        "Комментарий",
        blank=True,
        help_text="Дополнительная информация о событии"
    )

    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Кто создал"
    )

    created_at = models.DateTimeField(
        "Создано",
        auto_now_add=True
    )

    # =========================================================
    # Строковое представление
    # =========================================================
    def __str__(self):
        label = dict(self.EVENT_CHOICES).get(self.event_type, self.event_type)
        return f"{self.student.full_name} — {label} ({self.event_date})"

    # =========================================================
    # Meta
    # =========================================================
    class Meta:
        verbose_name = "Запись в истории"
        verbose_name_plural = "📜 История учащихся"
        ordering = ['-created_at', '-event_date']