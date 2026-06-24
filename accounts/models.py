from decimal import Decimal

from django.conf import settings
from django.db import models


YES_NO_CHOICES = [
    ('sim', 'Sim'),
    ('nao', 'Não'),
]

GENDER_CHOICES = [
    ('masculino', 'Masculino'),
    ('feminino', 'Feminino'),
]

FINANCIAL_TRANSACTION_TYPES = [
    ('entrada', 'Entrada'),
    ('saida', 'Saída'),
]

EXPENSE_CATEGORIES = [
    'Medicamento',
    'Alimentação',
    'Transporte',
    'Hospedagem / Estadia',
    'Comunicação',
    'Material / Equipamento',
    'Despesa administrativa',
    'Despesa extra',
]

INCOME_CATEGORIES = [
    'Taxa de inscrição',
    'Cestas básicas',
    'Doação',
    'Oferta',
    'Apoio institucional',
]

MISSIONARY_PAYMENT_TYPES = [
    ('participacao', 'Taxa de participação'),
    ('cestas', 'Doação solidária - 5 cestas básicas'),
]

MISSIONARY_PAYMENT_AMOUNTS = {
    'participacao': '1600.00',
    'cestas': '450.00',
}


class PanelPermission(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='panel_permission')
    can_view_registrations = models.BooleanField('Ver inscritos', default=False)
    can_manage_financial = models.BooleanField('Acessar financeiro', default=False)
    can_manage_permissions = models.BooleanField('Gerenciar permissões', default=False)
    can_review_submissions = models.BooleanField('Conferir documentos e comprovantes', default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Permissão do painel'
        verbose_name_plural = 'Permissões do painel'

    def __str__(self):
        return f'Permissões de {self.user.username}'


class Registration(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    force_password_change = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Inscrição'
        verbose_name_plural = 'Inscrições'

    def __str__(self):
        return f'Inscrição de {self.user.username}'


class Volunteer(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='volunteers')
    full_name = models.CharField('Nome completo', max_length=180)
    birth_date = models.DateField('Data de nascimento')
    gender = models.CharField('Gênero', max_length=20, choices=GENDER_CHOICES)
    full_address = models.TextField('Endereço completo')
    phone = models.CharField('Telefone com código da sua cidade', max_length=30)
    email = models.EmailField('E-mail')
    identity_document = models.CharField('Documento de Identidade', max_length=40)
    cpf = models.CharField('CPF', max_length=20)
    guardian_name = models.CharField('Nome do responsável', max_length=180, blank=True)
    guardian_phone = models.CharField('Telefone do responsável', max_length=30, blank=True)
    emergency_contact_name = models.CharField('Nome completo do contato de emergência', max_length=180, blank=True)
    emergency_contact_relationship = models.CharField('Parentesco do contato de emergência', max_length=80, blank=True)
    emergency_contact_phone = models.CharField('Telefone do contato de emergência', max_length=30, blank=True)
    has_allergies = models.CharField('Possui alguma alergia?', max_length=3, choices=YES_NO_CHOICES, blank=True)
    allergies = models.TextField('Qual(is) alergia(s)?', blank=True)
    has_continuous_medication = models.CharField(
        'Faz uso de medicamentos contínuos?',
        max_length=3,
        choices=YES_NO_CHOICES,
        blank=True,
    )
    medication_in_use = models.TextField('Nome, dosagem e horário dos medicamentos', blank=True)
    special_notes = models.TextField('Condições médicas relevantes ou necessidades especiais', blank=True)
    has_food_restriction = models.CharField(
        'Possui alguma restrição alimentar?',
        max_length=3,
        choices=YES_NO_CHOICES,
        blank=True,
    )
    food_restrictions = models.TextField('Qual(is) restrição(ões) alimentar(es)?', blank=True)
    work_health = models.BooleanField('Saúde', default=False)
    work_education = models.BooleanField('Educação', default=False)
    work_general_help = models.BooleanField('Apoio geral', default=False)
    work_evangelism = models.BooleanField('Evangelismo', default=False)
    work_other = models.BooleanField('Outra', default=False)
    work_other_description = models.CharField('Outra área de atuação', max_length=160, blank=True)
    education = models.CharField('Qual a sua formação ou experiência principal?', max_length=180, blank=True)
    other_skills = models.TextField('Outras habilidades que possam contribuir para a missão', blank=True)
    wants_to_participate = models.CharField(
        'Desejo participar voluntariamente da Missão Andrews',
        max_length=3,
        choices=YES_NO_CHOICES,
    )
    understands_no_payment = models.CharField(
        'Compreendo que atividades desenvolvidas são sem remuneração',
        max_length=3,
        choices=YES_NO_CHOICES,
    )
    aware_pays_tickets = models.CharField(
        'Estou ciente que devo pagar minhas passagens aéreas',
        max_length=3,
        choices=YES_NO_CHOICES,
    )
    aware_pays_project_fee = models.CharField(
        'Estou ciente que devo pagar a taxa de participação do projeto',
        max_length=3,
        choices=YES_NO_CHOICES,
    )
    aware_documents_vaccines = models.CharField(
        'Estou ciente que meus documentos e vacinas devem estar em dia',
        max_length=3,
        choices=YES_NO_CHOICES,
    )
    aware_non_refundable_fee = models.CharField(
        'Estou ciente que o valor da taxa de inscrição é não-reembolsável',
        max_length=3,
        choices=YES_NO_CHOICES,
    )
    authorizes_image_use = models.CharField(
        'Autorizo o uso de minha imagem para fins institucionais, educativos e de divulgação',
        max_length=3,
        choices=YES_NO_CHOICES,
        blank=True,
    )
    declares_true_information = models.CharField(
        'Declaro que as informações acima são verdadeiras',
        max_length=3,
        choices=YES_NO_CHOICES,
        blank=True,
    )
    agrees_guidelines = models.CharField(
        'Concordo em seguir as diretrizes, normas e regulamentos da viagem e da missão',
        max_length=3,
        choices=YES_NO_CHOICES,
        blank=True,
    )
    city_and_date = models.CharField('Local e data', max_length=120, blank=True)
    signed_registration_document = models.FileField(
        'Ficha de inscrição assinada',
        upload_to='documentos/fichas_assinadas/',
        blank=True,
    )
    insurance_policy_document = models.FileField(
        'Apólice de seguro assinada',
        upload_to='documentos/apolices/',
        blank=True,
    )
    flight_ticket_document = models.FileField(
        'Passagem aérea',
        upload_to='documentos/passagens/',
        blank=True,
    )
    flight_date = models.DateField('Data do voo', null=True, blank=True)
    flight_time = models.TimeField('Hora do voo', null=True, blank=True)
    signed_registration_document_confirmed = models.BooleanField('Ficha assinada conferida', default=False)
    insurance_policy_document_confirmed = models.BooleanField('Apolice de seguro conferida', default=False)
    documentation_reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_volunteer_documentations',
    )
    documentation_reviewed_at = models.DateTimeField('Documentacao conferida em', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Voluntário'
        verbose_name_plural = 'Voluntários'

    def __str__(self):
        return self.full_name

    @property
    def has_signed_registration_document(self):
        return bool(self.signed_registration_document)

    @property
    def has_insurance_policy_document(self):
        return bool(self.insurance_policy_document)

    @property
    def has_flight_ticket_document(self):
        return bool(self.flight_ticket_document)

    @property
    def documentation_complete(self):
        return self.has_signed_registration_document and self.has_insurance_policy_document

    @property
    def documentation_review_complete(self):
        return (
            self.has_signed_registration_document
            and self.signed_registration_document_confirmed
            and self.has_insurance_policy_document
            and self.insurance_policy_document_confirmed
        )

    @property
    def documentation_status_label(self):
        if self.documentation_review_complete:
            return 'Documentacao conferida'
        if self.documentation_complete:
            return 'Enviada - aguardando conferencia'
        return 'Documentacao pendente'


class FinancialTransaction(models.Model):
    transaction_type = models.CharField('Tipo', max_length=10, choices=FINANCIAL_TRANSACTION_TYPES)
    category = models.CharField('Categoria', max_length=120)
    description = models.TextField('Descrição')
    amount = models.DecimalField('Valor', max_digits=10, decimal_places=2)
    transaction_date = models.DateField('Data')
    receipt = models.FileField('Comprovante', upload_to='comprovantes/', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lançamento financeiro'
        verbose_name_plural = 'Lançamentos financeiros'
        ordering = ['-transaction_date', '-created_at']

    def __str__(self):
        return f'{self.get_transaction_type_display()} - {self.category} - R$ {self.amount}'

    @property
    def amount_brl(self):
        amount = Decimal(str(self.amount))
        value = f'{amount:,.2f}'
        return value.replace(',', 'X').replace('.', ',').replace('X', '.')


class MissionaryPayment(models.Model):
    volunteer = models.ForeignKey(Volunteer, on_delete=models.CASCADE, related_name='payments')
    payment_type = models.CharField('Tipo de pagamento', max_length=20, choices=MISSIONARY_PAYMENT_TYPES)
    amount = models.DecimalField('Valor', max_digits=10, decimal_places=2)
    receipt = models.FileField('Comprovante', upload_to='comprovantes_missionarios/', blank=True)
    submitted_at = models.DateTimeField('Enviado em', null=True, blank=True)
    is_confirmed = models.BooleanField('Conferido pelo financeiro', default=False)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_missionary_payments',
    )
    confirmed_at = models.DateTimeField('Conferido em', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pagamento de missionário'
        verbose_name_plural = 'Pagamentos de missionários'
        unique_together = ('volunteer', 'payment_type')
        ordering = ['volunteer__full_name', 'payment_type']

    def __str__(self):
        return f'{self.volunteer.full_name} - {self.get_payment_type_display()}'

    @property
    def has_receipt(self):
        return bool(self.receipt)

    @property
    def status_label(self):
        if self.is_confirmed:
            return 'Conferido'
        if self.has_receipt:
            return 'Pago - aguardando conferência'
        return 'Pendente'

    @property
    def amount_brl(self):
        amount = Decimal(str(self.amount))
        value = f'{amount:,.2f}'
        return value.replace(',', 'X').replace('.', ',').replace('X', '.')


class MissionaryDonationReceipt(models.Model):
    volunteer = models.ForeignKey(Volunteer, on_delete=models.CASCADE, related_name='donation_receipts')
    description = models.CharField('Descrição da doação', max_length=180, blank=True)
    amount = models.DecimalField('Valor da doação', max_digits=10, decimal_places=2, default=0)
    receipt = models.FileField('Comprovante de doação', upload_to='comprovantes_doacoes/')
    submitted_at = models.DateTimeField('Enviado em', auto_now_add=True)
    is_confirmed = models.BooleanField('Conferido', default=False)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_donation_receipts',
    )
    confirmed_at = models.DateTimeField('Conferido em', null=True, blank=True)

    class Meta:
        verbose_name = 'Comprovante de doação'
        verbose_name_plural = 'Comprovantes de doações'
        ordering = ['-submitted_at']

    def __str__(self):
        return f'Doação opcional - {self.volunteer.full_name}'

    @property
    def status_label(self):
        if self.is_confirmed:
            return 'Conferido'
        return 'Aguardando conferencia'

    @property
    def amount_brl(self):
        amount = Decimal(str(self.amount))
        value = f'{amount:,.2f}'
        return value.replace(',', 'X').replace('.', ',').replace('X', '.')
