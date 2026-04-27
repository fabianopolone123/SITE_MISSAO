from django.conf import settings
from django.db import models


YES_NO_CHOICES = [
    ('sim', 'Sim'),
    ('nao', 'Nao'),
]

GENDER_CHOICES = [
    ('masculino', 'Masculino'),
    ('feminino', 'Feminino'),
]


class Registration(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Inscricao'
        verbose_name_plural = 'Inscricoes'

    def __str__(self):
        return f'Inscricao de {self.user.username}'


class Volunteer(models.Model):
    registration = models.ForeignKey(Registration, on_delete=models.CASCADE, related_name='volunteers')
    full_name = models.CharField('Nome completo', max_length=180)
    birth_date = models.DateField('Data de nascimento')
    gender = models.CharField('Genero', max_length=20, choices=GENDER_CHOICES)
    full_address = models.TextField('Endereco completo')
    phone = models.CharField('Telefone com codigo da sua cidade', max_length=30)
    email = models.EmailField('E-mail')
    identity_document = models.CharField('Documento de Identidade', max_length=40)
    cpf = models.CharField('CPF', max_length=20)
    guardian_name = models.CharField('Nome do responsavel', max_length=180, blank=True)
    guardian_phone = models.CharField('Telefone do responsavel', max_length=30, blank=True)
    allergies = models.TextField('Alergias', blank=True)
    medication_in_use = models.TextField('Medicamento em uso', blank=True)
    special_notes = models.TextField('Observacoes especiais', blank=True)
    work_health = models.BooleanField('Saude', default=False)
    work_education = models.BooleanField('Educacao', default=False)
    work_general_help = models.BooleanField('Auxilio geral', default=False)
    work_evangelism = models.BooleanField('Evangelismo', default=False)
    education = models.CharField('Qual a sua formacao', max_length=180, blank=True)
    wants_to_participate = models.CharField(
        'Desejo participar voluntariamente da Missao Andrews',
        max_length=3,
        choices=YES_NO_CHOICES,
        default='sim',
    )
    understands_no_payment = models.CharField(
        'Compreendo que atividades desenvolvidas sao sem remuneracao',
        max_length=3,
        choices=YES_NO_CHOICES,
        default='sim',
    )
    aware_pays_tickets = models.CharField(
        'Estou ciente que devo pagar minhas passagens aereas',
        max_length=3,
        choices=YES_NO_CHOICES,
        default='sim',
    )
    aware_pays_project_fee = models.CharField(
        'Estou ciente que devo pagar a taxa de participacao do projeto',
        max_length=3,
        choices=YES_NO_CHOICES,
        default='sim',
    )
    aware_documents_vaccines = models.CharField(
        'Estou ciente que meus documentos e vacinas devem estar em dia',
        max_length=3,
        choices=YES_NO_CHOICES,
        default='sim',
    )
    aware_non_refundable_fee = models.CharField(
        'Estou ciente que o valor da taxa de inscricao e nao-reembolsavel',
        max_length=3,
        choices=YES_NO_CHOICES,
        default='sim',
    )
    city_and_date = models.CharField('Cidade e Data', max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Voluntario'
        verbose_name_plural = 'Voluntarios'

    def __str__(self):
        return self.full_name
