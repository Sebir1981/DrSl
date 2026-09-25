from django import forms
from .models import RouteSheet
from masters.models import MasterPouts
from cars.models import Car
from students.models import Student


class RouteSheetForm(forms.ModelForm):
    """Форма для создания и редактирования путевого листа"""

    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Учащиеся"
    )

    class Meta:
        model = RouteSheet
        fields = [
            'date', 'master', 'car', 'status',
            'start_time', 'end_time', 'duration_hours',
            'mileage_start', 'mileage_end', 'fuel_consumed',
            'students', 'exercises', 'route_description', 'notes'
        ]
        widgets = {
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-input'
            }),
            'master': forms.Select(attrs={'class': 'form-input'}),
            'car': forms.Select(attrs={'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'start_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-input'
            }),
            'end_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'form-input'
            }),
            'duration_hours': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.5',
                'min': '0'
            }),
            'mileage_start': forms.NumberInput(attrs={'class': 'form-input'}),
            'mileage_end': forms.NumberInput(attrs={'class': 'form-input'}),
            'fuel_consumed': forms.NumberInput(attrs={
                'class': 'form-input',
                'step': '0.1'
            }),
            'exercises': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3
            }),
            'route_description': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3
            }),
        }