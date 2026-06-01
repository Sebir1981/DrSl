# vault/admin.py
from django.contrib import admin
from django import forms
from cryptography.fernet import Fernet
from django.conf import settings
from .models import VaultEntry

class VaultEntryAdminForm(forms.ModelForm):
    raw_password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(render_value=True),
        required=False,
        help_text="Оставьте пустым, если не меняете пароль"
    )
    class Meta:
        model = VaultEntry
        fields = '__all__'
        exclude = ('encrypted_password',)

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_pass = self.cleaned_data.get('raw_password')
        if raw_pass:
            fernet = Fernet(settings.VAULT_ENCRYPTION_KEY.encode())
            instance.encrypted_password = fernet.encrypt(raw_pass.encode()).decode()
        elif not instance.pk:
            raise forms.ValidationError("Для новой записи укажите пароль.")
        if commit:
            instance.save()
        return instance

@admin.register(VaultEntry)
class VaultEntryAdmin(admin.ModelAdmin):
    form = VaultEntryAdminForm
    list_display = ('full_name', 'position', 'username', 'roles_list', 'has_encrypted_pass', 'created_by', 'updated_at')
    list_filter = ('allowed_roles', 'created_by')
    search_fields = ('full_name', 'position', 'username', 'url', 'notes')
    filter_horizontal = ('allowed_roles',)
    readonly_fields = ('created_by', 'created_at', 'updated_at')
    ordering = ('-updated_at',)
    fieldsets = (
        ('Основная информация', {
            'fields': ('full_name', 'position', 'username', 'raw_password', 'url')
        }),
        ('Доступ и заметки', {
            'fields': ('allowed_roles', 'notes'),
            'classes': ('collapse',)
        }),
        ('Системное', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse', 'extrapretty')
        }),
    )

    @admin.display(description="Роли")
    def roles_list(self, obj):
        return ", ".join([g.name for g in obj.allowed_roles.all()]) or "—"

    @admin.display(description="Зашифрован", boolean=True)
    def has_encrypted_pass(self, obj):
        return bool(obj.encrypted_password)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)