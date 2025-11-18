#!/usr/bin/env python3
"""
UTILITY SCRIPT - Elaborazione Report JSON Medical AI

Questo script fornisce funzioni utili per:
- Leggere e validare report JSON
- Convertire JSON in altri formati (CSV, PDF, HTML)
- Estrarre informazioni specifiche
- Generare statistiche
"""

import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class JSONReportReader:
    """Classe per leggere e elaborare report JSON Medical AI"""

    def __init__(self, filepath: str):
        """Inizializza il lettore del report"""
        self.filepath = Path(filepath)
        self.data = None
        self.load()

    def load(self) -> bool:
        """Carica il file JSON"""
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            print(f"✅ Report caricato: {self.filepath}")
            return True
        except FileNotFoundError:
            print(f"❌ File non trovato: {self.filepath}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ JSON non valido: {e}")
            return False

    def validate(self) -> bool:
        """Valida la struttura del JSON"""
        required_keys = ['metadata', 'avvertenze', 'analisi_strutturata', 'informazioni_finali']
        for key in required_keys:
            if key not in self.data:
                print(f"❌ Campo mancante: {key}")
                return False
        print("✅ Report valido")
        return True

    def get_metadata(self) -> Dict:
        """Ritorna i metadati del report"""
        return self.data.get('metadata', {})

    def get_patient_name(self) -> str:
        """Ritorna il nome del paziente"""
        return self.data.get('metadata', {}).get('paziente_id', 'Sconosciuto')

    def get_num_questions(self) -> int:
        """Ritorna il numero di domande"""
        return len(self.data.get('analisi_strutturata', []))

    def get_questions(self) -> List[Dict]:
        """Ritorna tutte le domande e risposte"""
        return self.data.get('analisi_strutturata', [])

    def get_question(self, index: int) -> Optional[Dict]:
        """Ritorna una domanda specifica per indice (0-based)"""
        questions = self.get_questions()
        if 0 <= index < len(questions):
            return questions[index]
        return None

    def get_by_category(self, category: str) -> List[Dict]:
        """Filtra domande per categoria"""
        return [q for q in self.get_questions() if q.get('categoria') == category]

    def get_categories(self) -> List[str]:
        """Ritorna lista di categorie uniche"""
        return list(set(q.get('categoria', 'Generale') for q in self.get_questions()))

    def print_summary(self):
        """Stampa un riassunto del report"""
        meta = self.get_metadata()
        print("\n" + "=" * 70)
        print("RIASSUNTO REPORT")
        print("=" * 70)
        print(f"Paziente: {meta.get('paziente_id', 'N/A')}")
        print(f"Data: {meta.get('data_ora', 'N/A')}")
        print(f"Versione: {meta.get('versione', 'N/A')}")
        print(f"Domande: {self.get_num_questions()}")
        print(f"Documenti analizzati: {meta.get('numero_documenti_analizzati', 'N/A')}")
        print("Categorie:")
        for cat in self.get_categories():
            count = len(self.get_by_category(cat))
            print(f"  - {cat}: {count} domande")
        print("=" * 70 + "\n")

    def print_all_questions(self):
        """Stampa tutte le domande e risposte"""
        for q in self.get_questions():
            print(f"\n{'=' * 70}")
            print(f"#{q['numero']} - {q['categoria']}")
            print(f"{'=' * 70}")
            print(f"Q: {q['domanda']}")
            print(f"\nA: {q['risposta']}")

            if q.get('estratti_documenti'):
                print(f"\n📄 Estratti dai documenti:")
                for estratto in q['estratti_documenti']:
                    print(f"   • {estratto['testo']} (rilevanza: {estratto['rilevanza']})")

    def export_to_csv(self, output_file: str = None) -> str:
        """Esporta il report in formato CSV"""
        if output_file is None:
            patient = self.get_patient_name().replace(" ", "_")
            output_file = f"report_{patient}.csv"

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['#', 'Categoria', 'Domanda', 'Risposta', 'Estratti'])

            for q in self.get_questions():
                estratti = "; ".join([e['testo'][:50] + "..." for e in q.get('estratti_documenti', [])])
                writer.writerow([
                    q['numero'],
                    q['categoria'],
                    q['domanda'],
                    q['risposta'],
                    estratti
                ])

        print(f"✅ CSV esportato: {output_file}")
        return output_file

    def export_to_html(self, output_file: str = None) -> str:
        """Esporta il report in formato HTML"""
        if output_file is None:
            patient = self.get_patient_name().replace(" ", "_")
            output_file = f"report_{patient}.html"

        meta = self.get_metadata()
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Report Medico - {meta.get('paziente_id', 'Paziente')}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        .header {{ background: #1f4788; color: white; padding: 20px; border-radius: 5px; }}
        .metadata {{ background: #e3f2fd; padding: 15px; margin: 20px 0; border-left: 4px solid #1f4788; }}
        .question {{ background: #f5f5f5; padding: 15px; margin: 15px 0; border-left: 4px solid #1565c0; }}
        .category {{ color: #1f4788; font-weight: bold; font-size: 0.9em; }}
        .warning {{ background: #ffcdd2; color: #b71c1c; padding: 15px; margin: 20px 0; border-left: 4px solid #c62828; }}
        .estratti {{ background: #fff9c4; padding: 10px; margin: 10px 0; font-size: 0.9em; }}
        h1 {{ color: #1f4788; }}
        h2 {{ color: #1f4788; border-bottom: 2px solid #1f4788; padding-bottom: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>REPORT MEDICO - AI SYSTEM</h1>
    </div>

    <div class="metadata">
        <h2>Informazioni Report</h2>
        <p><strong>Paziente:</strong> {meta.get('paziente_id', 'N/A')}</p>
        <p><strong>Data:</strong> {meta.get('data_ora', 'N/A')}</p>
        <p><strong>Domande Elaborate:</strong> {self.get_num_questions()}</p>
        <p><strong>Documenti Analizzati:</strong> {meta.get('numero_documenti_analizzati', 'N/A')}</p>
    </div>

    <div class="warning">
        <h3>⚠️ AVVERTENZE IMPORTANTI</h3>
        {json.dumps(self.data.get('avvertenze', {}), indent=2, ensure_ascii=False)}
    </div>

    <h2>Analisi Strutturata</h2>
"""

        for q in self.get_questions():
            html += f"""
    <div class="question">
        <div class="category">{q['categoria']}</div>
        <h3>#{q['numero']}. {q['domanda']}</h3>
        <p>{q['risposta']}</p>
"""
            if q.get('estratti_documenti'):
                html += '<div class="estratti"><strong>Estratti dai documenti:</strong><ul>'
                for e in q['estratti_documenti']:
                    html += f'<li>{e["testo"]} <em>(rilevanza: {e["rilevanza"]})</em></li>'
                html += '</ul></div>'
            html += '</div>'

        html += """
    <div class="metadata">
        <h2>Informazioni Finali</h2>
"""
        finali = self.data.get('informazioni_finali', {})
        for key, value in finali.items():
            html += f"<p><strong>{key}:</strong> {value}</p>"

        html += """
    </div>

    <p style="text-align: center; color: #999; margin-top: 50px;">
        Report generato automaticamente da Medical AI System
    </p>
</body>
</html>
"""

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"✅ HTML esportato: {output_file}")
        return output_file

    def export_to_markdown(self, output_file: str = None) -> str:
        """Esporta il report in formato Markdown"""
        if output_file is None:
            patient = self.get_patient_name().replace(" ", "_")
            output_file = f"report_{patient}.md"

        meta = self.get_metadata()
        md = f"""# Report Medico

**Paziente:** {meta.get('paziente_id', 'N/A')}  
**Data:** {meta.get('data_ora', 'N/A')}  
**Versione:** {meta.get('versione', 'N/A')}  

## ⚠️ Avvertenze Importanti

"""
        for key, value in self.data.get('avvertenze', {}).items():
            md += f"- **{key}:** {value}\n"

        md += "\n## Analisi Strutturata\n"

        for q in self.get_questions():
            md += f"\n### #{q['numero']}. {q['domanda']}\n\n"
            md += f"**Categoria:** {q['categoria']}\n\n"
            md += f"{q['risposta']}\n"

            if q.get('estratti_documenti'):
                md += "\n**Estratti dai documenti:**\n"
                for e in q['estratti_documenti']:
                    md += f"- {e['testo']} *(rilevanza: {e['rilevanza']})*\n"

        md += "\n## Informazioni Finali\n"
        finali = self.data.get('informazioni_finali', {})
        for key, value in finali.items():
            md += f"- **{key}:** {value}\n"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(md)

        print(f"✅ Markdown esportato: {output_file}")
        return output_file

    def get_statistics(self) -> Dict:
        """Genera statistiche sul report"""
        questions = self.get_questions()

        # Calcola lunghezze medie
        avg_q_length = sum(len(q['domanda']) for q in questions) / len(questions) if questions else 0
        avg_a_length = sum(len(q['risposta']) for q in questions) / len(questions) if questions else 0

        # Conta estratti
        total_extracts = sum(len(q.get('estratti_documenti', [])) for q in questions)

        return {
            'numero_domande': len(questions),
            'numero_categorie': len(self.get_categories()),
            'lunghezza_media_domanda': round(avg_q_length, 1),
            'lunghezza_media_risposta': round(avg_a_length, 1),
            'numero_estratti_totali': total_extracts,
            'categorie': self.get_categories()
        }

    def print_statistics(self):
        """Stampa statistiche formattate"""
        stats = self.get_statistics()
        print("\n" + "=" * 70)
        print("STATISTICHE REPORT")
        print("=" * 70)
        print(f"Domande totali: {stats['numero_domande']}")
        print(f"Categorie uniche: {stats['numero_categorie']}")
        print(f"Lunghezza media domanda: {stats['lunghezza_media_domanda']} caratteri")
        print(f"Lunghezza media risposta: {stats['lunghezza_media_risposta']} caratteri")
        print(f"Estratti totali dai documenti: {stats['numero_estratti_totali']}")
        print("=" * 70 + "\n")


# ============================================================================
# SCRIPT DI ESEMPIO - UTILIZZO PRINCIPALE
# ============================================================================

if __name__ == "__main__":
    import sys
    #sys.argv.append("C:\logs\\reports\\report_Daniele Speziale_20251031_114940.json")
    sys.argv.append("C:\logs\\reports\\report_Daniele Speziale_20251031_121320.json")
    sys.argv.append("all")

    if len(sys.argv) < 2:
        print("""
        Utilizzo: python json_report_reader.py <file.json> [opzione]
        
        Opzioni:
          summary      - Stampa un riassunto del report
          all          - Stampa tutte le domande e risposte
          stats        - Stampa statistiche del report
          csv          - Esporta in CSV
          html         - Esporta in HTML
          markdown     - Esporta in Markdown
          validate     - Valida il file JSON
        
        Esempio:
          python json_report_reader.py report_Mario_Rossi_20251031_104500.json summary
          python json_report_reader.py report_Mario_Rossi_20251031_104500.json csv
        """)
        sys.exit(1)

    filepath = sys.argv[1]
    option = sys.argv[2] if len(sys.argv) > 2 else "summary"

    reader = JSONReportReader(filepath)

    if not reader.data:
        sys.exit(1)

    if option == "validate":
        reader.validate()
    elif option == "summary":
        reader.print_summary()
    elif option == "all":
        reader.print_all_questions()
    elif option == "stats":
        reader.print_statistics()
    elif option == "csv":
        reader.export_to_csv()
    elif option == "html":
        reader.export_to_html()
    elif option == "markdown":
        reader.export_to_markdown()
    else:
        print(f"❌ Opzione sconosciuta: {option}")