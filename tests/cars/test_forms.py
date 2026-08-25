from django.test import TestCase
from cars.models import Car
from cars.forms import CarForm, CarDocumentForm, TireChangeForm

class CarFormTest(TestCase):
    def test_valid_car_form(self):
        form_data = {
            'make': 'Ford Focus',
            'license_plate': '1111 AA-1',
            'vin': '12345678901234567',
            'transmission': 'MT',
            'fuel': 'GASOLINE_92',
            'pts_number': '9999999999',
            'initial_odometer': 10000
        }
        form = CarForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_invalid_vin_form(self):
        form_data = {
            'make': 'Ford', 'license_plate': '1111 AA-1', 'vin': '123', # Короткий VIN
            'transmission': 'MT', 'fuel': 'GASOLINE_92', 'pts_number': '1', 'initial_odometer': 100
        }
        form = CarForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('vin', form.errors)


class TireChangeFormTest(TestCase):
    def test_valid_tire_form(self):
        form_data = {
            'date': '24.08.2026',
            'odometer': 50000,
            'wheels': ['1', '3'],
            'comment': 'Зимняя резина'
        }
        form = TireChangeForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_tire_form_without_wheels(self):
        form_data = {'date': '24.08.2026', 'odometer': 50000, 'wheels': []}
        form = TireChangeForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('wheels', form.errors)