# teachers/forms.py  (если добавите даты в модель Teacher)
from django import forms
from .models import Teacher
from core.widgets import RuDateWidget


class TeacherAdminForm(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = '__all__'
        widgets = {
            # Если добавите date-поля, укажите здесь:
            # 'some_date': RuDateWidget(),
        }

    class Media:
        js = ('js/phone-mask.js', 'js/date-mask.js')