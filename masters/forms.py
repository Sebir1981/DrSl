from django import forms
from .models import MasterPouts


class MasterPoutsForm(forms.ModelForm):
    """Форма для создания и редактирования Мастера ПОУТС"""

    # Явно переопределяем поле категорий как множественный выбор
    license_category = forms.MultipleChoiceField(
        choices=MasterPouts.CATEGORY_CHOICES,
        widget=forms.CheckboxSelectMultiple(),
        required=True,
        label="Категории"
    )

    class Meta:
        model = MasterPouts
        fields = [
            'last_name', 'first_name', 'patronymic',
            'passport_number', 'birth_date',
            'license_number', 'license_category', 'license_expiry',
            'medical_cert_number', 'medical_cert_expiry',
            'qualification_cert_number', 'qualification_cert_expiry',
            'phone', 'fuel_card_number', 'car'
        ]
        widgets = {
            # === ФИО ===
            'last_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Иванов'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Иван'
            }),
            'patronymic': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Иванович'
            }),

            # === Документы ===
            'passport_number': forms.TextInput(attrs={                
                'class': 'form-input input-uppercase-en',
                'placeholder': 'Например: HB 1234567'
            }),
            'birth_date': forms.TextInput(attrs={
                'class': 'form-input',
                'data-date-input': 'true',
                'placeholder': 'дд.мм.гггг',
                'autocomplete': 'off'
            }),
            'license_number': forms.TextInput(attrs={
                'class': 'form-input input-uppercase-en',
                'placeholder': 'Например: AAA 123456'
            }),
            'license_expiry': forms.TextInput(attrs={
                'class': 'form-input',
                'data-date-input': 'true',
                'placeholder': 'дд.мм.гггг',
                'autocomplete': 'off'
            }),
            'medical_cert_number': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Номер справки'
            }),
            'medical_cert_expiry': forms.TextInput(attrs={
                'class': 'form-input',
                'data-date-input': 'true',
                'placeholder': 'дд.мм.гггг',
                'autocomplete': 'off'
            }),
            'qualification_cert_number': forms.TextInput(attrs={
                'class': 'form-input input-uppercase-en',
                'placeholder': 'Номер свидетельства'
            }),
            'qualification_cert_expiry': forms.TextInput(attrs={
                'class': 'form-input',
                'data-date-input': 'true',
                'placeholder': 'дд.мм.гггг',
                'autocomplete': 'off'
            }),

            # === Контакты ===
            'phone': forms.TextInput(attrs={
                'class': 'form-input',
                'data-phone-input': 'true',
                'placeholder': '+375 (__) ___-__-__',
                'autocomplete': 'off'
            }),
            'fuel_card_number': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': '9 цифр',
                'maxlength': '9',
                'inputmode': 'numeric'
            }),
            'car': forms.Select(attrs={
                'class': 'form-input'
            }),
        }

    def clean_passport_number(self):
        """Автоматически приводим буквы паспорта к верхнему регистру"""
        data = self.cleaned_data.get('passport_number', '')
        return data.upper() if data else data

    def clean_license_number(self):
        """Автоматически приводим буквы ВУ к верхнему регистру"""
        data = self.cleaned_data.get('license_number', '')
        return data.upper() if data else data