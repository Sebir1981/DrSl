# DrSl/jazzmin_config.py
from django.urls import reverse_lazy

JAZZMIN_SETTINGS = {
    "site_title": "Автошкола Админ",
    "site_header": "🔐 Автошкола",
    "site_brand": "🚗 Автошкола",
    "welcome_sign": "Добро пожаловать в панель управления",
    "copyright": "Автошкола © 2026",
    "site_url": reverse_lazy("vault:dashboard"),
    "search_model": ["auth.User", "vault.VaultEntry"],
    "user_avatar": None,

    # 🔹 Порядок приложений
    "order_with_respect_to": [
        "vault", "groups", "students", "classrooms", "teachers", "masters", "reference", "auth",
    ],

    # 🔹 Иконки
    "icons": {
        "auth": "fas fa-users-cog",
        "vault": "fas fa-key",
        "students": "fas fa-user-graduate",
        "groups": "fas fa-layer-group",
        "classrooms": "fas fa-door-open",
        "teachers": "fas fa-chalkboard-teacher",
        "masters.master": "fas fa-user-cog",
        "reference": "fas fa-book-open",
        "reference.groupcategory": "fas fa-folder-open",
    },

    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "show_ui_builder": False,
    "related_modal_active": True,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "students.student": "vertical_tabs",
        "groups.group": "vertical_tabs",
        "classrooms.classroom": "vertical_tabs",
        "teachers.teacher": "vertical_tabs",
    },
    "show_sidebar": True,
    "navigation_expanded": True,
}