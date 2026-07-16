# DrSl/templatetags/user_extras.py
from django import template

register = template.Library()

@register.filter
def get_attr(obj, attr_name):
    """Получить атрибут объекта по имени"""
    return getattr(obj, attr_name, False)

@register.filter
def is_in_group(user, group_name):
    """Проверка принадлежности к группе"""
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()