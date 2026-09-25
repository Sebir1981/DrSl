from django.db import models
from django.core.validators import RegexValidator, MinLengthValidator, MaxLengthValidator
from cars.models import Car  # Связь с автопарком


class MasterPouts(models.Model):
    """Мастер производственного обучения управлению транспортного средства"""

    # Категории водительских прав
    CATEGORY_CHOICES = [
        ('A', 'A — Мотоциклы'),
        ('A1', 'A1 — Лёгкие мотоциклы'),
        ('B', 'B — Легковые автомобили'),
        ('B1', 'B1 — Трициклы и квадрициклы'),
        ('BE', 'BE — Легковые с прицепом'),
        ('C', 'C — Грузовые автомобили'),
        ('C1', 'C1 — Средние грузовые'),
        ('CE', 'CE — Грузовые с прицепом'),
        ('D', 'D — Автобусы'),
        ('D1', 'D1 — Малые автобусы'),
        ('DE', 'DE — Автобусы с прицепом'),
        ('M', 'M — Мопеды'),
        ('TM', 'TM — Трамваи'),
        ('TB', 'TB — Троллейбусы'),
    ]

    # === 1. ФИО ===
    last_name = models.CharField("Фамилия", max_length=100)
    first_name = models.CharField("Имя", max_length=100)
    patronymic = models.CharField("Отчество", max_length=100, blank=True)

    # === 1.1. Пол ===
    GENDER_CHOICES = [
        ('male', 'Мужской'),
        ('female', 'Женский'),
    ]
    gender = models.CharField(
        "Пол",
        max_length=10,
        choices=GENDER_CHOICES,
        blank=True,
        default='male'
    )

    # === 2. Паспорт и дата рождения ===
    passport_number = models.CharField(
        "№ паспорта", max_length=20,
        validators=[RegexValidator(
            r'^[A-ZА-Я]{2} \d{7}$',
            'Формат: 2 заглавные буквы, пробел, 7 цифр (например: HB 1234567)'
        )]
    )
    birth_date = models.DateField("Дата рождения")

    # === 3. Водительское удостоверение ===
    license_number = models.CharField(
        "№ водительского удостоверения", max_length=20,
        validators=[RegexValidator(
            r'^[A-Z]{3} \d{6}$',
            'Формат: 3 заглавные латинские буквы, пробел, 6 цифр (например: AAA 123456)'
        )]
    )
    license_category = models.JSONField(
        "Категории ВУ",
        default=list,
        help_text="Выберите одну или несколько категорий",
        blank=True
    )
    license_expiry = models.DateField("Срок действия ВУ")

    @property
    def license_categories_display(self):
        """Возвращает строку с выбранными категориями"""
        if not self.license_category:
            return "—"
        category_dict = dict(self.CATEGORY_CHOICES)
        return ", ".join([category_dict.get(cat, cat) for cat in self.license_category])

    # === 4. Медицинская справка ===
    medical_cert_number = models.CharField(
        "№ медицинской справки", max_length=30, blank=True
    )
    medical_cert_expiry = models.DateField(
        "Срок действия мед. справки", null=True, blank=True
    )

    # === 5. Свидетельство о повышении квалификации ===
    qualification_cert_number = models.CharField(
        "№ свидетельства о повышении квалификации", max_length=50, blank=True
    )
    qualification_cert_expiry = models.DateField(
        "Срок действия свидетельства", null=True, blank=True
    )

    # === 6. Телефон ===
    phone = models.CharField(
        "Номер телефона", max_length=20,
        validators=[RegexValidator(
            r'^\+375 \(\d{2}\) \d{3}-\d{2}-\d{2}$',
            'Формат: +375 (XX) XXX-XX-XX'
        )]
    )

    # === 7. Топливная карта ===
    fuel_card_number = models.CharField(
        "№ топливной карты", max_length=9,
        validators=[
            MinLengthValidator(9, 'Ровно 9 знаков'),
            MaxLengthValidator(9, 'Ровно 9 знаков'),
            RegexValidator(r'^\d{9}$', 'Только 9 цифр')
        ],
        help_text="Ровно 9 цифр"
    )

    # === 8. Автомобиль ===
    car = models.ForeignKey(
        Car, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='masters', verbose_name="Закреплённый автомобиль"
    )

    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Мастер ПОУТС"
        verbose_name_plural = "🚗 Мастера ПОУТС"
        ordering = ['last_name', 'first_name']

    @property
    def full_name(self):
        """Возвращает полное ФИО: Фамилия Имя Отчество"""
        parts = [self.last_name, self.first_name, self.patronymic]
        return ' '.join(p for p in parts if p).strip()

    @property
    def short_name(self):
        """Возвращает короткое ФИО: Фамилия И.О."""
        initials = f"{self.first_name[:1]}." if self.first_name else ""
        patronymic_init = f"{self.patronymic[:1]}." if self.patronymic else ""
        return f"{self.last_name} {initials}{patronymic_init}".strip()

    def __str__(self):
        return self.short_name

    @property
    def is_license_valid(self):
        """Проверка актуальности ВУ"""
        from django.utils import timezone
        return self.license_expiry >= timezone.now().date()

    @property
    def is_medical_valid(self):
        """Проверка актуальности мед. справки"""
        from django.utils import timezone
        if not self.medical_cert_expiry:
            return False
        return self.medical_cert_expiry >= timezone.now().date()

Master = MasterPouts