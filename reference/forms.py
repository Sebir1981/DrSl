from django import forms
from .models import SubjectDictionary

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