from django.contrib.auth import login
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.forms import formset_factory
from django.shortcuts import redirect, render

from .forms import FinancialTransactionForm, SignUpForm, VolunteerForm
from .models import FinancialTransaction, Registration, Volunteer


def is_admin_user(user):
    return user.is_authenticated and user.is_staff


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


@user_passes_test(is_admin_user, login_url='login')
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


@user_passes_test(is_admin_user, login_url='login')
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
        'category_summary': transactions.values('category', 'transaction_type').annotate(total=Sum('amount')).order_by('category'),
    }
    return render(request, 'registration/financial_dashboard.html', context)
