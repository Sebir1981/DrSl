# classrooms/models.py
from django.db import models


class Classroom(models.Model):
    # 🔹 Основная информация
    classroom_number = models.CharField("№ аудитории", max_length=10, unique=True)
    address = models.CharField("Адрес", max_length=255, blank=True)
    capacity = models.PositiveSmallIntegerField("Количество учащихся", default=20)

    # 🔹 Договор аренды
    contract_number = models.CharField("№ договора", max_length=50, null=True, blank=True)
    contract_start = models.DateField("Действует с", null=True, blank=True)
    contract_end = models.DateField("по", null=True, blank=True)
    contract_file = models.FileField("Файл договора", upload_to='contracts/', blank=True, null=True)

    # 🔹 Санстанция (СЭС) — только дата, без номера свидетельства
    san_certificate_valid_until = models.DateField("СЭС действует до", null=True, blank=True)

    # 🔹 Системные поля
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    def __str__(self):
        return self.address if self.address else "Без адреса"

    class Meta:
        verbose_name = "Аудитория"
        verbose_name_plural = "🏫 Аудитории"
        ordering = ['classroom_number']