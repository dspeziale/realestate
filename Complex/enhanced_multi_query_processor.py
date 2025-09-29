#
# ENHANCED_MULTI_QUERY_PROCESSOR.py - MULTITASKING EDITION
# Copyright 2025 TIM SPA
# Author Daniele Speziale
# Filename: Complex/enhanced_multi_query_processor.py
# Created 25/09/25
# Update  29/09/25
# Enhanced by: Multitasking con ThreadPoolExecutor + filtro enabled queries
#
import logging
import pandas as pd
import warnings
import re
from typing import Dict, Any, Tuple, List
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from Complex.database_manager import DatabaseManager

# Sopprime warning pandas
warnings.filterwarnings('ignore', message='.*pandas only supports SQLAlchemy.*')


class EnhancedMultiQueryProcessor:
    """Processore per query multi-database con supporto multitasking e filtro enabled"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_manager = DatabaseManager(config)
        self.logger = logging.getLogger(__name__)
        self.batch_size = min(config['execution']['batch_size'], 5000)
        self.drop_existing = config['execution']['drop_existing_tables']

        # Filtra solo le query abilitate (enabled: true)
        all_queries = config.get('queries', [])
        self.queries = [q for q in all_queries if q.get('enabled', True)]

        # Log statistiche queries
        disabled_count = len(all_queries) - len(self.queries)
        self.logger.info(f"SETUP: {len(self.queries)} query abilitate, {disabled_count} disabilitate")

        # Directory per file SQL esterni
        self.query_directory = Path(config.get('execution', {}).get('query_directory', 'queries'))

        # Crea directory queries se non esiste
        if not self.query_directory.exists():
            self.query_directory.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"SETUP: Directory queries creata: {self.query_directory}")

        # Lock per thread-safety su operazioni condivise
        self._results_lock = Lock()
        self._log_lock = Lock()

        # Numero di worker per multitasking (default: 12)
        self.max_workers = config.get('execution', {}).get('max_workers', 12)

    def _thread_safe_log(self, level: str, message: str):
        """Log thread-safe per multitasking"""
        with self._log_lock:
            if level == 'info':
                self.logger.info(message)
            elif level == 'warning':
                self.logger.warning(message)
            elif level == 'error':
                self.logger.error(message)

    def resolve_sql_query(self, query_config: Dict[str, Any]) -> str:
        """Risolve la query SQL da diverse sorgenti (inline, array, file, template)"""
        query_name = query_config.get('name', 'unnamed')

        try:
            # METODO 1: SQL come array di stringhe (multiriga)
            if 'sql' in query_config and isinstance(query_config['sql'], list):
                sql = ' '.join(line.strip() for line in query_config['sql'])
                self._thread_safe_log('info',
                                      f"QUERY: [{query_name}] risolto da array multiriga ({len(query_config['sql'])} righe)")
                return sql

            # METODO 2: SQL come stringa inline
            elif 'sql' in query_config and isinstance(query_config['sql'], str):
                sql = query_config['sql'].strip()
                self._thread_safe_log('info', f"QUERY: [{query_name}] risolto da stringa inline ({len(sql)} caratteri)")
                return sql

            # METODO 3: SQL da file esterno
            elif 'sql_file' in query_config:
                sql_file_path = self.query_directory / query_config['sql_file']

                if not sql_file_path.exists():
                    raise FileNotFoundError(f"File SQL non trovato: {sql_file_path}")

                with open(sql_file_path, 'r', encoding='utf-8') as f:
                    sql = f.read().strip()

                self._thread_safe_log('info', f"QUERY: [{query_name}] risolto da file {query_config['sql_file']}")
                return sql

            # METODO 4: SQL Template con parametri
            elif 'sql_template' in query_config:
                template = query_config['sql_template']
                parameters = query_config.get('parameters', {})

                # Sostituisce parametri nel template
                sql = template
                for param_name, param_value in parameters.items():
                    placeholder = '{' + param_name + '}'
                    sql = sql.replace(placeholder, str(param_value))

                # Verifica parametri non sostituiti
                remaining_params = re.findall(r'\{(\w+)\}', sql)
                if remaining_params:
                    raise ValueError(f"Parametri non risolti nel template: {remaining_params}")

                self._thread_safe_log('info',
                                      f"QUERY: [{query_name}] risolto da template con {len(parameters)} parametri")
                return sql.strip()

            else:
                raise ValueError(f"Nessuna sorgente SQL valida trovata per query '{query_name}'")

        except Exception as e:
            self._thread_safe_log('error', f"ERRORE risoluzione SQL [{query_name}]: {e}")
            raise

    def execute_query(self, query_config: Dict[str, Any]) -> Tuple[pd.DataFrame, str, str]:
        """Esegue una singola query e restituisce DataFrame + info destinazione"""
        query_name = query_config['name']
        source_db = query_config['source_database']
        dest_db = query_config['destination_database']
        dest_table = query_config['destination_table']
        dest_schema = query_config.get('destination_schema',
                                       self.config['databases'][dest_db].get('default_schema', 'dbo'))

        try:
            # Risolve SQL da sorgente configurata
            sql = self.resolve_sql_query(query_config)

            # Log esecuzione
            self._thread_safe_log('info', f"QUERY: Esecuzione {query_name} da [{source_db}]")

            # Esegue query sulla sorgente usando context manager
            with self.db_manager.get_connection(source_db) as conn:
                df = pd.read_sql(sql, conn)

            full_table_name = f"[{dest_schema}].[{dest_table}]"
            self._thread_safe_log('info', f"OK: Query {query_name} completata: {len(df)} righe -> {full_table_name}")

            return df, dest_db, full_table_name

        except Exception as e:
            self._thread_safe_log('error', f"ERRORE query {query_name}: {e}")
            raise

    def write_to_destination(self, df: pd.DataFrame, dest_db: str,
                             full_table_name: str, query_name: str) -> Dict[str, Any]:
        """Scrive DataFrame su database destinazione"""
        try:
            # Estrae schema e table dal nome completo
            match = re.search(r'\[([^\]]+)\]\.\[([^\]]+)\]', full_table_name)
            if not match:
                raise ValueError(f"Nome tabella invalido: {full_table_name}")

            schema_name = match.group(1)
            table_name = match.group(2)

            # Connessione destinazione usando context manager
            with self.db_manager.get_connection(dest_db) as conn:
                cursor = conn.cursor()

                try:
                    # Crea schema se non esiste
                    cursor.execute(f"""
                        IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = '{schema_name}')
                        BEGIN
                            EXEC('CREATE SCHEMA [{schema_name}]')
                        END
                    """)
                    conn.commit()
                    self._thread_safe_log('info', f"SCHEMA: Schema [{schema_name}] verificato/creato in [{dest_db}]")

                    # Drop tabella se richiesto
                    if self.drop_existing:
                        cursor.execute(f"DROP TABLE IF EXISTS {full_table_name}")
                        conn.commit()
                        self._thread_safe_log('info', f"DROP: Tabella {full_table_name} eliminata in [{dest_db}]")

                    # Crea tabella
                    self._create_table_from_dataframe(cursor, conn, df, schema_name, table_name)
                    self._thread_safe_log('info', f"CREATE: Tabella {full_table_name} creata in [{dest_db}]")

                    # Inserisce dati
                    self._insert_data_batch(cursor, conn, df, full_table_name)

                finally:
                    cursor.close()

            return {
                'success': True,
                'database': dest_db,
                'table': full_table_name,
                'rows': len(df)
            }

        except Exception as e:
            self._thread_safe_log('error', f"ERRORE scrittura {query_name}: {e}")
            raise

    def _execute_single_query_task(self, query_config: Dict[str, Any]) -> Dict[str, Any]:
        """Task per eseguire una singola query (usato dal ThreadPoolExecutor)"""
        query_name = query_config['name']

        try:
            # Esegue query
            df, dest_db, full_table_name = self.execute_query(query_config)

            # Scrive su destinazione
            write_result = self.write_to_destination(df, dest_db, full_table_name, query_name)

            return {
                'query_name': query_name,
                'status': 'success',
                'rows': len(df),
                'source': query_config['source_database'],
                'destination': dest_db,
                'table': full_table_name,
                'sql_type': self._get_sql_source_type(query_config)
            }

        except Exception as e:
            return {
                'query_name': query_name,
                'status': 'error',
                'error': str(e)
            }

    def execute_all_queries(self) -> Dict[str, Any]:
        """Esegue tutte le query ABILITATE in multitasking"""
        self.logger.info("AVVIO: Pipeline multi-database avanzata (MULTITASKING)")

        if not self.queries:
            self.logger.warning("ATTENZIONE: Nessuna query abilitata da eseguire")
            return {
                'executed_queries': {},
                'written_tables': [],
                'errors': []
            }

        # Genera file di esempio se la directory è vuota
        if not any(self.query_directory.glob('*.sql')):
            self.generate_sample_query_files()

        results = {
            'executed_queries': {},
            'written_tables': [],
            'errors': []
        }

        # Esegue queries in parallelo con ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            self.logger.info(f"MULTITASKING: Avvio {len(self.queries)} query con {self.max_workers} worker")

            # Sottomette tutti i task
            future_to_query = {
                executor.submit(self._execute_single_query_task, query_config): query_config
                for query_config in self.queries
            }

            # Raccoglie risultati man mano che completano
            for future in as_completed(future_to_query):
                query_config = future_to_query[future]
                query_name = query_config['name']

                try:
                    result = future.result()

                    if result['status'] == 'success':
                        with self._results_lock:
                            results['executed_queries'][query_name] = {
                                'rows': result['rows'],
                                'source': result['source'],
                                'destination': result['destination'],
                                'table': result['table'],
                                'sql_type': result['sql_type']
                            }
                            results['written_tables'].append({
                                'database': result['destination'],
                                'table': result['table']
                            })
                    else:
                        with self._results_lock:
                            results['errors'].append(f"{query_name}: {result.get('error', 'Unknown error')}")

                except Exception as e:
                    self.logger.error(f"ERRORE task {query_name}: {e}")
                    with self._results_lock:
                        results['errors'].append(f"{query_name}: {str(e)}")

        self.logger.info("OK: Pipeline multi-database avanzata completata")
        return results

    def _get_sql_source_type(self, query_config: Dict[str, Any]) -> str:
        """Determina il tipo di sorgente SQL"""
        if 'sql' in query_config and isinstance(query_config['sql'], list):
            return "Array Multiriga"
        elif 'sql' in query_config:
            return "Stringa Inline"
        elif 'sql_file' in query_config:
            return "File Esterno"
        elif 'sql_template' in query_config:
            return "Template"
        return "Sconosciuto"

    def _create_table_from_dataframe(self, cursor, conn, df: pd.DataFrame,
                                     schema_name: str, table_name: str):
        """Crea tabella SQL Server da DataFrame pandas"""
        columns_sql = []

        for col_name, dtype in df.dtypes.items():
            sql_type = self._map_pandas_dtype_to_sql(dtype)
            safe_col_name = col_name.replace('[', '').replace(']', '')
            columns_sql.append(f"[{safe_col_name}] {sql_type}")

        create_sql = f"CREATE TABLE [{schema_name}].[{table_name}] ({', '.join(columns_sql)})"
        cursor.execute(create_sql)
        conn.commit()

    def _map_pandas_dtype_to_sql(self, dtype) -> str:
        """Mappa dtype pandas a tipo SQL Server"""
        dtype_str = str(dtype)

        if dtype_str.startswith('int'):
            return 'BIGINT'
        elif dtype_str.startswith('float'):
            return 'FLOAT'
        elif dtype_str == 'bool':
            return 'BIT'
        elif dtype_str.startswith('datetime'):
            return 'DATETIME2'
        elif dtype_str == 'object':
            return 'NVARCHAR(MAX)'
        else:
            return 'NVARCHAR(MAX)'

    def _insert_data_batch(self, cursor, conn, df: pd.DataFrame, table_name: str):
        """Inserisce dati a batch nel database destinazione con progress logging"""
        placeholders = ', '.join(['?' for _ in df.columns])
        insert_sql = f"INSERT INTO {table_name} VALUES ({placeholders})"

        total_rows = len(df)
        batch_size = min(100, self.batch_size)
        inserted_rows = 0

        for start_idx in range(0, total_rows, batch_size):
            end_idx = min(start_idx + batch_size, total_rows)
            batch_data = []

            for idx in range(start_idx, end_idx):
                row_data = []
                for col_idx, value in enumerate(df.iloc[idx]):
                    processed_value = self._process_value_for_sql(value)
                    row_data.append(processed_value)
                batch_data.append(tuple(row_data))

            cursor.executemany(insert_sql, batch_data)
            conn.commit()

            inserted_rows += len(batch_data)
            if inserted_rows % 1000 == 0:
                self._thread_safe_log('info', f"PROGRESS: {inserted_rows}/{total_rows} righe inserite in {table_name}")

        self._thread_safe_log('info', f"OK: {total_rows} righe inserite in {table_name}")

    def _process_value_for_sql(self, value):
        """Processa valore per inserimento SQL"""
        if pd.isna(value):
            return None
        elif isinstance(value, pd.Timestamp):
            return value.to_pydatetime()
        elif isinstance(value, bool):
            return 1 if value else 0
        elif str(type(value)).find('numpy.int') >= 0:
            return int(value)
        elif str(type(value)).find('numpy.float') >= 0:
            return float(value)
        else:
            return str(value) if value is not None else None

    def get_table_info(self, database: str, full_table_name: str) -> Dict[str, Any]:
        """Recupera informazioni su una tabella"""
        try:
            with self.db_manager.get_connection(database) as conn:
                cursor = conn.cursor()

                # Verifica esistenza tabella
                match = re.search(r'\[([^\]]+)\]\.\[([^\]]+)\]', full_table_name)
                if not match:
                    return {'exists': False}

                schema_name = match.group(1)
                table_name = match.group(2)

                cursor.execute(f"""
                    SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                """, (schema_name, table_name))

                exists = cursor.fetchone()[0] > 0

                if not exists:
                    cursor.close()
                    return {'exists': False}

                # Conta righe
                cursor.execute(f"SELECT COUNT(*) FROM {full_table_name}")
                row_count = cursor.fetchone()[0]

                # Info colonne
                cursor.execute(f"""
                    SELECT COLUMN_NAME, DATA_TYPE 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                    ORDER BY ORDINAL_POSITION
                """, (schema_name, table_name))

                columns = [{'name': row[0], 'type': row[1]} for row in cursor.fetchall()]
                cursor.close()

            return {
                'exists': True,
                'table_name': full_table_name,
                'row_count': row_count,
                'columns': columns
            }

        except Exception as e:
            self.logger.error(f"Errore recupero info tabella {full_table_name}: {e}")
            return {'exists': False, 'error': str(e)}

    def generate_sample_query_files(self):
        """Genera file SQL di esempio nella directory queries"""
        sample_queries = {
            'esempio_analisi_sox.sql': """
-- Esempio: Analisi sistemi SOX complessa
SELECT 
    s.sistema_id,
    s.nome_sistema,
    s.classificazione_sox,
    COUNT(c.controllo_id) as numero_controlli
FROM sistemi s
LEFT JOIN controlli c ON s.sistema_id = c.sistema_id
WHERE s.classificazione_sox = 'CRITICO'
GROUP BY s.sistema_id, s.nome_sistema, s.classificazione_sox
ORDER BY numero_controlli DESC
""",
            'esempio_referenti_progetti.sql': """
-- Esempio: Referenti con progetti attivi
SELECT 
    r.id,
    r.nome,
    r.cognome,
    r.email,
    COUNT(p.id) as progetti_attivi
FROM referenti r
LEFT JOIN progetti p ON r.id = p.referente_id
WHERE r.stato = 'ATTIVO'
GROUP BY r.id, r.nome, r.cognome, r.email
HAVING COUNT(p.id) > 0
ORDER BY progetti_attivi DESC
"""
        }

        for filename, content in sample_queries.items():
            file_path = self.query_directory / filename
            if not file_path.exists():
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content.strip())
                self.logger.info(f"SAMPLE: File SQL creato: {file_path}")