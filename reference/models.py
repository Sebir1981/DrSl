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

