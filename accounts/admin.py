from django.contrib import admin

from .models import FinancialTransaction, PanelPermission, Registration, Volunteer


class VolunteerInline(admin.TabularInline):
    model = Volunteer
    extra = 0


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    inlines = [VolunteerInline]


@admin.register(Volunteer)
class VolunteerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'cpf', 'email', 'phone', 'registration')
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
        'can_manage_financial',
        'can_manage_permissions',
        'updated_at',
    )
    search_fields = ('user__username', 'user__email')
