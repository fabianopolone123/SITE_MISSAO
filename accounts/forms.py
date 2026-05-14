from decimal import Decimal, InvalidOperation
from pathlib import Path

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import (
    FinancialTransaction,
    MissionaryDonationReceipt,
    MissionaryPayment,
    PanelPermission,
    Volunteer,
    YES_NO_CHOICES,
)


class SignUpForm(UserCreationForm):
    email = forms.EmailField(label='E-mail')

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        labels = {
            'username': 'Usuário',
            'password1': 'Senha',
            'password2': 'Confirmação de senha',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class VolunteerForm(forms.ModelForm):
    class Meta:
        model = Volunteer
        exclude = [
            'registration',
            'signed_registration_document',
            'insurance_policy_document',
            'created_at',
        ]
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'full_address': forms.Textarea(attrs={'rows': 2}),
            'allergies': forms.Textarea(attrs={'rows': 2}),
            'medication_in_use': forms.Textarea(attrs={'rows': 2}),
            'special_notes': forms.Textarea(attrs={'rows': 2}),
            'food_restrictions': forms.Textarea(attrs={'rows': 2}),
            'other_skills': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

        for field_name in [
            'has_allergies',
            'has_continuous_medication',
            'has_food_restriction',
            'wants_to_participate',
            'understands_no_payment',
            'aware_pays_tickets',
            'aware_pays_project_fee',
            'aware_documents_vaccines',
            'aware_non_refundable_fee',
            'authorizes_image_use',
            'declares_true_information',
            'agrees_guidelines',
        ]:
            self.fields[field_name].widget = forms.RadioSelect(choices=YES_NO_CHOICES)

        for field_name in [
            'has_allergies',
            'has_continuous_medication',
            'has_food_restriction',
            'authorizes_image_use',
            'declares_true_information',
            'agrees_guidelines',
        ]:
            self.fields[field_name].required = False

        for field_name in [
            'work_health',
            'work_education',
            'work_general_help',
            'work_evangelism',
            'work_other',
        ]:
            self.fields[field_name].widget.attrs['class'] = 'checkbox-control'

        if not self.is_bound and not self.initial.get('city_and_date') and not self.instance.city_and_date:
            self.initial['city_and_date'] = timezone.localdate().strftime('%d/%m/%Y')


class VolunteerDocumentationForm(forms.ModelForm):
    class Meta:
        model = Volunteer
        fields = ['signed_registration_document', 'insurance_policy_document']
        labels = {
            'signed_registration_document': 'Ficha de inscrição assinada pelo gov.br',
            'insurance_policy_document': 'Apólice de seguro assinada',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False
            field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        cleaned_data = super().clean()

        for field_name in ['signed_registration_document', 'insurance_policy_document']:
            file = cleaned_data.get(field_name)
            if file and Path(file.name).suffix.lower() != '.pdf':
                self.add_error(field_name, 'Envie um arquivo PDF.')

        return cleaned_data


class MissionaryPaymentReceiptForm(forms.ModelForm):
    class Meta:
        model = MissionaryPayment
        fields = ['receipt']
        labels = {
            'receipt': 'Comprovante de pagamento',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['receipt'].required = True
        self.fields['receipt'].widget.attrs.setdefault('class', 'form-control')

    def clean_receipt(self):
        receipt = self.cleaned_data['receipt']
        allowed_suffixes = {'.pdf', '.jpg', '.jpeg', '.png'}

        if Path(receipt.name).suffix.lower() not in allowed_suffixes:
            raise forms.ValidationError('Envie um comprovante em PDF, JPG ou PNG.')

        return receipt


class MissionaryDonationReceiptForm(forms.ModelForm):
    class Meta:
        model = MissionaryDonationReceipt
        fields = ['description', 'receipt']
        labels = {
            'description': 'Descrição da doação',
            'receipt': 'Comprovante da doação',
        }
        widgets = {
            'description': forms.TextInput(attrs={'placeholder': 'Ex.: oferta, doação extra, apoio a missionário'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        self.fields['receipt'].required = True
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean_receipt(self):
        receipt = self.cleaned_data['receipt']
        allowed_suffixes = {'.pdf', '.jpg', '.jpeg', '.png'}

        if Path(receipt.name).suffix.lower() not in allowed_suffixes:
            raise forms.ValidationError('Envie um comprovante em PDF, JPG ou PNG.')

        return receipt


class PanelPermissionForm(forms.ModelForm):
    is_staff = forms.BooleanField(label='Acesso administrativo', required=False)

    class Meta:
        model = PanelPermission
        fields = [
            'is_staff',
            'can_view_registrations',
            'can_manage_financial',
            'can_manage_permissions',
        ]

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        initial = kwargs.pop('initial', {})

        if user is not None:
            initial['is_staff'] = user.is_staff

        super().__init__(*args, initial=initial, **kwargs)

        for field in self.fields.values():
            field.widget.attrs['class'] = 'checkbox-control'

    def save(self, commit=True):
        permission = super().save(commit=False)

        if self.user is not None:
            self.user.is_staff = self.cleaned_data['is_staff']
            if commit:
                self.user.save(update_fields=['is_staff'])

        if commit:
            permission.save()

        return permission


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
            'description': 'Descrição',
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
            raise forms.ValidationError('Informe um valor válido no formato 1.234,56.')
