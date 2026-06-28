from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import PanelPermission, Registration, Volunteer


class SupportTeamAreaTests(TestCase):
    def setUp(self):
        self.client = Client()

    def create_volunteer(self, username='apoio'):
        user = User.objects.create_user(username=username, password='senha-forte-123')
        registration = Registration.objects.create(user=user)
        volunteer = Volunteer.objects.create(
            registration=registration,
            full_name=f'{username} Silva',
            birth_date=date(2000, 1, 1),
            gender='masculino',
            full_address='Rua Teste, 123',
            phone='11999999999',
            email=f'{username}@example.com',
            identity_document='123456',
            cpf='000.000.000-00',
            city_and_date='Sao Paulo, 01/01/2026',
            work_support_team=True,
        )
        return user, registration, volunteer

    def test_signup_renders_support_team_option(self):
        response = self.client.get(reverse('signup'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Equipe de apoio')
        self.assertContains(response, timezone.localdate().strftime('%d/%m/%Y'))

    def test_admin_dashboard_shows_support_team_area(self):
        admin = User.objects.create_superuser(username='admin', password='senha-forte-123')
        _, registration, volunteer = self.create_volunteer()
        self.client.force_login(admin)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Equipe de apoio')
        self.assertContains(response, f'data-modal-target="registration-modal-{registration.id}"')
        self.assertContains(response, f'data-modal-target="volunteer-modal-{volunteer.id}"')

    def test_reports_dashboard_includes_support_team_work_area(self):
        user, _, _ = self.create_volunteer()
        PanelPermission.objects.create(user=user, can_view_reports=True)
        self.client.force_login(user)

        response = self.client.get(reverse('reports_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Equipe de apoio')
        self.assertContains(response, '"label": "Equipe de apoio"')
        self.assertContains(response, '"count": 1')
