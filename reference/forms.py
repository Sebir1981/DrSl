from django import forms
from .models import SubjectDictionary
from .models import Credit, GroupCategory

class SubjectDictionaryForm(forms.ModelForm):
    class Meta:
        model = SubjectDictionary
        fields = ['name', 'short_name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Первая помощь пострадавшим при ДТП'
            }),
            'short_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: med',
                'pattern': '[a-z]+',
                'title': 'Только латинские буквы в нижнем регистре'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
        }


class CreditForm(forms.ModelForm):
    """Форма для добавления/редактирования темы зачёта"""

    class Meta:
        model = Credit
        fields = ['number', 'topic']
        widgets = {
            'number': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: 1',
                'min': '1',
                'max': '10'
            }),
            'topic': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Основы управления транспортным средством',
                'style': 'width: 100%;'
            }),
        }


class CreditCategoryFilterForm(forms.Form):
    """Форма фильтрации тем зачётов по категориям"""
    category = forms.ModelChoiceField(
        queryset=GroupCategory.objects.all().order_by('code'),
        required=False,
        label='Категория',
        widget=forms.Select(attrs={
            'class': 'form-control',
            'onchange': 'this.form.submit()'
        }),
        empty_label='Все категории'
    )