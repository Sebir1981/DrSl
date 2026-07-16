# vault/models.py
from django.db import models
from django.contrib.auth.models import Group, User
from cryptography.fernet import Fernet
from django.conf import settings

import logging

logger = logging.getLogger(__name__)


class VaultEntry(models.Model):
    """Основная модель записи в хранилище"""
    full_name = models.CharField("ФИО", max_length=200, default="")
    position = models.CharField("Должность", max_length=100, default="")
    username = models.CharField("Логин/Пользователь", max_length=150, blank=True)
    encrypted_password = models.TextField("Зашифрованный пароль")
    url = models.URLField("Ссылка (опц.)", blank=True)
    notes = models.TextField("Заметки", blank=True)
    allowed_roles = models.ManyToManyField(Group, verbose_name="Доступно ролям", blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Создал")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Запись в хранилище"
        verbose_name_plural = "Хранилище паролей"

    def set_password(self, plaintext: str):
        """Шифрует пароль перед сохранением"""
        fernet = Fernet(settings.VAULT_ENCRYPTION_KEY.encode())
        self.encrypted_password = fernet.encrypt(plaintext.encode()).decode()

    def get_decrypted_password(self) -> str:
        """Расшифровывает пароль"""
        try:
            fernet = Fernet(settings.VAULT_ENCRYPTION_KEY.encode())
            return fernet.decrypt(self.encrypted_password.encode()).decode()
        except Exception as e:
            logger.error(f"Ошибка расшифровки пароля ID {self.pk}: {e}")
            return "❌ Ошибка расшифровки"

    def __str__(self):
        return self.full_name or self.username or f"Запись #{self.pk}"


# =========================================================
# 🔐 МОДЕЛЬ РАЗРЕШЕНИЙ ДОСТУПА (ОТДЕЛЬНЫЙ КЛАСС)
# =========================================================
class VaultPermission(models.Model):
    """Индивидуальные разрешения для доступа к записям хранилища"""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
        related_name='vault_permissions'
    )
    vault_entry = models.ForeignKey(
        VaultEntry,  # ✅ Прямая ссылка, так как класс уже определён выше
        on_delete=models.CASCADE,
        verbose_name='Запись хранилища',
        related_name='permissions'
    )

    # 🔹 Основные разделы
    can_view_groups = models.BooleanField('👥 Группы (раздел)', default=False)
    can_view_students = models.BooleanField('🎓 Учащиеся (раздел)', default=False)
    can_view_credits = models.BooleanField('✅ Зачёты (раздел)', default=False)
    can_view_reports = models.BooleanField('📊 Отчёты (раздел)', default=False)
    can_view_references = models.BooleanField('📁 Справочники (раздел)', default=False)
    can_view_vault = models.BooleanField('🔐 Хранилище (раздел)', default=False)

    # vault/models.py (добавить в класс VaultPermission)

    # 🔹 👥 ГРУППЫ
    perm_grp_create = models.BooleanField('Создание группы', default=False)
    perm_grp_list = models.BooleanField('Список групп', default=False)
    perm_grp_schedule1 = models.BooleanField('План-графики 1', default=False)
    perm_grp_schedule2 = models.BooleanField('План-графики 2', default=False)
    perm_grp_timetable = models.BooleanField('Расписание', default=False)
    perm_grp_close = models.BooleanField('Закрытие групп', default=False)

    #  🎓 УЧАЩИЕСЯ
    perm_stu_list = models.BooleanField('Список учащихся', default=False)
    perm_stu_create = models.BooleanField('Создание учащегося', default=False)
    perm_stu_progress = models.BooleanField('Прогресс обучения', default=False)
    perm_stu_dismiss = models.BooleanField('Отчисления', default=False)

    # 🔹 ✅ ЗАЧЁТЫ И ЭКЗАМЕНЫ
    perm_cred_dashboard = models.BooleanField('Панель зачётов', default=False)
    perm_cred_add = models.BooleanField('Добавление зачёта', default=False)
    perm_cred_reports = models.BooleanField('Отчёты по экзаменам', default=False)

    # 🔹 📊 ОТЧЁТЫ
    perm_rep_dashboard = models.BooleanField('Панель отчётов', default=False)
    perm_rep_generate = models.BooleanField('Генерация отчётов', default=False)
    perm_rep_export = models.BooleanField('Экспорт данных', default=False)

    # 🔹 📁 СПРАВОЧНИКИ
    perm_ref_classrooms = models.BooleanField('Аудитории', default=False)
    perm_ref_teachers = models.BooleanField('Преподаватели', default=False)
    perm_ref_masters = models.BooleanField('Мастера', default=False)
    perm_ref_topics = models.BooleanField('Темы занятий', default=False)
    perm_ref_categories = models.BooleanField('Категории', default=False)

    # 🔹 🔐 ХРАНИЛИЩЕ
    perm_vault_list = models.BooleanField('Список записей', default=False)
    perm_vault_add = models.BooleanField('Добавление записи', default=False)
    perm_vault_manage = models.BooleanField('Управление доступом', default=False)

    # 🔹 ⚙️ АДМИНКА
    perm_admin_access = models.BooleanField('Доступ к админке', default=False)

    # 🔹 Системные
    can_view_vault = models.BooleanField('🔐 Хранилище', default=False)
    can_view_admin = models.BooleanField('⚙️ Админка', default=False)

    # Мета-данные
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Разрешение доступа'
        verbose_name_plural = 'Разрешения доступа'
        unique_together = ['user', 'vault_entry']  # Один пользователь — одна запись разрешений
        ordering = ['user__username', 'vault_entry__full_name']

    def __str__(self):
        return f"{self.user.username} → {self.vault_entry.full_name}"