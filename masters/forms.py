# masters/forms.py
from django import forms
from .models import Master
from DrSl.widgets import RuDateWidget

class MasterAdminForm(forms.ModelForm):
    # ✅ Явно определяем даты БЕЗ наследования BaseDateForm → ограничения 2020-2040 не применяются
    birth_date = forms.DateField(
        label="Дата рождения", input_formats=['%d.%m.%Y'],
        widget=RuDateWidget(), required=False
    )
    license_expiry = forms.DateField(
        label="Срок действия ВУ", input_formats=['%d.%m.%Y'],
        widget=RuDateWidget(), required=False
    )
    medical_expiry = forms.DateField(
        label="Срок действия мед. справки", input_formats=['%d.%m.%Y'],
        widget=RuDateWidget(), required=False
    )

    class Meta:
        model = Master
        fields = '__all__'
        widgets = {
            'license_categories': forms.CheckboxSelectMultiple(attrs={'style': 'columns: 2; column-gap: 20px;'}),
            'teaching_categories': forms.CheckboxSelectMultiple(attrs={'style': 'columns: 2; column-gap: 20px;'}),
            'phone': forms.TextInput(attrs={'placeholder': '+375 (__) ___-__-__'}),
            'work_time_start': forms.TimeInput(attrs={'type': 'time'}),
            'work_time_end': forms.TimeInput(attrs={'type': 'time'}),
        }

    class Media:
        js = ('js/date-mask.js', 'js/phone-mask.js')