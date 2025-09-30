#
# GENERATE_EXCEL_REPORTS.py - Script per generare report Excel
# Copyright 2025 TIM SPA
# Author Daniele Speziale
# Filename: Complex/generate_excel_reports.py
# Created 29/09/25
# Description: Script standalone per generare report Excel multi-foglio
#
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from Complex.Core.excel_report_generator import ExcelReportGenerator

def setup_logging(config: Dict[str, Any]):
    """Configura il sistema di logging"""
    log_level = config['execution'].get('log_level', 'INFO')
    log_directory = config['execution'].get('log_directory', 'logs')

    Path(log_directory).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"excel_reports_{timestamp}.log"
    log_filepath = Path(log_directory) / log_filename

    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filepath, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Fix console Windows
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except AttributeError:
            pass

    print(f"LOGS: File di log creato in {log_filepath}")
    return log_filepath

def load_config() -> Dict[str, Any]:
    """Carica la configurazione dal file config.json"""
    config_path = Path('config.json')

    if not config_path.exists():
        raise FileNotFoundError("File config.json non trovato")

    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def validate_excel_config(config: Dict[str, Any]):
    """Valida la configurazione per report Excel"""
    if 'excel_reports' not in config:
        raise ValueError("Sezione 'excel_reports' mancante in config.json")

    if not config['excel_reports']:
        raise ValueError("Nessun report Excel configurato")

    # Valida ogni report
    for idx, report in enumerate(config['excel_reports']):
        report_id = f"Report {idx + 1} ({report.get('name', 'unnamed')})"

        # Campi obbligatori
        if 'name' not in report:
            raise ValueError(f"{report_id}: Campo 'name' mancante")

        if 'sheets' not in report or not report['sheets']:
            raise ValueError(f"{report_id}: Nessun foglio configurato")

        # Valida ogni foglio
        for sheet_idx, sheet in enumerate(report['sheets']):
            sheet_id = f"{report_id}, Foglio {sheet_idx + 1} ({sheet.get('name', 'unnamed')})"

            if 'name' not in sheet:
                raise ValueError(f"{sheet_id}: Campo 'name' mancante")

            if 'database' not in sheet:
                raise ValueError(f"{sheet_id}: Campo 'database' mancante")

            # Deve avere almeno una sorgente SQL
            sql_sources = ['sql', 'sql_file', 'sql_template']
            if not any(source in sheet for source in sql_sources):
                raise ValueError(f"{sheet_id}: Nessuna sorgente SQL trovata")

            # Verifica database esiste
            if sheet['database'] not in config['databases']:
                raise ValueError(f"{sheet_id}: Database '{sheet['database']}' non trovato")


def print_excel_reports_summary(config: Dict[str, Any]):
    """Mostra riepilogo report Excel configurati"""
    print("\nREPORT EXCEL CONFIGURATI:")
    print("-" * 70)

    for report in config.get('excel_reports', []):
        report_name = report.get('name', 'unnamed')
        enabled = report.get('enabled', True)
        sheets = report.get('sheets', [])

        status = "ABILITATO" if enabled else "DISABILITATO"
        print(f"\n  {report_name} [{status}] - {len(sheets)} fogli:")

        for sheet in sheets:
            sheet_name = sheet.get('name', 'unnamed')
            database = sheet.get('database', 'unknown')

            # Determina tipo SQL
            if 'sql_file' in sheet:
                sql_type = f"File: {sheet['sql_file']}"
            elif 'sql_template' in sheet:
                sql_type = "Template con parametri"
            elif 'sql' in sheet and isinstance(sheet['sql'], list):
                sql_type = f"Array ({len(sheet['sql'])} righe)"
            else:
                sql_type = "SQL inline"

            print(f"    • {sheet_name} <- [{database}] ({sql_type})")


def print_results_summary(results: list):
    """Stampa riepilogo risultati generazione"""
    print("\n" + "=" * 70)
    print("RIEPILOGO GENERAZIONE REPORT EXCEL")
    print("=" * 70)

    total_reports = len(results)
    successful_reports = sum(1 for r in results if r.get('success', False))

    print(f"\nReport processati: {total_reports}")
    print(f"Report generati con successo: {successful_reports}")
    print(f"Report con errori: {total_reports - successful_reports}")

    for result in results:
        report_name = result.get('report_name', 'unknown')

        if result.get('success', False):
            print(f"\n✓ {report_name}")
            print(f"  File: {result.get('filepath', 'N/A')}")
            print(f"  Fogli creati: {len(result.get('sheets_created', []))}")

            for sheet_info in result.get('sheets_created', []):
                print(f"    • {sheet_info['name']}: {sheet_info['rows']:,} righe, {sheet_info['columns']} colonne")
        else:
            print(f"\n✗ {report_name} - FALLITO")
            for error in result.get('errors', []):
                print(f"  Errore: {error}")

    print("\n" + "=" * 70)


def main():
    """Funzione principale"""
    print("=" * 70)
    print("EXCEL REPORT GENERATOR - Generazione Report Multi-Foglio")
    print("=" * 70)

    try:
        # Carica configurazione
        print("\nCONFIG: Caricamento configurazione...")
        config = load_config()
        validate_excel_config(config)
        print("OK: Configurazione valida")

        # Setup logging
        log_filepath = setup_logging(config)

        # Mostra riepilogo
        print_excel_reports_summary(config)

        # Test connessioni database
        print("\nTEST: Verifica connessioni database...")
        from Complex.Core.database_manager import DatabaseManager

        db_manager = DatabaseManager(config)

        # Trova tutti i database usati nei report
        used_databases = set()
        for report in config.get('excel_reports', []):
            if not report.get('enabled', True):
                continue
            for sheet in report.get('sheets', []):
                used_databases.add(sheet.get('database'))

        # Testa solo i database necessari
        connection_ok = True
        for db_name in used_databases:
            if db_manager.test_connection(db_name):
                print(f"  ✓ [{db_name}] connesso")
            else:
                print(f"  ✗ [{db_name}] ERRORE connessione")
                connection_ok = False

        if not connection_ok:
            response = input("\nContinuare comunque? (y/N): ")
            if response.lower() != 'y':
                print("Operazione annullata")
                return

        # Genera report
        print(f"\nAVVIO: Generazione report Excel...")
        generator = ExcelReportGenerator(config)
        results = generator.generate_all_reports()

        # Mostra risultati
        print_results_summary(results)

        print(f"\nCOMPLETATO: Processo completato!")
        print(f"LOG: Dettagli completi in {log_filepath}")

        # Directory output
        output_dir = config.get('execution', {}).get('excel_output_directory', 'reports')
        print(f"REPORTS: File Excel salvati in {output_dir}/")

    except KeyboardInterrupt:
        print("\nINTERROTTO: Operazione interrotta dall'utente")
        sys.exit(1)

    except Exception as e:
        print(f"\nERRORE CRITICO: {e}")
        logging.error(f"Errore critico: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()