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
        verbose_name_plural = "📁 Категории"
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


# 🔹 НОВОЕ: Модель для тем занятий
class LessonTopic(models.Model):
    CATEGORY_CHOICES = [
        ('pdd', 'Правила дорожного движения (ПДД)'),
        ('outs_bd', 'Основы управления транспортным средством и безопасность движения (ОУТС и БД)'),
        ('podd', 'Правовые основы дорожного движения (ПОДД)'),
        ('mp', 'Первая помощь пострадавшим при дорожно-транспортных происшествиях (МП)'),
        ('ua', 'Устройство и техническое обслуживание автомобилей категории «B» (УА)'),
    ]

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        verbose_name="Справочник"
    )
    hours = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        verbose_name="Количество часов"
    )
    topic_number = models.PositiveIntegerField(
        verbose_name="Тема №"
    )
    content = models.TextField(
        verbose_name="Содержание темы"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Тема занятия"
        verbose_name_plural = "📚 Темы занятий"
        ordering = ['category', 'topic_number']

    def __str__(self):
        return f"{self.get_category_display()} — Тема №{self.topic_number}"