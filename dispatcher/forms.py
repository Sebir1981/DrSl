from django import forms
from .models import RouteSheet, IndividualBook, BookEntry
from reference.models import PracticeExercise, PracticeCategory


class RouteSheetForm(forms.ModelForm):
    """Форма путевого листа"""

    class Meta:
        model = RouteSheet
        fields = [
            'date', 'master', 'car', 'status',
            'start_time', 'end_time', 'duration_hours',
            'mileage_start', 'mileage_end', 'fuel_consumed',
            'students', 'exercises', 'route_description', 'notes'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'master': forms.Select(attrs={'class': 'form-input'}),
            'car': forms.Select(attrs={'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'duration_hours': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.5'}),
            'mileage_start': forms.NumberInput(attrs={'class': 'form-input'}),
            'mileage_end': forms.NumberInput(attrs={'class': 'form-input'}),
            'fuel_consumed': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.1'}),
            'students': forms.CheckboxSelectMultiple(attrs={'class': 'form-input'}),
            'exercises': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'route_description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }


class IndividualBookForm(forms.ModelForm):
    """Форма индивидуальной книжки"""

    class Meta:
        model = IndividualBook
        fields = ['student', 'group', 'master', 'car']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-input', 'id': 'book-student-select'}),
            'group': forms.Select(attrs={'class': 'form-input', 'id': 'book-group-select'}),
            'master': forms.Select(attrs={'class': 'form-input'}),
            'car': forms.Select(attrs={'class': 'form-input'}),
        }


class BookEntryForm(forms.ModelForm):
    """Форма записи в индивидуальной книжке"""

    class Meta:
        model = BookEntry
        fields = [
            'exercise', 'exercise_name', 'date',
            'route_sheet_number', 'start_time', 'end_time',
            'odometer_start', 'odometer_end',
            'student_signature', 'master_signature'
        ]
        widgets = {
            'exercise': forms.Select(attrs={'class': 'form-input exercise-select'}),
            'exercise_name': forms.TextInput(attrs={'class': 'form-input', 'readonly': 'readonly'}),
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'route_sheet_number': forms.TextInput(attrs={'class': 'form-input'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-input time-input', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-input time-input', 'type': 'time'}),
            'odometer_start': forms.NumberInput(attrs={'class': 'form-input odometer-input', 'inputmode': 'numeric'}),
            'odometer_end': forms.NumberInput(attrs={'class': 'form-input odometer-input', 'inputmode': 'numeric'}),
            'student_signature': forms.TextInput(attrs={'class': 'form-input'}),
            'master_signature': forms.TextInput(attrs={'class': 'form-input'}),
        }

class IndividualBookForm(forms.ModelForm):
    """Форма индивидуальной книжки"""

    class Meta:
        model = IndividualBook
        fields = ['student', 'group', 'master', 'car']
        widgets = {
            'student': forms.Select(attrs={
                'class': 'form-input',
                'id': 'book-student-select'
            }),
            'group': forms.Select(attrs={
                'class': 'form-input',
                'id': 'book-group-select'
            }),
            'master': forms.Select(attrs={'class': 'form-input'}),
            'car': forms.Select(attrs={'class': 'form-input'}),
        }


class BookEntryForm(forms.ModelForm):
    """Форма записи в индивидуальной книжке"""

    class Meta:
        model = BookEntry
        fields = [
            'exercise', 'exercise_name', 'date',
            'route_sheet_number', 'start_time', 'end_time',
            'odometer_start', 'odometer_end',
            'student_signature', 'master_signature'
        ]
        widgets = {
            'exercise': forms.Select(attrs={
                'class': 'form-input exercise-select'
            }),
            'exercise_name': forms.TextInput(attrs={
                'class': 'form-input',
                'readonly': 'readonly',
                'placeholder': 'Заполнится автоматически при выборе упражнения'
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date',
                'data-date-input': 'true'
            }),
            'route_sheet_number': forms.TextInput(attrs={'class': 'form-input'}),
            'start_time': forms.TimeInput(attrs={
                'class': 'form-input time-input',
                'type': 'time'
            }),
            'end_time': forms.TimeInput(attrs={
                'class': 'form-input time-input',
                'type': 'time'
            }),
            'odometer_start': forms.NumberInput(attrs={
                'class': 'form-input odometer-input',
                'inputmode': 'numeric'
            }),
            'odometer_end': forms.NumberInput(attrs={
                'class': 'form-input odometer-input',
                'inputmode': 'numeric'
            }),
            'student_signature': forms.TextInput(attrs={'class': 'form-input'}),
            'master_signature': forms.TextInput(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        """Фильтруем упражнения по категории группы, если она задана"""
        super().__init__(*args, **kwargs)
        # Опционально: можно отфильтровать упражнения по категории
        # self.fields['exercise'].queryset = PracticeExercise.objects.filter(
        #     category__code='B'  # пример
        # ).order_by('order', 'exercise_number')