from django.contrib import admin

from .models import FinancialTransaction, Registration, Volunteer


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
