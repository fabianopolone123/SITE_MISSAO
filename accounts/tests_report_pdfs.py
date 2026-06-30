from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import PanelPermission, Registration, Volunteer


class ReportsPdfTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='relatorios', password='senha-forte-123')
        PanelPermission.objects.create(user=self.user, can_view_reports=True)
        registration = Registration.objects.create(user=self.user)
        self.volunteer = Volunteer.objects.create(
            registration=registration,
            full_name='Missionario PDF',
            birth_date=date(2000, 1, 1),
            gender='masculino',
            full_address='Rua Teste, 123',
            phone='11999999999',
            email='pdf@example.com',
            identity_document='RG 123456',
            cpf='000.000.000-00',
            emergency_contact_name='Contato Teste',
            emergency_contact_relationship='Irmão',
            emergency_contact_phone='11888887777',
            has_allergies='sim',
            allergies='Po',
            has_food_restriction='sim',
            food_restrictions='Lactose',
            city_and_date='Sao Paulo, 01/01/2026',
            flight_date=date(2026, 7, 3),
            work_support_team=True,
        )

    def test_reports_dashboard_shows_new_pdf_buttons(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('reports_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('reports_medical_pdf'))
        self.assertContains(response, reverse('reports_boat_passenger_pdf'))

    def test_reports_medical_pdf_downloads_full_personal_sheet(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('reports_medical_pdf'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn(b'FICHA MEDICA E INFORMACOES PESSOAIS', response.content)
        self.assertIn(self.volunteer.full_name.encode(), response.content)
        self.assertIn(b'Contato Teste', response.content)
        self.assertIn(b'Lactose', response.content)
        self.assertIn(b'03/07/2026', response.content)

    def test_reports_boat_passenger_pdf_downloads_name_and_cpf_list(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('reports_boat_passenger_pdf'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn(b'LISTA PARA COMPRA DAS PASSAGENS DO BARCO', response.content)
        self.assertIn(self.volunteer.full_name.encode(), response.content)
        self.assertIn(self.volunteer.cpf.encode(), response.content)
