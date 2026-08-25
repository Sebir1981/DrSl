from django.test import TestCase
from django.core.exceptions import ValidationError
from cars.models import Car, CarDocument, TireChangeLog

class CarModelTest(TestCase):
    def setUp(self):
        self.car = Car.objects.create(
            make="Hyundai Solaris",
            license_plate="1234 AA-1",
            vin="1HGCM82633A123456",
            transmission="AT",
            fuel="GASOLINE_95",
            pts_number="7777777777",
            initial_odometer=15000
        )

    def test_car_creation(self):
        self.assertEqual(self.car.make, "Hyundai Solaris")
        self.assertEqual(str(self.car), "Hyundai Solaris (1234 AA-1)")

    def test_invalid_license_plate(self):
        self.car.license_plate = "НЕВЕРНЫЙ_НОМЕР"
        with self.assertRaises(ValidationError):
            self.car.full_clean()  # Запускает валидацию модели

    def test_invalid_vin_length(self):
        self.car.vin = "SHORT"
        with self.assertRaises(ValidationError):
            self.car.full_clean()


class CarDocumentModelTest(TestCase):
    def setUp(self):
        self.car = Car.objects.create(
            make="Kia Rio", license_plate="5678 BB-12", vin="12345678901234567",
            transmission="MT", fuel="DIESEL", pts_number="1111111111", initial_odometer=0
        )

    def test_document_creation(self):
        doc = CarDocument.objects.create(
            car=self.car,
            tech_inspection_date="2027-01-01",
            insurance_active=True
        )
        self.assertEqual(doc.car, self.car)
        self.assertTrue(doc.insurance_active)


class TireChangeLogModelTest(TestCase):
    def setUp(self):
        self.car = Car.objects.create(
            make="Toyota", license_plate="9999 CC-1", vin="12345678901234567",
            transmission="AT", fuel="GAS", pts_number="2222222222", initial_odometer=0
        )

    def test_tire_change_creation(self):
        change = TireChangeLog.objects.create(
            car=self.car,
            date="2026-08-24",
            odometer=50000,
            wheels=[1, 3]  # JSONField
        )
        self.assertEqual(change.odometer, 50000)
        self.assertIn(1, change.wheels)