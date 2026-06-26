from django.contrib import admin

from .models import (
    FinancialTransaction,
    MissionaryDonationReceipt,
    MissionaryPayment,
    PanelPermission,
    Registration,
    Volunteer,
)


class VolunteerInline(admin.TabularInline):
    model = Volunteer
    extra = 0


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    inlines = [VolunteerInline]


@admin.register(Volunteer)
class VolunteerAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'cpf',
        'email',
        'phone',
        'registration',
        'documentation_complete',
        'documentation_review_complete',
    )
    search_fields = ('full_name', 'cpf', 'email')


@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_date', 'transaction_type', 'category', 'amount')
    list_filter = ('transaction_type', 'category', 'transaction_date')
    search_fields = ('category', 'description')


@admin.register(PanelPermission)
class PanelPermissionAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'can_view_registrations',
        'can_view_reports',
        'can_manage_financial',
        'can_register_expenses',
        'can_manage_permissions',
        'can_review_submissions',
        'updated_at',
    )
    search_fields = ('user__username', 'user__email')


@admin.register(MissionaryPayment)
class MissionaryPaymentAdmin(admin.ModelAdmin):
    list_display = ('volunteer', 'payment_type', 'amount', 'has_receipt', 'is_confirmed', 'confirmed_by', 'confirmed_at')
    list_filter = ('payment_type', 'is_confirmed')
    search_fields = ('volunteer__full_name', 'volunteer__cpf', 'volunteer__email')


@admin.register(MissionaryDonationReceipt)
class MissionaryDonationReceiptAdmin(admin.ModelAdmin):
    list_display = ('volunteer', 'description', 'amount', 'submitted_at', 'is_confirmed', 'confirmed_by', 'confirmed_at')
    list_filter = ('is_confirmed', 'submitted_at')
    search_fields = ('volunteer__full_name', 'volunteer__cpf', 'volunteer__email', 'description')


