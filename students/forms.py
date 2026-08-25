# students/forms.py
from django import forms
from .models import Student, StudentHistory
from DrSl.validators import validate_date_range
from DrSl.widgets import RuDateWidget


# =============================================================================
# 🔹 КОНСТАНТЫ (для устранения дублирования строк)
# =============================================================================
LABEL_COMMENT = "Комментарий"
TEXTAREA_STYLE = 'resize: vertical;'
TEXTAREA_CLASS = 'form-control'
INPUT_FORMAT_ISO = '%Y-%m-%d'
INPUT_FORMAT_RU = '%d.%m.%Y'
# =============================================================================
# 🔹 Форма для админки учащегося
# =============================================================================
class StudentAdminForm(forms.ModelForm):
    birth_date = forms.DateField(
        label="Дата рождения",
        input_formats=['INPUT_FORMAT_RU'],
        widget=RuDateWidget(),
        required=False,
        validators=[]
    )

    class Meta:
        model = Student
        # ✅ Заменяем '__all__' на явный список полей
        fields = [
            'last_name', 'first_name', 'patronymic', 'phone',
            'birth_date', 'place_of_birth', 'place_of_residence', 'place_of_registration',
            'work_study_place', 'position',
            'group', 'teacher', 'master', 'gearbox_type',
            'enrolled_date', 'graduated_date', 'transferred_date',
            'activity_log',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'birth_date' in self.fields:
            f = self.fields['birth_date']
            if not isinstance(f.widget, RuDateWidget):
                f.widget = RuDateWidget()
            f.widget.attrs.pop('min', None)
            f.widget.attrs.pop('max', None)
            f.widget.attrs.pop('pattern', None)
            f.widget.attrs.pop('step', None)


# =============================================================================
# 🔹 Форма отчисления учащегося
# =============================================================================
class DismissalForm(forms.ModelForm):
    order_number = forms.CharField(
        label="№ приказа",
        max_length=50,
        widget=forms.TextInput(attrs={'placeholder': 'Например: 45-У', 'class': TEXTAREA_CLASS, 'autocomplete': 'off'})
    )
    order_date = forms.DateField(
        label="Дата приказа",
        # ✅ ИСПРАВЛЕНИЕ: Используем RuDateWidget
        widget=RuDateWidget(attrs={'class': TEXTAREA_CLASS}),
        input_formats=['INPUT_FORMAT_RU', 'INPUT_FORMAT_ISO'],
        required=False
    )
    comment = forms.CharField(
        label=LABEL_COMMENT,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Причина отчисления...', 'class': TEXTAREA_CLASS, 'style': TEXTAREA_STYLE}),
        required=False
    )

    class Meta:
        model = StudentHistory
        fields = ['order_number', 'order_date', 'comment']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['event_type'] = 'dismissed'


# =============================================================================
# 🔹 Форма отказа от обучения
# =============================================================================
class RefusalForm(forms.ModelForm):
    comment = forms.CharField(
        label=LABEL_COMMENT,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Причина отказа...', 'class': TEXTAREA_CLASS}),
        required=False
    )

    class Meta:
        model = StudentHistory
        fields = ['comment']  # ✅ УБРАНО event_date! Дата берётся из HTML-инпута во вью

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['event_type'] = 'refused'


# =============================================================================
# 🔹 Форма приостановки обучения
# =============================================================================
class SuspensionForm(forms.ModelForm):
    suspension_start = forms.DateField(
        label="Дата начала",
        # ✅ ИСПРАВЛЕНИЕ: Используем RuDateWidget
        widget=RuDateWidget(attrs={'class': TEXTAREA_CLASS}),
        input_formats=['INPUT_FORMAT_RU', 'INPUT_FORMAT_ISO']
    )
    suspension_end = forms.DateField(
        label="Дата окончания",
        # ✅ ИСПРАВЛЕНИЕ: Используем RuDateWidget
        widget=RuDateWidget(attrs={'class': TEXTAREA_CLASS}),
        input_formats=['INPUT_FORMAT_RU', 'INPUT_FORMAT_ISO'],
        required=False,
        help_text="Оставьте пустым, если срок не определён"
    )
    comment = forms.CharField(
        label=LABEL_COMMENT,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Причина приостановки...', 'class': TEXTAREA_CLASS, 'style': TEXTAREA_STYLE}),
        required=False,
        help_text="Причина, дополнительные сведения"
    )

    class Meta:
        model = StudentHistory
        fields = ['comment']  # ✅ УБРАНО event_date! Даты берутся из HTML-инпутов во вью

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['event_type'] = 'suspended'

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('suspension_start')
        end = cleaned_data.get('suspension_end')
        if start and end and end < start:
            self.add_error('suspension_end', 'Дата окончания не может быть раньше даты начала')
        return cleaned_data


# =============================================================================
# 🔹 Форма продления договора
# =============================================================================
class ContractExtensionForm(forms.Form):
    """Форма продления договора"""
    new_contract_number = forms.CharField(
        label='№ дополнительного договора',
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Например: Д-2026-45'})
    )
    new_start_date = forms.DateField(
        label='Дата начала (новая)',
        required=True,
        # ✅ ИСПРАВЛЕНИЕ: Используем RuDateWidget
        widget=RuDateWidget()
    )
    new_end_date = forms.DateField(
        label='Дата окончания (новая)',
        required=True,
        # ✅ ИСПРАВЛЕНИЕ: Используем RuDateWidget
        widget=RuDateWidget()
    )
    is_paid = forms.ChoiceField(
        label='Тип продления',
        choices=[
            ('paid', '💳 Платное продление'),
            ('free', '🎁 Бесплатное продление'),
        ],
        widget=forms.RadioSelect,
        initial='paid'
    )
    comment = forms.CharField(
        label=LABEL_COMMENT,
        required=True,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Введите причину или примечание к продлению...'})
    )


# =============================================================================
# 🔹 НОВОЕ: Форма для публичного добавления учащегося
# =============================================================================
class StudentPublicAddForm(forms.ModelForm):
    """Используется на странице /students/add/"""
    birth_date = forms.DateField(
        label="Дата рождения",
        required=False,
        widget=RuDateWidget()  # <--- Ваш виджет с маской
    )
    enrolled_date = forms.DateField(
        label="Дата зачисления",
        required=False,
        widget=RuDateWidget()
    )

    class Meta:
        model = Student
        fields = [
            'last_name', 'first_name', 'patronymic', 'phone',
            'birth_date', 'enrolled_date',
            'place_of_birth', 'place_of_residence', 'place_of_registration',
            'work_study_place', 'position',
            'group', 'teacher', 'master', 'gearbox_type',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Принудительно ставим маску, если вдруг что-то переопределило виджет
        for field_name in ['birth_date', 'enrolled_date']:
            if field_name in self.fields:
                f = self.fields[field_name]
                if not isinstance(f.widget, RuDateWidget):
                    f.widget = RuDateWidget()
                f.widget.attrs.pop('min', None)
                f.widget.attrs.pop('max', None)
                f.widget.attrs.pop('pattern', None)
                f.widget.attrs.pop('step', None)