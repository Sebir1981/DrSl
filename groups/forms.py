from django import forms
from .models import SchedulePlan, Group
from teachers.models import Teacher
from DrSl.validators import validate_date_range
from DrSl.widgets import RuDateWidget


# =========================================================
# 📌 Базовая форма для всех моделей с датами
# =========================================================
class BaseDateForm(forms.ModelForm):
    class Meta:
        model = None
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field, forms.DateField):
                if validate_date_range not in field.validators:
                    field.validators.append(validate_date_range)
                field.widget.attrs.setdefault('placeholder', 'дд.мм.гггг')
                field.widget.attrs.setdefault('min', '2020-01-01')
                field.widget.attrs.setdefault('max', '2040-12-31')


# =========================================================
# 📌 Форма админки Group
# =========================================================
class GroupAdminForm(BaseDateForm):
    contract_start = forms.DateField(
        label="Договор с", input_formats=['%d.%m.%Y'],
        widget=RuDateWidget(), required=False,
    )
    contract_end = forms.DateField(
        label="Договор по", input_formats=['%d.%m.%Y'],
        widget=RuDateWidget(), required=False,
    )

    class Meta(BaseDateForm.Meta):
        model = Group
        fields = '__all__'

    class Media:
        js = ('js/date-mask.js',)


# =========================================================
# ✅ НОВОЕ: Форма для План-графиков
# =========================================================
class SchedulePlanForm(forms.ModelForm):
    class Meta:
        model = SchedulePlan
        fields = ['group', 'teacher', 'date_start', 'date_end', 'time_start', 'time_end', 'required_hours', 'schedule_type', 'location']
        widgets = {
            'group': forms.Select(attrs={'class': 'form-control'}),
            'teacher': forms.Select(attrs={'class': 'form-control'}),
            'date_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'time_start': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'time_end': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'required_hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'placeholder': '170'}),
            'schedule_type': forms.Select(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Адрес проведения'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 🔹 Фильтруем только активные группы
        self.fields['group'].queryset = Group.objects.filter(status='active').order_by('group_number')