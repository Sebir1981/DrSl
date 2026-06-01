from django.db import models
from django.contrib.auth.models import Group, User
from cryptography.fernet import Fernet
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class VaultEntry(models.Model):
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