# masters/models.py
from django.db import models
from django.core.validators import RegexValidator
from reference.models import GroupCategory

class Master(models.Model):
    last_name = models.CharField("Фамилия", max_length=100)
    first_name = models.CharField("Имя", max_length=100)
    patronymic = models.CharField("Отчество", max_length=100, blank=True)
    birth_date = models.DateField("Дата рождения", null=True, blank=True)
    address = models.CharField("Адрес проживания", max_length=255, blank=True)
    phone = models.CharField(
        "Номер телефона", max_length=25, blank=True,
        validators=[RegexValidator(r'^\+375\s?\(\d{2}\)\s?\d{3}-\d{2}-\d{2}$', 'Формат: +375 (29) 123-45-67')]
    )
    # 🔹 Категории прав (M2M для чекбоксов)
    license_categories = models.ManyToManyField(
        GroupCategory, verbose_name="Категории прав",
        related_name='masters_with_license', blank=True
    )
    license_number = models.CharField("Номер водительского удостоверения", max_length=50, blank=True)
    license_expiry = models.DateField("Срок действия ВУ", null=True, blank=True)
    medical_expiry = models.DateField("Срок действия мед. справки", null=True, blank=True)
    # 🔹 Категории обучения (M2M для чекбоксов)
    teaching_categories = models.ManyToManyField(
        GroupCategory, verbose_name="Категории обучает",
        related_name='masters_teaching', blank=True
    )
    work_time_start = models.TimeField("Начало работы", null=True, blank=True)
    work_time_end = models.TimeField("Окончание работы", null=True, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    def __str__(self):
        return f"{self.last_name} {self.first_name}"

    class Meta:
        verbose_name = "Мастер"
        verbose_name_plural = "🚗 Мастера"
        ordering = ['last_name', 'first_name']