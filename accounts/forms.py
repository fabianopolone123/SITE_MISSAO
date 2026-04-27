from decimal import Decimal, InvalidOperation

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import FinancialTransaction, Volunteer, YES_NO_CHOICES


class SignUpForm(UserCreationForm):
    email = forms.EmailField(label='E-mail')

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        labels = {
            'username': 'Usuario',
            'password1': 'Senha',
            'password2': 'Confirmacao de senha',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class VolunteerForm(forms.ModelForm):
    class Meta:
        model = Volunteer
        exclude = ['registration', 'created_at']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'full_address': forms.Textarea(attrs={'rows': 2}),
            'allergies': forms.Textarea(attrs={'rows': 2}),
            'medication_in_use': forms.Textarea(attrs={'rows': 2}),
            'special_notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

        for field_name in [
            'wants_to_participate',
            'understands_no_payment',
            'aware_pays_tickets',
            'aware_pays_project_fee',
            'aware_documents_vaccines',
            'aware_non_refundable_fee',
        ]:
            self.fields[field_name].widget = forms.RadioSelect(choices=YES_NO_CHOICES)

        for field_name in [
            'work_health',
            'work_education',
            'work_general_help',
            'work_evangelism',
        ]:
            self.fields[field_name].widget.attrs['class'] = 'checkbox-control'


class FinancialTransactionForm(forms.ModelForm):
    amount = forms.CharField(
        label='Valor',
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'placeholder': '0,00'}),
    )

    class Meta:
        model = FinancialTransaction
        fields = ['transaction_type', 'category', 'description', 'amount', 'transaction_date', 'receipt']
        widgets = {
            'transaction_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'transaction_type': 'Tipo',
            'category': 'Categoria',
            'description': 'Descricao',
            'amount': 'Valor',
            'transaction_date': 'Data',
            'receipt': 'Anexar comprovante',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

        self.fields['amount'].widget.attrs['class'] = 'form-control money-input'

    def clean_amount(self):
        amount = str(self.cleaned_data['amount'])
        normalized_amount = amount.replace('.', '').replace(',', '.')

        try:
            return Decimal(normalized_amount)
        except InvalidOperation:
            raise forms.ValidationError('Informe um valor valido no formato 1.234,56.')
