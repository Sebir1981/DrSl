import json
from datetime import date, timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

# Импортируем модели
from groups.models import Group, SchedulePlan
from reference.models import GroupCategory, TrainingProgram, SubjectDictionary, ProgramSubject
from teachers.models import Teacher
from classrooms.models import Classroom

# Импортируем тестируемые хелперы
from groups.views.schedule_plans import _check_schedule_duplicates, _is_standard_schedule_day


class SchedulePlansViewsTestCase(TestCase):
    def setUp(self):
        """Настройка тестовых данных перед каждым тестом"""
        self.client = Client()

        # 1. Пользователь
        self.user = User.objects.create_user(
            username='testuser', password='testpass123', is_staff=True
        )
        self.other_user = User.objects.create_user(
            username='otheruser', password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')

        # 2. Преподаватель
        self.teacher = Teacher.objects.create(
            last_name='Иванов', first_name='Иван', is_active=True
        )
        self.med_teacher = Teacher.objects.create(
            last_name='Петров', first_name='Петр', is_active=True
        )

        # 3. Группа
        self.group = Group.objects.create(
            group_number='Группа-101',
            teacher=self.teacher,
            contract_start=date(2026, 9, 1),
            contract_end=date(2026, 9, 30),
            status='active'
        )

        # 4. Учебная программа и предметы (для Step 2)
        self.category = GroupCategory.objects.create(code='IT', description='IT курсы')
        self.program = TrainingProgram.objects.create(
            name='Python Basic', total_hours=50.0
        )
        self.program.categories.add(self.category)

        # ✅ SubjectDictionary вместо Subject
        self.subject1 = SubjectDictionary.objects.create(
            short_name='python', name='Python', short_name_display='PY'
        )
        self.subject2 = SubjectDictionary.objects.create(
            short_name='exam', name='Экзамен', short_name_display='EX'
        )

        ProgramSubject.objects.create(program=self.program, subject=self.subject1, hours=40.0)
        ProgramSubject.objects.create(program=self.program, subject=self.subject2, hours=10.0)

        # 5. Существующий план-график
        self.plan = SchedulePlan.objects.create(
            group=self.group,
            teacher=self.teacher,
            date_start=date(2026, 9, 1),
            date_end=date(2026, 9, 30),
            schedule_type='even',
            created_by=self.user,
            class_days={'_time_slots': ['morning'], '_category': 'IT'}
        )

    # =========================================================================
    # 🔹 Тесты вспомогательных функций (Helpers)
    # =========================================================================
    def test_is_standard_schedule_day(self):
        # 2 сентября 2026 = Среда (будни), день 2 (чётный)
        self.assertTrue(_is_standard_schedule_day('2026-09-02', 'even'))
        self.assertFalse(_is_standard_schedule_day('2026-09-02', 'odd'))

        # 5 сентября 2026 = Суббота (выходной)
        self.assertTrue(_is_standard_schedule_day('2026-09-05', 'weekend'))
        self.assertFalse(_is_standard_schedule_day('2026-09-05', 'even'))

    def test_check_schedule_duplicates(self):
        # Пересекающиеся даты
        duplicates = _check_schedule_duplicates(
            group=self.group, date_start=date(2026, 9, 15), date_end=date(2026, 9, 20)
        )
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0].pk, self.plan.pk)

        # Непересекающиеся даты
        duplicates = _check_schedule_duplicates(
            group=self.group, date_start=date(2026, 10, 1), date_end=date(2026, 10, 30)
        )
        self.assertEqual(len(duplicates), 0)

    # =========================================================================
    # 🔹 Тесты View: Список планов
    # =========================================================================
    def test_schedule_plans_list_get(self):
        response = self.client.get(reverse('groups:schedule_plans_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'groups/schedule_plans_list.html')
        self.assertIn('plans', response.context)

    # =========================================================================
    # 🔹 Тесты View: Создание/Редактирование (Шаг 1)
    # =========================================================================
    def test_schedule_plan_create_get(self):
        response = self.client.get(reverse('groups:schedule_plan_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'groups/schedule_plan_form.html')

    def test_schedule_plan_create_post_success(self):
        data = {
            'group': self.group.pk,
            'teacher': self.teacher.pk,
            'date_start': '2026-10-01',
            'date_end': '2026-10-10',
            'schedule_type': 'odd',
            'location': 'Аудитория 5',
            'med_teacher': str(self.med_teacher.pk),
            'time_morning': 'on',
            'class_days': json.dumps({
                '2026-10-01': {'scheduled': True, 'med_hours': 2},
                '2026-10-05': {'scheduled': True}
            })
        }
        response = self.client.post(reverse('groups:schedule_plan_create'), data)

        # Должен быть редирект на Step 2
        new_plan = SchedulePlan.objects.latest('id')
        self.assertRedirects(response, reverse('groups:schedule_plan_step2', args=[new_plan.pk]))

        # Проверка сохранённых данных
        self.assertEqual(new_plan.med_teacher, self.med_teacher)
        self.assertIn('2026-10-01', new_plan.class_days)
        self.assertIn('_med_days', new_plan.class_days)
        self.assertIn('2026-10-01', new_plan.class_days['_med_days'])

    def test_schedule_plan_create_post_duplicate_error(self):
        data = {
            'group': self.group.pk,
            'date_start': '2026-09-10',
            'date_end': '2026-09-20',
            'schedule_type': 'even',
        }
        response = self.client.post(reverse('groups:schedule_plan_create'), data)

        # Редиректа не должно быть, должна остаться та же страница с ошибкой
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'groups/schedule_plan_form.html')

        # Проверяем, что новый план НЕ создан
        self.assertEqual(SchedulePlan.objects.filter(group=self.group).count(), 1)

    # =========================================================================
    # 🔹 Тесты View: AJAX обновление дня
    # =========================================================================
    def test_schedule_plan_ajax_update_day_success(self):
        data = {'date': '2026-09-15', 'action': 'add'}
        response = self.client.post(
            reverse('groups:schedule_plan_ajax_update_day', args=[self.plan.pk]),
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'success': True})

        self.plan.refresh_from_db()
        self.assertIn('2026-09-15', self.plan.class_days)

    def test_schedule_plan_ajax_update_day_method_not_allowed(self):
        response = self.client.get(reverse('groups:schedule_plan_ajax_update_day', args=[self.plan.pk]))
        self.assertEqual(response.status_code, 405)

    # =========================================================================
    # 🔹 Тесты View: Шаг 2 (Распределение часов)
    # =========================================================================
    def test_schedule_plan_step2_get(self):
        url = f"{reverse('groups:schedule_plan_step2', args=[self.plan.pk])}?program_id={self.program.pk}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'groups/schedule_plan_step2.html')
        self.assertIn('days_by_month', response.context)
        self.assertIn('program_subjects', response.context)
        self.assertEqual(response.context['required_hours'], 50.0)

    def test_schedule_plan_step2_post_success(self):
        payload = {
            'topics': {
                '2026-09-02': {
                    'python': {'1': 2.5, '2': 1.5},
                    'exam': {'999': 1.0}
                }
            },
            'med_teacher': str(self.med_teacher.pk),
            'category': 'IT',
            'time_start': '09:00',
            'time_end': '17:00'
        }
        response = self.client.post(
            reverse('groups:schedule_plan_step2', args=[self.plan.pk]),
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'success': True})

        self.plan.refresh_from_db()
        class_days = self.plan.class_days

        # Проверяем, что часы просуммировались
        self.assertEqual(class_days['2026-09-02']['python'], 4.0)
        self.assertEqual(class_days['2026-09-02']['python_topics'], {'1': 2.5, '2': 1.5})
        self.assertEqual(class_days['_time_start'], '09:00')
        self.assertEqual(self.plan.med_teacher, self.med_teacher)

    def test_schedule_plan_step2_post_invalid_json(self):
        response = self.client.post(
            reverse('groups:schedule_plan_step2', args=[self.plan.pk]),
            data="invalid json string",
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    # =========================================================================
    #  Тесты View: Удаление и сброс
    # =========================================================================
    def test_schedule_plan_delete_success(self):
        response = self.client.get(reverse('groups:schedule_plan_delete', args=[self.plan.pk]))
        self.assertRedirects(response, reverse('groups:schedule_plans_list'))

        with self.assertRaises(SchedulePlan.DoesNotExist):
            SchedulePlan.objects.get(pk=self.plan.pk)

    def test_schedule_plan_delete_no_permission(self):
        other_plan = SchedulePlan.objects.create(
            group=self.group, date_start=date(2026, 10, 1), date_end=date(2026, 10, 10),
            created_by=self.other_user
        )
        response = self.client.get(reverse('groups:schedule_plan_delete', args=[other_plan.pk]))
        self.assertRedirects(response, reverse('groups:schedule_plans_list'))

        # План должен остаться на месте
        self.assertTrue(SchedulePlan.objects.filter(pk=other_plan.pk).exists())

    def test_schedule_plan_reset_success(self):
        self.plan.class_days = {
            '_time_slots': ['morning'],
            '2026-09-02': {'python': 4.0, 'python_topics': {'1': 4.0}, 'scheduled': True}
        }
        self.plan.save()

        response = self.client.delete(reverse('groups:schedule_plan_reset', args=[self.plan.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'success': True, 'message': 'Часы очищены', 'action': 'hours_cleared'})

        self.plan.refresh_from_db()
        self.assertIn('_time_slots', self.plan.class_days)
        self.assertNotIn('python', self.plan.class_days.get('2026-09-02', {}))

    def test_schedule_plan_reset_method_not_allowed(self):
        response = self.client.get(reverse('groups:schedule_plan_reset', args=[self.plan.pk]))
        self.assertEqual(response.status_code, 405)

    def test_clear_plan_topics_success(self):
        self.plan.class_days = {'2026-09-02': {'python': 4.0}}
        self.plan.excluded_dates = ['2026-09-05']
        self.plan.additional_dates = ['2026-09-06']
        self.plan.save()

        response = self.client.post(reverse('groups:clear_plan_topics', args=[self.plan.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'success': True, 'message': 'Данные план-графика очищены'})

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.class_days, {})
        self.assertEqual(self.plan.excluded_dates, [])
        self.assertEqual(self.plan.additional_dates, [])