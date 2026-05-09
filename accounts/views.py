from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.forms import formset_factory, modelformset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .forms import (
    FinancialTransactionForm,
    MissionaryPaymentReceiptForm,
    PanelPermissionForm,
    SignUpForm,
    VolunteerDocumentationForm,
    VolunteerForm,
)
from .models import (
    FinancialTransaction,
    MISSIONARY_PAYMENT_AMOUNTS,
    MISSIONARY_PAYMENT_TYPES,
    MissionaryPayment,
    PanelPermission,
    Registration,
    Volunteer,
)
from .pdf import build_registration_pdf


PANEL_PERMISSION_FIELDS = {
    'registrations': 'can_view_registrations',
    'financial': 'can_manage_financial',
    'permissions': 'can_manage_permissions',
}

MISSION_PAYMENT_PIX_KEY = '64.077.212/0001-50'
MISSION_PAYMENT_BANK_INFO = {
    'nome': 'Missao Andrews',
    'banco': 'Bradesco',
    'agencia': '2403',
    'conta_corrente': '58653-6',
    'pix': MISSION_PAYMENT_PIX_KEY,
}


def get_panel_permissions(user):
    permissions = {
        'can_view_registrations': False,
        'can_manage_financial': False,
        'can_manage_permissions': False,
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


def can_manage_financial(user):
    return has_panel_permission(user, 'financial')


def can_manage_permissions(user):
    return has_panel_permission(user, 'permissions')


def can_view_volunteer(user, volunteer):
    if not user.is_authenticated:
        return False
    return volunteer.registration.user_id == user.id or can_view_registrations(user)


def first_available_panel_url(user):
    if has_panel_permission(user, 'registrations'):
        return 'admin_dashboard'
    if has_panel_permission(user, 'financial'):
        return 'financial_dashboard'
    if has_panel_permission(user, 'permissions'):
        return 'permissions_dashboard'
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

            for form in formset:
                volunteer = form.save(commit=False)
                volunteer.registration = registration
                volunteer.save()

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

                    for form in formset:
                        volunteer = form.save(commit=False)
                        volunteer.registration = registration
                        volunteer.save()

                messages.success(request, 'Perfil missionario criado com sucesso.')
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
                messages.error(request, 'Nao foi possivel atualizar um cadastro de outro usuario.')
            else:
                formset.save()
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
        messages.error(request, 'Crie seu perfil missionario antes de enviar documentos.')
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
        messages.error(request, 'Crie seu perfil missionario antes de enviar comprovantes.')
        return redirect('volunteer_dashboard')

    volunteers = registration.volunteers.order_by('created_at')
    payment_groups = []

    for volunteer in volunteers:
        payment_groups.append({
            'volunteer': volunteer,
            'payments': ensure_missionary_payments(volunteer),
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
        messages.success(request, f'Comprovante de {payment.get_payment_type_display()} enviado.')
    else:
        messages.error(request, f'Nao foi possivel enviar o comprovante de {payment.get_payment_type_display()}.')

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
        form.save()
        messages.success(request, f'Documentacao de {volunteer.full_name} atualizada.')
    else:
        messages.error(request, f'Nao foi possivel atualizar a documentacao de {volunteer.full_name}.')

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
    if request.method == 'POST' and request.POST.get('missionary_payment_id'):
        payment = get_object_or_404(MissionaryPayment, pk=request.POST['missionary_payment_id'])
        action = request.POST.get('action')

        if action == 'confirm':
            payment.is_confirmed = True
            payment.confirmed_by = request.user
            payment.confirmed_at = timezone.now()
            payment.save(update_fields=['is_confirmed', 'confirmed_by', 'confirmed_at', 'updated_at'])
            messages.success(request, 'Comprovante conferido pelo financeiro.')
        elif action == 'unconfirm':
            payment.is_confirmed = False
            payment.confirmed_by = None
            payment.confirmed_at = None
            payment.save(update_fields=['is_confirmed', 'confirmed_by', 'confirmed_at', 'updated_at'])
            messages.success(request, 'Conferencia do comprovante removida.')

        return redirect('financial_dashboard')

    if request.method == 'POST':
        form = FinancialTransactionForm(request.POST, request.FILES)

        if form.is_valid():
            form.save()
            messages.success(request, 'Lancamento financeiro cadastrado com sucesso.')
            return redirect('financial_dashboard')
    else:
        form = FinancialTransactionForm()

    transactions = FinancialTransaction.objects.all()
    missionary_payments = (
        MissionaryPayment.objects
        .select_related('volunteer', 'volunteer__registration__user', 'confirmed_by')
        .filter(receipt__gt='')
        .order_by('is_confirmed', '-submitted_at', 'volunteer__full_name')
    )
    total_income = transactions.filter(transaction_type='entrada').aggregate(total=Sum('amount'))['total'] or 0
    total_expenses = transactions.filter(transaction_type='saida').aggregate(total=Sum('amount'))['total'] or 0
    balance = total_income - total_expenses

    context = {
        'form': form,
        'transactions': transactions,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'balance': balance,
        'expense_count': transactions.filter(transaction_type='saida').count(),
        'receipt_count': transactions.exclude(receipt='').count(),
        'missionary_payments': missionary_payments,
        'missionary_receipt_count': missionary_payments.count(),
        'missionary_confirmed_count': missionary_payments.filter(is_confirmed=True).count(),
        'panel_permissions': get_panel_permissions(request.user),
        'active_menu': 'financial',
        'category_summary': transactions.values('category', 'transaction_type').annotate(total=Sum('amount')).order_by('category'),
    }
    return render(request, 'registration/financial_dashboard.html', context)


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
            messages.success(request, f'Permissoes de {target_user.username} atualizadas.')
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
