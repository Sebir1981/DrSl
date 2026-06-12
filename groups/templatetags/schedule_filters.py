# groups/templatetags/schedule_filters.py
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Безопасное получение значения из словаря по ключу"""
    if dictionary is None:
        return ''
    return dictionary.get(key, '')