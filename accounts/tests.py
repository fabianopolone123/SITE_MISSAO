from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class SignupViewTests(TestCase):
    def test_signup_page_starts_with_one_volunteer_form(self):
        response = self.client.get(reverse('signup'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['formset'].forms), 1)
        self.assertContains(response, 'Volunt&aacute;rio 1')


class AdminDashboardTests(TestCase):
    def test_admin_dashboard_requires_staff_user(self):
        user = User.objects.create_user(username='voluntario', password='senha-forte-123')
        self.client.force_login(user)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])
