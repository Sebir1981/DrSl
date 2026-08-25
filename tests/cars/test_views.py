from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from cars.models import Car, CarDocument, TireChangeLog


class CarViewsTest(TestCase):
    def setUp(self):
        # Создаем тестового пользователя
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client.login(username='testuser', password='testpass123')

        # Создаем тестовый автомобиль
        self.car = Car.objects.create(
            make="Lada Vesta", license_plate="7777 AA-7", vin="12345678901234567",
            transmission="MT", fuel="GASOLINE_95", pts_number="3333333333", initial_odometer=5000
        )

    def test_car_list_view_status_code(self):
        response = self.client.get(reverse('cars:car_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lada Vesta")

    def test_car_add_view_post(self):
        data = {
            'make': 'Skoda Octavia', 'license_plate': '8888 BB-8', 'vin': '12345678901234568',
            'transmission': 'AT', 'fuel': 'DIESEL', 'pts_number': '4444444444', 'initial_odometer': 0
        }
        response = self.client.post(reverse('cars:car_add'), data)
        # После добавления должен быть редирект на страницу документов
        self.assertRedirects(response, reverse('cars:car_documents', kwargs={'pk': Car.objects.count()}))
        self.assertEqual(Car.objects.count(), 2)

    def test_car_documents_tire_change_post(self):
        """Тестируем добавление записи о замене колес через форму документов"""
        data = {
            'tire_date': '24.08.2026',
            'tire_odometer': '15000',
            'wheels': ['2', '4']
        }
        response = self.client.post(reverse('cars:car_documents', kwargs={'pk': self.car.pk}), data)

        self.assertRedirects(response, reverse('cars:car_documents', kwargs={'pk': self.car.pk}))

        # Проверяем, что запись создалась
        self.assertEqual(TireChangeLog.objects.count(), 1)
        change = TireChangeLog.objects.first()
        self.assertEqual(change.odometer, 15000)
        self.assertEqual(change.wheels, [2, 4])

        # Проверяем, что обновился текущий одометр автомобиля
        self.car.refresh_from_db()
        self.assertEqual(self.car.current_odometer, 15000)

    def test_car_delete_view(self):
        response = self.client.post(reverse('cars:car_delete', kwargs={'pk': self.car.pk}))
        self.assertRedirects(response, reverse('cars:car_list'))
        self.assertEqual(Car.objects.count(), 0)

    def test_unauthorized_access(self):
        self.client.logout()
        response = self.client.get(reverse('cars:car_list'))
        # Должен редиректить на страницу входа (LOGIN_URL)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/admin/login/') or response.url.startswith('/login/'))