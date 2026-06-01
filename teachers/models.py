# teachers/models.py
from django.db import models
from django.core.validators import RegexValidator


class Teacher(models.Model):
    # 🔹 Личные данные
    last_name = models.CharField("Фамилия", max_length=100)
    first_name = models.CharField("Имя", max_length=100)
    patronymic = models.CharField("Отчество", max_length=100, blank=True)

    phone = models.CharField(
        "Телефон", max_length=25,
        validators=[RegexValidator(
            regex=r'^\+375\s?\(\d{2}\)\s?\d{3}-\d{2}-\d{2}$',
            message="Формат: +375 (29) 123-45-67"
        )],
        help_text="Формат: +375 (29) 123-45-67"
    )

    # 🔹 Типы договоров (новые поля)
    contract_main = models.BooleanField(
        "По основному договору",
        default=False,
    )
    contract_part_time = models.BooleanField(
        "По договору совмещения",
        default=False,
    )

    # 🔹 Тип транспорта
    teaches_truck = models.BooleanField("🚛 Грузовой", default=False)
    teaches_car = models.BooleanField("🚗 Легковой", default=False)

    # 🔹 График
    schedule_morning = models.BooleanField("🌅 Утро", default=False)
    schedule_evening = models.BooleanField("🌆 Вечер", default=False)
    schedule_weekend = models.BooleanField("📅 Выходной", default=False)

    # 🔹 Системные поля
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    def __str__(self):
        return f"{self.last_name} {self.first_name} {self.patronymic}".strip()

    @property
    def full_name(self):
        return f"{self.last_name} {self.first_name} {self.patronymic}".strip()

    @property
    def vehicle_types(self):
        types = []
        if self.teaches_truck: types.append("🚛 Грузовой")
        if self.teaches_car: types.append("🚗 Легковой")
        return ", ".join(types) or "—"

    @property
    def schedule_badges(self):
        badges = []
        if self.schedule_morning: badges.append("🌅")
        if self.schedule_evening: badges.append("🌆")
        if self.schedule_weekend: badges.append("📅")
        return " ".join(badges) or "—"

    class Meta:
        verbose_name = "Преподаватель"
        verbose_name_plural = "📚 Преподаватели"
        ordering = ['last_name', 'first_name']