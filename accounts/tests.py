import json
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    FinancialTransaction,
    MissionaryDonationReceipt,
    MissionaryPayment,
    PanelPermission,
    Registration,
    Volunteer,
    WhatsAppConfig,
    WhatsAppNotificationType,
    WhatsAppRecipientPreference,
    WhatsAppTemplate,
)


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
        'volunteers-0-wants_to_participate': volunteer.wants_to_participate or 'sim',
        'volunteers-0-understands_no_payment': volunteer.understands_no_payment or 'sim',
        'volunteers-0-aware_pays_tickets': volunteer.aware_pays_tickets or 'sim',
        'volunteers-0-aware_pays_project_fee': volunteer.aware_pays_project_fee or 'sim',
        'volunteers-0-aware_documents_vaccines': volunteer.aware_documents_vaccines or 'sim',
        'volunteers-0-aware_non_refundable_fee': volunteer.aware_non_refundable_fee or 'sim',
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

    def test_signup_questionnaire_starts_without_checked_options(self):
        response = self.client.get(reverse('signup'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="volunteers-0-wants_to_participate" value="sim" checked')
        self.assertNotContains(response, 'name="volunteers-0-understands_no_payment" value="sim" checked')

    def test_signup_renders_new_missionary_fields_and_current_date(self):
        response = self.client.get(reverse('signup'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Contato de emerg')
        self.assertContains(response, 'Possui alguma restri')
        self.assertContains(response, 'uso de fotos')
        self.assertContains(response, timezone.localdate().strftime('%d/%m/%Y'))


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
        self.assertFalse(permission.can_review_submissions)

    def test_permissions_dashboard_grants_reports_access(self):
        admin = User.objects.create_superuser(username='admin', password='senha-forte-123')
        user, _, _ = create_registration()
        self.client.force_login(admin)

        response = self.client.post(
            reverse('permissions_dashboard'),
            {
                'user_id': user.id,
                'is_staff': 'on',
                'can_view_reports': 'on',
            },
            follow=True,
        )

        user.refresh_from_db()
        permission = PanelPermission.objects.get(user=user)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(user.is_staff)
        self.assertTrue(permission.can_view_reports)
        self.assertFalse(permission.can_view_registrations)

    def test_permissions_dashboard_grants_whatsapp_access(self):
        admin = User.objects.create_superuser(username='admin', password='senha-forte-123')
        user, _, _ = create_registration()
        self.client.force_login(admin)

        response = self.client.post(
            reverse('permissions_dashboard'),
            {
                'user_id': user.id,
                'is_staff': 'on',
                'can_manage_whatsapp': 'on',
            },
            follow=True,
        )

        user.refresh_from_db()
        permission = PanelPermission.objects.get(user=user)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(user.is_staff)
        self.assertTrue(permission.can_manage_whatsapp)

    def test_reports_dashboard_requires_reports_permission(self):
        user, _, _ = create_registration()
        PanelPermission.objects.create(user=user, can_view_registrations=True)
        self.client.force_login(user)

        response = self.client.get(reverse('reports_dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_reports_dashboard_allows_reports_permission_without_registrations(self):
        user, _, _ = create_registration()
        PanelPermission.objects.create(user=user, can_view_reports=True)
        self.client.force_login(user)

        response = self.client.get(reverse('reports_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Relat')
        self.assertNotContains(response, 'href="/painel/"')

    def test_permissions_dashboard_grants_conference_access(self):
        admin = User.objects.create_superuser(username='admin', password='senha-forte-123')
        user, _, _ = create_registration()
        self.client.force_login(admin)

        response = self.client.post(
            reverse('permissions_dashboard'),
            {
                'user_id': user.id,
                'is_staff': 'on',
                'can_review_submissions': 'on',
            },
            follow=True,
        )

        user.refresh_from_db()
        permission = PanelPermission.objects.get(user=user)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(user.is_staff)
        self.assertTrue(permission.can_review_submissions)

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

    def test_volunteer_dashboard_does_not_render_documentation_section(self):
        user, _, _ = create_registration()
        self.client.force_login(user)

        response = self.client.get(reverse('volunteer_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('volunteer_documentation_dashboard'))
        self.assertNotContains(response, 'Baixe a ficha, assine pelo gov.br')
        self.assertNotContains(response, 'Documenta&ccedil;&atilde;o pendente')
        self.assertNotContains(response, 'Enviar documenta&ccedil;&atilde;o')

    def test_missionary_profile_menu_does_not_show_admin_sections(self):
        user, _, _ = create_registration()
        user.is_staff = True
        user.save(update_fields=['is_staff'])
        PanelPermission.objects.create(
            user=user,
            can_view_registrations=True,
            can_manage_financial=True,
            can_manage_permissions=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('volunteer_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Minha inscri&ccedil;&atilde;o')
        self.assertContains(response, reverse('volunteer_documentation_dashboard'))
        self.assertNotContains(response, '<a class="menu-item " href="/painel/">Inscritos</a>', html=True)
        self.assertNotContains(response, '<a class="menu-item " href="/painel/financeiro/">Financeiro</a>', html=True)
        self.assertNotContains(response, '<a class="menu-item " href="/painel/permissoes/">Permiss&otilde;es</a>', html=True)
        self.assertContains(response, reverse('volunteer_financial_dashboard'))

    def test_volunteer_documentation_dashboard_renders_documentation_controls(self):
        user, _, volunteer = create_registration()
        self.client.force_login(user)

        response = self.client.get(reverse('volunteer_documentation_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Documenta&ccedil;&atilde;o pendente')
        self.assertContains(response, reverse('volunteer_registration_pdf', args=[volunteer.id]))
        self.assertContains(response, reverse('volunteer_documentation_upload', args=[volunteer.id]))
        self.assertContains(response, 'name="vaccination_card_document"')
        self.assertContains(response, 'name="flight_ticket_document"')
        self.assertContains(response, 'name="flight_date"')
        self.assertContains(response, 'name="flight_time"')

    def test_conference_dashboard_requires_permission(self):
        user, _, _ = create_registration()
        self.client.force_login(user)

        response = self.client.get(reverse('conference_dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_conference_dashboard_lists_documents_and_receipts(self):
        reviewer, _, _ = create_registration(username='revisor')
        PanelPermission.objects.create(user=reviewer, can_review_submissions=True)
        _, _, volunteer = create_registration(username='missionario')
        volunteer.signed_registration_document = SimpleUploadedFile(
            'ficha.pdf',
            b'%PDF-1.4 ficha assinada',
            content_type='application/pdf',
        )
        volunteer.vaccination_card_document = SimpleUploadedFile(
            'vacina.pdf',
            b'%PDF-1.4 carteira vacinacao',
            content_type='application/pdf',
        )
        volunteer.save(update_fields=['signed_registration_document', 'vaccination_card_document'])
        MissionaryDonationReceipt.objects.create(
            volunteer=volunteer,
            description='Doacao extra',
            receipt=SimpleUploadedFile(
                'doacao.pdf',
                b'%PDF-1.4 doacao',
                content_type='application/pdf',
            ),
        )
        self.client.force_login(reviewer)

        response = self.client.get(reverse('conference_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Confer&ecirc;ncia')
        self.assertContains(response, volunteer.full_name)
        self.assertContains(response, 'Ver arquivo')
        self.assertContains(response, 'Carteira de vacina')
        self.assertContains(response, 'Ver comprovante')

    def test_conference_dashboard_lists_flight_ticket_information(self):
        reviewer, _, _ = create_registration(username='revisor')
        PanelPermission.objects.create(user=reviewer, can_review_submissions=True)
        _, _, volunteer = create_registration(username='missionario')
        volunteer.flight_ticket_document = SimpleUploadedFile(
            'passagem.pdf',
            b'%PDF-1.4 passagem',
            content_type='application/pdf',
        )
        volunteer.flight_date = date(2026, 7, 3)
        volunteer.flight_time = '12:30'
        volunteer.save(update_fields=['flight_ticket_document', 'flight_date', 'flight_time'])
        self.client.force_login(reviewer)

        response = self.client.get(reverse('conference_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Passagem a&eacute;rea')
        self.assertContains(response, '03/07/2026')
        self.assertContains(response, '12:30')
        self.assertContains(response, 'Ver passagem')

    def test_conference_dashboard_can_confirm_documentation_file(self):
        reviewer, _, _ = create_registration(username='revisor')
        PanelPermission.objects.create(user=reviewer, can_review_submissions=True)
        _, _, volunteer = create_registration(username='missionario')
        volunteer.signed_registration_document = SimpleUploadedFile(
            'ficha.pdf',
            b'%PDF-1.4 ficha assinada',
            content_type='application/pdf',
        )
        volunteer.save(update_fields=['signed_registration_document'])
        self.client.force_login(reviewer)

        response = self.client.post(
            reverse('conference_dashboard'),
            {
                'volunteer_id': volunteer.id,
                'document_type': 'signed_registration',
                'action': 'confirm',
            },
        )

        volunteer.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(volunteer.signed_registration_document_confirmed)
        self.assertEqual(volunteer.documentation_reviewed_by, reviewer)

    def test_conference_dashboard_can_confirm_vaccination_card(self):
        reviewer, _, _ = create_registration(username='revisor')
        PanelPermission.objects.create(user=reviewer, can_review_submissions=True)
        _, _, volunteer = create_registration(username='missionario')
        volunteer.vaccination_card_document = SimpleUploadedFile(
            'vacina.pdf',
            b'%PDF-1.4 carteira vacinacao',
            content_type='application/pdf',
        )
        volunteer.save(update_fields=['vaccination_card_document'])
        self.client.force_login(reviewer)

        response = self.client.post(
            reverse('conference_dashboard'),
            {
                'volunteer_id': volunteer.id,
                'document_type': 'vaccination_card',
                'action': 'confirm',
            },
        )

        volunteer.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(volunteer.vaccination_card_document_confirmed)
        self.assertEqual(volunteer.documentation_reviewed_by, reviewer)

    def test_conference_dashboard_can_confirm_optional_donation_receipt(self):
        reviewer, _, _ = create_registration(username='revisor')
        PanelPermission.objects.create(user=reviewer, can_review_submissions=True)
        _, _, volunteer = create_registration(username='missionario')
        donation = MissionaryDonationReceipt.objects.create(
            volunteer=volunteer,
            description='Doacao extra',
            receipt=SimpleUploadedFile(
                'doacao.pdf',
                b'%PDF-1.4 doacao',
                content_type='application/pdf',
            ),
        )
        self.client.force_login(reviewer)

        response = self.client.post(
            reverse('conference_dashboard'),
            {
                'donation_receipt_id': donation.id,
                'action': 'confirm',
            },
        )

        donation.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(donation.is_confirmed)
        self.assertEqual(donation.confirmed_by, reviewer)

    def test_volunteer_financial_dashboard_renders_pix_and_payment_fields(self):
        user, _, volunteer = create_registration()
        self.client.force_login(user)

        response = self.client.get(reverse('volunteer_financial_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '64.077.212/0001-50')
        self.assertContains(response, 'R$ 1.600,00')
        self.assertContains(response, 'R$ 450,00')
        self.assertContains(response, 'R$ 2.050,00')
        self.assertContains(response, 'Comprovantes de doa')
        self.assertContains(response, reverse('volunteer_donation_receipt_upload', args=[volunteer.id]))
        self.assertEqual(MissionaryPayment.objects.filter(volunteer=volunteer).count(), 2)

    def test_volunteer_can_upload_payment_receipt(self):
        user, _, volunteer = create_registration()
        self.client.force_login(user)
        self.client.get(reverse('volunteer_financial_dashboard'))
        payment = MissionaryPayment.objects.get(volunteer=volunteer, payment_type='participacao')

        response = self.client.post(
            reverse('volunteer_payment_upload', args=[payment.id]),
            {
                'receipt': SimpleUploadedFile(
                    'comprovante.pdf',
                    b'%PDF-1.4 comprovante',
                    content_type='application/pdf',
                ),
            },
        )

        payment.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(payment.has_receipt)
        self.assertFalse(payment.is_confirmed)

    def test_volunteer_can_upload_optional_donation_receipt(self):
        user, _, volunteer = create_registration()
        self.client.force_login(user)

        response = self.client.post(
            reverse('volunteer_donation_receipt_upload', args=[volunteer.id]),
            {
                'donation-%s-description' % volunteer.id: 'Doação extra',
                'donation-%s-amount' % volunteer.id: '125,50',
                'donation-%s-receipt' % volunteer.id: SimpleUploadedFile(
                    'doacao.pdf',
                    b'%PDF-1.4 doacao',
                    content_type='application/pdf',
                ),
            },
        )

        self.assertEqual(response.status_code, 302)
        donation = MissionaryDonationReceipt.objects.get(volunteer=volunteer)
        self.assertEqual(donation.description, 'Doação extra')
        self.assertEqual(str(donation.amount), '125.50')

    def test_admin_financial_dashboard_lists_confirmed_entries_by_category(self):
        admin = User.objects.create_superuser(username='admin', password='senha-forte-123')
        _, _, volunteer = create_registration()
        MissionaryPayment.objects.create(
            volunteer=volunteer,
            payment_type='participacao',
            amount='1600.00',
            receipt=SimpleUploadedFile(
                'comprovante.pdf',
                b'%PDF-1.4 comprovante',
                content_type='application/pdf',
            ),
            is_confirmed=True,
            confirmed_by=admin,
            confirmed_at=timezone.now(),
        )
        MissionaryDonationReceipt.objects.create(
            volunteer=volunteer,
            description='Doação extra',
            amount='125.50',
            receipt=SimpleUploadedFile(
                'doacao.pdf',
                b'%PDF-1.4 doacao',
                content_type='application/pdf',
            ),
            is_confirmed=True,
            confirmed_by=admin,
            confirmed_at=timezone.now(),
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('financial_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Doa')
        self.assertContains(response, 'Doação extra')
        self.assertContains(response, 'Inscri')
        self.assertContains(response, '1.600,00')
        self.assertContains(response, '125,50')
        self.assertContains(response, 'R$ 1.725,50')

    def test_admin_financial_dashboard_handles_confirmed_donation_without_receipt(self):
        admin = User.objects.create_superuser(username='admin', password='senha-forte-123')
        _, _, volunteer = create_registration()
        MissionaryDonationReceipt.objects.create(
            volunteer=volunteer,
            description='Doacao sem arquivo',
            amount='50.00',
            receipt='',
            is_confirmed=True,
            confirmed_by=admin,
            confirmed_at=timezone.now(),
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('financial_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Doacao sem arquivo')

    def test_admin_financial_dashboard_handles_manual_transaction_date(self):
        admin = User.objects.create_superuser(username='admin', password='senha-forte-123')
        FinancialTransaction.objects.create(
            transaction_type='entrada',
            category='Oferta',
            description='Entrada manual',
            amount='100.00',
            transaction_date=date(2026, 6, 11),
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('financial_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Entrada manual')
        self.assertContains(response, '11/06/2026')

    def test_admin_financial_dashboard_does_not_confirm_missionary_payment(self):
        admin = User.objects.create_superuser(username='admin', password='senha-forte-123')
        _, _, volunteer = create_registration()
        payment = MissionaryPayment.objects.create(
            volunteer=volunteer,
            payment_type='participacao',
            amount='1600.00',
            receipt=SimpleUploadedFile(
                'comprovante.pdf',
                b'%PDF-1.4 comprovante',
                content_type='application/pdf',
            ),
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse('financial_dashboard'),
            {
                'missionary_payment_id': payment.id,
                'action': 'confirm',
            },
        )

        payment.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(payment.is_confirmed)
        self.assertIsNone(payment.confirmed_by)

    def test_expense_registration_requires_specific_permission(self):
        user = User.objects.create_user(username='lancador', password='senha-forte-123')
        self.client.force_login(user)

        response = self.client.get(reverse('expense_registration_dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_expense_registration_lists_only_own_expenses_without_financial_statement(self):
        user = User.objects.create_user(username='lancador', password='senha-forte-123')
        other = User.objects.create_user(username='outro', password='senha-forte-123')
        PanelPermission.objects.create(user=user, can_register_expenses=True)
        FinancialTransaction.objects.create(
            created_by=user,
            transaction_type='saida',
            category='Transporte',
            description='Barco local',
            amount='120.00',
            transaction_date=date(2026, 6, 11),
        )
        FinancialTransaction.objects.create(
            created_by=other,
            transaction_type='saida',
            category='Alimentacao',
            description='Compra de outro usuario',
            amount='80.00',
            transaction_date=date(2026, 6, 12),
        )
        self.client.force_login(user)

        response = self.client.get(reverse('expense_registration_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Barco local')
        self.assertNotContains(response, 'Compra de outro usuario')
        self.assertNotContains(response, 'Extrato financeiro')
        self.assertNotContains(response, 'Entradas totais')

    def test_expense_registration_creates_and_edits_own_expense(self):
        user = User.objects.create_user(username='lancador', password='senha-forte-123')
        PanelPermission.objects.create(user=user, can_register_expenses=True)
        self.client.force_login(user)

        create_response = self.client.post(
            reverse('expense_registration_dashboard'),
            {
                'category': 'Transporte',
                'description': 'Combustivel',
                'amount': '150,50',
                'transaction_date': '2026-06-11',
            },
        )

        expense = FinancialTransaction.objects.get(created_by=user)
        self.assertEqual(create_response.status_code, 302)
        self.assertEqual(expense.transaction_type, 'saida')
        self.assertEqual(expense.description, 'Combustivel')
        self.assertEqual(str(expense.amount), '150.50')

        edit_response = self.client.post(
            reverse('expense_registration_dashboard'),
            {
                'transaction_id': expense.id,
                'category': 'Medicamento',
                'description': 'Remedios',
                'amount': '99,90',
                'transaction_date': '2026-06-12',
            },
        )

        expense.refresh_from_db()
        self.assertEqual(edit_response.status_code, 302)
        self.assertEqual(expense.category, 'Medicamento')
        self.assertEqual(expense.description, 'Remedios')
        self.assertEqual(str(expense.amount), '99.90')

    def test_whatsapp_dashboard_requires_permission(self):
        user = User.objects.create_user(username='semwhatsapp', password='senha-forte-123')
        self.client.force_login(user)

        response = self.client.get(reverse('whatsapp_dashboard'))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response['Location'])

    def test_whatsapp_dashboard_saves_configuration(self):
        user = User.objects.create_user(username='whatsapp', password='senha-forte-123')
        PanelPermission.objects.create(user=user, can_manage_whatsapp=True)
        self.client.force_login(user)

        response = self.client.post(
            reverse('whatsapp_dashboard'),
            {
                'action': 'save_config',
                'notifications_enabled': 'on',
                'provider': 'wapi',
                'group_jid': '120363421981424263@g.us',
                'default_message': 'Aviso da missao',
                'wapi_token': 'token-123',
                'wapi_instance': 'instance-01',
                'wapi_base_url': 'https://api.w-api.app/v1',
                'webhook_url': '',
                'webhook_token': '',
            },
        )

        config = WhatsAppConfig.get()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(config.notifications_enabled)
        self.assertEqual(config.provider, 'wapi')
        self.assertEqual(config.group_jid, '120363421981424263@g.us')

    def test_whatsapp_dashboard_saves_recipients_and_templates(self):
        admin = User.objects.create_user(username='whatsapp', password='senha-forte-123')
        target = User.objects.create_user(username='destino', password='senha-forte-123')
        PanelPermission.objects.create(user=admin, can_manage_whatsapp=True)
        self.client.force_login(admin)

        response = self.client.post(
            reverse('whatsapp_dashboard'),
            {
                'action': 'save_recipients_templates',
                f'user_{target.id}_phone': '(16) 99999-8888',
                f'user_{target.id}_registrations': 'on',
                f'user_{target.id}_general': 'on',
                'template_registrations': 'Inscricoes: {mensagem}',
                'template_financial': 'Financeiro: {mensagem}',
                'template_documentation': 'Documentacao: {mensagem}',
                'template_general': 'Geral: {mensagem}',
                'template_test': 'Teste: {usuario}',
            },
        )

        preference = WhatsAppRecipientPreference.objects.get(user=target)
        template = WhatsAppTemplate.objects.get(notification_type=WhatsAppNotificationType.GENERAL)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(preference.phone_number, '(16) 99999-8888')
        self.assertTrue(preference.notify_registrations)
        self.assertTrue(preference.notify_general)
        self.assertFalse(preference.notify_financial)
        self.assertEqual(template.message_text, 'Geral: {mensagem}')

    def test_whatsapp_dashboard_updates_legacy_documentation_template(self):
        user = User.objects.create_user(username='whatsapp', password='senha-forte-123')
        PanelPermission.objects.create(user=user, can_manage_whatsapp=True)
        template = WhatsAppTemplate.objects.create(
            notification_type=WhatsAppNotificationType.DOCUMENTATION,
            message_text='Atualização de documentação - Missão Andrews\nData/Hora: {data_hora}\nMensagem: {mensagem}',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('whatsapp_dashboard'))

        template.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIn('{missionario}', template.message_text)
        self.assertIn('{documentos_pendentes}', template.message_text)
        self.assertIn('{link_documentacao}', template.message_text)

    def test_whatsapp_dashboard_sends_manual_message_via_wapi(self):
        user = User.objects.create_user(username='whatsapp', password='senha-forte-123')
        target = User.objects.create_user(username='destino', password='senha-forte-123')
        PanelPermission.objects.create(user=user, can_manage_whatsapp=True)
        WhatsAppConfig.objects.create(
            notifications_enabled=True,
            provider='wapi',
            wapi_token='token-123',
            wapi_instance='instance-01',
            wapi_base_url='https://api.w-api.app/v1',
        )
        WhatsAppRecipientPreference.objects.create(
            user=target,
            phone_number='(16) 99999-8888',
            notify_general=True,
        )
        WhatsAppTemplate.objects.create(
            notification_type=WhatsAppNotificationType.GENERAL,
            message_text='Mensagem: {mensagem}',
        )
        self.client.force_login(user)

        class ResponseMock:
            status = 200

            def getcode(self):
                return 200

            def read(self):
                return json.dumps({'status': 'success', 'messageId': 'abc123'}).encode('utf-8')

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch('accounts.whatsapp.request.urlopen', return_value=ResponseMock()) as mocked_urlopen:
            response = self.client.post(
                reverse('whatsapp_dashboard'),
                {
                    'action': 'send_message',
                    'notification_type': WhatsAppNotificationType.GENERAL,
                    'message': 'Aviso importante da missao',
                },
            )

        request_obj = mocked_urlopen.call_args.args[0]
        payload = json.loads(request_obj.data.decode('utf-8'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('message/send-text?instanceId=instance-01', request_obj.full_url)
        self.assertEqual(payload['phone'], '5516999998888')
        self.assertEqual(payload['message'], 'Mensagem: Aviso importante da missao')

    def test_whatsapp_dashboard_shows_documentation_charge_button(self):
        user = User.objects.create_user(username='whatsapp', password='senha-forte-123')
        _, _, volunteer = create_registration(username='pendente')
        PanelPermission.objects.create(user=user, can_manage_whatsapp=True)
        self.client.force_login(user)

        response = self.client.get(reverse('whatsapp_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Cobrar documenta')
        self.assertContains(response, volunteer.full_name)
        self.assertContains(response, 'carteira de vacina')

    def test_whatsapp_dashboard_charges_pending_documentation_via_wapi(self):
        user = User.objects.create_user(username='whatsapp', password='senha-forte-123')
        _, _, volunteer = create_registration(username='pendente')
        volunteer.phone = '(16) 99999-8888'
        volunteer.save(update_fields=['phone'])
        PanelPermission.objects.create(user=user, can_manage_whatsapp=True)
        WhatsAppConfig.objects.create(
            notifications_enabled=True,
            provider='wapi',
            wapi_token='token-123',
            wapi_instance='instance-01',
            wapi_base_url='https://api.w-api.app/v1',
        )
        WhatsAppTemplate.objects.create(
            notification_type=WhatsAppNotificationType.DOCUMENTATION,
            message_text='Docs {missionario}: {documentos_pendentes}. {mensagem}',
        )
        self.client.force_login(user)

        class ResponseMock:
            status = 200

            def getcode(self):
                return 200

            def read(self):
                return json.dumps({'status': 'success', 'messageId': 'abc123'}).encode('utf-8')

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch('accounts.whatsapp.request.urlopen', return_value=ResponseMock()) as mocked_urlopen:
            response = self.client.post(
                reverse('whatsapp_dashboard'),
                {
                    'action': 'charge_documentation',
                    'volunteer_ids': [str(volunteer.id)],
                },
            )

        request_obj = mocked_urlopen.call_args.args[0]
        payload = json.loads(request_obj.data.decode('utf-8'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['phone'], '5516999998888')
        self.assertIn(volunteer.full_name, payload['message'])
        self.assertIn('carteira', payload['message'])
        self.assertContains(response, 'Resultado do envio')
        self.assertContains(response, 'Docs')

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
        self.assertIn(b'AMAZONAS SEM FRONTEIRAS 2026', response.content)
        self.assertIn(b'64.077.212/0001-50', response.content)
        self.assertIn(b'R$ 2.050,00', response.content)
        self.assertIn(volunteer.full_name.encode(), response.content)

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
                'vaccination_card_document': SimpleUploadedFile(
                    'vacina.pdf',
                    b'%PDF-1.4 carteira vacinacao',
                    content_type='application/pdf',
                ),
                'flight_ticket_document': SimpleUploadedFile(
                    'passagem.pdf',
                    b'%PDF-1.4 passagem',
                    content_type='application/pdf',
                ),
                'flight_date': '2026-07-03',
                'flight_time': '12:30',
            },
        )

        volunteer.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(volunteer.documentation_complete)
        self.assertTrue(volunteer.vaccination_card_document)
        self.assertTrue(volunteer.flight_ticket_document)
        self.assertEqual(volunteer.flight_date, date(2026, 7, 3))
        self.assertEqual(volunteer.flight_time.strftime('%H:%M'), '12:30')

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
