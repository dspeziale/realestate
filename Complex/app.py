#
# Enhanced Database Transfer Tool - Versione con supporto query complesse
# Copyright 2025 TIM SPA
# Author Daniele Speziale
# Filename app.py
# Created 24/09/25
# Update  30/09/25
# Enhanced by: Query Multiiriga, Template, File esterni, Reports separati, Log cleanup
#
import json
import logging
import sys
import os
import glob
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any

from Complex.Core.database_manager import DatabaseManager
from Complex.Core.enhanced_multi_query_processor import EnhancedMultiQueryProcessor


def cleanup_old_logs(log_directory: str, max_age_days: int = 3):
    """Cancella i file di log più vecchi di max_age_days"""
    try:
        log_path = Path(log_directory)
        if not log_path.exists():
            return

        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        deleted_count = 0

        # Pattern per i file di log del progetto
        log_patterns = [
            "db_transfer_enhanced_*.log",
            "*.log"
        ]

        for pattern in log_patterns:
            for log_file in log_path.glob(pattern):
                try:
                    # Controlla data modifica file
                    file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)

                    if file_mtime < cutoff_date:
                        log_file.unlink()
                        deleted_count += 1
                        print(
                            f"LOG CLEANUP: Eliminato {log_file.name} (creato il {file_mtime.strftime('%d/%m/%Y %H:%M')})")

                except Exception as e:
                    print(f"LOG CLEANUP: Errore eliminando {log_file.name}: {e}")

        if deleted_count > 0:
            print(f"LOG CLEANUP: Eliminati {deleted_count} file di log vecchi (>{max_age_days} giorni)")
        else:
            print(f"LOG CLEANUP: Nessun file di log da eliminare (>{max_age_days} giorni)")

    except Exception as e:
        print(f"LOG CLEANUP: Errore durante pulizia: {e}")


def setup_logging(config: Dict[str, Any]):
    """Configura il sistema di logging con directory separata"""
    log_level = config['execution'].get('log_level', 'INFO')
    log_directory = config['execution'].get('log_directory', 'logs')

    # Crea directory logs se non esiste
    if not os.path.exists(log_directory):
        os.makedirs(log_directory, exist_ok=True)

    # CLEANUP AUTOMATICO: Elimina log vecchi all'avvio
    cleanup_old_logs(log_directory, max_age_days=3)

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


def setup_directories(config: Dict[str, Any]):
    """Configura tutte le directory necessarie incluse quelle per i reports"""
    directories = {
        'logs': config['execution'].get('log_directory', 'logs'),
        'queries': config['execution'].get('query_directory', 'queries'),
        'reports': config['execution'].get('reports_directory', 'reports'),
        'queries_reports': config['execution'].get('reports_query_directory', 'reports/queries')
    }

    created_dirs = []
    for dir_type, dir_path in directories.items():
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            created_dirs.append(f"{dir_type}: {dir_path}")

    if created_dirs:
        print(f"SETUP: Directory create: {', '.join(created_dirs)}")

    return directories


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
            template_params = query.get('template_params', {})
            if not isinstance(template_params, dict):
                raise ValueError(f"{query_id}: template_params deve essere un oggetto JSON")

    return True


def te_all_connections(config: Dict[str, Any]) -> bool:
    """Testa tutte le connessioni database configurate"""
    db_manager = DatabaseManager(config)
    all_success = True

    print("TEST: Verifica connessioni database...")

    for db_name in config['databases'].keys():
        try:
            db_config = config['databases'][db_name]
            db_type = db_config.get('type', 'unknown')

            print(f"   [{db_name}] ({db_type})...", end=' ')

            success = db_manager.test_connection(db_name)
            if success:
                print("OK")
            else:
                print("ERRORE")
                all_success = False

        except Exception as e:
            print(f"ERRORE: {e}")
            all_success = False

    return all_success


def print_enhanced_results_summary(results: Dict[str, Any]):
    """Stampa riepilogo risultati in formato enhanced"""
    print(f"\nRIEPILOGO ESECUZIONE:")
    print(f"{'=' * 50}")

    if results['executed_queries']:
        print(f"QUERY ESEGUITE: {len(results['executed_queries'])}")
        for query_name, info in results['executed_queries'].items():
            print(f"   ✓ {query_name}: {info['rows']:,} righe")
            print(f"     {info['source']} → {info['destination']}.{info['table']}")
            print(f"     Tipo: {info['sql_type']}")

    if results['written_tables']:
        print(f"\nTABELLE SCRITTE: {len(results['written_tables'])}")
        for table in results['written_tables']:
            print(f"   → {table['database']}.{table['table']}")

    if results['errors']:
        print(f"\nERRORI: {len(results['errors'])}")
        for error in results['errors']:
            print(f"   ✗ {error}")


def create_sample_report_queries(reports_query_dir: str):
    """Crea query di esempio per i reports in directory separata"""
    reports_path = Path(reports_query_dir)

    sample_reports = {
        "user_activity_summary.sql": """
-- User Activity Summary Report
-- Riepilogo attività utenti con statistiche aggregate
SELECT 
    u.user_id,
    u.username,
    u.full_name,
    u.department,
    COUNT(DISTINCT s.session_id) as total_sessions,
    MIN(s.login_time) as first_login,
    MAX(s.logout_time) as last_activity,
    AVG(DATEDIFF(minute, s.login_time, s.logout_time)) as avg_session_minutes,
    SUM(CASE WHEN s.login_time >= DATEADD(day, -30, GETDATE()) THEN 1 ELSE 0 END) as sessions_last_30_days
FROM users u
LEFT JOIN user_sessions s ON u.user_id = s.user_id
WHERE u.is_active = 1
GROUP BY u.user_id, u.username, u.full_name, u.department
ORDER BY last_activity DESC;
        """,

        "monthly_performance_report.sql": """
-- Monthly Performance Report
-- Report prestazioni mensili con trend
WITH monthly_stats AS (
    SELECT 
        YEAR(created_date) as report_year,
        MONTH(created_date) as report_month,
        COUNT(*) as total_records,
        COUNT(DISTINCT user_id) as unique_users,
        AVG(processing_time_ms) as avg_processing_time,
        SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_operations,
        SUM(CASE WHEN status = 'ERROR' THEN 1 ELSE 0 END) as failed_operations
    FROM operation_logs
    WHERE created_date >= DATEADD(month, -12, GETDATE())
    GROUP BY YEAR(created_date), MONTH(created_date)
)
SELECT 
    report_year,
    report_month,
    DATENAME(month, DATEFROMPARTS(report_year, report_month, 1)) as month_name,
    total_records,
    unique_users,
    avg_processing_time,
    successful_operations,
    failed_operations,
    CASE 
        WHEN total_records > 0 
        THEN CAST(successful_operations * 100.0 / total_records AS DECIMAL(5,2))
        ELSE 0 
    END as success_rate_percent
FROM monthly_stats
ORDER BY report_year DESC, report_month DESC;
        """,

        "system_health_report.sql": """
-- System Health Report
-- Report salute sistema con metriche chiave
SELECT 
    'Database Connections' as metric_category,
    COUNT(*) as current_value,
    'Active connections to database' as description,
    GETDATE() as snapshot_time
FROM sys.dm_exec_connections

UNION ALL

SELECT 
    'Error Rate',
    COUNT(*),
    'Errors in last 24 hours',
    GETDATE()
FROM error_logs 
WHERE created_date >= DATEADD(day, -1, GETDATE())

UNION ALL

SELECT 
    'Active Users',
    COUNT(DISTINCT user_id),
    'Users active in last hour',
    GETDATE()
FROM user_activity 
WHERE activity_time >= DATEADD(hour, -1, GETDATE())

UNION ALL

SELECT 
    'Pending Jobs',
    COUNT(*),
    'Jobs waiting for execution',
    GETDATE()
FROM job_queue 
WHERE status = 'PENDING';
        """,

        "data_quality_report.sql": """
-- Data Quality Report
-- Report qualità dati con controlli di integrità
WITH quality_checks AS (
    SELECT 
        'Missing Email Addresses' as check_name,
        COUNT(*) as issue_count,
        'users' as table_name,
        'email IS NULL OR email = ''' as condition_desc
    FROM users 
    WHERE email IS NULL OR email = ''

    UNION ALL

    SELECT 
        'Duplicate Records',
        COUNT(*) - COUNT(DISTINCT email),
        'users',
        'Duplicate email addresses'
    FROM users
    WHERE email IS NOT NULL

    UNION ALL

    SELECT 
        'Orphaned Records',
        COUNT(*),
        'user_profiles',
        'No matching user_id in users table'
    FROM user_profiles p
    WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.user_id = p.user_id)

    UNION ALL

    SELECT 
        'Invalid Dates',
        COUNT(*),
        'operations',
        'created_date in future or before 2020'
    FROM operations
    WHERE created_date > GETDATE() OR created_date < '2020-01-01'
)
SELECT 
    check_name,
    table_name,
    issue_count,
    condition_desc,
    CASE 
        WHEN issue_count = 0 THEN 'PASS'
        WHEN issue_count < 10 THEN 'WARNING'
        ELSE 'FAIL'
    END as status,
    GETDATE() as report_generated
FROM quality_checks
ORDER BY issue_count DESC;
        """
    }

    created_reports = []
    for filename, content in sample_reports.items():
        file_path = reports_path / filename
        if not file_path.exists():
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content.strip())
            created_reports.append(filename)

    if created_reports:
        print(f"REPORTS: Creati {len(created_reports)} file di esempio in {reports_path}")
        for report in created_reports:
            print(f"   → {report}")


def main():
    """Funzione principale con supporto enhanced completo"""
    print("=" * 60)
    print("DATABASE TRANSFER TOOL - ENHANCED VERSION")
    print("Copyright 2025 TIM SPA - Enhanced by Daniele Speziale")
    print("=" * 60)

    try:
        # Carica configurazione
        print("INIT: Caricamento configurazione...")
        config = load_config()

        # Setup directory (incluse reports)
        directories = setup_directories(config)

        # Validazione configurazione
        print("INIT: Validazione configurazione enhanced...")
        validate_enhanced_config(config)

        # Setup logging con cleanup automatico
        log_filepath = setup_logging(config)

        # Creazione query di esempio per reports
        #create_sample_report_queries(directories['queries_reports'])

        print(f"INIT: Configurazione caricata ({len(config['databases'])} database, {len(config['queries'])} query)")

        # Test connessioni
        print("\nTEST: Verifica connessioni...")
        connections_ok = te_all_connections(config)

        if not connections_ok:
            response = input("\nALCUNE CONNESSIONI FALLITE. Continuare comunque? (y/N): ")
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

        # Suggerimenti per l'uso con informazioni sui reports
        print(f"\nSUGGERIMENTI:")
        print(f"  • File SQL standard: {directories['queries']}/")
        print(f"  • Query per reports: {directories['queries_reports']}/")
        print(f"  • Output reports: {directories['reports']}/")
        print(f"  • Template con parametri: Usare {{param_name}} nelle query")
        print(f"  • Query multiriga: Array di stringhe nel config.json")
        print(f"  • Log dettagliati: Controllare {log_filepath}")
        print(f"  • Cleanup automatico: Log più vecchi di 3 giorni eliminati all'avvio")

    except KeyboardInterrupt:
        print("\nINTERROTTO: Operazione interrotta dall'utente")
        sys.exit(1)

    except Exception as e:
        print(f"\nERRORE CRITICO: {e}")
        logging.error(f"Errore critico enhanced: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()