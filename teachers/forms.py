from django import forms
from .models import Teacher


class TeacherForm(forms.ModelForm):
    """Форма для создания и редактирования преподавателя"""

    class Meta:
        model = Teacher
        fields = [
            'last_name', 'first_name', 'patronymic', 'phone',
            'contract_main', 'contract_part_time',
            'teaches_truck', 'teaches_car',
            'schedule_morning', 'schedule_evening', 'schedule_weekend',
        ]
        widgets = {
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
            'phone': forms.TextInput(attrs={
                'class': 'form-input',
                'data-phone-input': 'true',
                'placeholder': '+375 (__) ___-__-__',
                'autocomplete': 'off'
            }),
            'contract_main': forms.CheckboxInput(),
            'contract_part_time': forms.CheckboxInput(),
            'teaches_truck': forms.CheckboxInput(),
            'teaches_car': forms.CheckboxInput(),
            'schedule_morning': forms.CheckboxInput(),
            'schedule_evening': forms.CheckboxInput(),
            'schedule_weekend': forms.CheckboxInput(),
        }