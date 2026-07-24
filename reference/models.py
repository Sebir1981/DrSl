#reference/models.py

from django.db import models
from django.core.validators import RegexValidator


class GroupCategory(models.Model):
    code = models.CharField(
        "Код (1-2 знака)", max_length=2, unique=True,
        validators=[RegexValidator(r'^[A-Z0-9]{1,2}$', '1-2 заглавные буквы или цифры')]
    )
    description = models.TextField("Описание", help_text="Отображается в таблице")
    hint = models.TextField("Подсказка", blank=True, help_text="Всплывает при наведении")

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = " Категории"
        ordering = ['code']


class Credit(models.Model):
    number = models.PositiveSmallIntegerField("Номер", unique=True)
    topic = models.CharField("Тема", max_length=255)

    class Meta:
        verbose_name = "Зачёт"
        verbose_name_plural = "✅ Зачёты"
        ordering = ['number']

    def __str__(self):
        return f"{self.number}. {self.topic}"


class SubjectDictionary(models.Model):
    """Справочник учебных предметов"""
    name = models.CharField("Название предмета", max_length=200)

    # 🔹 Поле 1: Код для БД (латиница)
    short_name = models.CharField(
        "Код (латиницей)",
        max_length=20,
        unique=True,
        help_text="Используется в базе данных: pdd, ua, bd..."
    )

    # 🔹 Поле 2: Краткое обозначение для таблиц (кириллица)
    short_name_display = models.CharField(
        "Краткое обозначение (кириллицей)",
        max_length=50,
        blank=True,
        default="",
        help_text="Отображается в заголовках и таблицах: ПДД, УА, БД..."
    )

    categories = models.ManyToManyField(
        'GroupCategory',
        verbose_name="Категории транспортных средств",
        related_name='subjects',
        blank=True
    )
    description = models.TextField("Описание", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Учебный предмет"
        verbose_name_plural = "📚 Учебные предметы"
        ordering = ['name']

    def __str__(self):
        display = self.short_name_display if self.short_name_display else self.short_name.upper()
        return f"{self.name} ({display})"

    def categories_list(self):
        return ", ".join([cat.code for cat in self.categories.all()])

    categories_list.short_description = "Категории"


class LessonTopic(models.Model):
    subject = models.ForeignKey(
        SubjectDictionary,
        on_delete=models.CASCADE,
        verbose_name="Предмет",
        related_name='lesson_topics',  # 🔹 Изменено во избежание конфликтов имён
        null=True,
        blank=True
    )
    hours = models.DecimalField(max_digits=4, decimal_places=1, verbose_name="Количество часов")
    topic_number = models.PositiveIntegerField(verbose_name="Тема №")
    content = models.TextField(verbose_name="Содержание темы")

    # 🔹 ДОБАВЛЕНО: Поле для разделения теории и ПЗ
    is_pz = models.BooleanField("Практическое занятие (ПЗ)", default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Тема занятия"
        verbose_name_plural = "📚 Темы занятий"


    def __str__(self):
        subject_name = self.subject.name if self.subject else "Без предмета"
        pz_mark = " (ПЗ)" if self.is_pz else ""
        return f"{subject_name} — Тема №{self.topic_number}{pz_mark}"

class SubjectSet(models.Model):
    """Набор предметов для групп категорий (например, для B, BE, C)"""
    name = models.CharField("Название набора", max_length=200)
    description = models.TextField("Описание", blank=True)

    categories = models.ManyToManyField(
        GroupCategory,
        verbose_name="Категории транспортных средств",
        related_name='subject_sets',
        blank=True
    )
    subjects = models.ManyToManyField(
        SubjectDictionary,
        verbose_name="Предметы",
        related_name='subject_sets',
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Набор предметов"
        verbose_name_plural = "📦 Наборы предметов"
        ordering = ['name']

    def __str__(self):
        return self.name

    def categories_list(self):
        return ", ".join([cat.code for cat in self.categories.all()])

    categories_list.short_description = "Категории"

    def subjects_count(self):
        return self.subjects.count()

    subjects_count.short_description = "Предметов"


# 🔹 НОВЫЕ МОДЕЛИ: Вынесены на верхний уровень (без отступов!)
class TrainingProgram(models.Model):
    """Программа обучения для категорий ТС"""
    name = models.CharField("Название программы", max_length=200)
    total_hours = models.DecimalField(
        "Общее количество часов",
        max_digits=5,
        decimal_places=1,
        help_text="Например: 170 для категории B"
    )
    categories = models.ManyToManyField(
        GroupCategory,
        verbose_name="Категории",
        related_name='training_programs',
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Программа обучения"
        verbose_name_plural = "📋 Программы обучения"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.total_hours} ч.)"


class ProgramSubject(models.Model):
    """Предмет в программе обучения"""
    program = models.ForeignKey(
        TrainingProgram,
        on_delete=models.CASCADE,
        related_name='subjects'
    )
    subject = models.ForeignKey(
        SubjectDictionary,
        on_delete=models.CASCADE,
        related_name='program_items'
    )
    is_enabled = models.BooleanField("Включён", default=True)
    hours = models.DecimalField(
        "Часов по предмету",
        max_digits=5,
        decimal_places=1,
        default=0
    )

    class Meta:
        unique_together = ['program', 'subject']
        ordering = ['subject__short_name']

    def __str__(self):
        return f"{self.program.name} - {self.subject.name}"


class ProgramTopic(models.Model):
    """Тема в программе обучения"""
    program_subject = models.ForeignKey(
        ProgramSubject,
        on_delete=models.CASCADE,
        related_name='topics'
    )
    topic = models.ForeignKey(
        LessonTopic,
        on_delete=models.CASCADE,
        related_name='program_topics'
    )
    hours = models.DecimalField(
        "Часов",
        max_digits=4,
        decimal_places=1,
        help_text="Количество часов на эту тему"
    )

    class Meta:
        unique_together = ['program_subject', 'topic']
        ordering = ['topic__topic_number']

    def __str__(self):
        return f"{self.topic.content} ({self.hours} ч.)"