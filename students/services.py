# students/services.py
import datetime
from typing import Optional, Dict, List
from django.db import transaction
from django.utils import timezone

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
            created_by=created_by  # <--- Записываем пользователя, который сделал действие
        )

        # 2. Обновление activity_log (в ISO-формате для правильной сортировки)
        author_name = created_by.get_full_name() if created_by else 'Система'
        log_entry = {
            'type': event_type,
            'date': event_date.isoformat(),
            'title': self._get_title(event_type, details),
            'details': details,
            'author': author_name  # <--- ДОБАВЛЕНО: записываем имя автора в JSON
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
        # Здесь можно реализовать строгую машину состояний
        # Например: Нельзя активировать, если студент уже активен.
        return True

    def _update_student_fields(self, event_type: str, event_date: datetime.date, details: Dict):
        """Обновляет поля самого студента в зависимости от события."""
        if event_type == 'transfer':
            self.student.group_id = details.get('to_group_id')
            self.student.transferred_date = event_date
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

        # ✅ КОНСТАНТЫ для статуса "Активен"
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

        # Если ничего не найдено, возвращаем дефолт
        return {'status': DEFAULT_STATUS, 'color': DEFAULT_COLOR}

    def test_add_suspension_event(self):
        """Сервис: добавление события приостановки."""
        self.service.add_event(
            event_type='suspension',
            details={'comment': 'По медицинским показаниям'}
        )
        self.student.refresh_from_db()

        self.assertEqual(len(self.student.activity_log), 1)
        self.assertEqual(self.student.activity_log[0]['type'], 'suspension')
        self.assertEqual(self.student.activity_log[0]['details']['comment'], 'По медицинским показаниям')

    def test_add_refusal_event(self):
        """Сервис: добавление события отказа."""
        self.service.add_event(
            event_type='refusal',
            details={'comment': 'Личные причины'}
        )
        self.student.refresh_from_db()

        self.assertEqual(len(self.student.activity_log), 1)
        self.assertEqual(self.student.activity_log[0]['type'], 'refusal')
        self.assertEqual(self.student.activity_log[0]['details']['comment'], 'Личные причины')

    def test_add_dismissal_event(self):
        """Сервис: добавление события отчисления."""
        self.service.add_event(
            event_type='dismissal',
            details={'order_number': '45-У', 'comment': 'За неуспеваемость'}
        )
        self.student.refresh_from_db()

        self.assertEqual(len(self.student.activity_log), 1)
        self.assertEqual(self.student.activity_log[0]['type'], 'dismissal')
        self.assertEqual(self.student.activity_log[0]['details']['order_number'], '45-У')

    def test_add_activation_event(self):
        """Сервис: добавление события активации."""
        # Сначала создаём приостановку
        self.service.add_event(event_type='suspension')

        # Затем активируем
        self.service.add_event(event_type='activation')
        self.student.refresh_from_db()

        # В логе должно быть 2 события
        self.assertEqual(len(self.student.activity_log), 2)
        self.assertEqual(self.student.activity_log[-1]['type'], 'activation')

    def test_add_teacher_change_event(self):
        """Сервис: добавление события смены преподавателя."""
        self.service.add_event(
            event_type='teacher_change',
            details={
                'to_teacher_id': 999,
                'to_teacher': 'Иванов И.И.'
            }
        )
        self.student.refresh_from_db()

        self.assertEqual(len(self.student.activity_log), 1)
        self.assertEqual(self.student.activity_log[0]['type'], 'teacher_change')
        self.assertEqual(self.student.activity_log[0]['details']['to_teacher'], 'Иванов И.И.')

    def test_get_current_status_active(self):
        """Сервис: метод get_current_status возвращает 'Активен' для нового студента."""
        status = self.service.get_current_status()
        self.assertEqual(status['status'], 'Активен')
        self.assertEqual(status['color'], '#16a34a')

    def test_get_current_status_suspended(self):
        """Сервис: метод get_current_status возвращает 'Приостановлен' после suspension."""
        self.service.add_event(event_type='suspension')
        status = self.service.get_current_status()
        self.assertEqual(status['status'], 'Приостановлен')
        self.assertEqual(status['color'], '#7c3aed')