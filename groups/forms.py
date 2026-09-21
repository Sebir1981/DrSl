# groups/forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import SchedulePlan, Group
from teachers.models import Teacher
from DrSl.validators import validate_date_range
from DrSl.widgets import RuDateWidget
import json


class BaseDateForm(forms.ModelForm):
    """Базовая форма с автоматической валидацией дат"""

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


# =============================================================================
# ✅ ФОРМА АДМИНИСТРАТОРА ГРУППЫ (для детальной страницы)
# =============================================================================
class GroupAdminForm(BaseDateForm):
    contract_start = forms.DateField(
        label="Договор с",
        input_formats=['%d.%m.%Y'],
        widget=RuDateWidget(),
        required=False,
    )
    contract_end = forms.DateField(
        label="Договор по",
        input_formats=['%d.%m.%Y'],
        widget=RuDateWidget(),
        required=False,
    )

    class Meta(BaseDateForm.Meta):
        model = Group
        fields = '__all__'

    class Media:
        js = ('js/date-mask.js',)


# =============================================================================
# ✅ ФОРМА ДЛЯ ПЛАН-ГРАФИКОВ
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
                except Exception:
                    class_days = {}

            time_slots = class_days.get('_time_slots', [])

            if 'time_morning' not in self.initial:
                self.initial['time_morning'] = 'morning' in time_slots
            if 'time_day' not in self.initial:
                self.initial['time_day'] = 'day' in time_slots
            if 'time_evening' not in self.initial:
                self.initial['time_evening'] = 'evening' in time_slots

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data


# =============================================================================
# ✅ ФОРМА ДЛЯ СОЗДАНИЯ/РЕДАКТИРОВАНИЯ ГРУППЫ
# =============================================================================
class GroupForm(forms.ModelForm):
    """Форма для создания и редактирования группы.

    Включает все ключевые поля модели Group + кастомные поля дат
    с русским форматом ввода.
    """

    # 🔹 Кастомные поля дат с русским виджетом
    contract_start = forms.DateField(
        label="Начало договора",
        required=False,
        widget=RuDateWidget(attrs={'class': 'form-control', 'placeholder': 'дд.мм.гггг'})
    )
    contract_end = forms.DateField(
        label="Окончание договора",
        required=False,
        widget=RuDateWidget(attrs={'class': 'form-control', 'placeholder': 'дд.мм.гггг'})
    )
    exam_internal_theory_date = forms.DateField(
        label="ПДД (внутр.)",
        required=False,
        widget=RuDateWidget(attrs={'class': 'form-control', 'placeholder': 'дд.мм.гггг'})
    )
    exam_internal_driving_date = forms.DateField(
        label="Вождение (внутр.)",
        required=False,
        widget=RuDateWidget(attrs={'class': 'form-control', 'placeholder': 'дд.мм.гггг'})
    )
    exam_gai_date = forms.DateField(
        label="Экзамен ГАИ",
        required=False,
        widget=RuDateWidget(attrs={'class': 'form-control', 'placeholder': 'дд.мм.гггг'})
    )

    class Meta:
        model = Group
        fields = [
            'group_number',  # 🔥 ДОБАВЛЕНО — это и было причиной KeyError
            'category',  # 🔥 ДОБАВЛЕНО — категория группы (B, C и т.д.)
            'status',
            'schedule_type',
            'duration',
            'classroom',
            'teacher',
            'contract_start',
            'contract_end',
            'exam_internal_theory_date',
            'exam_internal_driving_date',
            'exam_gai_date',
            'comments',
        ]
        widgets = {
            'group_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: 131',
                'autocomplete': 'off',
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'schedule_type': forms.Select(attrs={'class': 'form-control'}),
            'duration': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Кол-во часов',
            }),
            'classroom': forms.Select(attrs={'class': 'form-control'}),
            'teacher': forms.Select(attrs={'class': 'form-control'}),
            'comments': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Комментарий (необязательно)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 🔹 Настройка placeholder для полей дат
        for field_name in ['contract_start', 'contract_end',
                           'exam_internal_theory_date',
                           'exam_internal_driving_date',
                           'exam_gai_date']:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.setdefault('placeholder', 'дд.мм.гггг')

    # =======================================================================
    #  ВАЛИДАЦИЯ УНИКАЛЬНОСТИ НОМЕРА ГРУППЫ
    # =======================================================================
    def clean_group_number(self):
        """Проверка, что номер группы уникален (исключая текущую при редактировании)."""
        group_number = self.cleaned_data.get('group_number')

        if not group_number:
            raise ValidationError('Номер группы обязателен для заполнения.')

        # Нормализация: убираем лишние пробелы
        group_number = str(group_number).strip()

        # Ищем существующие группы с таким номером
        qs = Group.objects.filter(group_number=group_number)

        # При редактировании исключаем текущую группу
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError(f'Группа с номером "{group_number}" уже существует.')

        return group_number

    # =======================================================================
    # 🔹 ОБЩАЯ ВАЛИДАЦИЯ ДИАПАЗОНА ДАТ ДОГОВОРА
    # =======================================================================
    def clean(self):
        cleaned_data = super().clean()

        contract_start = cleaned_data.get('contract_start')
        contract_end = cleaned_data.get('contract_end')

        if contract_start and contract_end and contract_end < contract_start:
            raise ValidationError({
                'contract_end': 'Дата окончания договора не может быть раньше даты начала.'
            })

        return cleaned_data

    class Media:
        js = ('js/date-mask.js',)