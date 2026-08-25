# DrSl/utils.py

from DrSl.utils import get_user_fio



def get_user_fio(user):
    """
    Р’РѕР·РІСЂР°С‰Р°РµС‚ СЃС‚СЂРѕРєСѓ: 'Р¤Р°РјРёР»РёСЏ Р.Рћ.'
    Р•СЃР»Рё РґР°РЅРЅС‹С… РЅРµС‚ вЂ” РІРѕР·РІСЂР°С‰Р°РµС‚ username РёР»Рё 'РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ'
    """
    if not user or not user.is_authenticated:
        return 'Р“РѕСЃС‚СЊ'

    # Р•СЃР»Рё Сѓ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ РµСЃС‚СЊ СЃРІСЏР·Р°РЅРЅС‹Рµ РїРѕР»СЏ (С‡РµСЂРµР· РїСЂРѕС„РёР»СЊ РёР»Рё custom user)
    if hasattr(user, 'last_name') and user.last_name:
        first_initial = user.first_name[0] + '.' if user.first_name else ''
        patronymic_initial = ''
        # РџСЂРѕРІРµСЂСЏРµРј, РµСЃС‚СЊ Р»Рё РѕС‚С‡РµСЃС‚РІРѕ (РІ РєР°СЃС‚РѕРјРЅРѕР№ РјРѕРґРµР»Рё РёР»Рё С‡РµСЂРµР· РїСЂРѕС„РёР»СЊ)
        if hasattr(user, 'patronymic') and user.patronymic:
            patronymic_initial = user.patronymic[0] + '.'
        elif hasattr(user, 'profile') and hasattr(user.profile, 'patronymic') and user.profile.patronymic:
            patronymic_initial = user.profile.patronymic[0] + '.'

        return f"{user.last_name} {first_initial}{patronymic_initial}".strip()

    # Р¤РѕР»Р±СЌРє РЅР° username, РµСЃР»Рё РЅРµС‚ Р¤РРћ
    return get_user_fio(user) or 'РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ'


# рџ”№ РЁР°Р±Р»РѕРЅРЅС‹Р№ С„РёР»СЊС‚СЂ РґР»СЏ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ РІ HTML
from django import template

register = template.Library()


@register.filter
def fio(user):
    return get_user_fio(user)
