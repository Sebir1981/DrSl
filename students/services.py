# students/services.py
import datetime
from typing import Optional, Dict
from django.db import transaction
from django.utils import timezone

from groups.models import Group
from .models import Student, StudentHistory


class StudentStatusService:
    """Единый сервис для управления статусом и историей учащегося"""

    def __init__(self, student: Student):
        self.student = student

    @transaction.atomic
    def add_event(self, event_type: str, created_by=None, event_date: Optional[datetime.date] = None,
                  details: Dict = None, comment: str = ''):
        """
        Добавляет событие в историю и обновляет статус учащегося.
        Все изменения происходят в одной транзакции (атомарно).
        """
        if event_date is None:
            event_date = timezone.now().date()

        if details is None:
            details = {}

        # Валидация статусов (бизнес-логика)
        if not self._can_perform_event(event_type):
            raise ValueError(f"Невозможно выполнить '{event_type}' для текущего статуса студента.")

        # 1. Запись в SQL-историю (StudentHistory)
        history = StudentHistory.objects.create(
            student=self.student,
            event_type=event_type,
            event_date=event_date,
            comment=comment,
            created_by=created_by
        )

        # 2. Обновление activity_log (в ISO-формате для правильной сортировки)
        author_name = created_by.get_full_name() if created_by else 'Система'
        log_entry = {
            'type': event_type,
            'date': event_date.isoformat(),
            'title': self._get_title(event_type, details),
            'details': details,
            'author': author_name
        }
        current_log = self.student.activity_log or []
        current_log.append(log_entry)
        current_log.sort(key=lambda x: x.get('date', ''))
        self.student.activity_log = current_log

        # 3. Обновление полей студента
        self._update_student_fields(event_type, event_date, details)

        # 4. Сохраняем студента
        self.student.save(
            update_fields=['group', 'teacher', 'transferred_date', 'graduated_date', 'activity_log', 'updated_at'])

        return history

    def _can_perform_event(self, _event_type: str) -> bool:
        """Проверка разрешенных переходов статусов."""
        return True

    def _update_student_fields(self, event_type: str, event_date: datetime.date, details: Dict):
        """Обновляет поля самого студента в зависимости от события."""
        if event_type == 'transfer':
            new_group_id = details.get('to_group_id')
            self.student.group_id = new_group_id
            self.student.transferred_date = event_date

            # 🔹 НАСЛЕДОВАНИЕ: преподаватель из новой группы
            if new_group_id:
                new_group = (
                    Group.objects.select_related('teacher')
                    .filter(pk=new_group_id)
                    .first()
                )
                if new_group and new_group.teacher_id:
                    self.student.teacher_id = new_group.teacher_id

        elif event_type == 'teacher_change':
            self.student.teacher_id = details.get('to_teacher_id')

        elif event_type == 'graduation':
            self.student.graduated_date = event_date

    def _get_title(self, event_type: str, details: Dict) -> str:
        """Генерирует заголовок для JSON-лога."""
        titles = {
            'enrollment': 'Зачисление в автошколу',
            'transfer': f"Перевод в группу {details.get('to_group', '—')}",
            'teacher_change': f"Смена преподавателя на {details.get('to_teacher', '—')}",
            'suspension': 'Приостановка обучения',
            'activation': 'Активация учащегося',
            'refusal': 'Отказ от обучения',
            'dismissal': f"Отчисление: приказ №{details.get('order_number', '—')}",
            'graduation': 'Выпуск из автошколы'
        }
        return titles.get(event_type, 'Событие')

    def get_current_status(self):
        """Возвращает текущий статус студента и цвет для отображения."""
        DEFAULT_STATUS = 'Активен'
        DEFAULT_COLOR = '#16a34a'

        # 1. Если выпустился
        if self.student.graduated_date:
            return {'status': 'Выпуск', 'color': '#0ea5e9'}

        # 2. Если нет истории, студент активен по умолчанию
        if not self.student.activity_log:
            return {'status': DEFAULT_STATUS, 'color': DEFAULT_COLOR}

        # 3. Сортируем историю по дате
        sorted_events = sorted(self.student.activity_log, key=lambda x: x.get('date', ''), reverse=True)

        for event in sorted_events:
            etype = event.get('type', '')

            status_map = {
                'dismissal': {'status': 'Отчислен', 'color': '#dc2626'},
                'refusal': {'status': 'Отказ', 'color': '#f59e0b'},
                'suspension': {'status': 'Приостановлен', 'color': '#7c3aed'},
                'activation': {'status': DEFAULT_STATUS, 'color': DEFAULT_COLOR},
                'enrollment': {'status': DEFAULT_STATUS, 'color': DEFAULT_COLOR},
                'transfer': {'status': DEFAULT_STATUS, 'color': DEFAULT_COLOR},
            }

            if etype in status_map:
                return status_map[etype]

        return {'status': DEFAULT_STATUS, 'color': DEFAULT_COLOR}