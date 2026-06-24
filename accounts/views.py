import json
import logging
import time
from datetime import date

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.forms import formset_factory, modelformset_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .forms import (
    ExpenseRegistrationForm,
    FinancialTransactionForm,
    MissionaryDonationReceiptForm,
    MissionaryPaymentReceiptForm,
    PanelPermissionForm,
    SignUpForm,
    VolunteerDocumentationForm,
    VolunteerForm,
    WhatsAppConfigForm,
    WhatsAppMessageForm,
)
from .models import (
    EXPENSE_CATEGORIES,
    INCOME_CATEGORIES,
    FinancialTransaction,
    MISSIONARY_PAYMENT_AMOUNTS,
    MISSIONARY_PAYMENT_TYPES,
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
from .pdf import build_prestacao_contas_pdf, build_registration_pdf
from . import whatsapp

logger = logging.getLogger(__name__)


def _auto_notify(notification_type, message, extra_payload=None):
    try:
        payload = {
            **whatsapp.template_context(sent_by='sistema', message=message),
            **(extra_payload or {}),
        }
        whatsapp.send_template_notification(notification_type, payload=payload, sent_by='sistema')
    except Exception:
        logger.exception('Erro na notificacao automatica WhatsApp tipo %s', notification_type)


PANEL_PERMISSION_FIELDS = {
    'registrations': 'can_view_registrations',
    'reports': 'can_view_reports',
    'financial': 'can_manage_financial',
    'expense_registration': 'can_register_expenses',
    'whatsapp': 'can_manage_whatsapp',
    'permissions': 'can_manage_permissions',
    'conference': 'can_review_submissions',
}

MISSION_PAYMENT_PIX_KEY = '64.077.212/0001-50'
MISSION_PAYMENT_BANK_INFO = {
    'nome': 'Missão Andrews',
    'banco': 'Bradesco',
    'agencia': '2403',
    'conta_corrente': '58653-6',
    'pix': MISSION_PAYMENT_PIX_KEY,
}


def format_brl(amount):
    value = f'{amount or 0:,.2f}'
    return value.replace(',', 'X').replace('.', ',').replace('X', '.')


def get_panel_permissions(user):
    permissions = {
        'can_view_registrations': False,
        'can_view_reports': False,
        'can_manage_financial': False,
        'can_register_expenses': False,
        'can_manage_whatsapp': False,
        'can_manage_permissions': False,
        'can_review_submissions': False,
    }

    if not user.is_authenticated:
        return permissions

    if user.is_superuser:
        return {key: True for key in permissions}

    panel_permission = getattr(user, 'panel_permission', None)
    if panel_permission is None:
        return permissions

    for key in permissions:
        permissions[key] = getattr(panel_permission, key)

    return permissions


def has_panel_permission(user, permission_key):
    if not user.is_authenticated:
        return False

    field_name = PANEL_PERMISSION_FIELDS[permission_key]
    return get_panel_permissions(user)[field_name]


def can_view_registrations(user):
    return has_panel_permission(user, 'registrations')


def can_view_reports(user):
    return has_panel_permission(user, 'reports')


def can_manage_financial(user):
    return has_panel_permission(user, 'financial')


def can_register_expenses(user):
    return has_panel_permission(user, 'expense_registration')


def can_manage_whatsapp(user):
    return has_panel_permission(user, 'whatsapp')


def can_manage_permissions(user):
    return has_panel_permission(user, 'permissions')


def can_review_submissions(user):
    return has_panel_permission(user, 'conference')


def can_view_volunteer(user, volunteer):
    if not user.is_authenticated:
        return False
    return volunteer.registration.user_id == user.id or can_view_registrations(user)


def first_available_panel_url(user):
    if has_panel_permission(user, 'registrations'):
        return 'admin_dashboard'
    if has_panel_permission(user, 'reports'):
        return 'reports_dashboard'
    if has_panel_permission(user, 'financial'):
        return 'financial_dashboard'
    if has_panel_permission(user, 'expense_registration'):
        return 'expense_registration_dashboard'
    if has_panel_permission(user, 'whatsapp'):
        return 'whatsapp_dashboard'
    if has_panel_permission(user, 'permissions'):
        return 'permissions_dashboard'
    if has_panel_permission(user, 'conference'):
        return 'conference_dashboard'
    return 'volunteer_dashboard'


def ensure_missionary_payments(volunteer):
    payments = []

    for payment_type, _ in MISSIONARY_PAYMENT_TYPES:
        payment, _ = MissionaryPayment.objects.get_or_create(
            volunteer=volunteer,
            payment_type=payment_type,
            defaults={'amount': MISSIONARY_PAYMENT_AMOUNTS[payment_type]},
        )
        payments.append(payment)

    return payments


class SmartLoginView(LoginView):
    template_name = 'registration/login.html'

    def get_success_url(self):
        try:
            if self.request.user.registration.force_password_change:
                return '/trocar-senha/'
        except Exception:
            pass
        return super().get_success_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['logged_redirect_url'] = first_available_panel_url(self.request.user)
        return context


def signup(request):
    VolunteerFormSet = formset_factory(VolunteerForm, extra=0, min_num=1, validate_min=True, max_num=20)

    if request.method == 'POST':
        user_form = SignUpForm(request.POST)
        formset = VolunteerFormSet(request.POST, prefix='volunteers')

        if user_form.is_valid() and formset.is_valid():
            user = user_form.save(commit=False)
            user.email = user_form.cleaned_data['email']
            user.save()
            registration = Registration.objects.create(user=user)

            saved_volunteers = []
            for form in formset:
                volunteer = form.save(commit=False)
                volunteer.registration = registration
                volunteer.save()
                saved_volunteers.append(volunteer.full_name)

            _auto_notify(
                WhatsAppNotificationType.REGISTRATIONS,
                f'Nova inscrição realizada!\nMissionário(s): {", ".join(saved_volunteers)}\nTotal de inscritos: {Volunteer.objects.count()}',
            )
            login(request, user)
            return redirect('signup_success')
    else:
        user_form = SignUpForm()
        formset = VolunteerFormSet(prefix='volunteers')

    return render(
        request,
        'registration/signup.html',
        {
            'user_form': user_form,
            'formset': formset,
        },
    )


def signup_success(request):
    return render(request, 'registration/signup_success.html')


@login_required(login_url='login')
def volunteer_dashboard(request):
    try:
        registration = request.user.registration
    except Registration.DoesNotExist:
        registration = None

    if registration is None:
        VolunteerFormSet = formset_factory(VolunteerForm, extra=0, min_num=1, validate_min=True, max_num=20)

        if request.method == 'POST':
            formset = VolunteerFormSet(request.POST, prefix='volunteers')

            if formset.is_valid():
                with transaction.atomic():
                    registration = Registration.objects.create(user=request.user)

                    new_names = []
                    for form in formset:
                        volunteer = form.save(commit=False)
                        volunteer.registration = registration
                        volunteer.save()
                        new_names.append(volunteer.full_name)

                _auto_notify(
                    WhatsAppNotificationType.REGISTRATIONS,
                    f'Novo perfil missionário criado!\nMissionário(s): {", ".join(new_names)}\nTotal de inscritos: {Volunteer.objects.count()}',
                )
                messages.success(request, 'Perfil missionário criado com sucesso.')
                return redirect('volunteer_dashboard')
        else:
            formset = VolunteerFormSet(prefix='volunteers')

        return render(
            request,
            'registration/volunteer_dashboard.html',
            {
                'registration': registration,
                'formset': formset,
                'panel_permissions': get_panel_permissions(request.user),
                'active_menu': 'volunteer',
                'is_creating_missionary_profile': True,
            },
        )

    VolunteerFormSet = modelformset_factory(Volunteer, form=VolunteerForm, extra=0)
    queryset = registration.volunteers.order_by('created_at')

    if request.method == 'POST':
        formset = VolunteerFormSet(request.POST, queryset=queryset, prefix='volunteers')

        if formset.is_valid():
            allowed_volunteer_ids = set(queryset.values_list('id', flat=True))
            submitted_volunteer_ids = {
                form.cleaned_data['id'].id
                for form in formset.forms
                if form.cleaned_data.get('id')
            }

            if not submitted_volunteer_ids.issubset(allowed_volunteer_ids):
                messages.error(request, 'Não foi possível atualizar um cadastro de outro usuário.')
            else:
                formset.save()
                _auto_notify(
                    WhatsAppNotificationType.REGISTRATIONS,
                    f'Cadastro atualizado por {request.user.get_full_name() or request.user.username}.',
                )
                messages.success(request, 'Dados atualizados com sucesso.')
                return redirect('volunteer_dashboard')
    else:
        formset = VolunteerFormSet(queryset=queryset, prefix='volunteers')

    return render(
        request,
        'registration/volunteer_dashboard.html',
        {
            'registration': registration,
            'formset': formset,
            'panel_permissions': get_panel_permissions(request.user),
            'active_menu': 'volunteer',
            'is_creating_missionary_profile': False,
        },
    )


@login_required(login_url='login')
def volunteer_documentation_dashboard(request):
    try:
        registration = request.user.registration
    except Registration.DoesNotExist:
        messages.error(request, 'Crie seu perfil missionário antes de enviar documentos.')
        return redirect('volunteer_dashboard')

    return render(
        request,
        'registration/volunteer_documentation.html',
        {
            'registration': registration,
            'panel_permissions': get_panel_permissions(request.user),
            'active_menu': 'documentation',
        },
    )


@login_required(login_url='login')
def volunteer_financial_dashboard(request):
    try:
        registration = request.user.registration
    except Registration.DoesNotExist:
        messages.error(request, 'Crie seu perfil missionário antes de enviar comprovantes.')
        return redirect('volunteer_dashboard')

    volunteers = registration.volunteers.order_by('created_at')
    payment_groups = []

    for volunteer in volunteers:
        payment_groups.append({
            'volunteer': volunteer,
            'payments': ensure_missionary_payments(volunteer),
            'donation_receipts': volunteer.donation_receipts.all(),
            'donation_form': MissionaryDonationReceiptForm(prefix=f'donation-{volunteer.id}'),
        })

    return render(
        request,
        'registration/volunteer_financial.html',
        {
            'registration': registration,
            'payment_groups': payment_groups,
            'panel_permissions': get_panel_permissions(request.user),
            'active_menu': 'missionary_financial',
            'bank_info': MISSION_PAYMENT_BANK_INFO,
            'total_amount': '2.050,00',
        },
    )


@login_required(login_url='login')
@require_POST
def volunteer_payment_upload(request, payment_id):
    payment = get_object_or_404(
        MissionaryPayment.objects.select_related('volunteer__registration__user'),
        pk=payment_id,
        volunteer__registration__user=request.user,
    )
    form = MissionaryPaymentReceiptForm(request.POST, request.FILES, instance=payment)

    if form.is_valid():
        payment = form.save(commit=False)
        payment.submitted_at = timezone.now()
        payment.is_confirmed = False
        payment.confirmed_by = None
        payment.confirmed_at = None
        payment.save()
        _auto_notify(
            WhatsAppNotificationType.FINANCIAL,
            f'Comprovante enviado!\nTipo: {payment.get_payment_type_display()}\nMissionário: {payment.volunteer.full_name}\nAguarda conferência.',
        )
        messages.success(request, f'Comprovante de {payment.get_payment_type_display()} enviado.')
    else:
        messages.error(request, f'Não foi possível enviar o comprovante de {payment.get_payment_type_display()}.')

    return redirect('volunteer_financial_dashboard')


@login_required(login_url='login')
@require_POST
def volunteer_donation_receipt_upload(request, volunteer_id):
    volunteer = get_object_or_404(
        Volunteer.objects.select_related('registration__user'),
        pk=volunteer_id,
        registration__user=request.user,
    )
    form = MissionaryDonationReceiptForm(
        request.POST,
        request.FILES,
        prefix=f'donation-{volunteer.id}',
    )

    if form.is_valid():
        donation_receipt = form.save(commit=False)
        donation_receipt.volunteer = volunteer
        donation_receipt.save()
        _auto_notify(
            WhatsAppNotificationType.FINANCIAL,
            f'Comprovante de doação enviado!\nMissionário: {donation_receipt.volunteer.full_name}\nAguarda conferência.',
        )
        messages.success(request, 'Comprovante de doação enviado.')
    else:
        messages.error(request, 'Não foi possível enviar o comprovante de doação.')

    return redirect('volunteer_financial_dashboard')


@login_required(login_url='login')
def volunteer_registration_pdf(request, volunteer_id):
    volunteer = get_object_or_404(
        Volunteer.objects.select_related('registration__user'),
        pk=volunteer_id,
    )

    if not can_view_volunteer(request.user, volunteer):
        return redirect('login')

    filename = f'ficha-inscricao-{slugify(volunteer.full_name)}.pdf'
    response = HttpResponse(build_registration_pdf(volunteer), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required(login_url='login')
@require_POST
def volunteer_documentation_upload(request, volunteer_id):
    volunteer = get_object_or_404(
        Volunteer.objects.select_related('registration__user'),
        pk=volunteer_id,
        registration__user=request.user,
    )
    form = VolunteerDocumentationForm(request.POST, request.FILES, instance=volunteer)

    if form.is_valid():
        volunteer = form.save(commit=False)

        if 'signed_registration_document' in request.FILES:
            volunteer.signed_registration_document_confirmed = False

        if 'insurance_policy_document' in request.FILES:
            volunteer.insurance_policy_document_confirmed = False

        if 'vaccination_card_document' in request.FILES:
            volunteer.vaccination_card_document_confirmed = False

        if (
            'signed_registration_document' in request.FILES
            or 'insurance_policy_document' in request.FILES
            or 'vaccination_card_document' in request.FILES
        ):
            volunteer.documentation_reviewed_by = None
            volunteer.documentation_reviewed_at = None

        volunteer.save()
        uploaded_docs = []
        if 'signed_registration_document' in request.FILES:
            uploaded_docs.append('Formulário assinado')
        if 'insurance_policy_document' in request.FILES:
            uploaded_docs.append('Apólice de seguro')
        if 'vaccination_card_document' in request.FILES:
            uploaded_docs.append('Carteira de vacinação')
        if uploaded_docs:
            docs_str = ', '.join(uploaded_docs)
            _auto_notify(
                WhatsAppNotificationType.DOCUMENTATION,
                f'Documento(s) enviado(s): {docs_str}',
                extra_payload={
                    'missionario': volunteer.full_name,
                    'documentos_pendentes': docs_str,
                },
            )
        messages.success(request, f'Documentação de {volunteer.full_name} atualizada.')
    else:
        messages.error(request, f'Não foi possível atualizar a documentação de {volunteer.full_name}.')

    return redirect('volunteer_dashboard')


@user_passes_test(can_view_registrations, login_url='login')
def admin_dashboard(request):
    registrations = (
        Registration.objects
        .select_related('user')
        .prefetch_related('volunteers')
        .order_by('-created_at')
    )
    volunteers = Volunteer.objects.select_related('registration__user').order_by('-created_at')

    context = {
        'registration_count': registrations.count(),
        'volunteer_count': volunteers.count(),
        'health_count': volunteers.filter(work_health=True).count(),
        'education_count': volunteers.filter(work_education=True).count(),
        'general_help_count': volunteers.filter(work_general_help=True).count(),
        'evangelism_count': volunteers.filter(work_evangelism=True).count(),
        'registrations': registrations.annotate(total_volunteers=Count('volunteers')),
        'volunteers': volunteers,
        'gender_summary': volunteers.values('gender').annotate(total=Count('id')).order_by('gender'),
        'panel_permissions': get_panel_permissions(request.user),
        'active_menu': 'registrations',
        'pending_questionnaire_count': volunteers.filter(
            Q(wants_to_participate='nao')
            | Q(understands_no_payment='nao')
            | Q(aware_pays_tickets='nao')
            | Q(aware_pays_project_fee='nao')
            | Q(aware_documents_vaccines='nao')
            | Q(aware_non_refundable_fee='nao')
        ).count(),
    }
    return render(request, 'registration/admin_dashboard.html', context)


@user_passes_test(can_manage_financial, login_url='login')
def financial_dashboard(request):
    if request.method == 'POST':
        form = FinancialTransactionForm(request.POST, request.FILES)

        if form.is_valid():
            financial_transaction = form.save(commit=False)
            financial_transaction.created_by = request.user
            financial_transaction.save()
            _auto_notify(
                WhatsAppNotificationType.FINANCIAL,
                f'Novo lançamento financeiro!\nTipo: {financial_transaction.get_transaction_type_display()}\nCategoria: {financial_transaction.category}\nValor: R$ {financial_transaction.amount}',
            )
            messages.success(request, 'Lançamento financeiro cadastrado com sucesso.')
            return redirect('financial_dashboard')
    else:
        form = FinancialTransactionForm()

    transactions = FinancialTransaction.objects.all()
    confirmed_missionary_payments = (
        MissionaryPayment.objects
        .select_related('volunteer', 'volunteer__registration__user', 'confirmed_by')
        .filter(receipt__gt='', is_confirmed=True)
        .order_by('-confirmed_at', 'volunteer__full_name')
    )
    confirmed_donation_receipts = (
        MissionaryDonationReceipt.objects
        .select_related('volunteer', 'volunteer__registration__user', 'confirmed_by')
        .filter(is_confirmed=True)
        .order_by('-confirmed_at', '-submitted_at', 'volunteer__full_name')
    )
    manual_income = transactions.filter(transaction_type='entrada').aggregate(total=Sum('amount'))['total'] or 0
    total_expenses = transactions.filter(transaction_type='saida').aggregate(total=Sum('amount'))['total'] or 0
    participation_total = confirmed_missionary_payments.filter(payment_type='participacao').aggregate(total=Sum('amount'))['total'] or 0
    baskets_total = confirmed_missionary_payments.filter(payment_type='cestas').aggregate(total=Sum('amount'))['total'] or 0
    donations_total = confirmed_donation_receipts.aggregate(total=Sum('amount'))['total'] or 0
    total_income = manual_income + participation_total + baskets_total + donations_total
    balance = total_income - total_expenses
    statement_entries = []

    for entry in transactions:
        signed_amount = entry.amount if entry.transaction_type == 'entrada' else -entry.amount
        statement_entries.append({
            'date': entry.transaction_date,
            'date_format': 'd/m/Y',
            'type': entry.get_transaction_type_display(),
            'category': entry.category,
            'description': entry.description,
            'amount': signed_amount,
            'amount_brl': format_brl(entry.amount),
            'receipt': entry.receipt,
        })

    for payment in confirmed_missionary_payments:
        category = 'Inscrição' if payment.payment_type == 'participacao' else 'Cestas básicas'
        statement_entries.append({
            'date': payment.confirmed_at or payment.submitted_at,
            'date_format': 'd/m/Y H:i',
            'type': 'Entrada',
            'category': category,
            'description': f'{category} - {payment.volunteer.full_name}',
            'amount': payment.amount,
            'amount_brl': payment.amount_brl,
            'receipt': payment.receipt,
        })

    for donation in confirmed_donation_receipts:
        statement_entries.append({
            'date': donation.confirmed_at or donation.submitted_at,
            'date_format': 'd/m/Y H:i',
            'type': 'Entrada',
            'category': 'Doação',
            'description': f'{donation.description or "Doação opcional"} - {donation.volunteer.full_name}',
            'amount': donation.amount,
            'amount_brl': donation.amount_brl,
            'receipt': donation.receipt,
        })

    statement_entries.sort(key=lambda entry: str(entry['date']), reverse=True)

    expense_by_category = list(
        transactions
        .filter(transaction_type='saida')
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    for item in expense_by_category:
        item['total_brl'] = format_brl(item['total'])
        item['percent'] = round(float(item['total']) / float(total_expenses) * 100, 1) if total_expenses else 0

    context = {
        'form': form,
        'transactions': transactions,
        'total_income': total_income,
        'total_income_brl': format_brl(total_income),
        'total_expenses': total_expenses,
        'total_expenses_brl': format_brl(total_expenses),
        'balance': balance,
        'balance_brl': format_brl(balance),
        'expense_count': transactions.filter(transaction_type='saida').count(),
        'receipt_count': transactions.exclude(receipt='').count(),
        'manual_income': manual_income,
        'manual_income_brl': format_brl(manual_income),
        'participation_total': participation_total,
        'participation_total_brl': format_brl(participation_total),
        'baskets_total': baskets_total,
        'baskets_total_brl': format_brl(baskets_total),
        'donations_total': donations_total,
        'donations_total_brl': format_brl(donations_total),
        'confirmed_missionary_payments': confirmed_missionary_payments,
        'confirmed_donation_receipts': confirmed_donation_receipts,
        'statement_entries': statement_entries,
        'expense_by_category': expense_by_category,
        'expense_categories_json': json.dumps(EXPENSE_CATEGORIES, ensure_ascii=False),
        'income_categories_json': json.dumps(INCOME_CATEGORIES, ensure_ascii=False),
        'panel_permissions': get_panel_permissions(request.user),
        'active_menu': 'financial',
    }
    return render(request, 'registration/financial_dashboard.html', context)


@user_passes_test(can_register_expenses, login_url='login')
def expense_registration_dashboard(request):
    editing_transaction = None
    edit_id = request.GET.get('editar')

    if edit_id:
        editing_transaction = get_object_or_404(
            FinancialTransaction,
            pk=edit_id,
            created_by=request.user,
            transaction_type='saida',
        )

    if request.method == 'POST':
        transaction_id = request.POST.get('transaction_id')

        if transaction_id:
            editing_transaction = get_object_or_404(
                FinancialTransaction,
                pk=transaction_id,
                created_by=request.user,
                transaction_type='saida',
            )

        form = ExpenseRegistrationForm(request.POST, request.FILES, instance=editing_transaction)

        if form.is_valid():
            expense = form.save(commit=False)
            expense.transaction_type = 'saida'
            expense.created_by = request.user
            expense.save()
            action_label = 'atualizada' if transaction_id else 'registrada'
            _auto_notify(
                WhatsAppNotificationType.FINANCIAL,
                f'Despesa {action_label}!\nCategoria: {expense.category}\nValor: R$ {expense.amount}\nPor: {request.user.get_full_name() or request.user.username}',
            )
            messages.success(request, 'Despesa registrada com sucesso.' if not transaction_id else 'Despesa atualizada com sucesso.')
            return redirect('expense_registration_dashboard')
    else:
        form = ExpenseRegistrationForm(instance=editing_transaction)

    transactions = (
        FinancialTransaction.objects
        .filter(created_by=request.user, transaction_type='saida')
        .order_by('-transaction_date', '-created_at')
    )

    context = {
        'form': form,
        'transactions': transactions,
        'editing_transaction': editing_transaction,
        'expense_categories_json': json.dumps(EXPENSE_CATEGORIES, ensure_ascii=False),
        'panel_permissions': get_panel_permissions(request.user),
        'active_menu': 'expense_registration',
    }
    return render(request, 'registration/expense_registration_dashboard.html', context)


def volunteer_pending_documentation_items(volunteer):
    items = []
    if not volunteer.signed_registration_document:
        items.append('ficha assinada')
    if not volunteer.insurance_policy_document:
        items.append('apólice de seguro')
    if not volunteer.vaccination_card_document:
        items.append('carteira de vacinação')
    return items


def send_documentation_charge(request, volunteer, charge_template_text, sent_by):
    pending_items = volunteer_pending_documentation_items(volunteer)
    if not pending_items:
        return {
            'volunteer': volunteer.full_name,
            'ok': False,
            'error_message': 'Missionário sem documentação pendente.',
            'phone': whatsapp.normalize_phone_number(volunteer.phone) or volunteer.phone,
            'message': '',
        }

    payload = {
        **whatsapp.template_context(sent_by=sent_by),
        'missionario': volunteer.full_name,
        'documentos_pendentes': ', '.join(pending_items),
        'link_documentacao': request.build_absolute_uri('/minha-inscricao/documentacao/'),
    }
    message_text = whatsapp.render_message(charge_template_text, payload)
    normalized_phone = whatsapp.normalize_phone_number(volunteer.phone)
    if normalized_phone:
        ok, error_message = whatsapp.send_message_to_phone(normalized_phone, message_text, sent_by=sent_by)
    else:
        ok = False
        error_message = 'Telefone inválido ou ausente.'

    return {
        'volunteer': volunteer.full_name,
        'ok': ok,
        'error_message': error_message,
        'phone': normalized_phone or volunteer.phone,
        'message': message_text,
    }


@user_passes_test(can_manage_whatsapp, login_url='login')
def whatsapp_dashboard(request):
    config = WhatsAppConfig.get()
    whatsapp.ensure_default_templates()
    config_form = WhatsAppConfigForm(instance=config)
    initial_message = config.default_message or 'Olá! Esta é uma notificação da Missão Andrews.'
    message_form = WhatsAppMessageForm(initial={'message': initial_message})
    selected_notification_type = request.POST.get('notification_type') or WhatsAppNotificationType.GENERAL
    default_charge_delay_seconds = max(0.0, float(getattr(settings, 'WHATSAPP_DOCUMENTATION_SEND_DELAY_SECONDS', 2) or 0))
    charge_template_text = whatsapp.get_template_message(WhatsAppNotificationType.DOCUMENTATION)
    charge_delay_seconds = default_charge_delay_seconds
    charge_results = []
    charge_message_sent = ''
    open_charge_modal = False

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_config':
            config_form = WhatsAppConfigForm(request.POST, instance=config)
            if config_form.is_valid():
                config_form.save()
                messages.success(request, 'Configurações de WhatsApp salvas com sucesso.')
                return redirect('whatsapp_dashboard')
            message_form = WhatsAppMessageForm(initial={'message': request.POST.get('default_message') or initial_message})

        elif action == 'save_recipients_templates':
            for user in User.objects.filter(is_active=True):
                preference, _ = WhatsAppRecipientPreference.objects.get_or_create(user=user)
                prefix = f'user_{user.id}'
                preference.phone_number = request.POST.get(f'{prefix}_phone', '').strip()
                preference.notify_registrations = request.POST.get(f'{prefix}_registrations') == 'on'
                preference.notify_financial = request.POST.get(f'{prefix}_financial') == 'on'
                preference.notify_documentation = request.POST.get(f'{prefix}_documentation') == 'on'
                preference.notify_general = request.POST.get(f'{prefix}_general') == 'on'
                preference.notify_test = request.POST.get(f'{prefix}_test') == 'on'
                preference.save()

            for notification_type, _label in WhatsAppNotificationType.choices:
                WhatsAppTemplate.objects.update_or_create(
                    notification_type=notification_type,
                    defaults={'message_text': request.POST.get(f'template_{notification_type}', '').strip()},
                )

            messages.success(request, 'Destinatários e templates salvos com sucesso.')
            return redirect('whatsapp_dashboard')

        elif action == 'send_message':
            message_form = WhatsAppMessageForm(request.POST)
            if message_form.is_valid():
                sent_by = request.user.get_full_name() or request.user.username
                payload = whatsapp.template_context(sent_by=sent_by, message=message_form.cleaned_data['message'])
                results, _message = whatsapp.send_template_notification(selected_notification_type, payload=payload, sent_by=sent_by)
                sent_count = sum(1 for _user, ok, _error_message in results if ok)
                failed_count = sum(1 for _user, ok, _error_message in results if not ok)
                error_message = 'Nenhum destinatário marcado para este tipo de notificação.'
                if failed_count:
                    error_message = '; '.join(f'{user.username}: {message}' for user, _ok, message in results[:4])
                if sent_count:
                    messages.success(request, 'Notificação enviada com sucesso para o WhatsApp.')
                    return redirect('whatsapp_dashboard')
                messages.error(request, f'Falha ao enviar notificação: {error_message}')

        elif action == 'send_test':
            sent_by = request.user.get_full_name() or request.user.username
            payload = whatsapp.template_context(sent_by=sent_by, message='Teste de configuração do WhatsApp.')
            results, _message = whatsapp.send_template_notification(WhatsAppNotificationType.TEST, payload=payload, sent_by=sent_by)
            sent_count = sum(1 for _user, ok, _error_message in results if ok)
            error_message = 'Nenhum destinatário marcado em Teste.'
            if sent_count:
                messages.success(request, 'Mensagem de teste enviada com sucesso para o WhatsApp.')
            else:
                messages.error(request, f'Falha ao enviar teste: {error_message}')
            return redirect('whatsapp_dashboard')

        elif action == 'send_message_single_to_phone':
            phone = (request.POST.get('phone') or '').strip()
            message_text = (request.POST.get('message') or '').strip()
            sent_by = request.user.get_full_name() or request.user.username
            try:
                if not phone or not message_text:
                    return JsonResponse({'ok': False, 'error': 'Dados inválidos.'})
                normalized = whatsapp.normalize_phone_number(phone)
                if not normalized:
                    return JsonResponse({'ok': False, 'error': 'Telefone inválido.'})
                rendered = whatsapp.render_message(message_text, whatsapp.template_context(sent_by=sent_by))
                ok, error = whatsapp.send_message_to_phone(normalized, rendered, sent_by=sent_by)
                return JsonResponse({'ok': ok, 'error': error or ''})
            except Exception as exc:
                logger.exception('Erro ao enviar mensagem manual: %s', exc)
                return JsonResponse({'ok': False, 'error': str(exc)})

        elif action == 'charge_documentation_single':
            sent_by = request.user.get_full_name() or request.user.username
            submitted_charge_template = (request.POST.get('charge_template') or '').strip()
            if submitted_charge_template:
                charge_template_text = submitted_charge_template

            WhatsAppTemplate.objects.update_or_create(
                notification_type=WhatsAppNotificationType.DOCUMENTATION,
                defaults={'message_text': charge_template_text},
            )
            try:
                volunteer = get_object_or_404(
                    Volunteer.objects.select_related('registration__user'),
                    pk=request.POST.get('volunteer_id'),
                )
                return JsonResponse(send_documentation_charge(request, volunteer, charge_template_text, sent_by))
            except Exception as exc:
                logger.exception('Erro ao enviar cobranca de documentacao individual: %s', exc)
                return JsonResponse({'volunteer': '-', 'ok': False, 'error_message': str(exc), 'phone': '', 'message': ''}, status=200)

        elif action == 'charge_documentation':
            sent_by = request.user.get_full_name() or request.user.username
            selected_ids = request.POST.getlist('volunteer_ids')
            submitted_charge_template = (request.POST.get('charge_template') or '').strip()
            if submitted_charge_template:
                charge_template_text = submitted_charge_template
            try:
                charge_delay_seconds = max(0.0, float((request.POST.get('charge_delay_seconds') or '').replace(',', '.')))
            except ValueError:
                charge_delay_seconds = default_charge_delay_seconds
                messages.error(request, 'Pausa inválida. Foi usada a pausa padrão.')

            WhatsAppTemplate.objects.update_or_create(
                notification_type=WhatsAppNotificationType.DOCUMENTATION,
                defaults={'message_text': charge_template_text},
            )
            selected_volunteers = (
                Volunteer.objects
                .select_related('registration__user')
                .filter(id__in=selected_ids)
                .order_by('full_name')
            )
            for index, volunteer in enumerate(selected_volunteers):
                if index > 0 and charge_delay_seconds > 0:
                    time.sleep(charge_delay_seconds)
                result = send_documentation_charge(request, volunteer, charge_template_text, sent_by)
                if not result['message']:
                    continue
                charge_message_sent = result['message']
                charge_results.append({
                    'volunteer': volunteer,
                    'ok': result['ok'],
                    'error_message': result['error_message'],
                    'phone': result['phone'],
                    'message': result['message'],
                })

            sent_count = sum(1 for item in charge_results if item['ok'])
            if sent_count:
                messages.success(request, f'Cobrança de documentação enviada para {sent_count} missionário(s).')
            elif charge_results:
                messages.error(request, 'Nenhuma cobrança foi enviada. Confira os telefones e a configuração do WhatsApp.')
            else:
                messages.error(request, 'Nenhum missionário pendente foi selecionado.')
            open_charge_modal = True

    rows = []
    for user in User.objects.filter(is_active=True).order_by('username'):
        preference, _ = WhatsAppRecipientPreference.objects.get_or_create(user=user)
        rows.append({
            'user': user,
            'preference': preference,
            'effective_phone': whatsapp.normalize_phone_number(preference.phone_number or whatsapp.resolve_user_phone(user)),
        })

    templates = []
    for notification_type, label in WhatsAppNotificationType.choices:
        templates.append({
            'type': notification_type,
            'label': label,
            'message': whatsapp.get_template_message(notification_type),
        })

    pending_documentation_volunteers = []
    for volunteer in (
        Volunteer.objects
        .select_related('registration__user')
        .order_by('full_name')
    ):
        pending_items = volunteer_pending_documentation_items(volunteer)
        if pending_items:
            pending_documentation_volunteers.append({
                'volunteer': volunteer,
                'pending_items': pending_items,
                'phone': whatsapp.normalize_phone_number(volunteer.phone),
            })

    context = {
        'config_form': config_form,
        'message_form': message_form,
        'notification_types': WhatsAppNotificationType.choices,
        'selected_notification_type': selected_notification_type,
        'rows': rows,
        'templates': templates,
        'pending_documentation_volunteers': pending_documentation_volunteers,
        'charge_template_text': charge_template_text,
        'charge_delay_seconds': charge_delay_seconds,
        'charge_results': charge_results,
        'charge_message_sent': charge_message_sent,
        'open_charge_modal': open_charge_modal,
        'active_provider': whatsapp.active_provider(),
        'notifications_enabled': whatsapp.notifications_enabled(),
        'panel_permissions': get_panel_permissions(request.user),
        'active_menu': 'whatsapp',
    }
    return render(request, 'registration/whatsapp_dashboard.html', context)


@user_passes_test(can_review_submissions, login_url='login')
def conference_dashboard(request):
    if request.method == 'POST' and request.POST.get('missionary_payment_id'):
        payment = get_object_or_404(MissionaryPayment, pk=request.POST['missionary_payment_id'])
        action = request.POST.get('action')

        if action == 'confirm':
            payment.is_confirmed = True
            payment.confirmed_by = request.user
            payment.confirmed_at = timezone.now()
            payment.save(update_fields=['is_confirmed', 'confirmed_by', 'confirmed_at', 'updated_at'])
            _auto_notify(
                WhatsAppNotificationType.FINANCIAL,
                f'Comprovante conferido!\nTipo: {payment.get_payment_type_display()}\nMissionário: {payment.volunteer.full_name}',
            )
            messages.success(request, 'Comprovante obrigatorio conferido.')
        elif action == 'unconfirm':
            payment.is_confirmed = False
            payment.confirmed_by = None
            payment.confirmed_at = None
            payment.save(update_fields=['is_confirmed', 'confirmed_by', 'confirmed_at', 'updated_at'])
            messages.success(request, 'Conferencia do comprovante obrigatorio removida.')

        return redirect('conference_dashboard')

    if request.method == 'POST' and request.POST.get('donation_receipt_id'):
        donation = get_object_or_404(MissionaryDonationReceipt, pk=request.POST['donation_receipt_id'])
        action = request.POST.get('action')

        if action == 'confirm':
            donation.is_confirmed = True
            donation.confirmed_by = request.user
            donation.confirmed_at = timezone.now()
            donation.save(update_fields=['is_confirmed', 'confirmed_by', 'confirmed_at'])
            _auto_notify(
                WhatsAppNotificationType.FINANCIAL,
                f'Doação conferida!\nMissionário: {donation.volunteer.full_name}',
            )
            messages.success(request, 'Comprovante de doacao conferido.')
        elif action == 'unconfirm':
            donation.is_confirmed = False
            donation.confirmed_by = None
            donation.confirmed_at = None
            donation.save(update_fields=['is_confirmed', 'confirmed_by', 'confirmed_at'])
            messages.success(request, 'Conferencia da doacao removida.')

        return redirect('conference_dashboard')

    if request.method == 'POST' and request.POST.get('volunteer_id'):
        volunteer = get_object_or_404(Volunteer, pk=request.POST['volunteer_id'])
        document_type = request.POST.get('document_type')
        action = request.POST.get('action')
        field_by_type = {
            'signed_registration': 'signed_registration_document_confirmed',
            'insurance_policy': 'insurance_policy_document_confirmed',
            'vaccination_card': 'vaccination_card_document_confirmed',
        }
        file_by_type = {
            'signed_registration': volunteer.signed_registration_document,
            'insurance_policy': volunteer.insurance_policy_document,
            'vaccination_card': volunteer.vaccination_card_document,
        }
        field_name = field_by_type.get(document_type)

        if field_name and file_by_type.get(document_type):
            setattr(volunteer, field_name, action == 'confirm')
            volunteer.documentation_reviewed_by = request.user if action == 'confirm' else None
            volunteer.documentation_reviewed_at = timezone.now() if action == 'confirm' else None
            volunteer.save(update_fields=[field_name, 'documentation_reviewed_by', 'documentation_reviewed_at'])

            if action == 'confirm':
                doc_labels = {
                    'signed_registration': 'Formulário assinado',
                    'insurance_policy': 'Apólice de seguro',
                    'vaccination_card': 'Carteira de vacinação',
                }
                _auto_notify(
                    WhatsAppNotificationType.DOCUMENTATION,
                    f'Documento conferido: {doc_labels.get(document_type, document_type)}',
                    extra_payload={
                        'missionario': volunteer.full_name,
                        'documentos_pendentes': doc_labels.get(document_type, document_type),
                    },
                )
                messages.success(request, 'Documento conferido.')
            elif action == 'unconfirm':
                messages.success(request, 'Conferencia do documento removida.')
        else:
            messages.error(request, 'Documento nao encontrado para conferencia.')

        return redirect('conference_dashboard')

    document_volunteers = (
        Volunteer.objects
        .select_related('registration__user', 'documentation_reviewed_by')
        .filter(
            Q(signed_registration_document__gt='')
            | Q(insurance_policy_document__gt='')
            | Q(vaccination_card_document__gt='')
            | Q(flight_ticket_document__gt='')
            | Q(flight_date__isnull=False)
            | Q(flight_time__isnull=False)
        )
        .order_by('documentation_reviewed_at', 'full_name')
    )
    missionary_payments = (
        MissionaryPayment.objects
        .select_related('volunteer', 'volunteer__registration__user', 'confirmed_by')
        .filter(receipt__gt='')
        .order_by('is_confirmed', '-submitted_at', 'volunteer__full_name')
    )
    donation_receipts = (
        MissionaryDonationReceipt.objects
        .select_related('volunteer', 'volunteer__registration__user', 'confirmed_by')
        .order_by('is_confirmed', '-submitted_at', 'volunteer__full_name')
    )
    conference_groups = {}

    for volunteer in document_volunteers:
        conference_groups.setdefault(
            volunteer.id,
            {'volunteer': volunteer, 'payments': [], 'donations': []},
        )

    for payment in missionary_payments:
        conference_groups.setdefault(
            payment.volunteer_id,
            {'volunteer': payment.volunteer, 'payments': [], 'donations': []},
        )['payments'].append(payment)

    for donation in donation_receipts:
        conference_groups.setdefault(
            donation.volunteer_id,
            {'volunteer': donation.volunteer, 'payments': [], 'donations': []},
        )['donations'].append(donation)

    conference_groups = sorted(
        conference_groups.values(),
        key=lambda group: group['volunteer'].full_name.lower(),
    )

    context = {
        'conference_groups': conference_groups,
        'document_count': document_volunteers.count(),
        'document_pending_count': document_volunteers.filter(
            Q(signed_registration_document__gt='', signed_registration_document_confirmed=False)
            | Q(insurance_policy_document__gt='', insurance_policy_document_confirmed=False)
            | Q(vaccination_card_document__gt='', vaccination_card_document_confirmed=False)
        ).count(),
        'payment_count': missionary_payments.count(),
        'payment_pending_count': missionary_payments.filter(is_confirmed=False).count(),
        'donation_count': donation_receipts.count(),
        'donation_pending_count': donation_receipts.filter(is_confirmed=False).count(),
        'panel_permissions': get_panel_permissions(request.user),
        'active_menu': 'conference',
    }
    return render(request, 'registration/conference_dashboard.html', context)


@user_passes_test(can_view_registrations, login_url='login')
@require_POST
def admin_reset_password(request, registration_id):
    registration = get_object_or_404(Registration, pk=registration_id)
    registration.user.set_password('1234')
    registration.user.save()
    registration.force_password_change = True
    registration.save(update_fields=['force_password_change'])
    messages.success(request, f'Senha de {registration.user.username} redefinida para 1234.')
    return redirect('admin_dashboard')


@login_required(login_url='login')
def change_password(request):
    try:
        registration = request.user.registration
    except Registration.DoesNotExist:
        return redirect('volunteer_dashboard')

    if not registration.force_password_change:
        return redirect(first_available_panel_url(request.user))

    error = None

    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')

        if not password1:
            error = 'Digite a nova senha.'
        elif password1 != password2:
            error = 'As senhas não coincidem.'
        elif len(password1) < 6:
            error = 'A senha deve ter pelo menos 6 caracteres.'
        else:
            request.user.set_password(password1)
            request.user.save()
            registration.force_password_change = False
            registration.save(update_fields=['force_password_change'])
            login(request, request.user)
            messages.success(request, 'Senha alterada com sucesso.')
            return redirect(first_available_panel_url(request.user))

    return render(request, 'registration/change_password.html', {'error': error})


@user_passes_test(can_manage_permissions, login_url='login')
def permissions_dashboard(request):
    if request.method == 'POST':
        target_user = get_object_or_404(
            User,
            pk=request.POST.get('user_id'),
            registration__isnull=False,
            is_superuser=False,
        )
        permission, _ = PanelPermission.objects.get_or_create(user=target_user)
        form = PanelPermissionForm(request.POST, instance=permission, user=target_user)

        if form.is_valid():
            form.save()
            messages.success(request, f'Permissões de {target_user.username} atualizadas.')
            return redirect('permissions_dashboard')
    else:
        form = None

    users = (
        User.objects
        .filter(registration__isnull=False, is_superuser=False)
        .select_related('registration', 'panel_permission')
        .order_by('username')
    )

    return render(
        request,
        'registration/permissions_dashboard.html',
        {
            'users': users,
            'form': form,
            'panel_permissions': get_panel_permissions(request.user),
            'active_menu': 'permissions',
        },
    )


@user_passes_test(can_manage_financial, login_url='login')
def prestacao_contas(request):
    from collections import defaultdict
    transactions = FinancialTransaction.objects.all()
    confirmed_missionary_payments = (
        MissionaryPayment.objects
        .select_related('volunteer', 'volunteer__registration__user', 'confirmed_by')
        .filter(receipt__gt='', is_confirmed=True)
        .order_by('volunteer__full_name', 'payment_type')
    )
    confirmed_donation_receipts = (
        MissionaryDonationReceipt.objects
        .select_related('volunteer', 'volunteer__registration__user', 'confirmed_by')
        .filter(is_confirmed=True)
        .order_by('volunteer__full_name', '-submitted_at')
    )

    manual_income = transactions.filter(transaction_type='entrada').aggregate(total=Sum('amount'))['total'] or 0
    total_expenses = transactions.filter(transaction_type='saida').aggregate(total=Sum('amount'))['total'] or 0
    participation_total = confirmed_missionary_payments.filter(payment_type='participacao').aggregate(total=Sum('amount'))['total'] or 0
    baskets_total = confirmed_missionary_payments.filter(payment_type='cestas').aggregate(total=Sum('amount'))['total'] or 0
    donations_total = confirmed_donation_receipts.aggregate(total=Sum('amount'))['total'] or 0
    total_income = manual_income + participation_total + baskets_total + donations_total
    balance = total_income - total_expenses

    expense_by_category = list(
        transactions
        .filter(transaction_type='saida')
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    for item in expense_by_category:
        item['total_brl'] = format_brl(item['total'])
        item['percent'] = round(float(item['total']) / float(total_expenses) * 100, 1) if total_expenses else 0

    contrib_map = defaultdict(lambda: {
        'volunteer': None, 'participacao': 0, 'cestas': 0, 'doacao': 0, 'total': 0,
        'participacao_brl': '0,00', 'cestas_brl': '0,00', 'doacao_brl': '0,00', 'total_brl': '0,00',
    })
    for payment in confirmed_missionary_payments:
        key = payment.volunteer.id
        if contrib_map[key]['volunteer'] is None:
            contrib_map[key]['volunteer'] = payment.volunteer
        contrib_map[key][payment.payment_type] = float(payment.amount)
        contrib_map[key]['total'] += float(payment.amount)
    for donation in confirmed_donation_receipts:
        key = donation.volunteer.id
        if contrib_map[key]['volunteer'] is None:
            contrib_map[key]['volunteer'] = donation.volunteer
        contrib_map[key]['doacao'] += float(donation.amount)
        contrib_map[key]['total'] += float(donation.amount)
    for v in contrib_map.values():
        v['participacao_brl'] = format_brl(v['participacao'])
        v['cestas_brl'] = format_brl(v['cestas'])
        v['doacao_brl'] = format_brl(v['doacao'])
        v['total_brl'] = format_brl(v['total'])
    volunteer_contributions = sorted(
        [v for v in contrib_map.values() if v['volunteer']],
        key=lambda x: x['volunteer'].full_name,
    )

    manual_entries = list(transactions.filter(transaction_type='entrada').order_by('-transaction_date'))

    context = {
        'total_income': total_income,
        'total_income_brl': format_brl(total_income),
        'total_expenses': total_expenses,
        'total_expenses_brl': format_brl(total_expenses),
        'balance': balance,
        'balance_brl': format_brl(balance),
        'participation_total': participation_total,
        'participation_total_brl': format_brl(participation_total),
        'baskets_total': baskets_total,
        'baskets_total_brl': format_brl(baskets_total),
        'donations_total': donations_total,
        'donations_total_brl': format_brl(donations_total),
        'manual_income': manual_income,
        'manual_income_brl': format_brl(manual_income),
        'expense_by_category': expense_by_category,
        'volunteer_contributions': volunteer_contributions,
        'manual_entries': manual_entries,
        'panel_permissions': get_panel_permissions(request.user),
        'active_menu': 'prestacao_contas',
    }
    return render(request, 'registration/prestacao_contas.html', context)


@user_passes_test(can_manage_financial, login_url='login')
def prestacao_contas_pdf(request):
    from collections import defaultdict
    transactions = FinancialTransaction.objects.all()
    confirmed_missionary_payments = (
        MissionaryPayment.objects
        .select_related('volunteer', 'confirmed_by')
        .filter(receipt__gt='', is_confirmed=True)
        .order_by('volunteer__full_name', 'payment_type')
    )
    confirmed_donation_receipts = (
        MissionaryDonationReceipt.objects
        .select_related('volunteer', 'confirmed_by')
        .filter(is_confirmed=True)
        .order_by('volunteer__full_name', '-submitted_at')
    )

    manual_income = transactions.filter(transaction_type='entrada').aggregate(total=Sum('amount'))['total'] or 0
    total_expenses = transactions.filter(transaction_type='saida').aggregate(total=Sum('amount'))['total'] or 0
    participation_total = confirmed_missionary_payments.filter(payment_type='participacao').aggregate(total=Sum('amount'))['total'] or 0
    baskets_total = confirmed_missionary_payments.filter(payment_type='cestas').aggregate(total=Sum('amount'))['total'] or 0
    donations_total = confirmed_donation_receipts.aggregate(total=Sum('amount'))['total'] or 0
    total_income = manual_income + participation_total + baskets_total + donations_total
    balance = total_income - total_expenses

    expense_by_category = list(
        transactions.filter(transaction_type='saida')
        .values('category').annotate(total=Sum('amount')).order_by('-total')
    )
    for item in expense_by_category:
        item['total_brl'] = format_brl(item['total'])
        item['percent'] = round(float(item['total']) / float(total_expenses) * 100, 1) if total_expenses else 0

    contrib_map = defaultdict(lambda: {
        'volunteer': None, 'participacao': 0, 'cestas': 0, 'doacao': 0, 'total': 0,
    })
    for payment in confirmed_missionary_payments:
        key = payment.volunteer.id
        if contrib_map[key]['volunteer'] is None:
            contrib_map[key]['volunteer'] = payment.volunteer
        contrib_map[key][payment.payment_type] = float(payment.amount)
        contrib_map[key]['total'] += float(payment.amount)
    for donation in confirmed_donation_receipts:
        key = donation.volunteer.id
        if contrib_map[key]['volunteer'] is None:
            contrib_map[key]['volunteer'] = donation.volunteer
        contrib_map[key]['doacao'] += float(donation.amount)
        contrib_map[key]['total'] += float(donation.amount)
    volunteer_contributions = sorted(
        [v for v in contrib_map.values() if v['volunteer']],
        key=lambda x: x['volunteer'].full_name,
    )

    manual_expense_entries = list(transactions.filter(transaction_type='saida').order_by('-transaction_date'))

    data = {
        'total_income': total_income,
        'total_expenses': total_expenses,
        'balance': balance,
        'participation_total': participation_total,
        'baskets_total': baskets_total,
        'donations_total': donations_total,
        'manual_income': manual_income,
        'expense_by_category': expense_by_category,
        'volunteer_contributions': volunteer_contributions,
        'manual_expense_entries': manual_expense_entries,
    }

    pdf_bytes = build_prestacao_contas_pdf(data)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="prestacao-de-contas.pdf"'
    return response


@user_passes_test(can_view_reports, login_url='login')
def reports_dashboard(request):
    from collections import defaultdict

    food_restriction_volunteers = (
        Volunteer.objects
        .select_related('registration__user')
        .filter(has_food_restriction='sim')
        .order_by('full_name')
    )

    today = date.today()
    all_volunteers = list(
        Volunteer.objects.select_related('registration__user').order_by('full_name')
    )

    age_ranges = [
        {'label': 'Até 20 anos', 'min': 0, 'max': 20, 'volunteers': []},
        {'label': '21 a 30 anos', 'min': 21, 'max': 30, 'volunteers': []},
        {'label': '31 a 40 anos', 'min': 31, 'max': 40, 'volunteers': []},
        {'label': '41 a 50 anos', 'min': 41, 'max': 50, 'volunteers': []},
        {'label': '51 anos ou mais', 'min': 51, 'max': 999, 'volunteers': []},
    ]

    work_areas = [
        {'label': 'Saúde', 'field': 'work_health', 'volunteers': []},
        {'label': 'Educação', 'field': 'work_education', 'volunteers': []},
        {'label': 'Apoio geral', 'field': 'work_general_help', 'volunteers': []},
        {'label': 'Evangelismo', 'field': 'work_evangelism', 'volunteers': []},
        {'label': 'Outra', 'field': 'work_other', 'volunteers': []},
    ]

    for volunteer in all_volunteers:
        age = (today - volunteer.birth_date).days // 365
        volunteer.age = age
        for age_range in age_ranges:
            if age_range['min'] <= age <= age_range['max']:
                age_range['volunteers'].append(volunteer)
                break
        for area in work_areas:
            if getattr(volunteer, area['field']):
                area['volunteers'].append(volunteer)

    # Financial data (shown only if user has financial permission)
    has_financial_access = can_manage_financial(request.user)
    financial_ctx = {}
    if has_financial_access:
        transactions = FinancialTransaction.objects.all()
        confirmed_missionary_payments = (
            MissionaryPayment.objects
            .select_related('volunteer', 'confirmed_by')
            .filter(receipt__gt='', is_confirmed=True)
            .order_by('volunteer__full_name', 'payment_type')
        )
        confirmed_donation_receipts = (
            MissionaryDonationReceipt.objects
            .select_related('volunteer', 'confirmed_by')
            .filter(is_confirmed=True)
            .order_by('volunteer__full_name', '-submitted_at')
        )

        manual_income = transactions.filter(transaction_type='entrada').aggregate(total=Sum('amount'))['total'] or 0
        total_expenses = transactions.filter(transaction_type='saida').aggregate(total=Sum('amount'))['total'] or 0
        participation_total = confirmed_missionary_payments.filter(payment_type='participacao').aggregate(total=Sum('amount'))['total'] or 0
        baskets_total = confirmed_missionary_payments.filter(payment_type='cestas').aggregate(total=Sum('amount'))['total'] or 0
        donations_total = confirmed_donation_receipts.aggregate(total=Sum('amount'))['total'] or 0
        total_income = manual_income + participation_total + baskets_total + donations_total
        balance = total_income - total_expenses

        expense_by_category = list(
            transactions.filter(transaction_type='saida')
            .values('category').annotate(total=Sum('amount')).order_by('-total')
        )
        for item in expense_by_category:
            item['total_brl'] = format_brl(item['total'])
            item['percent'] = round(float(item['total']) / float(total_expenses) * 100, 1) if total_expenses else 0

        contrib_map = defaultdict(lambda: {
            'volunteer': None, 'participacao': 0, 'cestas': 0, 'doacao': 0, 'total': 0,
            'participacao_brl': '0,00', 'cestas_brl': '0,00', 'doacao_brl': '0,00', 'total_brl': '0,00',
        })
        for payment in confirmed_missionary_payments:
            key = payment.volunteer.id
            if contrib_map[key]['volunteer'] is None:
                contrib_map[key]['volunteer'] = payment.volunteer
            contrib_map[key][payment.payment_type] = float(payment.amount)
            contrib_map[key]['total'] += float(payment.amount)
        for donation in confirmed_donation_receipts:
            key = donation.volunteer.id
            if contrib_map[key]['volunteer'] is None:
                contrib_map[key]['volunteer'] = donation.volunteer
            contrib_map[key]['doacao'] += float(donation.amount)
            contrib_map[key]['total'] += float(donation.amount)
        for v in contrib_map.values():
            v['participacao_brl'] = format_brl(v['participacao'])
            v['cestas_brl'] = format_brl(v['cestas'])
            v['doacao_brl'] = format_brl(v['doacao'])
            v['total_brl'] = format_brl(v['total'])
        volunteer_contributions = sorted(
            [v for v in contrib_map.values() if v['volunteer']],
            key=lambda x: x['volunteer'].full_name,
        )

        # Detalhes por categoria de saída (para o donut clicável)
        expense_detail_by_cat = {}
        for t in transactions.filter(transaction_type='saida').order_by('-transaction_date'):
            cat = t.category
            expense_detail_by_cat.setdefault(cat, []).append({
                'date': t.transaction_date.strftime('%d/%m/%Y') if t.transaction_date else '-',
                'description': t.description,
                'amount': format_brl(t.amount),
            })

        # Detalhes por tipo de entrada (para as barras clicáveis)
        income_detail = {
            'Inscrições': [
                {'name': p.volunteer.full_name, 'amount': p.amount_brl, 'date': p.confirmed_at.strftime('%d/%m/%Y') if p.confirmed_at else '-'}
                for p in confirmed_missionary_payments.filter(payment_type='participacao')
            ],
            'Cestas': [
                {'name': p.volunteer.full_name, 'amount': p.amount_brl, 'date': p.confirmed_at.strftime('%d/%m/%Y') if p.confirmed_at else '-'}
                for p in confirmed_missionary_payments.filter(payment_type='cestas')
            ],
            'Doações': [
                {'name': d.volunteer.full_name, 'amount': d.amount_brl, 'description': d.description or '—', 'date': d.submitted_at.strftime('%d/%m/%Y') if d.submitted_at else '-'}
                for d in confirmed_donation_receipts
            ],
            'Manuais': [
                {'date': t.transaction_date.strftime('%d/%m/%Y') if t.transaction_date else '-', 'description': t.description, 'amount': format_brl(t.amount)}
                for t in transactions.filter(transaction_type='entrada').order_by('-transaction_date')
            ],
        }

        financial_ctx = {
            'total_income': total_income,
            'total_income_brl': format_brl(total_income),
            'total_expenses': total_expenses,
            'total_expenses_brl': format_brl(total_expenses),
            'balance': balance,
            'balance_brl': format_brl(balance),
            'participation_total': participation_total,
            'participation_total_brl': format_brl(participation_total),
            'baskets_total': baskets_total,
            'baskets_total_brl': format_brl(baskets_total),
            'donations_total': donations_total,
            'donations_total_brl': format_brl(donations_total),
            'manual_income': manual_income,
            'manual_income_brl': format_brl(manual_income),
            'expense_by_category': expense_by_category,
            'expense_by_category_json': json.dumps(
                [{'label': i['category'], 'value': float(i['total']), 'pct': i['percent'],
                  'items': expense_detail_by_cat.get(i['category'], [])} for i in expense_by_category],
                ensure_ascii=False,
            ),
            'income_chart_json': json.dumps([
                {'label': 'Inscrições', 'value': float(participation_total), 'items': income_detail['Inscrições']},
                {'label': 'Cestas',     'value': float(baskets_total),       'items': income_detail['Cestas']},
                {'label': 'Doações',    'value': float(donations_total),     'items': income_detail['Doações']},
                {'label': 'Manuais',    'value': float(manual_income),       'items': income_detail['Manuais']},
            ], ensure_ascii=False),
            'volunteer_contributions': volunteer_contributions,
            'missionario_count': len(volunteer_contributions),
        }

    food_restriction_count = food_restriction_volunteers.count()
    no_restriction_count = len(all_volunteers) - food_restriction_count

    age_ranges_json = json.dumps([
        {
            'label': r['label'],
            'count': len(r['volunteers']),
            'volunteers': [
                {'name': v.full_name, 'age': v.age, 'login': v.registration.user.username, 'email': v.email}
                for v in r['volunteers']
            ],
        }
        for r in age_ranges
    ], ensure_ascii=False)

    work_areas_json = json.dumps([
        {
            'label': a['label'],
            'count': len(a['volunteers']),
            'volunteers': [
                {'name': v.full_name, 'login': v.registration.user.username, 'email': v.email}
                for v in a['volunteers']
            ],
        }
        for a in work_areas
    ], ensure_ascii=False)

    food_json = json.dumps([
        {'label': 'Com restrição', 'count': food_restriction_count,
         'volunteers': [{'name': v.full_name, 'login': v.registration.user.username, 'email': v.email, 'restrictions': v.food_restrictions} for v in food_restriction_volunteers]},
        {'label': 'Sem restrição', 'count': no_restriction_count, 'volunteers': []},
    ], ensure_ascii=False)

    return render(
        request,
        'registration/reports_dashboard.html',
        {
            'food_restriction_volunteers': food_restriction_volunteers,
            'food_restriction_count': food_restriction_count,
            'age_ranges': age_ranges,
            'volunteer_count': len(all_volunteers),
            'work_areas': work_areas,
            'has_financial_access': has_financial_access,
            'age_ranges_json': age_ranges_json,
            'work_areas_json': work_areas_json,
            'food_json': food_json,
            'panel_permissions': get_panel_permissions(request.user),
            'active_menu': 'reports',
            **financial_ctx,
        },
    )
