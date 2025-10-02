#
# markdown_to_pdf.py - Convertitore Markdown a PDF Professionale
# Copyright 2025 TIM SPA
# Author: Daniele Speziale
# Manager: Cinzia Pontoni
# Filename: markdown_to_pdf.py
# Created: 30/09/25
# Description: Script per convertire documentazione Markdown in PDF professionale
#

import markdown
import pdfkit
import os
import sys
import argparse
import requests
from pathlib import Path
from datetime import datetime
import base64
import tempfile
import webbrowser


class MarkdownToPdfConverter:
    """Convertitore Markdown a PDF con styling professionale TIM"""

    def __init__(self):
        self.tim_blue = "#0066CC"
        self.tim_light_blue = "#E6F2FF"
        self.tim_dark_blue = "#003366"
        self.setup_css_styles()

    def setup_css_styles(self):
        """Definisce gli stili CSS professionali per TIM"""
        self.css_styles = f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        * {{
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 210mm;
            margin: 0 auto;
            padding: 20mm;
            background: white;
        }}

        /* Header con logo TIM */
        .tim-header {{
            text-align: center;
            margin-bottom: 40px;
            padding: 30px 0;
            border-bottom: 3px solid {self.tim_blue};
            background: linear-gradient(135deg, {self.tim_light_blue} 0%, white 100%);
        }}

        .tim-logo {{
            max-width: 150px;
            margin-bottom: 20px;
        }}

        /* Titoli */
        h1 {{
            color: {self.tim_blue};
            font-size: 2.5em;
            font-weight: 700;
            margin: 30px 0 20px 0;
            text-align: center;
            border-bottom: 2px solid {self.tim_blue};
            padding-bottom: 15px;
        }}

        h2 {{
            color: {self.tim_dark_blue};
            font-size: 1.8em;
            font-weight: 600;
            margin: 25px 0 15px 0;
            padding: 10px 0 5px 15px;
            border-left: 4px solid {self.tim_blue};
            background: {self.tim_light_blue};
        }}

        h3 {{
            color: {self.tim_blue};
            font-size: 1.4em;
            font-weight: 600;
            margin: 20px 0 10px 0;
            padding-left: 10px;
        }}

        h4 {{
            color: {self.tim_dark_blue};
            font-size: 1.2em;
            font-weight: 500;
            margin: 15px 0 8px 0;
        }}

        /* Paragrafi e testo */
        p {{
            margin: 12px 0;
            text-align: justify;
        }}

        /* Codice */
        code {{
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 4px;
            padding: 2px 6px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 0.9em;
            color: #d63384;
        }}

        pre {{
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 15px;
            overflow-x: auto;
            margin: 15px 0;
        }}

        pre code {{
            background: none;
            border: none;
            padding: 0;
            color: #333;
        }}

        /* Tabelle */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 0.9em;
        }}

        th {{
            background: {self.tim_blue};
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}

        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #dee2e6;
        }}

        tr:nth-child(even) {{
            background: {self.tim_light_blue};
        }}

        tr:hover {{
            background: #f1f8ff;
        }}

        /* Liste */
        ul, ol {{
            padding-left: 25px;
            margin: 12px 0;
        }}

        li {{
            margin: 5px 0;
        }}

        /* Blockquote */
        blockquote {{
            border-left: 4px solid {self.tim_blue};
            background: {self.tim_light_blue};
            margin: 15px 0;
            padding: 10px 15px;
            font-style: italic;
        }}

        /* Link */
        a {{
            color: {self.tim_blue};
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        /* Badges e alert */
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: 500;
            margin: 2px;
        }}

        .badge-info {{
            background: {self.tim_blue};
            color: white;
        }}

        /* Footer */
        .tim-footer {{
            margin-top: 50px;
            padding: 30px 0;
            border-top: 2px solid {self.tim_blue};
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}

        /* Interruzioni di pagina */
        .page-break {{
            page-break-before: always;
        }}

        /* Print styles */
        @media print {{
            body {{
                margin: 0;
                padding: 15mm;
            }}

            .page-break {{
                page-break-before: always;
            }}
        }}
        </style>
        """

    def download_tim_logo(self):
        """Scarica il logo TIM e lo converte in base64"""
        try:
            # URL logo TIM (Wikipedia)
            logo_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/TIM_logo_2016.svg/200px-TIM_logo_2016.svg.png"

            response = requests.get(logo_url, timeout=10)
            if response.status_code == 200:
                logo_base64 = base64.b64encode(response.content).decode('utf-8')
                return f"data:image/png;base64,{logo_base64}"
            else:
                print(f"⚠️  Impossibile scaricare il logo TIM (status: {response.status_code})")
                return None
        except Exception as e:
            print(f"⚠️  Errore download logo TIM: {e}")
            return None

    def process_markdown_content(self, markdown_content):
        """Processa il contenuto Markdown e aggiunge header/footer TIM"""

        # Scarica logo TIM
        tim_logo_data = self.download_tim_logo()

        # Header TIM
        tim_header = f"""
        <div class="tim-header">
            {f'<img src="{tim_logo_data}" alt="TIM Logo" class="tim-logo">' if tim_logo_data else ''}
            <h1 style="margin: 0; color: {self.tim_blue};">TIM S.p.A.</h1>
            <p style="margin: 5px 0; color: {self.tim_dark_blue}; font-weight: 500;">
                Sicurezza Cyber & Digital Operations - SEC.CS.CDO
            </p>
        </div>
        """

        # Footer TIM
        tim_footer = f"""
        <div class="tim-footer">
            <hr style="border: 1px solid {self.tim_blue}; margin: 20px 0;">
            <p><strong>TIM S.p.A.</strong> - Sicurezza Cyber & Digital Operations</p>
            <p>Documento generato il {datetime.now().strftime('%d/%m/%Y alle %H:%M')}</p>
            <p>Autore: <strong>Daniele Speziale</strong> | Manager: <strong>Cinzia Pontoni</strong></p>
            <p style="font-size: 0.8em; color: #999;">
                © 2025 TIM S.p.A. - Tutti i diritti riservati
            </p>
        </div>
        """

        # Converte Markdown in HTML
        md = markdown.Markdown(extensions=[
            'extra',  # Tabelle e funzionalità extra
            'codehilite',  # Syntax highlighting
            'toc',  # Table of contents
            'fenced_code',  # Code blocks
            'tables'  # Supporto tabelle
        ])

        html_content = md.convert(markdown_content)

        # Processa emoji e simboli speciali
        html_content = self.process_emoji(html_content)

        # HTML completo
        full_html = f"""
        <!DOCTYPE html>
        <html lang="it">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Documentazione TIM - Complex System</title>
            {self.css_styles}
        </head>
        <body>
            {tim_header}
            <div class="content">
                {html_content}
            </div>
            {tim_footer}
        </body>
        </html>
        """

        return full_html

    def process_emoji(self, html_content):
        """Converte emoji markdown in testo o simboli HTML"""
        emoji_map = {
            '🔄': '🔄',  # Mantiene emoji se supportate
            '🎯': '🎯',
            '🏗️': '🏗️',
            '🗂️': '🗂️',
            '⚙️': '⚙️',
            '🔧': '🔧',
            '📊': '📊',
            '🚀': '🚀',
            '💻': '💻',
            '🔍': '🔍',
            '🛠️': '🛠️',
            '📖': '📖',
            '🔐': '🔐',
            '📝': '📝',
            '✨': '✨',
            '🏢': '🏢',
            '🧵': '🧵',
            '📋': '📋',
            '🎨': '🎨',
            '📈': '📈',
            '❌': '❌',
            '✅': '✓',
            '⚠️': '⚠',
            '📞': '📞',
            '📄': '📄',
            '⚖️': '⚖',
            '❤️': '♥'
        }

        for emoji, replacement in emoji_map.items():
            html_content = html_content.replace(emoji, replacement)

        return html_content

    def convert_to_pdf(self, markdown_file, output_file=None, open_pdf=False):
        """Converte file Markdown in PDF"""

        print(f"📄 Conversione Markdown → PDF: {markdown_file}")

        # Verifica file input
        if not Path(markdown_file).exists():
            raise FileNotFoundError(f"File Markdown non trovato: {markdown_file}")

        # Leggi contenuto Markdown
        with open(markdown_file, 'r', encoding='utf-8') as f:
            markdown_content = f.read()

        # Processa contenuto
        html_content = self.process_markdown_content(markdown_content)

        # File output
        if not output_file:
            output_file = Path(markdown_file).stem + "_TIM.pdf"

        # Crea file HTML temporaneo
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_html:
            temp_html.write(html_content)
            temp_html_path = temp_html.name

        try:
            # Opzioni PDF
            options = {
                'page-size': 'A4',
                'margin-top': '15mm',
                'margin-right': '15mm',
                'margin-bottom': '15mm',
                'margin-left': '15mm',
                'encoding': "UTF-8",
                'no-outline': None,
                'enable-local-file-access': None,
                'print-media-type': None,
                'disable-smart-shrinking': None,
                'zoom': '0.8'
            }

            # Converte in PDF
            print("🔄 Generazione PDF in corso...")
            pdfkit.from_file(temp_html_path, output_file, options=options)

            print(f"✅ PDF generato con successo: {output_file}")

            # Apri PDF se richiesto
            if open_pdf:
                try:
                    if sys.platform.startswith('win'):
                        os.startfile(output_file)
                    elif sys.platform.startswith('darwin'):
                        os.system(f'open "{output_file}"')
                    else:
                        os.system(f'xdg-open "{output_file}"')
                    print(f"📖 PDF aperto: {output_file}")
                except Exception as e:
                    print(f"⚠️  Impossibile aprire PDF automaticamente: {e}")

            return output_file

        except Exception as e:
            raise Exception(f"Errore conversione PDF: {e}")

        finally:
            # Pulisci file temporaneo
            try:
                os.unlink(temp_html_path)
            except:
                pass

    def create_sample_markdown(self):
        """Crea un file Markdown di esempio"""
        sample_content = """# 🔄 COMPLEX - Sistema Esempio

## 📋 Panoramica

Questo è un **documento di esempio** per testare la conversione Markdown → PDF con stili TIM professionali.

### ✨ Caratteristiche

- ✅ **Styling professionale** con colori TIM
- ✅ **Logo aziendale** integrato
- ✅ **Tabelle formattate**
- ✅ **Codice evidenziato**

## 📊 Tabella Esempio

| Componente | Stato | Note |
|------------|-------|------|
| Database Manager | ✅ Attivo | Connessioni OK |
| Query Processor | ✅ Attivo | Performance ottimali |
| Excel Generator | ✅ Attivo | Report funzionanti |

## 💻 Esempio Codice

```python
# Esempio configurazione
config = {
    "databases": {
        "oracle_iam": {
            "type": "oracle",
            "host": "localhost",
            "port": 1521
        }
    }
}
```

## 🔧 Note Tecniche

> **Importante:** Questo documento dimostra la capacità di conversione PDF con formattazione professionale TIM.

### 📝 Lista Funzionalità

1. **Conversione automatica** Markdown → HTML → PDF
2. **Styling TIM** con colori e font aziendali
3. **Header/Footer** personalizzati
4. **Supporto emoji** e simboli speciali

---

**Documento generato dal sistema TIM Complex**  
*Sviluppato da Daniele Speziale - Manager: Cinzia Pontoni*
"""

        with open('sample_documentation.md', 'w', encoding='utf-8') as f:
            f.write(sample_content)

        print("📝 File esempio creato: sample_documentation.md")
        return 'sample_documentation.md'


def check_dependencies():
    """Verifica dipendenze necessarie"""
    missing_deps = []

    try:
        import markdown
    except ImportError:
        missing_deps.append('markdown')

    try:
        import pdfkit
    except ImportError:
        missing_deps.append('pdfkit')

    try:
        import requests
    except ImportError:
        missing_deps.append('requests')

    # Verifica wkhtmltopdf
    try:
        import pdfkit
        pdfkit.configuration()
    except Exception as e:
        print(f"⚠️  wkhtmltopdf non trovato: {e}")
        print("📥 Installa da: https://wkhtmltopdf.org/downloads.html")
        missing_deps.append('wkhtmltopdf')

    if missing_deps:
        print(f"❌ Dipendenze mancanti: {', '.join(missing_deps)}")
        print("\n📦 Installa con:")
        print("pip install markdown pdfkit requests")
        print("+ Installa wkhtmltopdf dal sito ufficiale")
        return False

    return True


def main():
    """Funzione principale"""

    parser = argparse.ArgumentParser(
        description='Convertitore Markdown → PDF con styling TIM professionale',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi d'uso:
  python markdown_to_pdf.py doc.md                    # Converte doc.md → doc_TIM.pdf
  python markdown_to_pdf.py doc.md -o report.pdf     # Output personalizzato
  python markdown_to_pdf.py doc.md --open            # Apri PDF dopo conversione
  python markdown_to_pdf.py --sample                 # Crea file esempio
        """
    )

    parser.add_argument('input_file', default="..\\complex_documentation.md", nargs='?', help='File Markdown da convertire')
    parser.add_argument('-o', '--output', help='File PDF output')
    parser.add_argument('--open', action='store_true', help='Apri PDF dopo conversione')
    parser.add_argument('--sample', action='store_true', help='Crea file Markdown esempio')

    args = parser.parse_args()

    print("=" * 60)
    print("📄 MARKDOWN → PDF CONVERTER - TIM Professional Edition")
    print("Copyright 2025 TIM S.p.A. - Daniele Speziale")
    print("=" * 60)

    # Verifica dipendenze
    if not check_dependencies():
        sys.exit(1)

    # Crea converter
    converter = MarkdownToPdfConverter()

    # Modalità esempio
    if args.sample:
        sample_file = converter.create_sample_markdown()
        converter.convert_to_pdf(sample_file, open_pdf=True)
        return

    # Verifica input
    if not args.input_file:
        parser.print_help()
        return

    try:
        # Converte file
        output_file = converter.convert_to_pdf(
            args.input_file,
            args.output,
            args.open
        )

        # Info file generato
        file_size = Path(output_file).stat().st_size / 1024  # KB
        print(f"📊 Dimensione PDF: {file_size:.1f} KB")
        print(f"📁 Percorso completo: {Path(output_file).absolute()}")

        print(f"\n✅ Conversione completata con successo!")

    except Exception as e:
        print(f"\n❌ ERRORE: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()