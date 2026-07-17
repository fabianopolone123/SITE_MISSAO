from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image as FlowImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


GREEN = colors.HexColor('#2f6844')
GREEN_DARK = colors.HexColor('#1d442c')
GREEN_SOFT = colors.HexColor('#e8f0eb')
ORANGE = colors.HexColor('#d95d18')
LINE = colors.HexColor('#dbe3de')
TEXT = colors.HexColor('#101513')
MUTED = colors.HexColor('#647067')


def checkbox(label, selected):
    mark = 'x' if selected else ' '
    return f'( {mark} ) {label}'


def yes_no_options(value):
    return f'{checkbox("Sim", value == "sim")}    {checkbox("Não", value == "nao")}'


def display_choice(value):
    if value == 'sim':
        return 'Sim'
    if value == 'nao':
        return 'Não'
    return ''


def text(value):
    return escape(str(value or ''))


def paragraph(value, style):
    return Paragraph(text(value).replace('\n', '<br/>'), style)


def field_line(label, value, styles):
    return Paragraph(f'<b>{text(label)}:</b> {text(value)}', styles['FormBody'])


def section_title(title, styles):
    return Paragraph(text(title), styles['SectionTitle'])


def bullet_list(items, styles):
    rows = [[Paragraph(f'&bull; {text(item)}', styles['FormBody'])] for item in items]
    table = Table(rows, colWidths=[17 * cm])
    table.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    return table


def info_card(flowables):
    table = Table([[flowables]], colWidths=[17 * cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.8, LINE),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    return table


def proportional_image(path, max_width, max_height):
    image_width, image_height = ImageReader(str(path)).getSize()
    scale = min(max_width / image_width, max_height / image_height)
    return FlowImage(str(path), width=image_width * scale, height=image_height * scale)


IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}


def scaled_image_from_bytes(data, max_width, max_height):
    image_width, image_height = ImageReader(BytesIO(data)).getSize()
    scale = min(max_width / image_width, max_height / image_height)
    return FlowImage(BytesIO(data), width=image_width * scale, height=image_height * scale)


def receipt_flowables(receipt, styles, max_width, max_height):
    """Transforma um comprovante (imagem ou PDF) em flowables do reportlab.

    Imagens sao embutidas diretamente; PDFs sao rasterizados pagina a pagina
    com o PyMuPDF, de modo que todo o comprovante fique dentro de um unico
    documento e os links internos ("Abrir") funcionem em qualquer leitor.
    """
    ext = receipt.get('ext', '')
    path = receipt['path']
    flowables = []

    try:
        if ext == '.pdf':
            import fitz

            with fitz.open(path) as pdf:
                for page_index, page in enumerate(pdf):
                    pixmap = page.get_pixmap(dpi=150)
                    flowables.append(scaled_image_from_bytes(pixmap.tobytes('png'), max_width, max_height))
                    if page_index < len(pdf) - 1:
                        flowables.append(PageBreak())
        elif ext in IMAGE_EXTS:
            flowables.append(proportional_image(path, max_width, max_height))
        else:
            flowables.append(Paragraph('Formato de arquivo nao suportado para exibicao.', styles['FormBody']))
    except Exception:
        flowables.append(Paragraph('Nao foi possivel exibir este comprovante.', styles['FormBody']))

    return flowables


def receipt_link(index):
    if not index:
        return '&#8212;'
    return f'<a href="#rec_{index}" color="#2f6844"><b>Abrir &#9656;</b></a>'


def first_page_header(styles):
    logo_path = Path(settings.BASE_DIR) / 'accounts' / 'static' / 'accounts' / 'images' / 'logo-full-transparent.png'
    logo = proportional_image(logo_path, 4.2 * cm, 3.6 * cm) if logo_path.exists() else Paragraph('', styles['HeaderText'])

    institution = [
        Paragraph('INSTITUTO MISSÃO<br/>ANDREWS', styles['HeaderTitle']),
        Paragraph('Rua Hélio Castro Maia, 529 - (Sala 1)', styles['HeaderText']),
        Paragraph('Bairro Jardim Paulista - Campo Grande-MS', styles['HeaderText']),
        Paragraph('CEP: 79050-020 - (+55 67 99239-3858)', styles['HeaderText']),
        Paragraph('Amazonas Sem Fronteiras 2026', styles['HeaderMotto']),
    ]
    table = Table([[logo, institution]], colWidths=[5.4 * cm, 11.6 * cm])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('BACKGROUND', (0, 0), (-1, -1), GREEN_SOFT),
        ('BOX', (0, 0), (-1, -1), 0.8, LINE),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    return table


def build_prestacao_contas_pdf(data):
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title='Prestação de Contas - Missão Andrews',
        pageCompression=0,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='HeaderTitle', parent=styles['Title'], fontSize=16, leading=18, textColor=GREEN_DARK, alignment=1))
    styles.add(ParagraphStyle(name='HeaderText', parent=styles['BodyText'], fontSize=9, leading=11, textColor=TEXT, alignment=1))
    styles.add(ParagraphStyle(name='HeaderMotto', parent=styles['BodyText'], fontSize=10, leading=12, textColor=ORANGE, alignment=1))
    styles.add(ParagraphStyle(name='FormTitle', parent=styles['Heading1'], fontSize=15, leading=18, textColor=GREEN_DARK, alignment=1, spaceAfter=12))
    styles.add(ParagraphStyle(name='SectionTitle', parent=styles['Heading2'], fontSize=11, leading=13, textColor=colors.white, backColor=GREEN, borderPadding=5, spaceBefore=10, spaceAfter=8))
    styles.add(ParagraphStyle(name='FormBody', parent=styles['BodyText'], fontSize=9, leading=12, textColor=TEXT, spaceAfter=4))
    styles.add(ParagraphStyle(name='Muted', parent=styles['BodyText'], fontSize=8, leading=10, textColor=MUTED, alignment=1))
    styles.add(ParagraphStyle(name='TableHeader', parent=styles['BodyText'], fontSize=9, leading=11, textColor=colors.white, alignment=1))
    styles.add(ParagraphStyle(name='TableCell', parent=styles['BodyText'], fontSize=8, leading=11, textColor=TEXT))
    styles.add(ParagraphStyle(name='TableCellRight', parent=styles['BodyText'], fontSize=8, leading=11, textColor=TEXT, alignment=2))
    styles.add(ParagraphStyle(name='TableCellCenter', parent=styles['BodyText'], fontSize=8, leading=11, textColor=TEXT, alignment=1))
    styles.add(ParagraphStyle(name='ReceiptCaption', parent=styles['Heading2'], fontSize=11, leading=14, textColor=colors.white, backColor=GREEN, borderPadding=6, spaceAfter=10))
    styles.add(ParagraphStyle(name='SummaryValue', parent=styles['BodyText'], fontSize=12, leading=14, textColor=GREEN_DARK, alignment=1))
    styles.add(ParagraphStyle(name='SummaryLabel', parent=styles['BodyText'], fontSize=8, leading=10, textColor=MUTED, alignment=1))

    def brl(amount):
        value = f'{float(amount or 0):,.2f}'
        return 'R$ ' + value.replace(',', 'X').replace('.', ',').replace('X', '.')

    total_income = data['total_income']
    total_expenses = data['total_expenses']
    balance = data['balance']

    summary_data = [
        [
            [Paragraph('ENTRADAS TOTAIS', styles['SummaryLabel']), Paragraph(brl(total_income), styles['SummaryValue'])],
            [Paragraph('SAÍDAS TOTAIS', styles['SummaryLabel']), Paragraph(brl(total_expenses), styles['SummaryValue'])],
            [Paragraph('SALDO', styles['SummaryLabel']), Paragraph(brl(balance), styles['SummaryValue'])],
        ]
    ]
    summary_table = Table(summary_data, colWidths=[5.7 * cm, 5.7 * cm, 5.7 * cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), GREEN_SOFT),
        ('BOX', (0, 0), (-1, -1), 0.8, LINE),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, LINE),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))

    # Expense by category table
    expense_by_category = data.get('expense_by_category', [])
    if expense_by_category:
        cat_rows = [[
            Paragraph('CATEGORIA', styles['TableHeader']),
            Paragraph('VALOR', styles['TableHeader']),
            Paragraph('%', styles['TableHeader']),
        ]]
        for item in expense_by_category:
            cat_rows.append([
                Paragraph(text(item['category']), styles['TableCell']),
                Paragraph(item['total_brl'], styles['TableCellRight']),
                Paragraph(f"{item['percent']}%", styles['TableCellRight']),
            ])
        cat_rows.append([
            Paragraph('<b>TOTAL</b>', styles['TableCell']),
            Paragraph(f'<b>{brl(total_expenses)}</b>', styles['TableCellRight']),
            Paragraph('<b>100%</b>', styles['TableCellRight']),
        ])
        cat_table = Table(cat_rows, colWidths=[10 * cm, 4 * cm, 3 * cm])
        cat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), GREEN),
            ('BACKGROUND', (0, -1), (-1, -1), GREEN_SOFT),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, GREEN_SOFT]),
            ('BOX', (0, 0), (-1, -1), 0.8, LINE),
            ('INNERGRID', (0, 0), (-1, -1), 0.4, LINE),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ]))
    else:
        cat_table = Paragraph('Nenhuma saída registrada.', styles['FormBody'])

    # Volunteer contributions table
    volunteer_contributions = data.get('volunteer_contributions', [])
    if volunteer_contributions:
        vol_rows = [[
            Paragraph('MISSIONÁRIO', styles['TableHeader']),
            Paragraph('INSCRIÇÃO', styles['TableHeader']),
            Paragraph('CESTAS', styles['TableHeader']),
            Paragraph('DOAÇÃO', styles['TableHeader']),
            Paragraph('TOTAL', styles['TableHeader']),
        ]]
        for v in volunteer_contributions:
            vol_rows.append([
                Paragraph(text(v['volunteer'].full_name), styles['TableCell']),
                Paragraph(brl(v['participacao']), styles['TableCellRight']),
                Paragraph(brl(v['cestas']), styles['TableCellRight']),
                Paragraph(brl(v['doacao']), styles['TableCellRight']),
                Paragraph(brl(v['total']), styles['TableCellRight']),
            ])
        vol_table = Table(vol_rows, colWidths=[6.5 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 3 * cm])
        vol_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), GREEN),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GREEN_SOFT]),
            ('BOX', (0, 0), (-1, -1), 0.8, LINE),
            ('INNERGRID', (0, 0), (-1, -1), 0.4, LINE),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
    else:
        vol_table = Paragraph('Nenhuma entrada de missionário conferida.', styles['FormBody'])

    # Expense detail table
    manual_expense_entries = data.get('manual_expense_entries', [])
    if manual_expense_entries:
        exp_rows = [[
            Paragraph('DATA', styles['TableHeader']),
            Paragraph('CATEGORIA', styles['TableHeader']),
            Paragraph('DESCRIÇÃO', styles['TableHeader']),
            Paragraph('VALOR', styles['TableHeader']),
            Paragraph('COMPROVANTE', styles['TableHeader']),
        ]]
        for entry in manual_expense_entries:
            date_str = entry.transaction_date.strftime('%d/%m/%Y') if entry.transaction_date else '-'
            val = f'{float(entry.amount):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
            exp_rows.append([
                Paragraph(date_str, styles['TableCell']),
                Paragraph(text(entry.category), styles['TableCell']),
                Paragraph(text(entry.description), styles['TableCell']),
                Paragraph(f'R$ {val}', styles['TableCellRight']),
                Paragraph(receipt_link(getattr(entry, 'receipt_index', None)), styles['TableCellCenter']),
            ])
        exp_table = Table(exp_rows, colWidths=[2.2 * cm, 3 * cm, 6.8 * cm, 2.5 * cm, 2.5 * cm], repeatRows=1)
        exp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), GREEN),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GREEN_SOFT]),
            ('BOX', (0, 0), (-1, -1), 0.8, LINE),
            ('INNERGRID', (0, 0), (-1, -1), 0.4, LINE),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
    else:
        exp_table = Paragraph('Nenhuma saída registrada.', styles['FormBody'])

    # Income receipts table (entradas com comprovante conferido)
    income_receipt_rows = data.get('income_receipt_rows', [])
    if income_receipt_rows:
        inc_rows = [[
            Paragraph('DATA', styles['TableHeader']),
            Paragraph('MISSIONÁRIO', styles['TableHeader']),
            Paragraph('TIPO', styles['TableHeader']),
            Paragraph('VALOR', styles['TableHeader']),
            Paragraph('COMPROVANTE', styles['TableHeader']),
        ]]
        for row in income_receipt_rows:
            date_value = row.get('date')
            date_str = date_value.strftime('%d/%m/%Y') if hasattr(date_value, 'strftime') else '-'
            inc_rows.append([
                Paragraph(date_str, styles['TableCell']),
                Paragraph(text(row['name']), styles['TableCell']),
                Paragraph(text(row['type']), styles['TableCell']),
                Paragraph(f'R$ {row["amount_brl"]}', styles['TableCellRight']),
                Paragraph(receipt_link(row.get('receipt_index')), styles['TableCellCenter']),
            ])
        inc_table = Table(inc_rows, colWidths=[2.5 * cm, 6.5 * cm, 2.5 * cm, 3 * cm, 2.5 * cm], repeatRows=1)
        inc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), GREEN),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GREEN_SOFT]),
            ('BOX', (0, 0), (-1, -1), 0.8, LINE),
            ('INNERGRID', (0, 0), (-1, -1), 0.4, LINE),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
    else:
        inc_table = Paragraph('Nenhuma entrada com comprovante conferido.', styles['FormBody'])

    story = [
        first_page_header(styles),
        Spacer(1, 10),
        Paragraph('PRESTAÇÃO DE CONTAS<br/>AMAZONAS SEM FRONTEIRAS 2026', styles['FormTitle']),
        Spacer(1, 6),
        summary_table,
        Spacer(1, 6),
        info_card([
            Paragraph(
                f'<b>Inscrições:</b> {brl(data["participation_total"])}   '
                f'<b>Cestas:</b> {brl(data["baskets_total"])}   '
                f'<b>Doações:</b> {brl(data["donations_total"])}   '
                f'<b>Entradas manuais:</b> {brl(data["manual_income"])}',
                styles['FormBody'],
            )
        ]),
        Spacer(1, 10),
        section_title('Saídas por Categoria', styles),
        cat_table,
        Spacer(1, 10),
        section_title('Entradas por Missionário', styles),
        vol_table,
        Spacer(1, 10),
        section_title('Detalhamento das Saídas', styles),
        exp_table,
        Spacer(1, 10),
        section_title('Comprovantes de Entradas', styles),
        inc_table,
    ]

    # Anexos: cada comprovante em sua propria pagina, com ancora para o link.
    receipts = data.get('receipts', [])
    if receipts:
        story.append(PageBreak())
        story.append(section_title('Comprovantes anexados', styles))
        story.append(Paragraph(
            f'Total de comprovantes anexados: {len(receipts)}. '
            'Use os links "Abrir" nas tabelas acima para ir direto a cada comprovante.',
            styles['FormBody'],
        ))
        receipt_max_width = 17 * cm
        receipt_max_height = 23 * cm
        for receipt in receipts:
            story.append(PageBreak())
            story.append(Paragraph(
                f'<a name="rec_{receipt["index"]}"/>Comprovante {receipt["index"]} &#8212; {text(receipt["label"])}',
                styles['ReceiptCaption'],
            ))
            story.extend(receipt_flowables(receipt, styles, receipt_max_width, receipt_max_height))

    document.build(story)
    buffer.seek(0)
    return buffer.getvalue()


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
    styles.add(ParagraphStyle(name='HeaderTitle', parent=styles['Title'], fontSize=16, leading=18, textColor=GREEN_DARK, alignment=1))
    styles.add(ParagraphStyle(name='HeaderText', parent=styles['BodyText'], fontSize=9, leading=11, textColor=TEXT, alignment=1))
    styles.add(ParagraphStyle(name='HeaderMotto', parent=styles['BodyText'], fontSize=10, leading=12, textColor=ORANGE, alignment=1))
    styles.add(ParagraphStyle(name='FormTitle', parent=styles['Heading1'], fontSize=15, leading=18, textColor=GREEN_DARK, alignment=1, spaceAfter=12))
    styles.add(ParagraphStyle(name='SectionTitle', parent=styles['Heading2'], fontSize=11, leading=13, textColor=colors.white, backColor=GREEN, borderPadding=5, spaceBefore=10, spaceAfter=8))
    styles.add(ParagraphStyle(name='FormBody', parent=styles['BodyText'], fontSize=9, leading=12, textColor=TEXT, spaceAfter=4))
    styles.add(ParagraphStyle(name='Muted', parent=styles['BodyText'], fontSize=8, leading=10, textColor=MUTED, alignment=1))

    story = [
        first_page_header(styles),
        Spacer(1, 12),
        Paragraph('FICHA DE INSCRIÇÃO<br/>AMAZONAS SEM FRONTEIRAS 2026', styles['FormTitle']),
        info_card([
            paragraph(
                'Uma experiência de 10 dias de missão, serviço e transformação, levando apoio às comunidades '
                'ribeirinhas e indígenas da região de Maués (Ilha Michellis - Sateré Mawé).',
                styles['FormBody'],
            )
        ]),
        section_title('Atendimentos', styles),
        bullet_list([
            'Atendimento básico de saúde;',
            'Consultas médicas;',
            'Atendimento básico odontológico;',
            'Visitação nos lares;',
            'Doações de medicamentos, roupas, calçados etc.;',
            'Evangelismo (a participação do voluntário é opcional);',
            'Construção de uma base de voluntariado da Missão Andrews;',
            'Apoio de infraestrutura às comunidades (construção, pintura e limpeza);',
            'Outras necessidades;',
        ], styles),
        section_title('Observações gerais', styles),
        bullet_list([
            'A missão está prevista para 03 a 13 de julho de 2026;',
            'IDA - 03/07: saída do porto de Manaus às 15h. Chegar em Manaus até 12h;',
            'VOLTA - 13/07: chegada ao porto de Manaus por volta de 12h. Comprar voo de retorno a partir das 16h ou ficar mais dias em Manaus;',
            (
                'Valor de participação: R$ 1.600,00. Inclui transporte fluvial Manaus/Maués ida e volta, '
                'transporte fluvial Maués/Ilha Michellis ida e volta, alimentação completa durante toda a missão, '
                'água mineral à vontade e 2 camisetas personalizadas da missão.'
            ),
            'Doação solidária: 5 cestas básicas compradas em Manaus, valor médio de R$ 90,00 cada, totalizando R$ 450,00;',
            'Total financeiro por missionário: R$ 2.050,00;',
            'Por conta do missionário: passagem aérea até Manaus ida e volta, seguro de vida e rede;',
            (
                'Conta oficial para depósitos: Nome Missão Andrews, Banco Bradesco, Agência 2403, '
                'Conta Corrente 58653-6, Pix (CNPJ) 64.077.212/0001-50.'
            ),
            'Valores e informações podem sofrer ajustes conforme a realidade do período.',
        ], styles),
        PageBreak(),
        section_title('DADOS PESSOAIS', styles),
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
        section_title('Contato de emergência', styles),
        field_line('Nome completo', volunteer.emergency_contact_name, styles),
        field_line('Parentesco', volunteer.emergency_contact_relationship, styles),
        field_line('Telefone', volunteer.emergency_contact_phone, styles),
        section_title('Informações médicas', styles),
        field_line('Possui alguma alergia?', display_choice(volunteer.has_allergies), styles),
        field_line('Qual(is) alergia(s)?', volunteer.allergies, styles),
        field_line('Faz uso de medicamentos contínuos?', display_choice(volunteer.has_continuous_medication), styles),
        field_line('Nome, dosagem e horário dos medicamentos', volunteer.medication_in_use, styles),
        field_line('Condições médicas relevantes ou necessidades especiais', volunteer.special_notes, styles),
        field_line('Possui alguma restrição alimentar?', display_choice(volunteer.has_food_restriction), styles),
        field_line('Qual(is) restrição(ões) alimentar(es)?', volunteer.food_restrictions, styles),
        section_title('Área de atuação e formação', styles),
        paragraph(
            '    '.join([
                checkbox('Saúde', volunteer.work_health),
                checkbox('Educação', volunteer.work_education),
                checkbox('Apoio geral', volunteer.work_general_help),
                checkbox('Evangelismo', volunteer.work_evangelism),
                checkbox('Equipe de apoio', volunteer.work_support_team),
                checkbox('Outra', volunteer.work_other),
            ]),
            styles['FormBody'],
        ),
        field_line('Outra área de atuação', volunteer.work_other_description, styles),
        field_line('Qual a sua formação ou experiência principal?', volunteer.education, styles),
        field_line('Outras habilidades que possam contribuir para a missão', volunteer.other_skills, styles),
        section_title('QUESTIONÁRIO', styles),
        field_line('1-Desejo participar voluntariamente da Missão Andrews', yes_no_options(volunteer.wants_to_participate), styles),
        field_line('2-Compreendo que atividades desenvolvidas são sem remuneração', yes_no_options(volunteer.understands_no_payment), styles),
        field_line('3-Estou ciente que devo pagar minhas passagens aéreas', yes_no_options(volunteer.aware_pays_tickets), styles),
        field_line('4-Estou ciente que devo pagar a taxa de participação do projeto', yes_no_options(volunteer.aware_pays_project_fee), styles),
        field_line('5-Estou ciente que meus documentos e vacinas devem estar em dia', yes_no_options(volunteer.aware_documents_vaccines), styles),
        field_line('6-Estou ciente que o valor da taxa de inscrição é não-reembolsável', yes_no_options(volunteer.aware_non_refundable_fee), styles),
        Spacer(1, 14),
        section_title('Uso de imagem e declaração final', styles),
        field_line(
            'Autorizo o uso de minha imagem para fins institucionais, educativos e de divulgação',
            yes_no_options(volunteer.authorizes_image_use),
            styles,
        ),
        field_line('Declaro que as informações acima são verdadeiras', yes_no_options(volunteer.declares_true_information), styles),
        field_line(
            'Concordo em seguir as diretrizes, normas e regulamentos da viagem e da missão',
            yes_no_options(volunteer.agrees_guidelines),
            styles,
        ),
        Spacer(1, 8),
        info_card([
            paragraph(
                'Ao preencher essa ficha, concordo em seguir as diretrizes e regulamentos estabelecidos para a viagem.',
                styles['FormBody'],
            )
        ]),
        Spacer(1, 20),
        field_line('Cidade e Data', volunteer.city_and_date, styles),
        Spacer(1, 26),
        paragraph('Assinatura: ____________________________________', styles['FormBody']),
    ]

    document.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def build_volunteer_medical_report_pdf(volunteers):
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title='Ficha medica e informacoes pessoais - Missao Andrews',
        pageCompression=0,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='HeaderTitle', parent=styles['Title'], fontSize=16, leading=18, textColor=GREEN_DARK, alignment=1))
    styles.add(ParagraphStyle(name='HeaderText', parent=styles['BodyText'], fontSize=9, leading=11, textColor=TEXT, alignment=1))
    styles.add(ParagraphStyle(name='HeaderMotto', parent=styles['BodyText'], fontSize=10, leading=12, textColor=ORANGE, alignment=1))
    styles.add(ParagraphStyle(name='FormTitle', parent=styles['Heading1'], fontSize=15, leading=18, textColor=GREEN_DARK, alignment=1, spaceAfter=12))
    styles.add(ParagraphStyle(name='VolunteerTitle', parent=styles['Heading2'], fontSize=13, leading=15, textColor=GREEN_DARK, spaceAfter=8))
    styles.add(ParagraphStyle(name='SectionTitle', parent=styles['Heading2'], fontSize=11, leading=13, textColor=colors.white, backColor=GREEN, borderPadding=5, spaceBefore=10, spaceAfter=8))
    styles.add(ParagraphStyle(name='FormBody', parent=styles['BodyText'], fontSize=9, leading=12, textColor=TEXT, spaceAfter=4))

    story = [
        first_page_header(styles),
        Spacer(1, 12),
        Paragraph('FICHA MEDICA E INFORMACOES PESSOAIS', styles['FormTitle']),
    ]

    volunteer_list = list(volunteers)
    for index, volunteer in enumerate(volunteer_list):
        story.extend([
            section_title('MISSIONARIO', styles),
            Paragraph(text(volunteer.full_name), styles['VolunteerTitle']),
            field_line('CPF', volunteer.cpf, styles),
            field_line('Documento de identidade', volunteer.identity_document, styles),
            field_line('Data de nascimento', volunteer.birth_date.strftime('%d/%m/%Y'), styles),
            field_line('Genero', volunteer.get_gender_display(), styles),
            field_line('Telefone', volunteer.phone, styles),
            field_line('E-mail', volunteer.email, styles),
            field_line('Endereco completo', volunteer.full_address, styles),
            field_line('Responsavel (se menor)', volunteer.guardian_name, styles),
            field_line('Telefone do responsavel', volunteer.guardian_phone, styles),
            section_title('Contato de emergencia', styles),
            field_line('Nome', volunteer.emergency_contact_name, styles),
            field_line('Parentesco', volunteer.emergency_contact_relationship, styles),
            field_line('Telefone', volunteer.emergency_contact_phone, styles),
            section_title('Informacoes medicas', styles),
            field_line('Possui alergia?', display_choice(volunteer.has_allergies), styles),
            field_line('Alergias', volunteer.allergies, styles),
            field_line('Usa medicamento continuo?', display_choice(volunteer.has_continuous_medication), styles),
            field_line('Medicamentos em uso', volunteer.medication_in_use, styles),
            field_line('Condicoes medicas relevantes', volunteer.special_notes, styles),
            field_line('Restricao alimentar?', display_choice(volunteer.has_food_restriction), styles),
            field_line('Restricoes alimentares', volunteer.food_restrictions, styles),
            section_title('Logistica e atuacao', styles),
            field_line('Data do voo', volunteer.flight_date.strftime('%d/%m/%Y') if volunteer.flight_date else '', styles),
            field_line('Hora do voo', volunteer.flight_time.strftime('%H:%M') if volunteer.flight_time else '', styles),
            field_line('Areas de atuacao', volunteer.work_areas_display, styles),
            field_line('Formacao principal', volunteer.education, styles),
            field_line('Outras habilidades', volunteer.other_skills, styles),
        ])
        if index < len(volunteer_list) - 1:
            story.append(PageBreak())

    document.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def build_boat_passenger_list_pdf(volunteers):
    volunteer_list = list(volunteers)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title='Lista para passagens do barco - Missao Andrews',
        pageCompression=0,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='HeaderTitle', parent=styles['Title'], fontSize=16, leading=18, textColor=GREEN_DARK, alignment=1))
    styles.add(ParagraphStyle(name='HeaderText', parent=styles['BodyText'], fontSize=9, leading=11, textColor=TEXT, alignment=1))
    styles.add(ParagraphStyle(name='HeaderMotto', parent=styles['BodyText'], fontSize=10, leading=12, textColor=ORANGE, alignment=1))
    styles.add(ParagraphStyle(name='FormTitle', parent=styles['Heading1'], fontSize=15, leading=18, textColor=GREEN_DARK, alignment=1, spaceAfter=12))
    styles.add(ParagraphStyle(name='FormBody', parent=styles['BodyText'], fontSize=9, leading=12, textColor=TEXT, spaceAfter=4))
    styles.add(ParagraphStyle(name='TableHeader', parent=styles['BodyText'], fontSize=9, leading=11, textColor=colors.white, alignment=1))
    styles.add(ParagraphStyle(name='TableCell', parent=styles['BodyText'], fontSize=9, leading=12, textColor=TEXT))

    rows = [[
        Paragraph('NOME COMPLETO', styles['TableHeader']),
        Paragraph('CPF', styles['TableHeader']),
    ]]
    for volunteer in volunteer_list:
        rows.append([
            Paragraph(text(volunteer.full_name), styles['TableCell']),
            Paragraph(text(volunteer.cpf), styles['TableCell']),
        ])

    table = Table(rows, colWidths=[12.5 * cm, 5 * cm], repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GREEN),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GREEN_SOFT]),
        ('BOX', (0, 0), (-1, -1), 0.8, LINE),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))

    story = [
        first_page_header(styles),
        Spacer(1, 12),
        Paragraph('LISTA PARA COMPRA DAS PASSAGENS DO BARCO', styles['FormTitle']),
        Paragraph(f'Total de missionarios: {len(volunteer_list)}', styles['FormBody']),
        table,
    ]

    document.build(story)
    buffer.seek(0)
    return buffer.getvalue()
