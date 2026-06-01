# classrooms/forms.py
from django import forms
from .models import Classroom
from core.widgets import RuDateWidget


class ClassroomAdminForm(forms.ModelForm):
    contract_start = forms.DateField(
        label="Договор с",
        input_formats=['%d.%m.%Y'],
        widget=RuDateWidget(),
        required=False
    )
    contract_end = forms.DateField(
        label="Договор по",
        input_formats=['%d.%m.%Y'],
        widget=RuDateWidget(),
        required=False
    )
    san_certificate_valid_until = forms.DateField(
        label="СЭС действует до",
        input_formats=['%d.%m.%Y'],
        widget=RuDateWidget(),
        required=False
    )

    class Meta:
        model = Classroom
        fields = '__all__'

    class Media:
        js = ('js/date-mask.js',)