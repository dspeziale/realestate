"""
Convertitore Markdown → PDF CORRETTO
Soluzione: Estrae blocchi di codice PRIMA di fare il parsing

Installa: pip install markdown2 reportlab
"""

import markdown2
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
import re
from pathlib import Path


def escape_for_reportlab(text):
    """Escapa il testo per evitare errori di parsing HTML in ReportLab"""
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


def clean_markdown_formatting(text):
    """Converte markdown formatting a ReportLab XML in modo sicuro"""
    text = escape_for_reportlab(text)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    text = re.sub(r' \*(.*?)\* ', r' <i>\1</i> ', text)
    text = re.sub(r'`(.*?)`', r'<font color="red"><b>\1</b></font>', text)
    return text


def extract_code_blocks(content):
    """
    Estrae i blocchi di codice dal markdown
    Ritorna lista di (tipo, contenuto)
    """
    blocks = []
    parts = content.split('```')

    # parts[0] = testo prima del primo ```
    # parts[1] = linguaggio + codice
    # parts[2] = testo dopo il primo ```
    # etc.

    for i in range(1, len(parts), 2):
        if i + 1 < len(parts):
            header = parts[i].split('\n', 1)[0]  # Prendi prima linea (linguaggio)
            code = '\n'.join(parts[i].split('\n')[1:])  # Resto è il codice
            language = header.strip()

            blocks.append({
                'index': (i - 1) // 2,
                'language': language,
                'code': code.strip(),
                'full': f"```{header}\n{code}```"
            })

    return blocks


def markdown_to_pdf_fixed(md_file, pdf_file=None):
    """
    Converte Markdown in PDF - VERSIONE CORRETTA
    """

    if pdf_file is None:
        pdf_file = Path(md_file).stem + '.pdf'

    # Leggi file
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # ESTRAI BLOCCHI DI CODICE PRIMA DI PROCESSARE
    code_blocks = extract_code_blocks(md_content)
    print(f"\n✅ Estratti {len(code_blocks)} blocchi di codice:")
    for block in code_blocks:
        print(f"   - Blocco {block['index']}: {block['language']} ({len(block['code'].split(chr(10)))} righe)")

    # Crea PDF CON METADATI
    doc = SimpleDocTemplate(
        pdf_file,
        pagesize=A4,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="AI SOC Stack Guide",
        author="Daniele Speziale",
        subject="Security Operations Center - Technical Documentation",
        creator="Python Markdown to PDF Converter"
    )

    # Definisci stili
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='H1Custom',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=12,
        spaceBefore=12
    ))

    styles.add(ParagraphStyle(
        name='H2Custom',
        parent=styles['Heading2'],
        fontSize=18,
        textColor=colors.HexColor('#2563eb'),
        spaceAfter=10,
        spaceBefore=10
    ))

    styles.add(ParagraphStyle(
        name='H3Custom',
        parent=styles['Heading3'],
        fontSize=14,
        textColor=colors.HexColor('#3b82f6'),
        spaceAfter=8,
        spaceBefore=8
    ))

    styles.add(ParagraphStyle(
        name='BodyCustom',
        parent=styles['BodyText'],
        fontSize=11,
        alignment=TA_JUSTIFY,
        spaceAfter=10,
        leading=14
    ))

    # STILE CODICE IMPORTANTE!
    styles.add(ParagraphStyle(
        name='CodeStyle',
        fontName='Courier',
        fontSize=8,
        textColor=colors.HexColor('#ffffff'),  # Bianco puro
        backColor=colors.HexColor('#000000'),  # Nero puro
        leftIndent=20,
        rightIndent=20,
        spaceAfter=15,
        spaceBefore=10,
        leading=10,
        borderPadding=15,
        borderColor=colors.HexColor('#000000'),
        borderWidth=2
    ))

    styles.add(ParagraphStyle(
        name='BulletStyle',
        parent=styles['BodyText'],
        fontSize=11,
        spaceAfter=6,
        leftIndent=30,
        leading=14
    ))

    # PARSE RIGA PER RIGA
    story = []
    lines = md_content.split('\n')
    i = 0
    code_block_index = 0

    while i < len(lines):
        line = lines[i].rstrip()

        # TITOLI H1
        if line.startswith('# '):
            text = clean_markdown_formatting(line[2:].strip())
            try:
                story.append(Paragraph(text, styles['H1Custom']))
                story.append(Spacer(1, 0.15 * inch))
            except Exception as e:
                print(f"⚠️ H1 error: {e}")
            i += 1

        # TITOLI H2
        elif line.startswith('## '):
            text = clean_markdown_formatting(line[3:].strip())
            try:
                story.append(Paragraph(text, styles['H2Custom']))
                story.append(Spacer(1, 0.1 * inch))
            except Exception as e:
                print(f"⚠️ H2 error: {e}")
            i += 1

        # TITOLI H3
        elif line.startswith('### '):
            text = clean_markdown_formatting(line[4:].strip())
            try:
                story.append(Paragraph(text, styles['H3Custom']))
                story.append(Spacer(1, 0.08 * inch))
            except Exception as e:
                print(f"⚠️ H3 error: {e}")
            i += 1

        # BLOCCHI DI CODICE - USA QUELLI ESTRATTI!
        elif line.startswith('```'):
            if code_block_index < len(code_blocks):
                block = code_blocks[code_block_index]
                code_text = block['code']
                language = block['language']

                # Aggiungi header con linguaggio
                if language:
                    story.append(Paragraph(f"<b>Code: {language}</b>", styles['H3Custom']))

                # Crea una TABLE con sfondo nero
                try:
                    # Preformatted dentro una table con backColor
                    code_para = Preformatted(code_text, styles['CodeStyle'])

                    # Table con 1 colonna
                    code_table = Table([[code_para]], colWidths=[7.5 * inch])
                    code_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#000000')),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#ffffff')),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                        ('FONTNAME', (0, 0), (-1, -1), 'Courier'),
                        ('FONTSIZE', (0, 0), (-1, -1), 8),
                        ('LEFTPADDING', (0, 0), (-1, -1), 15),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 15),
                        ('TOPPADDING', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                        ('BORDER', (0, 0), (-1, -1), 1),
                        ('BORDERCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
                    ]))

                    story.append(code_table)
                    print(f"✓ Aggiunto blocco {code_block_index}: {language} ({len(code_text.split(chr(10)))} righe)")
                except Exception as e:
                    print(f"✗ Errore blocco {code_block_index}: {e}")
                    import traceback
                    traceback.print_exc()

                story.append(Spacer(1, 0.15 * inch))
                code_block_index += 1

            # Salta al prossimo ``` nel file
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                i += 1
            i += 1

        # LISTE
        elif line.startswith('- ') or line.startswith('* '):
            text = clean_markdown_formatting(line[2:].strip())
            try:
                story.append(Paragraph(f"• {text}", styles['BulletStyle']))
            except Exception as e:
                print(f"⚠️ List error: {e}")
            i += 1

        # RIGHE VUOTE
        elif line.strip() == '':
            story.append(Spacer(1, 0.05 * inch))
            i += 1

        # SEPARATORI
        elif line.strip() in ['---', '***', '___']:
            story.append(Spacer(1, 0.1 * inch))
            i += 1

        # PARAGRAFI
        elif line.strip():
            text = clean_markdown_formatting(line.strip())
            try:
                story.append(Paragraph(text, styles['BodyCustom']))
            except Exception as e:
                print(f"⚠️ Paragraph error: {str(e)[:80]}")
                safe_text = escape_for_reportlab(line.strip())
                story.append(Paragraph(safe_text, styles['BodyCustom']))
            i += 1
        else:
            i += 1

    # BUILD PDF
    try:
        doc.build(story)
        print(f"\n✅ PDF CREATO!")
        print(f"   File: {pdf_file}")
        print(f"   Dimensione: {Path(pdf_file).stat().st_size / 1024:.1f} KB")
        return True

    except Exception as e:
        print(f"❌ Errore: {e}")
        return False


# ========== UTILIZZO ==========

if __name__ == "__main__":
    import sys

    md_file = 'ai_soc_stack_guide.md'
    pdf_file = 'ai_soc_stack_guide.pdf'

    if not Path(md_file).exists():
        print(f"❌ File non trovato: {md_file}")
        sys.exit(1)

    print("=" * 70)
    print("🔄 CONVERSIONE MARKDOWN → PDF (VERSIONE CORRETTA)")
    print("=" * 70)

    markdown_to_pdf_fixed(md_file, pdf_file)