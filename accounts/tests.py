from datetime import date

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import PanelPermission, Registration, Volunteer


def create_registration(username='voluntario', password='senha-forte-123'):
    user = User.objects.create_user(username=username, password=password, email=f'{username}@example.com')
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
    )
    return user, registration, volunteer


def volunteer_post_data(volunteer, full_name):
    return {
        'volunteers-TOTAL_FORMS': '1',
        'volunteers-INITIAL_FORMS': '1',
        'volunteers-MIN_NUM_FORMS': '0',
        'volunteers-MAX_NUM_FORMS': '1000',
        'volunteers-0-id': str(volunteer.id),
        'volunteers-0-full_name': full_name,
        'volunteers-0-birth_date': volunteer.birth_date.strftime('%Y-%m-%d'),
        'volunteers-0-gender': volunteer.gender,
        'volunteers-0-full_address': volunteer.full_address,
        'volunteers-0-phone': volunteer.phone,
        'volunteers-0-email': volunteer.email,
        'volunteers-0-identity_document': volunteer.identity_document,
        'volunteers-0-cpf': volunteer.cpf,
        'volunteers-0-guardian_name': volunteer.guardian_name,
        'volunteers-0-guardian_phone': volunteer.guardian_phone,
        'volunteers-0-allergies': volunteer.allergies,
        'volunteers-0-medication_in_use': volunteer.medication_in_use,
        'volunteers-0-special_notes': volunteer.special_notes,
        'volunteers-0-education': volunteer.education,
        'volunteers-0-wants_to_participate': volunteer.wants_to_participate,
        'volunteers-0-understands_no_payment': volunteer.understands_no_payment,
        'volunteers-0-aware_pays_tickets': volunteer.aware_pays_tickets,
        'volunteers-0-aware_pays_project_fee': volunteer.aware_pays_project_fee,
        'volunteers-0-aware_documents_vaccines': volunteer.aware_documents_vaccines,
        'volunteers-0-aware_non_refundable_fee': volunteer.aware_non_refundable_fee,
        'volunteers-0-city_and_date': volunteer.city_and_date,
    }


def new_volunteer_post_data(full_name='Admin Missionario'):
    return {
        'volunteers-TOTAL_FORMS': '1',
        'volunteers-INITIAL_FORMS': '0',
        'volunteers-MIN_NUM_FORMS': '1',
        'volunteers-MAX_NUM_FORMS': '20',
        'volunteers-0-full_name': full_name,
        'volunteers-0-birth_date': '2000-01-01',
        'volunteers-0-gender': 'masculino',
        'volunteers-0-full_address': 'Rua Teste, 123',
        'volunteers-0-phone': '11999999999',
        'volunteers-0-email': 'admin@example.com',
        'volunteers-0-identity_document': '123456',
        'volunteers-0-cpf': '000.000.000-00',
        'volunteers-0-guardian_name': '',
        'volunteers-0-guardian_phone': '',
        'volunteers-0-allergies': '',
        'volunteers-0-medication_in_use': '',
        'volunteers-0-special_notes': '',
        'volunteers-0-education': '',
        'volunteers-0-wants_to_participate': 'sim',
        'volunteers-0-understands_no_payment': 'sim',
        'volunteers-0-aware_pays_tickets': 'sim',
        'volunteers-0-aware_pays_project_fee': 'sim',
        'volunteers-0-aware_documents_vaccines': 'sim',
        'volunteers-0-aware_non_refundable_fee': 'sim',
        'volunteers-0-city_and_date': 'Sao Paulo, 01/01/2026',
    }


class SignupViewTests(TestCase):
    def test_signup_page_starts_with_one_volunteer_form(self):
        response = self.client.get(reverse('signup'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['formset'].forms), 1)
        self.assertContains(response, 'Volunt&aacute;rio 1')


class AdminDashboardTests(TestCase):
    def test_admin_dashboard_requires_registration_permission(self):
        user = User.objects.create_user(username='voluntario', password='senha-forte-123')
        self.client.force_login(user)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_permissions_dashboard_grants_panel_access(self):
        admin = User.objects.create_superuser(username='admin', password='senha-forte-123')
        user, _, _ = create_registration()
        self.client.force_login(admin)

        response = self.client.post(
            reverse('permissions_dashboard'),
            {
                'user_id': user.id,
                'is_staff': 'on',
                'can_view_registrations': 'on',
                'can_manage_financial': 'on',
            },
            follow=True,
        )

        user.refresh_from_db()
        permission = PanelPermission.objects.get(user=user)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(user.is_staff)
        self.assertTrue(permission.can_view_registrations)
        self.assertTrue(permission.can_manage_financial)
        self.assertFalse(permission.can_manage_permissions)

    def test_permissions_dashboard_lists_users_without_existing_permission(self):
        admin = User.objects.create_superuser(username='admin', password='senha-forte-123')
        user, _, _ = create_registration()
        self.client.force_login(admin)

        response = self.client.get(reverse('permissions_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, user.username)

    def test_admin_dashboard_renders_volunteer_search_and_detail_modals(self):
        admin = User.objects.create_superuser(username='admin', password='senha-forte-123')
        _, registration, volunteer = create_registration()
        self.client.force_login(admin)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="volunteer-search"')
        self.assertContains(response, f'data-modal-target="registration-modal-{registration.id}"')
        self.assertContains(response, f'data-modal-target="volunteer-modal-{volunteer.id}"')
        self.assertContains(response, 'Mission&aacute;rios deste login')

    def test_admin_dashboard_shows_documentation_status(self):
        admin = User.objects.create_superuser(username='admin', password='senha-forte-123')
        _, _, volunteer = create_registration()
        self.client.force_login(admin)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'volunteer-modal-{volunteer.id}')
        self.assertContains(response, 'Status da documenta&ccedil;&atilde;o')

    def test_admin_user_can_switch_to_missionary_profile(self):
        user, _, _ = create_registration()
        user.is_staff = True
        user.save(update_fields=['is_staff'])
        PanelPermission.objects.create(user=user, can_view_registrations=True)
        self.client.force_login(user)

        response = self.client.get(reverse('admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Perfil mission&aacute;rio')
        self.assertContains(response, reverse('volunteer_dashboard'))


class VolunteerDashboardTests(TestCase):
    def test_admin_without_registration_can_open_missionary_profile_creation(self):
        admin = User.objects.create_superuser(username='admin', password='senha-forte-123')
        self.client.force_login(admin)

        response = self.client.get(reverse('volunteer_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Criar perfil mission&aacute;rio')
        self.assertEqual(len(response.context['formset'].forms), 1)

    def test_admin_without_registration_can_create_missionary_profile(self):
        admin = User.objects.create_superuser(username='admin', password='senha-forte-123')
        self.client.force_login(admin)

        response = self.client.post(reverse('volunteer_dashboard'), new_volunteer_post_data())

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Registration.objects.filter(user=admin).exists())
        self.assertTrue(Volunteer.objects.filter(registration__user=admin, full_name='Admin Missionario').exists())

    def test_volunteer_can_update_only_own_registration(self):
        user, _, volunteer = create_registration()
        _, _, other_volunteer = create_registration(username='outro')
        self.client.force_login(user)

        response = self.client.post(
            reverse('volunteer_dashboard'),
            volunteer_post_data(volunteer, 'Nome Atualizado'),
        )

        volunteer.refresh_from_db()
        other_volunteer.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(volunteer.full_name, 'Nome Atualizado')
        self.assertEqual(other_volunteer.full_name, 'outro Silva')

    def test_volunteer_cannot_submit_another_registration_volunteer_id(self):
        user, _, volunteer = create_registration()
        _, _, other_volunteer = create_registration(username='outro')
        self.client.force_login(user)

        data = volunteer_post_data(volunteer, 'Nome Indevido')
        data['volunteers-0-id'] = str(other_volunteer.id)
        response = self.client.post(reverse('volunteer_dashboard'), data)

        volunteer.refresh_from_db()
        other_volunteer.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(volunteer.full_name, 'voluntario Silva')
        self.assertEqual(other_volunteer.full_name, 'outro Silva')

    def test_volunteer_dashboard_renders_documentation_controls(self):
        user, _, volunteer = create_registration()
        self.client.force_login(user)

        response = self.client.get(reverse('volunteer_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Documenta&ccedil;&atilde;o')
        self.assertContains(response, reverse('volunteer_registration_pdf', args=[volunteer.id]))
        self.assertContains(response, reverse('volunteer_documentation_upload', args=[volunteer.id]))

    def test_admin_user_can_switch_back_to_admin_panel_from_missionary_profile(self):
        user, _, _ = create_registration()
        user.is_staff = True
        user.save(update_fields=['is_staff'])
        PanelPermission.objects.create(user=user, can_view_registrations=True)
        self.client.force_login(user)

        response = self.client.get(reverse('volunteer_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Painel ADM')
        self.assertContains(response, reverse('admin_dashboard'))

    def test_volunteer_can_download_own_registration_pdf(self):
        user, _, volunteer = create_registration()
        self.client.force_login(user)

        response = self.client.get(reverse('volunteer_registration_pdf', args=[volunteer.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_volunteer_can_upload_documentation_files(self):
        user, _, volunteer = create_registration()
        self.client.force_login(user)

        response = self.client.post(
            reverse('volunteer_documentation_upload', args=[volunteer.id]),
            {
                'signed_registration_document': SimpleUploadedFile(
                    'ficha.pdf',
                    b'%PDF-1.4 ficha assinada',
                    content_type='application/pdf',
                ),
                'insurance_policy_document': SimpleUploadedFile(
                    'apolice.pdf',
                    b'%PDF-1.4 apolice assinada',
                    content_type='application/pdf',
                ),
            },
        )

        volunteer.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(volunteer.documentation_complete)

    def test_volunteer_cannot_upload_documentation_for_another_user(self):
        user, _, _ = create_registration()
        _, _, other_volunteer = create_registration(username='outro')
        self.client.force_login(user)

        response = self.client.post(
            reverse('volunteer_documentation_upload', args=[other_volunteer.id]),
            {
                'signed_registration_document': SimpleUploadedFile(
                    'ficha.pdf',
                    b'%PDF-1.4 ficha assinada',
                    content_type='application/pdf',
                ),
            },
        )

        other_volunteer.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertFalse(other_volunteer.signed_registration_document)
