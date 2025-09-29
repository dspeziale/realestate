#
# Enhanced Database Transfer Tool - Versione con supporto query complesse
# Copyright 2025 TIM SPA
# Author Daniele Speziale
# Filename app.py
# Created 24/09/25
# Update  29/09/25
# Enhanced by: Query Multiiriga, Template, File esterni
#
import json
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from Complex.Core.database_manager import DatabaseManager
from Complex.Core.enhanced_multi_query_processor import EnhancedMultiQueryProcessor

def setup_logging(config: Dict[str, Any]):
    """Configura il sistema di logging con directory separata"""
    log_level = config['execution'].get('log_level', 'INFO')
    log_directory = config['execution'].get('log_directory', 'logs')

    # Crea directory logs se non esiste
    if not os.path.exists(log_directory):
        os.makedirs(log_directory, exist_ok=True)

    # Nome file log con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"db_transfer_enhanced_{timestamp}.log"
    log_filepath = os.path.join(log_directory, log_filename)

    # Configura logging con file e console
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filepath, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Fix per console Windows
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
        raise FileNotFoundError("File config.json non trovato nella directory corrente")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except json.JSONDecodeError as e:
        raise ValueError(f"Errore parsing config.json: {e}")

def validate_enhanced_config(config: Dict[str, Any]) -> bool:
    """Valida la configurazione con supporto query complesse"""
    # Controlla sezioni principali
    required_sections = ['databases', 'queries', 'execution']
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Sezione '{section}' mancante in config.json")

    # Controlla che ci siano database
    if not config['databases']:
        raise ValueError("Nessun database configurato")

    # Controlla che ci siano query
    if not config['queries']:
        raise ValueError("Nessuna query configurata")

    # Valida ogni query con supporto formati multipli
    for i, query in enumerate(config['queries']):
        query_id = f"Query {i + 1} ({query.get('name', 'unnamed')})"

        # Campi base sempre richiesti
        required_base_fields = ['name', 'source_database', 'destination_database', 'destination_table']
        for field in required_base_fields:
            if field not in query:
                raise ValueError(f"{query_id}: Campo '{field}' mancante")

        # Valida che ci sia almeno una sorgente SQL
        sql_sources = ['sql', 'sql_file', 'sql_template']
        found_sources = [source for source in sql_sources if source in query]

        if not found_sources:
            raise ValueError(f"{query_id}: Nessuna sorgente SQL trovata. Richiesto uno tra: {sql_sources}")

        if len(found_sources) > 1:
            raise ValueError(f"{query_id}: Multiple sorgenti SQL trovate: {found_sources}. Usare solo una.")

        # Validazione specifica per template
        if 'sql_template' in query:
            if 'parameters' not in query:
                raise ValueError(f"{query_id}: sql_template richiede sezione 'parameters'")

        # Verifica che i database esistano nella configurazione
        source_db = query['source_database']
        dest_db = query['destination_database']

        if source_db not in config['databases']:
            raise ValueError(f"{query_id}: Database sorgente '{source_db}' non trovato")

        if dest_db not in config['databases']:
            raise ValueError(f"{query_id}: Database destinazione '{dest_db}' non trovato")

        # Verifica tipo database destinazione (per ora solo SQL Server)
        dest_config = config['databases'][dest_db]
        if dest_config.get('type') != 'mssql':
            raise ValueError(f"{query_id}: Database destinazione '{dest_db}' deve essere di tipo 'mssql'")

    return True

def print_database_summary(config: Dict[str, Any]):
    """Mostra riepilogo database configurati"""
    print("\nDATABASE CONFIGURATI:")
    print("-" * 50)

    for db_name, db_config in config['databases'].items():
        db_type = db_config.get('type', 'unknown')
        if db_type == 'oracle':
            host_info = f"{db_config['host']}:{db_config['port']}"
            service_info = db_config.get('service_name', db_config.get('sid', 'N/A'))
            print(f"  {db_name} (Oracle): {host_info}/{service_info}")
        elif db_type == 'mssql':
            server_info = f"{db_config['server']}/{db_config['database']}"
            print(f"  {db_name} (SQL Server): {server_info}")
        else:
            print(f"  {db_name} (Tipo sconosciuto)")

def print_enhanced_queries_summary(config: Dict[str, Any]):
    """Mostra riepilogo query configurate con tipi SQL"""
    print("\nQUERY CONFIGURATE (ENHANCED):")
    print("-" * 50)

    for i, query in enumerate(config['queries'], 1):
        source_db = query['source_database']
        dest_db = query['destination_database']
        dest_table = query['destination_table']
        dest_schema = query.get('destination_schema', config['databases'][dest_db].get('default_schema', 'dbo'))

        # Determina tipo sorgente SQL
        if 'sql' in query and isinstance(query['sql'], list):
            sql_type = "Array Multiriga"
            line_count = len(query['sql'])
            sql_info = f"({line_count} righe)"
        elif 'sql' in query:
            sql_type = "Stringa Inline"
            sql_info = f"({len(query['sql'])} caratteri)"
        elif 'sql_file' in query:
            sql_type = "File Esterno"
            sql_info = f"({query['sql_file']})"
        elif 'sql_template' in query:
            sql_type = "Template"
            param_count = len(query.get('parameters', {}))
            sql_info = f"({param_count} parametri)"
        else:
            sql_type = "Sconosciuto"
            sql_info = ""

        print(f"  {i}. {query['name']} [{sql_type}] {sql_info}")
        print(f"     Da: [{source_db}] -> A: [{dest_db}].[{dest_schema}].[{dest_table}]")

def print_enhanced_results_summary(results: Dict[str, Any]):
    """Stampa riepilogo risultati con info aggiuntive"""
    print("\n" + "=" * 60)
    print("RIEPILOGO ESECUZIONE ENHANCED")
    print("=" * 60)

    # Query eseguite con dettagli SQL
    if results['executed_queries']:
        print("\nQUERY ESEGUITE:")
        for query_name, info in results['executed_queries'].items():
            sql_type = info.get('sql_type', 'unknown')
            print(f"   OK {query_name} [{sql_type}]: {info['rows']:,} righe")
            print(f"      {info['source']} -> {info['destination']} ({info['table']})")

    # Tabelle scritte
    if results['written_tables']:
        print(f"\nTABELLE SCRITTE ({len(results['written_tables'])}):")
        for table_info in results['written_tables']:
            print(f"   OK {table_info['table']} su [{table_info['database']}]")

    # Errori
    if results['errors']:
        print(f"\nERRORI ({len(results['errors'])}):")
        for error in results['errors']:
            print(f"   ERRORE {error}")

    print("\n" + "=" * 60)

def main():
    """Funzione principale enhanced con supporto query complesse"""
    print("AVVIO Enhanced Database Transfer Tool")
    print("Supporto: Query Multiriga, Template, File esterni, Parametri")
    print("=" * 70)

    try:
        # Carica configurazione
        print("CONFIG: Caricamento configurazione enhanced...")
        config = load_config()
        validate_enhanced_config(config)
        print("OK: Configurazione enhanced valida")

        # Setup logging
        log_filepath = setup_logging(config)
        logging.getLogger(__name__)

        # Mostra riepiloghi enhanced
        print_database_summary(config)
        print_enhanced_queries_summary(config)

        # Inizializza database manager
        db_manager = DatabaseManager(config)

        # Test connessioni
        print(f"\nTEST: Connessioni database ({len(config['databases'])} database)...")
        connection_results = db_manager.test_all_connections()

        failed_connections = [db for db, result in connection_results.items() if not result]

        if failed_connections:
            print(f"ERRORE: Connessioni fallite: {', '.join(failed_connections)}")
            response = input("Continuare comunque? (y/N): ")
            if response.lower() != 'y':
                print("Operazione annullata")
                return
        else:
            print("OK: Tutte le connessioni")

        # Esecuzione pipeline enhanced
        print(f"\nAVVIO: Trasferimento dati enhanced ({len(config['queries'])} query)...")
        processor = EnhancedMultiQueryProcessor(config)

        # Genera file di esempio se necessario
        query_dir = Path(config.get('execution', {}).get('query_directory', 'queries'))
        if not query_dir.exists() or not any(query_dir.glob('*.sql')):
            print("SETUP: Generazione file SQL di esempio...")
            processor.generate_sample_query_files()

        results = processor.execute_all_queries()

        # Riepilogo enhanced
        print_enhanced_results_summary(results)

        # Verifica finale con dettagli
        if results['written_tables']:
            print(f"\nVERIFICA: Tabelle create...")
            for table_info in results['written_tables']:
                info = processor.get_table_info(table_info['database'], table_info['table'])
                if info['exists']:
                    print(f"   OK {info['table_name']}: {info['row_count']:,} righe, {len(info['columns'])} colonne")

                    # Mostra alcune colonne per verifica
                    if info['columns']:
                        col_sample = info['columns'][:3]
                        col_names = [col['name'] for col in col_sample]
                        col_suffix = "..." if len(info['columns']) > 3 else ""
                        print(f"      Colonne: {', '.join(col_names)}{col_suffix}")
                else:
                    print(f"   ERRORE {table_info['table']}: Verifica fallita")

        print(f"\nCOMPLETATO: Processo enhanced completato!")
        print(f"LOG: Dettagli completi in {log_filepath}")

        # Suggerimenti per l'uso
        print(f"\nSUGGERIMENTI:")
        print(f"  • File SQL esterni: Posto in {query_dir}/")
        print(f"  • Template con parametri: Usare {{param_name}} nelle query")
        print(f"  • Query multiriga: Array di stringhe nel config.json")
        print(f"  • Log dettagliati: Controllare {log_filepath}")

    except KeyboardInterrupt:
        print("\nINTERROTTO: Operazione interrotta dall'utente")
        sys.exit(1)

    except Exception as e:
        print(f"\nERRORE CRITICO: {e}")
        logging.error(f"Errore critico enhanced: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()