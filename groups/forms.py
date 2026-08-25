# groups/forms.py
from django import forms
from .models import SchedulePlan, Group
from teachers.models import Teacher
from DrSl.validators import validate_date_range
from DrSl.widgets import RuDateWidget
import json


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


# =============================================================================
# ✅ ФОРМА ДЛЯ ПЛАН-ГРАФИКОВ (исправленная)
# =============================================================================
class SchedulePlanForm(forms.ModelForm):
    # 🔹 Преподаватель медицины (дополнительное поле)
    med_teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.filter(is_active=True).order_by('last_name', 'first_name'),
        required=False,
        empty_label="— Не выбран —",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    # 🔹 Поля для времени занятий (НЕ в модели, обрабатываются вручную)
    time_morning = forms.BooleanField(required=False, label='Утро')
    time_day = forms.BooleanField(required=False, label='День')
    time_evening = forms.BooleanField(required=False, label='Вечер')

    class Meta:
        model = SchedulePlan
        # 🔹 ВАЖНО: time_* поля НЕ включаем сюда, т.к. их нет в модели
        fields = ['group', 'teacher', 'date_start', 'date_end',
                  'med_teacher', 'schedule_type', 'location']
        widgets = {
            'group': forms.Select(attrs={'class': 'form-control'}),
            'teacher': forms.Select(attrs={'class': 'form-control'}),
            'med_teacher': forms.Select(attrs={'class': 'form-control'}),
            'date_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'schedule_type': forms.Select(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Адрес проведения'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 🔹 Фильтруем только активные группы
        self.fields['group'].queryset = Group.objects.filter(status='active').order_by('group_number')

        # 🔹 Загружаем значения времени при редактировании
        if self.instance and self.instance.pk and self.instance.class_days:
            class_days = self.instance.class_days
            if isinstance(class_days, str):
                try:
                    class_days = json.loads(class_days)
                except:
                    class_days = {}

            # Извлекаем time_slots из class_days
            time_slots = class_days.get('_time_slots', [])

            # Устанавливаем initial значения для чекбоксов
            if 'time_morning' not in self.initial:
                self.initial['time_morning'] = 'morning' in time_slots
            if 'time_day' not in self.initial:
                self.initial['time_day'] = 'day' in time_slots
            if 'time_evening' not in self.initial:
                self.initial['time_evening'] = 'evening' in time_slots

    def clean(self):
        cleaned_data = super().clean()
        # Здесь можно добавить валидацию, если нужно
        return cleaned_data


# =============================================================================
# ✅ ФОРМА ДЛЯ ГРУППЫ (исправлена, вынесена из SchedulePlanForm)
# =============================================================================
class GroupForm(forms.ModelForm):
    contract_start = forms.DateField(
        label="Начало договора",
        required=False,
        widget=RuDateWidget(attrs={'class': 'form-control vDateField'})  # <-- добавили vDateField
    )
    contract_end = forms.DateField(
        label="Окончание договора",
        required=False,
        widget=RuDateWidget(attrs={'class': 'form-control vDateField'})
    )
    exam_internal_theory_date = forms.DateField(
        label="ПДД (внутр.)",
        required=False,
        widget=RuDateWidget(attrs={'class': 'form-control vDateField'})
    )
    exam_internal_driving_date = forms.DateField(
        label="Вождение (внутр.)",
        required=False,
        widget=RuDateWidget(attrs={'class': 'form-control vDateField'})
    )
    exam_gai_date = forms.DateField(
        label="Экзамен ГАИ",
        required=False,
        widget=RuDateWidget(attrs={'class': 'form-control vDateField'})
    )

    class Meta:
        model = Group
        fields = [
            'contract_start', 'contract_end',
            'exam_internal_theory_date', 'exam_internal_driving_date', 'exam_gai_date',
            'status', 'schedule_type', 'duration',
            'classroom', 'teacher', 'comments',
        ]