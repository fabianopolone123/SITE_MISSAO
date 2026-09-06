from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import FinancialTransaction, PanelPermission


class FinancialTransactionEditTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.manager = User.objects.create_user(username='financeiro', password='senha-forte-123')
        PanelPermission.objects.create(user=self.manager, can_manage_financial=True)
        self.client.force_login(self.manager)

        self.expense = FinancialTransaction.objects.create(
            created_by=self.manager,
            transaction_type='saida',
            category='Alimentação',
            description='Marmitas da equipe',
            amount=Decimal('1234.56'),
            transaction_date=date(2026, 3, 10),
        )

    def test_statement_shows_edit_link_for_manual_transaction(self):
        response = self.client.get(reverse('financial_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'?editar={self.expense.pk}')

    def test_edit_view_opens_modal_prefilled_with_formatted_amount(self):
        response = self.client.get(reverse('financial_dashboard'), {'editar': self.expense.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['editing_transaction'], self.expense)
        self.assertContains(response, 'Salvar altera')
        self.assertContains(response, f'name="transaction_id" value="{self.expense.pk}"')
        # Valor volta no formato brasileiro que o campo money-input espera.
        self.assertEqual(response.context['form'].initial['amount'], '1.234,56')

    def test_post_with_transaction_id_updates_instead_of_creating(self):
        response = self.client.post(reverse('financial_dashboard'), {
            'transaction_id': self.expense.pk,
            'transaction_type': 'saida',
            'category': 'Transporte',
            'description': 'Combustivel da van',
            'amount': '1.500,00',
            'transaction_date': '2026-03-12',
        })

        self.assertRedirects(response, reverse('financial_dashboard'))
        self.assertEqual(FinancialTransaction.objects.count(), 1)

        self.expense.refresh_from_db()
        self.assertEqual(self.expense.category, 'Transporte')
        self.assertEqual(self.expense.description, 'Combustivel da van')
        self.assertEqual(self.expense.amount, Decimal('1500.00'))
        self.assertEqual(self.expense.transaction_date, date(2026, 3, 12))
        # Autor original preservado ao editar.
        self.assertEqual(self.expense.created_by, self.manager)

    def test_post_without_transaction_id_still_creates_new(self):
        response = self.client.post(reverse('financial_dashboard'), {
            'transaction_type': 'entrada',
            'category': 'Doação',
            'description': 'Doacao avulsa',
            'amount': '200,00',
            'transaction_date': '2026-03-15',
        })

        self.assertRedirects(response, reverse('financial_dashboard'))
        self.assertEqual(FinancialTransaction.objects.count(), 2)

    def test_edit_can_switch_type_and_category_recalculating_totals(self):
        self.client.post(reverse('financial_dashboard'), {
            'transaction_id': self.expense.pk,
            'transaction_type': 'entrada',
            'category': 'Doação',
            'description': 'Era despesa, virou doacao',
            'amount': '1.234,56',
            'transaction_date': '2026-03-10',
        })

        response = self.client.get(reverse('financial_dashboard'))
        self.assertEqual(response.context['total_expenses'], 0)
        self.assertEqual(response.context['donations_total'], Decimal('1234.56'))

    def test_editing_keeps_existing_receipt_when_no_new_file_sent(self):
        self.expense.receipt.name = 'comprovantes/nota.pdf'
        self.expense.save()

        self.client.post(reverse('financial_dashboard'), {
            'transaction_id': self.expense.pk,
            'transaction_type': 'saida',
            'category': 'Alimentação',
            'description': 'Marmitas da equipe',
            'amount': '1.234,56',
            'transaction_date': '2026-03-10',
        })

        self.expense.refresh_from_db()
        self.assertEqual(self.expense.receipt.name, 'comprovantes/nota.pdf')

    def test_user_without_financial_permission_cannot_edit(self):
        other = User.objects.create_user(username='semacesso', password='senha-forte-123')
        self.client.force_login(other)

        response = self.client.get(reverse('financial_dashboard'), {'editar': self.expense.pk})

        self.assertEqual(response.status_code, 302)
