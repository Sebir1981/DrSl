# DrSl/validators.py
from django.core.exceptions import ValidationError

def validate_date_range(value):
    """Валидатор диапазона дат: 2020–2040"""
    if value:
        if value.year < 2020 or value.year > 2040:
            raise ValidationError(
                f'Год должен быть в диапазоне 2020–2040. Вы указали: {value.year}',
                code='invalid_date_range'
            )