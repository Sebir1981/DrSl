# tests/master_plan/test_brand_filter.py
from datetime import date

from django.test import TestCase
from master_plan.models import MasterPlanGroup
from masters.models import MasterPouts
from cars.models import Car
from students.models import Student
from groups.models import Group


# =========================================================================
# 🔹 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================================

def make_master(last_name, first_name='И', patronymic='И',
                passport='AB 1234567', license='AAA 123456',
                phone='+375 (29) 000-00-00', fuel='123456789',
                car=None):
    """
    Создаёт мастера. У мастера ОДНА машина (FK `car`), не ManyToMany.
    """
    return MasterPouts.objects.create(
        last_name=last_name,
        first_name=first_name,
        patronymic=patronymic,
        passport_number=passport,
        birth_date=date(1990, 1, 1),
        license_number=license,
        license_expiry=date(2030, 1, 1),
        phone=phone,
        fuel_card_number=fuel,
        car=car,
    )


def make_car(make, license_plate, vin='TESTVIN0000000000',
             transmission='MT', fuel='GASOLINE_95',
             pts_number='PTS000000', initial_odometer=0):
    """
    Создаёт машину.
    Значения transmission/fuel — из choices (см. Car._meta).
    """
    return Car.objects.create(
        make=make,
        license_plate=license_plate,
        vin=vin,
        transmission=transmission,
        fuel=fuel,
        pts_number=pts_number,
        initial_odometer=initial_odometer,
    )


# =========================================================================
# 🔹 ТЕСТЫ
# =========================================================================

class BrandFilterTest(TestCase):

    def setUp(self):
        # Машина Toyota
        self.car_toyota = make_car('Toyota', '1234 AB-7')

        # Мастер A — с Toyota
        self.master_a = make_master('А', 'А', 'А',
                                     passport='AB 1111111',
                                     car=self.car_toyota)

        # Мастер B — без машины
        self.master_b = make_master(
            'Б', 'Б', 'Б',
            passport='AB 2222222',
            license='AAA 654321',
            phone='+375 (29) 111-11-11',
            fuel='987654321',
        )

        # Группа и студент
        self.group = Group.objects.create(
            group_number='TEST', status='active'
        )
        self.plan_group = MasterPlanGroup.objects.create(group=self.group)
        self.student = Student.objects.create(
            last_name='Иванов',
            first_name='Иван',
            group=self.group,
        )

    def test_filter_returns_only_matching_masters(self):
        """Только мастер A имеет Toyota."""
        filtered = MasterPouts.objects.filter(
            car__make__iexact='Toyota'
        ).distinct()
        self.assertIn(self.master_a, filtered)
        self.assertNotIn(self.master_b, filtered)

    def test_filter_by_unknown_brand_returns_empty(self):
        """Марки BMW ни у кого нет."""
        filtered = MasterPouts.objects.filter(
            car__make__iexact='BMW'
        ).distinct()
        self.assertEqual(list(filtered), [])

    def test_filter_case_insensitive(self):
        """Регистр не важен."""
        for variant in ('toyota', 'TOYOTA', 'Toyota', 'TOyota'):
            filtered = MasterPouts.objects.filter(
                car__make__iexact=variant
            ).distinct()
            self.assertIn(self.master_a, filtered,
                          msg=f'Не найден при {variant!r}')

    def test_master_b_without_car_not_in_filter(self):
        """Мастер без машины не попадает ни в один фильтр."""
        for brand in ('Toyota', 'Hyndai', 'BMW'):
            filtered = MasterPouts.objects.filter(
                car__make__iexact=brand
            ).distinct()
            self.assertNotIn(self.master_b, filtered)

    def test_student_with_toyota_has_car_brand_parsed(self):
        """Парсер услуг читает марку из activity_log."""
        self.student.activity_log = [{
            'type': 'service_added',
            'details': {
                'service_name': 'Марка автомобиля',
                'values': {'select-brand-4': 'Toyota'},
            },
        }]
        self.student.save()

        from master_plan.views import _get_student_service_prefs
        prefs = _get_student_service_prefs(self.student)
        self.assertEqual(prefs['car_brand'], 'Toyota')

    def test_student_without_brand_has_none(self):
        """Без услуги — car_brand = None."""
        from master_plan.views import _get_student_service_prefs
        prefs = _get_student_service_prefs(self.student)
        self.assertIsNone(prefs['car_brand'])

class ServiceValidationTests(TestCase):
    """Проверки совместимости при сохранении платных услуг."""

    def setUp(self):
        self.car = Car.objects.create(
            make='Toyota', license_plate='AB-1111',
            vin='TESTVIN0000000000', transmission='MT',
            fuel='GASOLINE_95', pts_number='PTS000000',
            initial_odometer=0,
        )
        self.master = MasterPouts.objects.create(
            last_name='А', first_name='А', patronymic='А',
            passport_number='AB 1111111', birth_date=date(1990, 1, 1),
            license_number='AAA 111111', license_expiry=date(2030, 1, 1),
            phone='+375 (29) 111-11-11', fuel_card_number='111111111',
            car=self.car, gender='male',
        )
        self.group = Group.objects.create(group_number='TEST', status='active')
        self.student = Student.objects.create(
            last_name='Иванов', first_name='Иван',
            group=self.group, gearbox_type='manual',
        )

    def test_validate_car_brand_match(self):
        from students.views import _validate_master_brand_compatibility
        ok, err = _validate_master_brand_compatibility(
            self.master.pk, 'Toyota'
        )
        self.assertTrue(ok)

    def test_validate_car_brand_mismatch(self):
        from students.views import _validate_master_brand_compatibility
        ok, err = _validate_master_brand_compatibility(
            self.master.pk, 'BMW'
        )
        self.assertFalse(ok)
        self.assertIn('BMW', err)