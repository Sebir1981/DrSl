from django import forms
from .models import Car, CarDocument, TireChangeLog

# ✅ Единый формат принятия дат: дд.мм.гггг или гггг-мм-дд
DATE_INPUT_FORMATS = ['%d.%m.%Y', '%Y-%m-%d']

class CarForm(forms.ModelForm):
    class Meta:
        model = Car
        fields = [
            'make', 'license_plate', 'vin', 'transmission', 'fuel',
            'pts_number', 'cert_number', 'cert_issue_date',
            'initial_odometer'
        ]
        widgets = {
            'make': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Например: Toyota Camry'}),
            'license_plate': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '1234 AA-1'}),
            'vin': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '17 символов', 'maxlength': '17'}),
            'transmission': forms.Select(attrs={'class': 'form-input'}),
            'fuel': forms.Select(attrs={'class': 'form-input'}),
            'pts_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Номер тех. паспорта'}),
            'cert_number': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Номер сертификата'}),
            'cert_issue_date': forms.TextInput(attrs={
                'class': 'form-input',
                'data-date-input': 'true',
                'placeholder': 'дд.мм.гггг'
            }),
            'initial_odometer': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Начальный пробег (км)'}),
        }


class CarDocumentForm(forms.ModelForm):
    # ✅ Явно переопределяем поля дат для поддержки формата дд.мм.гггг и маски
    tech_inspection_date = forms.DateField(
        required=False,
        input_formats=DATE_INPUT_FORMATS,
        widget=forms.TextInput(attrs={'class': 'form-input', 'data-date-input': 'true', 'placeholder': 'дд.мм.гггг'})
    )
    internal_tech_inspection_date = forms.DateField(
        required=False,
        input_formats=DATE_INPUT_FORMATS,
        widget=forms.TextInput(attrs={'class': 'form-input', 'data-date-input': 'true', 'placeholder': 'дд.мм.гггг'})
    )
    tire_replacement_date = forms.DateField(
        required=False,
        input_formats=DATE_INPUT_FORMATS,
        widget=forms.TextInput(attrs={'class': 'form-input', 'data-date-input': 'true', 'placeholder': 'дд.мм.гггг'})
    )
    insurance_next_payment = forms.DateField(
        required=False,
        input_formats=DATE_INPUT_FORMATS,
        widget=forms.TextInput(attrs={'class': 'form-input', 'data-date-input': 'true', 'placeholder': 'дд.мм.гггг', 'id': 'insurance-next-payment'})
    )
    insurance_expiry = forms.DateField(
        required=False,
        input_formats=DATE_INPUT_FORMATS,
        widget=forms.TextInput(attrs={'class': 'form-input', 'data-date-input': 'true', 'placeholder': 'дд.мм.гггг'})
    )
    gas_cylinder_test_date = forms.DateField(
        required=False,
        input_formats=DATE_INPUT_FORMATS,
        widget=forms.TextInput(attrs={'class': 'form-input', 'data-date-input': 'true', 'placeholder': 'дд.мм.гггг'})
    )

    class Meta:
        model = CarDocument
        fields = [
            'tech_inspection_date', 'internal_tech_inspection_date', 'internal_tech_odometer',
            'tire_replacement_date', 'tire_replacement_odometer',
            'insurance_active', 'insurance_next_payment', 'insurance_expiry',
            'gas_cylinder_test_date'
        ]
        widgets = {
            'internal_tech_odometer': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'км'}),
            'tire_replacement_odometer': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'км'}),
            'insurance_active': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'insurance-active-checkbox'}),
        }


class TireChangeForm(forms.Form):
    date = forms.DateField(
        label="Дата замены",
        input_formats=DATE_INPUT_FORMATS,
        widget=forms.TextInput(attrs={'class': 'form-input', 'data-date-input': 'true', 'placeholder': 'дд.мм.гггг', 'name': 'date'})
    )
    odometer = forms.IntegerField(
        label="Показания одометра",
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'км', 'name': 'odometer'})
    )
    wheels = forms.MultipleChoiceField(
        label="Заменённые колёса",
        choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4')],
        widget=forms.CheckboxSelectMultiple,
        required=True
    )
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Необязательно', 'name': 'comment'})
    )