# core/widgets.py  (создайте папку core/, если нет)
from django import forms


class RuDateWidget(forms.TextInput):
    """Виджет для ввода даты в формате дд.мм.гггг с маской"""

    def __init__(self, attrs=None):
        default_attrs = {
            'type': 'text',
            'placeholder': 'дд.мм.гггг',
            'maxlength': '10',  # 2+1+2+1+4
            'autocomplete': 'off',
            'class': 'vDateField',  # для совместимости со стилями Django
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    class Media:
        js = ('js/date-mask.js',)  # ✅ Подключаем маску