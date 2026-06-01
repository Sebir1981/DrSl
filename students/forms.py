# students/forms.py
from django import forms
from .models import Student, StudentHistory
from DrSl.validators import validate_date_range
from DrSl.widgets import RuDateWidget


# =============================================================================
# 🔹 Форма для админки учащегося
# =============================================================================
class StudentAdminForm(forms.ModelForm):
    birth_date = forms.DateField(
        label="Дата рождения",
        input_formats=['%d.%m.%Y'],
        widget=RuDateWidget(),
        required=False,
        validators=[]
    )

    class Meta:
        model = Student
        fields = '__all__'

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
        widget=forms.TextInput(attrs={'placeholder': 'Например: 45-У', 'class': 'form-control', 'autocomplete': 'off'})
    )
    order_date = forms.DateField(
        label="Дата приказа",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        input_formats=['%d.%m.%Y', '%Y-%m-%d'],
        required=False
    )
    comment = forms.CharField(
        label="Комментарий",
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Причина отчисления...', 'class': 'form-control', 'style': 'resize: vertical;'}),
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
        label="Комментарий",
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Причина отказа...', 'class': 'form-control'}),
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
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        input_formats=['%d.%m.%Y', '%Y-%m-%d']
    )
    suspension_end = forms.DateField(
        label="Дата окончания",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        input_formats=['%d.%m.%Y', '%Y-%m-%d'],
        required=False,
        help_text="Оставьте пустым, если срок не определён"
    )
    comment = forms.CharField(
        label="Комментарий",
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Причина приостановки...', 'class': 'form-control', 'style': 'resize: vertical;'}),
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