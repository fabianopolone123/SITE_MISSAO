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
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .forms import (
    FinancialTransactionForm,
    PanelPermissionForm,
    SignUpForm,
    VolunteerDocumentationForm,
    VolunteerForm,
)
from .models import FinancialTransaction, PanelPermission, Registration, Volunteer
from .pdf import build_registration_pdf


PANEL_PERMISSION_FIELDS = {
    'registrations': 'can_view_registrations',
    'financial': 'can_manage_financial',
    'permissions': 'can_manage_permissions',
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
    if request.method == 'POST':
        form = FinancialTransactionForm(request.POST, request.FILES)

        if form.is_valid():
            form.save()
            messages.success(request, 'Lancamento financeiro cadastrado com sucesso.')
            return redirect('financial_dashboard')
    else:
        form = FinancialTransactionForm()

    transactions = FinancialTransaction.objects.all()
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
