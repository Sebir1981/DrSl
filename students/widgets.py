# DrSl/widgets.py
from django import forms
from datetime import date, datetime


class RuDateWidget(forms.TextInput):
    """Единый виджет для дат в формате дд.мм.гггг"""

    def __init__(self, attrs=None):
        default_attrs = {
            'type': 'text',  # ❗ Не 'date' — иначе браузер применит свою валидацию
            'placeholder': 'дд.мм.гггг',
            'maxlength': '10',
            'autocomplete': 'off',
            'class': 'vDateField',
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    def format_value(self, value):
        """✅ Конвертируем дату из БД в дд.мм.гггг перед отображением"""
        if value:
            if isinstance(value, (date, datetime)):
                return value.strftime('%d.%m.%Y')
            if isinstance(value, str) and '-' in value:
                # Конвертация из ГГГГ-ММ-ДД в ДД.ММ.ГГГГ
                try:
                    y, m, d = value.split('-')
                    return f"{d}.{m}.{y}"
                except:
                    pass
        return value if value else ''

    class Media:
        js = ('js/date-mask.js',)