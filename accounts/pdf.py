from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def yes_no(value):
    return 'Sim' if value == 'sim' else 'Nao'


def checked(value):
    return 'Sim' if value else 'Nao'


def build_registration_pdf(volunteer):
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.3 * cm,
        bottomMargin=1.3 * cm,
        title=f'Ficha de inscricao - {volunteer.full_name}',
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='SectionTitle', parent=styles['Heading2'], fontSize=11, spaceAfter=8))
    styles.add(ParagraphStyle(name='SmallText', parent=styles['BodyText'], fontSize=8, leading=10))
    styles.add(ParagraphStyle(name='NormalText', parent=styles['BodyText'], fontSize=9, leading=11))

    story = [
        Paragraph('INSTITUTO MISSAO ANDREWS', styles['Title']),
        Paragraph('Ficha de Inscricao Amazonas Sem Fronteiras 2026', styles['Heading2']),
        Paragraph(
            'Documento gerado com os dados cadastrados pelo missionario. '
            'Baixe, assine pelo gov.br e envie novamente pelo sistema.',
            styles['NormalText'],
        ),
        Spacer(1, 10),
    ]

    def data_table(rows):
        table = Table(rows, colWidths=[5.2 * cm, 11.8 * cm])
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#dbe3de')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f0eb')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('LEADING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        return table

    story.extend([
        Paragraph('Dados pessoais', styles['SectionTitle']),
        data_table([
            ['Nome completo', volunteer.full_name],
            ['Data de nascimento', volunteer.birth_date.strftime('%d/%m/%Y')],
            ['Genero', volunteer.get_gender_display()],
            ['Endereco completo', volunteer.full_address],
            ['Telefone', volunteer.phone],
            ['E-mail', volunteer.email],
            ['Documento de identidade', volunteer.identity_document],
            ['CPF', volunteer.cpf],
            ['Responsavel', volunteer.guardian_name or '-'],
            ['Telefone do responsavel', volunteer.guardian_phone or '-'],
        ]),
        Spacer(1, 10),
        Paragraph('Informacoes medicas relevantes', styles['SectionTitle']),
        data_table([
            ['Alergias', volunteer.allergies or '-'],
            ['Medicamento em uso', volunteer.medication_in_use or '-'],
            ['Observacoes especiais', volunteer.special_notes or '-'],
        ]),
        Spacer(1, 10),
        Paragraph('Area de atuacao e formacao', styles['SectionTitle']),
        data_table([
            ['Saude', checked(volunteer.work_health)],
            ['Educacao', checked(volunteer.work_education)],
            ['Auxilio geral', checked(volunteer.work_general_help)],
            ['Evangelismo', checked(volunteer.work_evangelism)],
            ['Formacao', volunteer.education or '-'],
        ]),
        Spacer(1, 10),
        Paragraph('Questionario', styles['SectionTitle']),
        data_table([
            ['Desejo participar voluntariamente da Missao Andrews', yes_no(volunteer.wants_to_participate)],
            ['Compreendo que as atividades sao sem remuneracao', yes_no(volunteer.understands_no_payment)],
            ['Estou ciente que devo pagar minhas passagens aereas', yes_no(volunteer.aware_pays_tickets)],
            ['Estou ciente que devo pagar a taxa do projeto', yes_no(volunteer.aware_pays_project_fee)],
            ['Estou ciente que documentos e vacinas devem estar em dia', yes_no(volunteer.aware_documents_vaccines)],
            ['Estou ciente que a taxa de inscricao nao e reembolsavel', yes_no(volunteer.aware_non_refundable_fee)],
        ]),
        Spacer(1, 14),
        Paragraph('Declaracao', styles['SectionTitle']),
        Paragraph(
            'Ao preencher esta ficha, concordo em seguir as diretrizes e regulamentos estabelecidos '
            'para a viagem e confirmo que as informacoes acima sao verdadeiras.',
            styles['NormalText'],
        ),
        Spacer(1, 24),
        data_table([
            ['Cidade e data', volunteer.city_and_date or '____________________________________________'],
            ['Assinatura gov.br', '____________________________________________'],
        ]),
    ])

    document.build(story)
    buffer.seek(0)
    return buffer.getvalue()
