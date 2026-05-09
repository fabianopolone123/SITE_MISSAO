from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def checkbox(label, selected):
    mark = 'x' if selected else ' '
    return f'( {mark} ) {label}'


def yes_no_options(value):
    return f'{checkbox("Sim", value == "sim")}    {checkbox("Não", value == "nao")}'


def paragraph(text, style):
    return Paragraph(escape(str(text)).replace('\n', '<br/>'), style)


def header_story(styles):
    return [
        paragraph('INSTITUTO MISSÃO\nANDREWS', styles['HeaderTitle']),
        paragraph('Rua Hélio Castro Maia, 529 – (Sala 1)', styles['HeaderText']),
        paragraph('Bairro Jardim Paulista – Campo Grande-MS', styles['HeaderText']),
        paragraph('CEP: 79050-020 - (+55 67 99239-3858)', styles['HeaderText']),
        paragraph('Avante Sem Retroceder', styles['HeaderMotto']),
        Spacer(1, 10),
    ]


def bullet_list(items, styles):
    story = []
    for item in items:
        story.append(paragraph(f'ü {item}', styles['FormBody']))
    return story


def field_line(label, value, styles):
    value = value or ''
    return Paragraph(f'<b>{escape(label)}:</b> {escape(str(value))}', styles['FormBody'])


def build_registration_pdf(volunteer):
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title=f'Ficha de inscrição - {volunteer.full_name}',
        pageCompression=0,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='HeaderTitle', parent=styles['Title'], fontSize=17, leading=18, spaceAfter=4))
    styles.add(ParagraphStyle(name='HeaderText', parent=styles['BodyText'], fontSize=9, leading=11, alignment=1))
    styles.add(ParagraphStyle(name='HeaderMotto', parent=styles['BodyText'], fontSize=10, leading=12, alignment=1, spaceAfter=3))
    styles.add(ParagraphStyle(name='FormTitle', parent=styles['Heading1'], fontSize=14, leading=16, alignment=1, spaceAfter=10))
    styles.add(ParagraphStyle(name='SectionTitle', parent=styles['Heading2'], fontSize=11, leading=13, spaceBefore=8, spaceAfter=7))
    styles.add(ParagraphStyle(name='FormBody', parent=styles['BodyText'], fontSize=9, leading=12, spaceAfter=3))

    story = []
    story.extend(header_story(styles))
    story.extend([
        paragraph('FICHA DE INSCRIÇÃO\nAMAZONAS SEM FRONTEIRAS 2025', styles['FormTitle']),
        paragraph(
            'A Missão Andrews é um projeto de serviço voluntário voltado para as comunidades de baixa renda '
            'e povos isolados, onde o acesso à educação e saúde são escassos. Através do voluntariado '
            'diversas ações têm sido desenvolvidas no Amazonas – Brasil:',
            styles['FormBody'],
        ),
        paragraph('Atendimentos:', styles['SectionTitle']),
    ])
    story.extend(bullet_list([
        'Atendimento básico de saúde;',
        'Consultas médicas;',
        'Atendimento básico odontológico;',
        'Visitação nos lares;',
        'Doações de medicamentos, roupas, calçados etc.;',
        'Evangelismo (a participação do voluntário é opcional);',
        'Construção de uma base de voluntariado da Missão Andrews;',
        'Apoio de infraestrutura às comunidades (construção, pintura e limpeza);',
        'Outras necessidades;',
    ], styles))
    story.extend([
        paragraph('Observações gerais:', styles['SectionTitle']),
    ])
    story.extend(bullet_list([
        'Cada voluntário paga suas passagens;',
        'A data da missão está prevista para julho de 2025;',
        (
            'O valor da taxa de participação é de R$ 1.600,00 reais + 5 cestas básicas com valor aproximado '
            'de R$ 85,00. (Obs. Os valores das cestas podem oscilar de acordo com a realidade da época). '
            'Valor da taxa de R$ 1.600,00 deve ser pago até dia 20/06/2025.'
        ),
        (
            'Para EFETUAR a sua inscrição é preciso fazer um adiantamento de R$ 200,00 reais. Esse valor '
            'não é reembolsável devido aos compromissos e será descontado do valor da participação como uma parcela.'
        ),
        'O adiantamento deverá ser feito via pix: inst.missaoandrews@gmail.com',
        'Comprovante da inscrição enviar para os financeiros: Sâmela Polone – (16) 99759-2801',
    ], styles))

    story.append(PageBreak())
    story.extend(header_story(styles))
    story.extend([
        paragraph(
            'Ao preencher essa ficha, concordo em seguir as diretrizes e regulamentos estabelecidos para a viagem.',
            styles['FormBody'],
        ),
        Spacer(1, 12),
        paragraph('Assinatura: ____________________________________', styles['FormBody']),
        paragraph('DADOS PESSOAIS', styles['SectionTitle']),
        field_line('Nome', volunteer.full_name, styles),
        field_line('Data de nascimento', volunteer.birth_date.strftime('%d/%m/%Y'), styles),
        field_line(
            'Gênero',
            f'{checkbox("Masculino", volunteer.gender == "masculino")}    {checkbox("Feminino", volunteer.gender == "feminino")}',
            styles,
        ),
        field_line('Endereço completo', volunteer.full_address, styles),
        field_line('Telefone com código da sua cidade', volunteer.phone, styles),
        field_line('E-mail', volunteer.email, styles),
        field_line('Documento de Identidade', volunteer.identity_document, styles),
        field_line('CPF', volunteer.cpf, styles),
        field_line('Nome do responsável (se for menor de idade)', volunteer.guardian_name, styles),
        field_line('Telefone do Responsável', volunteer.guardian_phone, styles),
        paragraph('Informações médicas relevantes:', styles['SectionTitle']),
        field_line('Alergias', volunteer.allergies, styles),
        field_line('Medicamento em uso', volunteer.medication_in_use, styles),
        field_line('Observações especiais', volunteer.special_notes, styles),
        paragraph('Qual área você deseja atuar:', styles['SectionTitle']),
        paragraph(
            '    '.join([
                checkbox('Saúde', volunteer.work_health),
                checkbox('Educação', volunteer.work_education),
                checkbox('Auxílio geral', volunteer.work_general_help),
                checkbox('Evangelismo', volunteer.work_evangelism),
            ]),
            styles['FormBody'],
        ),
        field_line('Qual a sua formação', volunteer.education, styles),
        paragraph('QUESTIONÁRIO', styles['SectionTitle']),
        field_line('1-Desejo participar voluntariamente da Missão Andrews', yes_no_options(volunteer.wants_to_participate), styles),
        field_line('2-Compreendo que atividades desenvolvidas são sem remuneração', yes_no_options(volunteer.understands_no_payment), styles),
        field_line('3-Estou ciente que devo pagar minhas passagens aéreas', yes_no_options(volunteer.aware_pays_tickets), styles),
        field_line('4-Estou ciente que devo pagar a taxa de participação do projeto', yes_no_options(volunteer.aware_pays_project_fee), styles),
        field_line('5-Estou ciente que meus documentos e vacinas devem estar em dia', yes_no_options(volunteer.aware_documents_vaccines), styles),
        field_line('6-Estou ciente que o valor da taxa de inscrição é não-reembolsável', yes_no_options(volunteer.aware_non_refundable_fee), styles),
    ])

    story.append(PageBreak())
    story.extend(header_story(styles))
    story.extend([
        Spacer(1, 24),
        field_line('Cidade e Data', volunteer.city_and_date, styles),
    ])

    document.build(story)
    buffer.seek(0)
    return buffer.getvalue()
