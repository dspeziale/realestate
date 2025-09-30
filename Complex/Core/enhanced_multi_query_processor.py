#
# ENHANCED_MULTI_QUERY_PROCESSOR.py - MULTITASKING EDITION - CORRETTO
# Copyright 2025 TIM SPA
# Author Daniele Speziale
# Filename: Complex/enhanced_multi_query_processor.py
# Created 25/09/25
# Update  30/09/25
# Enhanced by: Multitasking con ThreadPoolExecutor + filtro enabled queries + FIX percorsi
#
import logging
import pandas as pd
import warnings
import re
from typing import Dict, Any, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from Complex.Core.database_manager import DatabaseManager

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

        # FIX CRITICO: Carica queries dalla configurazione correttamente
        all_queries = config.get('queries', [])  # NON '../queries'!
        self.queries = [q for q in all_queries if q.get('enabled', True)]

        # Log statistiche queries
        disabled_count = len(all_queries) - len(self.queries)
        self.logger.info(f"SETUP: {len(self.queries)} query abilitate, {disabled_count} disabilitate")

        # FIX CRITICO: Directory per file SQL esterni - percorso corretto
        self.query_directory = Path(config.get('execution', {}).get('query_directory', 'queries'))  # NON '../queries'!

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
                return self._validate_and_clean_sql(sql)

            # METODO 2: SQL come stringa inline
            elif 'sql' in query_config and isinstance(query_config['sql'], str):
                sql = query_config['sql'].strip()
                self._thread_safe_log('info', f"QUERY: [{query_name}] risolto da stringa inline ({len(sql)} caratteri)")
                return self._validate_and_clean_sql(sql)

            # METODO 3: SQL da file esterno
            elif 'sql_file' in query_config:
                sql_file_path = self.query_directory / query_config['sql_file']

                # DEBUG: Verifica percorso file
                self._thread_safe_log('info', f"DEBUG: Cercando file SQL: {sql_file_path.absolute()}")

                if not sql_file_path.exists():
                    # Lista file nella directory per debug
                    available_files = list(self.query_directory.glob('*.sql'))
                    self._thread_safe_log('error',
                                          f"DEBUG: File disponibili in {self.query_directory}: {[f.name for f in available_files]}")
                    raise FileNotFoundError(f"File SQL non trovato: {sql_file_path.absolute()}")

                with open(sql_file_path, 'r', encoding='utf-8') as f:
                    sql = f.read().strip()

                self._thread_safe_log('info', f"QUERY: [{query_name}] risolto da file {query_config['sql_file']}")
                return self._validate_and_clean_sql(sql)

            # METODO 4: SQL Template con parametri
            elif 'sql_template' in query_config:
                template = query_config['sql_template']
                parameters = query_config.get('parameters', {})

                # Normalizza template se è un array
                if isinstance(template, list):
                    template = ' '.join(line.strip() for line in template)

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
                return self._validate_and_clean_sql(sql.strip())

            else:
                raise ValueError(f"Nessuna sorgente SQL valida trovata per query '{query_name}'")

        except Exception as e:
            self._thread_safe_log('error', f"ERRORE risoluzione SQL [{query_name}]: {e}")
            raise

    def _validate_and_clean_sql(self, sql: str) -> str:
        """Valida e pulisce la query SQL"""
        # Rimuove commenti SQL
        sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)

        # Normalizza spazi bianchi
        sql = re.sub(r'\s+', ' ', sql).strip()

        # Validazioni di sicurezza base
        dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE']
        sql_upper = sql.upper()

        # Permette solo SELECT e WITH (per CTE)
        if not (sql_upper.startswith('SELECT') or sql_upper.startswith('WITH')):
            found_dangerous = [kw for kw in dangerous_keywords if kw in sql_upper]
            if found_dangerous:
                raise ValueError(f"Query potenzialmente pericolosa rilevata. Keywords trovate: {found_dangerous}")

        if len(sql) < 10:
            raise ValueError("Query troppo breve, potrebbe essere incompleta")

        return sql

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

            # Ottiene tipo di database sorgente per esecuzione corretta
            source_config = self.db_manager.get_database_config(source_db)
            source_type = source_config.get('type')

            if source_type == 'oracle':
                df = self._execute_oracle_query_direct(source_db, sql)
            elif source_type == 'mssql':
                # Esegue query sulla sorgente usando context manager
                with self.db_manager.get_connection(source_db) as conn:
                    df = pd.read_sql(sql, conn)
            else:
                raise ValueError(f"Tipo database '{source_type}' non supportato per query {query_name}")

            full_table_name = f"[{dest_schema}].[{dest_table}]"
            self._thread_safe_log('info', f"OK: Query {query_name} completata: {len(df)} righe -> {full_table_name}")

            return df, dest_db, full_table_name

        except Exception as e:
            self._thread_safe_log('error', f"ERRORE query {query_name}: {e}")
            raise

    def _execute_oracle_query_direct(self, source_db: str, sql: str) -> pd.DataFrame:
        """Esegue query Oracle con metodo diretto compatibile"""
        with self.db_manager.get_oracle_connection(source_db) as conn:
            cursor = conn.cursor()

            # Esegue la query
            cursor.execute(sql)

            # Recupera nomi colonne
            columns = [col[0] for col in cursor.description]

            # Recupera tutti i dati
            all_data = []
            row_count = 0
            while True:
                rows = cursor.fetchmany(self.batch_size)
                if not rows:
                    break
                all_data.extend(rows)
                row_count += len(rows)

                if row_count % 5000 == 0:
                    self._thread_safe_log('info', f"PROGRESS: {row_count} righe recuperate da [{source_db}]...")

            cursor.close()

            # Crea DataFrame
            return pd.DataFrame(all_data, columns=columns)

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

        # DEBUG: Verifica file SQL per tutte le query
        for query_config in self.queries:
            sql_file = query_config.get('sql_file')
            if sql_file:
                file_path = self.query_directory / sql_file
                self.logger.info(f"DEBUG: Cercando file {file_path.absolute()} - Esiste: {file_path.exists()}")

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
        """Crea tabella SQL Server da DataFrame pandas con tipi migliorati"""
        columns_sql = []

        for col_name, dtype in df.dtypes.items():
            # Inferisce tipo SQL migliorato basato sui dati
            non_null_data = df[col_name].dropna()
            sql_type = self._infer_sql_type_advanced(non_null_data, dtype)

            safe_col_name = str(col_name).replace('[', '').replace(']', '')
            columns_sql.append(f"[{safe_col_name}] {sql_type}")

        create_sql = f"CREATE TABLE [{schema_name}].[{table_name}] ({', '.join(columns_sql)})"
        cursor.execute(create_sql)
        conn.commit()

    def _infer_sql_type_advanced(self, col_data: pd.Series, dtype) -> str:
        """Inferisce tipo SQL con logica avanzata basata sui dati reali"""
        if len(col_data) == 0:
            return "NVARCHAR(MAX)"

        dtype_str = str(dtype)

        # Tipi numerici
        if dtype_str.startswith('int'):
            max_val = abs(col_data).max() if len(col_data) > 0 else 0
            if max_val <= 127:
                return 'TINYINT'
            elif max_val <= 32767:
                return 'SMALLINT'
            elif max_val <= 2147483647:
                return 'INT'
            else:
                return 'BIGINT'
        elif dtype_str.startswith('float'):
            return 'FLOAT'
        elif dtype_str == 'bool':
            return 'BIT'
        elif dtype_str.startswith('datetime'):
            return 'DATETIME2'
        elif dtype_str == 'object':
            # Analizza lunghezza massima per determinare VARCHAR appropriato
            max_len = col_data.astype(str).str.len().max()
            if max_len <= 50:
                return 'NVARCHAR(100)'
            elif max_len <= 255:
                return 'NVARCHAR(500)'
            elif max_len <= 4000:
                return f'NVARCHAR({min(max_len * 2, 4000)})'
            else:
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
                    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                    ORDER BY ORDINAL_POSITION
                """, (schema_name, table_name))

                columns = [{'name': row[0], 'type': row[1], 'max_length': row[2]} for row in cursor.fetchall()]
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
-- Esempio: Analisi sistemi SOX complessa con CTE
WITH sistemi_critici AS (
    SELECT 
        s.sistema_id,
        s.nome_sistema,
        s.classificazione_sox,
        s.data_ultima_validazione,
        COUNT(c.controllo_id) as numero_controlli
    FROM sistemi s
    LEFT JOIN controlli c ON s.sistema_id = c.sistema_id
    WHERE s.classificazione_sox IN ('CRITICO', 'ALTO')
      AND s.stato = 'ATTIVO'
    GROUP BY s.sistema_id, s.nome_sistema, s.classificazione_sox, s.data_ultima_validazione
)
SELECT 
    sistema_id,
    nome_sistema,
    classificazione_sox,
    data_ultima_validazione,
    numero_controlli,
    CASE 
        WHEN numero_controlli = 0 THEN 'NESSUN_CONTROLLO'
        WHEN numero_controlli > 10 THEN 'ALTO_CONTROLLO'
        ELSE 'MEDIO_CONTROLLO'
    END as livello_controllo
FROM sistemi_critici
ORDER BY numero_controlli DESC, classificazione_sox
""",
            'esempio_referenti_progetti.sql': """
-- Esempio: Referenti con progetti attivi e metriche
SELECT 
    r.id as referente_id,
    r.nome + ' ' + r.cognome as nome_completo,
    r.email,
    r.telefono,
    r.data_creazione,
    COUNT(p.id) as progetti_totali,
    COUNT(CASE WHEN p.stato = 'ATTIVO' THEN 1 END) as progetti_attivi,
    MAX(p.data_ultima_modifica) as ultimo_aggiornamento,
    CASE 
        WHEN COUNT(p.id) = 0 THEN 'INATTIVO'
        WHEN COUNT(CASE WHEN p.stato = 'ATTIVO' THEN 1 END) > 3 THEN 'MOLTO_ATTIVO'
        WHEN COUNT(CASE WHEN p.stato = 'ATTIVO' THEN 1 END) > 0 THEN 'ATTIVO'
        ELSE 'DORMIENTE'
    END as livello_attivita
FROM referenti r
LEFT JOIN progetti p ON r.id = p.referente_id
WHERE r.stato = 'ATTIVO'
  AND r.data_creazione >= DATEADD(month, -24, GETDATE())
GROUP BY r.id, r.nome, r.cognome, r.email, r.telefono, r.data_creazione
HAVING COUNT(p.id) >= 0
ORDER BY progetti_attivi DESC, ultimo_aggiornamento DESC
""",
            'esempio_template_parametrico.sql': """
-- Esempio: Template con parametri {data_inizio} e {stato_filtro}
SELECT 
    sistema_id,
    nome_sistema,
    stato,
    data_creazione,
    ultimo_aggiornamento
FROM sistemi_monitoraggio
WHERE data_creazione >= '{data_inizio}'
  AND stato = '{stato_filtro}'
  AND attivo = 1
ORDER BY data_creazione DESC
"""
        }

        for filename, content in sample_queries.items():
            file_path = self.query_directory / filename
            if not file_path.exists():
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content.strip())
                self.logger.info(f"SAMPLE: File SQL creato: {file_path}")