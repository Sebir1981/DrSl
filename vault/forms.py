# vault/forms.py
from django import forms
from .models import VaultEntry
from django.contrib.auth.models import Group

class AddVaultEntryForm(forms.ModelForm):
    raw_password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Введите пароль'}),
        required=True
    )
    allowed_roles = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'role-checkboxes'}),
        label="Доступно ролям",
        required=True
    )
    class Meta:
        model = VaultEntry
        fields = ['full_name', 'position', 'username', 'url', 'notes', 'allowed_roles']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Иванов Иван Иванович'}),
            'position': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Преподаватель'}),
            'username': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Логин/Пользователь'}),
            'url': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://...'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Заметки'}),
        }