# groups/views/mixins.py
import re

def parse_credit_comment(comment):
    """Парсит комментарий зачёта: 'Попытка №2, Тип: paid | Текст'"""
    # ... код из credits.py ...