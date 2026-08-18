from django import forms
from datetime import date, datetime


class RuDateWidget(forms.TextInput):
    def __init__(self, attrs=None):
        default_attrs = {
            'type': 'text',
            'placeholder': 'дд.мм.гггг',
            'maxlength': '10',
            'autocomplete': 'off',
            'class': 'vDateField',
        }

        # Создаем финальный словарь атрибутов
        final_attrs = default_attrs.copy()

        # Если переданы кастомные атрибуты (например, class='form-control') - применяем их
        if attrs:
            final_attrs.update(attrs)

        # ✅ ВАЖНО: Принудительно добавляем маркер для JS ПОВЕРХ всего
        final_attrs['data-date-input'] = 'true'

        super().__init__(attrs=final_attrs)

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
                except (ValueError, AttributeError):
                    pass  # Если что-то пошло не так, просто пропускаем

            return value if value else ''
        return ''

    def value_from_datadict(self, data, files, name):
        """
        ✅ Перехватываем данные из формы перед валидацией.
        Если пользователь ввёл 18.08.26, превращаем в 18.08.2026.
        """
        value = super().value_from_datadict(data, files, name)
        if not value or not isinstance(value, str):
            return value

        value = value.strip()
        parts = value.split('.')

        # Если формат дд.мм.гг (3 части)
        if len(parts) == 3:
            d, m, y = parts
            # Если год состоит из 2 цифр
            if len(y) == 2:
                # Дописываем 20 (для 2000-х годов)
                y = f"20{y}"
                return f"{d}.{m}.{y}"

        return value

    class Media:
        js = ('/static/js/date-mask.js',)