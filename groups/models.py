from django.db import models
from django.core.validators import RegexValidator
from teachers.models import Teacher


class SchedulePlan(models.Model):
    """План-график выполнения единой программы подготовки водителей"""

    SCHEDULE_TYPE_CHOICES = [
        ('even', 'Чётные дни'),
        ('odd', 'Нечётные дни'),
        ('weekend', 'Выходные дни'),
        ('custom', 'По указанию'),
    ]

    class Meta:
        verbose_name = "План-график"
        verbose_name_plural = "План-графики"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['group', 'date_start', 'date_end'],
                name='unique_group_schedule_period'
            ),
        ]

    # 🔹 Основные поля
    title = models.CharField("Заголовок", max_length=255, editable=False)
    group = models.ForeignKey('Group', on_delete=models.CASCADE, verbose_name="Учебная группа",
                              limit_choices_to={'status': 'active'})
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Преподаватель")
    med_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='medical_schedule_plans',
        verbose_name='Преподаватель медицины'
    )

    # 🔹 Даты (время убрано полностью)
    date_start = models.DateField("Начало периода")
    date_end = models.DateField("Конец периода")

    required_hours = models.PositiveIntegerField(
        default=170,
        verbose_name="Количество часов"
    )

    # 🔹 Расписание
    schedule_type = models.CharField("Тип расписания", max_length=20, choices=SCHEDULE_TYPE_CHOICES, default='custom')
    location = models.CharField("Место проведения", max_length=255, blank=True)

    # 🔹 Дни занятий (JSON: {"2026-06-01": {"start": "08:40", "end": "13:30", "pdd": 4, ...}, ...})
    class_days = models.JSONField("Дни занятий", default=dict, blank=True)

    #  Системные поля
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"План-график: {self.group.group_number} ({self.get_schedule_type_display()})"

    def save(self, *args, **kwargs):
        if not self.title and self.group and self.group.category:
            self.title = f'План-график выполнения единой программы подготовки водителей МТС категории "{self.group.category}"'
        super().save(*args, **kwargs)


class Group(models.Model):
    # 🔹 Идентификаторы
    group_number = models.CharField(
        "№ группы", max_length=20, unique=True,
        validators=[RegexValidator(r'^[A-Z0-9]{1,6}$', 'Введите от 1 до 6 заглавных букв или цифр')]
    )
    category = models.ForeignKey(
        'reference.GroupCategory',
        on_delete=models.PROTECT,
        verbose_name="Категория",
        null=True,
        blank=True
    )
    classroom = models.ForeignKey(
        'classrooms.Classroom',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Аудитория",
        related_name='groups'
    )
    teacher = models.ForeignKey(
        'teachers.Teacher',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Преподаватель"
    )

    # 🔹 Договор
    contract_start = models.DateField("Начало договора", null=True, blank=True)
    contract_end = models.DateField("Окончание договора", null=True, blank=True)

    # 🔹 Даты экзаменов
    exam_internal_theory_date = models.DateField("📚 Внутренний экзамен: ПДД", null=True, blank=True)
    exam_internal_driving_date = models.DateField("🚗 Внутренний экзамен: Вождение", null=True, blank=True)
    exam_gai_date = models.DateField("🏁 Экзамен в ГАИ", null=True, blank=True)

    # 🔹 Статус
    STATUS_CHOICES = [
        ('active', '🟢 Активна'),
        ('paused', '🟡 Приостановлена'),
        ('closed', ' Закрыта'),
    ]
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='active')

    # 🔹 Расписание (Время убрано, оставлен только Тип)
    SCHEDULE_TYPE_CHOICES = [
        ('odd', '📅 Нечётные дни (пн-пт)'),
        ('even', '📅 Чётные дни (пн-пт)'),
        ('weekend', '📅 Выходные (сб-вс)'),
        ('directed', '📅 По указанию'),
    ]
    schedule_type = models.CharField("Тип расписания", max_length=15, choices=SCHEDULE_TYPE_CHOICES, blank=True,
                                     default='directed')

    DURATION_CHOICES = [('standard', 'Стандартный'), ('accelerated', 'Ускоренный')]
    duration = models.CharField(
        "Срок обучения",
        max_length=15,
        choices=DURATION_CHOICES,
        default='standard',
        blank=True, null=True
    )

    # 🔹 JSON-поля и комментарии
    schedule_exceptions = models.JSONField("Исключения из расписания", blank=True, default=list)
    comments = models.TextField("Комментарии", blank=True, help_text="Внутренние заметки по группе")

    # 🔹 Системные поля
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)
    change_log = models.TextField("Журнал изменений", blank=True, editable=False)

    def __str__(self):
        cat = self.category.code if self.category else "Без категории"
        return f"{self.group_number} ({cat})"

    @property
    def contract_period(self):
        if self.contract_start and self.contract_end:
            return f"{self.contract_start.strftime('%d.%m.%Y')} — {self.contract_end.strftime('%d.%m.%Y')}"
        return "—"

    class Meta:
        verbose_name = "Группа"
        verbose_name_plural = "👥 Группы"
        ordering = ['group_number']


# =============================================================================
# 🔹 Результаты зачётов
# =============================================================================
class CreditResult(models.Model):
    STATUS_CHOICES = [('passed', '✅ Сдал'), ('failed', ' Не сдал')]

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, verbose_name="Учащийся",
                                related_name='credit_results')
    credit = models.ForeignKey('reference.Credit', on_delete=models.CASCADE, verbose_name="Зачёт",
                               related_name='results')
    credit_date = models.DateField("Дата зачёта")
    status = models.CharField("Статус", max_length=10, choices=STATUS_CHOICES, default='failed')

    chairman = models.ForeignKey('teachers.Teacher', on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name="Председатель комиссии", related_name='chairman_credits')
    member1 = models.ForeignKey('teachers.Teacher', on_delete=models.SET_NULL, null=True, blank=True,
                                verbose_name="Член комиссии 1", related_name='member1_credits')
    member2 = models.ForeignKey('teachers.Teacher', on_delete=models.SET_NULL, null=True, blank=True,
                                verbose_name="Член комиссии 2", related_name='member2_credits')
    member3 = models.ForeignKey('teachers.Teacher', on_delete=models.SET_NULL, null=True, blank=True,
                                verbose_name="Член комиссии 3", related_name='member3_credits')

    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Результат зачёта"
        verbose_name_plural = "📋 Результаты зачётов"
        ordering = ['-credit_date']

    def __str__(self):
        status_icon = '✅' if self.status == 'passed' else ''
        return f"{self.student.full_name} — Зачёт №{self.credit.number}: {status_icon}"


# =============================================================================
# 🔹 Результаты экзаменов
# =============================================================================
class ExamResult(models.Model):
    EXAM_TYPE_CHOICES = [('theory', ' Теория'), ('driving', '🚗 Вождение')]
    ATTEMPT_TYPE_CHOICES = [('free', 'Бесплатная'), ('paid', 'Платная')]
    STATUS_CHOICES = [('passed', '✅ Сдал'), ('failed', '❌ Не сдал')]

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, verbose_name="Учащийся",
                                related_name='exam_results')
    exam_type = models.CharField("Тип экзамена", max_length=10, choices=EXAM_TYPE_CHOICES)
    attempt_type = models.CharField("Тип попытки", max_length=10, choices=ATTEMPT_TYPE_CHOICES)
    status = models.CharField("Статус", max_length=10, choices=STATUS_CHOICES)
    exam_date = models.DateField("Дата экзамена")
    examiner = models.ForeignKey('teachers.Teacher', on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name="Экзаменатор")
    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Результат экзамена"
        verbose_name_plural = "🎓 Результаты экзаменов"
        ordering = ['-exam_date']

    def __str__(self):
        return f"{self.student.full_name} — {self.get_exam_type_display()}: {self.get_status_display()}"