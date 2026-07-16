# DrSl/decorators.py
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

def role_required(*role_names):
    """Декоратор: доступ только для указанных ролей"""
    def check_role(user):
        if not user.is_authenticated:
            return False
        if user.groups.filter(name__in=role_names).exists():
            return True
        raise PermissionDenied
    return user_passes_test(check_role)

# 🔹 Примеры использования:
# @role_required('admin') — только админ
# @role_required('admin', 'user') — админ или пользователь
# @role_required('guest') — только гость (просмотр)