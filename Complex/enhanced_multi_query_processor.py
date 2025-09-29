#
# ENHANCED_MULTI_QUERY_PROCESSOR.py -
# Copyright 2025 TIM SPA
# Author Daniele Speziale
# Filename enhanced_multi_query_processor.py
# Created 25/09/25
# Update  25/09/25
# Enhanced by: Query Processor con supporto multiriga e template
#
import logging
import pandas as pd
import warnings
import re
from typing import Dict, Any, Tuple
from pathlib import Path
from Complex.database_manager import DatabaseManager

# Sopprime warning pandas
warnings.filterwarnings('ignore', message='.*pandas only supports SQLAlchemy.*')


class EnhancedMultiQueryProcessor:
    """Processore per query multi-database con supporto avanzato per query complesse"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_manager = DatabaseManager(config)
        self.logger = logging.getLogger(__name__)
        self.batch_size = min(config['execution']['batch_size'], 500)
        self.drop_existing = config['execution']['drop_existing_tables']
        self.queries = config.get('queries', [])

        # Directory per file SQL esterni
        self.query_directory = Path(config.get('execution', {}).get('query_directory', 'queries'))

        # Crea directory queries se non esiste
        if not self.query_directory.exists():
            self.query_directory.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"SETUP: Directory queries creata: {self.query_directory}")

    def resolve_sql_query(self, query_config: Dict[str, Any]) -> str:
        """Risolve la query SQL da diverse sorgenti (inline, array, file, template)"""
        query_name = query_config.get('name', 'unnamed')

        try:
            # METODO 1: SQL come array di stringhe (multiriga)
            if 'sql' in query_config and isinstance(query_config['sql'], list):
                sql = ' '.join(line.strip() for line in query_config['sql'])
                self.logger.info(f"QUERY: [{query_name}] risolto da array multiriga ({len(query_config['sql'])} righe)")
                return self._validate_and_clean_sql(sql)

            # METODO 2: SQL come stringa singola
            elif 'sql' in query_config and isinstance(query_config['sql'], str):
                sql = query_config['sql']
                self.logger.info(f"QUERY: [{query_name}] risolto da stringa inline")
                return self._validate_and_clean_sql(sql)

            # METODO 3: SQL da file esterno
            elif 'sql_file' in query_config:
                sql_file_path = self.query_directory / query_config['sql_file']
                if not sql_file_path.exists():
                    raise FileNotFoundError(f"File SQL non trovato: {sql_file_path}")

                with open(sql_file_path, 'r', encoding='utf-8') as f:
                    sql = f.read()

                self.logger.info(f"QUERY: [{query_name}] risolto da file {sql_file_path}")
                return self._validate_and_clean_sql(sql)

            # METODO 4: SQL template con parametri
            elif 'sql_template' in query_config:
                return self._resolve_sql_template(query_config)

            else:
                raise ValueError(f"Nessuna sorgente SQL valida trovata per query '{query_name}'")

        except Exception as e:
            self.logger.error(f"ERRORE: Risoluzione SQL per [{query_name}]: {e}")
            raise

    def _resolve_sql_template(self, query_config: Dict[str, Any]) -> str:
        """Risolve SQL template con sostituzione parametri"""
        query_name = query_config.get('name', 'unnamed')

        # Ottiene template
        template = query_config['sql_template']
        if isinstance(template, list):
            template_sql = ' '.join(line.strip() for line in template)
        else:
            template_sql = template

        # Ottiene parametri
        parameters = query_config.get('parameters', {})

        # Sostituzione parametri con formato {param_name}
        resolved_sql = template_sql
        for param_name, param_value in parameters.items():
            placeholder = f"{{{param_name}}}"
            if placeholder in resolved_sql:
                resolved_sql = resolved_sql.replace(placeholder, str(param_value))
                self.logger.debug(f"PARAM: [{query_name}] {param_name} = {param_value}")

        # Verifica parametri non sostituiti
        unresolved_params = re.findall(r'\{([^}]+)\}', resolved_sql)
        if unresolved_params:
            raise ValueError(f"Parametri non risolti in [{query_name}]: {unresolved_params}")

        self.logger.info(f"QUERY: [{query_name}] template risolto con {len(parameters)} parametri")
        return self._validate_and_clean_sql(resolved_sql)

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
        """Esegue una singola query da qualsiasi sorgente con SQL risolto"""
        source_db = query_config['source_database']
        query_name = query_config['name']

        # Risolve la query SQL
        resolved_sql = self.resolve_sql_query(query_config)

        self.logger.info(f"QUERY: Esecuzione {query_name} da [{source_db}]")
        self.logger.debug(f"SQL: {resolved_sql[:200]}...")

        # Crea una copia della config con SQL risolto
        resolved_config = query_config.copy()
        resolved_config['sql'] = resolved_sql

        # Ottiene il tipo di database sorgente
        source_config = self.db_manager.get_database_config(source_db)
        source_type = source_config.get('type')

        if source_type == 'oracle':
            return self._execute_oracle_query(source_db, resolved_config)
        elif source_type == 'mssql':
            return self._execute_mssql_query(source_db, resolved_config)
        else:
            raise ValueError(f"Tipo database '{source_type}' non supportato per query {query_name}")

    def _execute_oracle_query(self, source_db: str, query_config: Dict[str, Any]) -> Tuple[pd.DataFrame, str, str]:
        """Esegue query Oracle con connessione diretta"""
        with self.db_manager.get_oracle_connection(source_db) as conn:
            cursor = conn.cursor()

            # Esegue la query risoluta
            cursor.execute(query_config['sql'])

            # Recupera nomi colonne
            columns = [col[0] for col in cursor.description]

            # Recupera dati in batch
            all_data = []
            row_count = 0
            while True:
                rows = cursor.fetchmany(self.batch_size)
                if not rows:
                    break
                all_data.extend(rows)
                row_count += len(rows)

                if row_count % 5000 == 0:
                    self.logger.info(f"PROGRESS: {row_count} righe recuperate da [{source_db}]...")

            # Crea DataFrame
            df = pd.DataFrame(all_data, columns=columns)

            # Calcola nome tabella completo
            dest_db = query_config['destination_database']
            dest_table = query_config['destination_table']
            dest_schema = self.db_manager.get_schema_for_destination(dest_db, query_config)
            full_table_name = f"[{dest_schema}].[{dest_table}]"

            cursor.close()
            self.logger.info(f"OK: Query {query_config['name']} completata: {len(df)} righe -> {full_table_name}")

            return df, dest_db, full_table_name

    def _execute_mssql_query(self, source_db: str, query_config: Dict[str, Any]) -> Tuple[pd.DataFrame, str, str]:
        """Esegue query SQL Server"""
        with self.db_manager.get_mssql_connection(source_db) as conn:
            # Usa pandas read_sql direttamente
            df = pd.read_sql(query_config['sql'], conn)

            # Calcola nome tabella completo
            dest_db = query_config['destination_database']
            dest_table = query_config['destination_table']
            dest_schema = self.db_manager.get_schema_for_destination(dest_db, query_config)
            full_table_name = f"[{dest_schema}].[{dest_table}]"

            self.logger.info(f"OK: Query {query_config['name']} completata: {len(df)} righe -> {full_table_name}")

            return df, dest_db, full_table_name

    def write_dataframe_to_destination(self, df: pd.DataFrame, dest_db: str, full_table_name: str):
        """Scrive DataFrame nel database di destinazione"""
        # Verifica che la destinazione sia SQL Server
        dest_config = self.db_manager.get_database_config(dest_db)
        if dest_config.get('type') != 'mssql':
            raise ValueError(f"Destinazione '{dest_db}' deve essere SQL Server")

        with self.db_manager.get_mssql_connection(dest_db) as conn:
            self._write_table_direct_insert(conn, dest_db, full_table_name, df)

    def _write_table_direct_insert(self, conn, dest_db: str, full_table_name: str, df: pd.DataFrame):
        """Scrittura diretta con gestione schema e tipi migliorata"""
        cursor = conn.cursor()

        try:
            # Estrae schema e nome tabella
            if '.' in full_table_name:
                schema_part, table_part = full_table_name.split('.')
                schema_name = schema_part.strip('[]')
                table_name = table_part.strip('[]')
            else:
                schema_name = 'dbo'
                table_name = full_table_name.strip('[]')

            # Crea schema se necessario
            self.db_manager.ensure_schema_exists(dest_db, schema_name)

            # Drop tabella se richiesto
            if self.drop_existing:
                cursor.execute(f"IF OBJECT_ID('{full_table_name}', 'U') IS NOT NULL DROP TABLE {full_table_name}")
                conn.commit()
                self.logger.info(f"DROP: Tabella {full_table_name} eliminata in [{dest_db}]")

            if len(df) == 0:
                self.logger.warning(f"WARNING: DataFrame vuoto per {full_table_name}")
                return

            # Sanitizza nomi colonne
            columns = []
            for col in df.columns:
                clean_col = str(col).replace(' ', '_').replace('-', '_').replace('.', '_')
                clean_col = ''.join(c for c in clean_col if c.isalnum() or c == '_')
                if clean_col and clean_col[0].isdigit():
                    clean_col = 'COL_' + clean_col
                if not clean_col:
                    clean_col = 'UNNAMED_COLUMN'
                columns.append(clean_col)

            # Analizza tipi dati dal DataFrame con logica migliorata
            create_sql = f"CREATE TABLE {full_table_name} ("
            col_definitions = []

            for i, col_name in enumerate(columns):
                col_data = df.iloc[:, i]
                sql_type = self._infer_sql_type(col_data)
                col_definitions.append(f"[{col_name}] {sql_type}")

            create_sql += ", ".join(col_definitions) + ")"
            cursor.execute(create_sql)
            conn.commit()
            self.logger.info(f"CREATE: Tabella {full_table_name} creata in [{dest_db}]")

            # Prepara INSERT statement
            placeholders = ", ".join(["?" for _ in columns])
            insert_sql = f"INSERT INTO {full_table_name} ([{'],['.join(columns)}]) VALUES ({placeholders})"

            # Inserisce dati in batch ottimizzati
            self._insert_data_optimized(cursor, conn, insert_sql, df, full_table_name)

        except Exception as e:
            self.logger.error(f"ERRORE: Inserimento {full_table_name} su [{dest_db}]: {e}")
            conn.rollback()
            raise
        finally:
            cursor.close()

    def _infer_sql_type(self, col_data: pd.Series) -> str:
        """Inferisce il tipo SQL appropriato con logica migliorata"""
        non_null_data = col_data.dropna()

        if len(non_null_data) == 0:
            return "VARCHAR(MAX)"

        # Controlla tipo dominante
        if pd.api.types.is_bool_dtype(col_data):
            return "BIT"
        elif pd.api.types.is_integer_dtype(col_data):
            max_val = abs(non_null_data).max()
            if max_val <= 127:
                return "TINYINT"
            elif max_val <= 32767:
                return "SMALLINT"
            elif max_val <= 2147483647:
                return "INT"
            else:
                return "BIGINT"
        elif pd.api.types.is_float_dtype(col_data):
            return "FLOAT"
        elif pd.api.types.is_datetime64_any_dtype(col_data):
            return "DATETIME2"
        else:
            # Calcola lunghezza VARCHAR ottimale
            max_len = non_null_data.astype(str).str.len().max()
            if max_len <= 50:
                return "VARCHAR(50)"
            elif max_len <= 255:
                return "VARCHAR(255)"
            elif max_len <= 4000:
                return f"VARCHAR({min(max_len + 100, 4000)})"
            else:
                return "VARCHAR(MAX)"

    def _insert_data_optimized(self, cursor, conn, insert_sql: str, df: pd.DataFrame, table_name: str):
        """Inserimento dati ottimizzato con batch adattivo"""
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

            # Inserisce batch
            cursor.executemany(insert_sql, batch_data)
            conn.commit()

            inserted_rows += len(batch_data)
            if inserted_rows % 1000 == 0:
                self.logger.info(f"PROGRESS: {inserted_rows}/{total_rows} righe inserite in {table_name}")

        self.logger.info(f"OK: {total_rows} righe inserite in {table_name}")

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

    def generate_sample_query_files(self):
        """Genera file SQL di esempio nella directory queries"""
        sample_queries = {
            'analisi_sistemi_sox.sql': """
-- Analisi sistemi SOX complessa
WITH sistemi_critici AS (
    SELECT 
        s.sistema_id,
        s.nome_sistema,
        s.classificazione_sox,
        s.data_ultima_validazione,
        COUNT(c.controllo_id) as numero_controlli
    FROM dbo.DWHMON_SOX_RISORSE s
    LEFT JOIN dbo.CONTROLLI c ON s.sistema_id = c.sistema_id
    WHERE s.classificazione_sox IN ('CRITICO', 'ALTO')
      AND s.stato = 'ATTIVO'
    GROUP BY s.sistema_id, s.nome_sistema, s.classificazione_sox, s.data_ultima_validazione
),
controlli_scaduti AS (
    SELECT 
        sistema_id,
        COUNT(*) as controlli_scaduti
    FROM dbo.CONTROLLI
    WHERE data_scadenza < GETDATE()
      AND stato = 'ATTIVO'
    GROUP BY sistema_id
)
SELECT 
    sc.sistema_id,
    sc.nome_sistema,
    sc.classificazione_sox,
    sc.data_ultima_validazione,
    sc.numero_controlli,
    COALESCE(cs.controlli_scaduti, 0) as controlli_scaduti,
    CASE 
        WHEN cs.controlli_scaduti > 0 THEN 'ATTENZIONE'
        WHEN DATEDIFF(day, sc.data_ultima_validazione, GETDATE()) > 90 THEN 'SCADUTO'
        ELSE 'OK'
    END as stato_compliance
FROM sistemi_critici sc
LEFT JOIN controlli_scaduti cs ON sc.sistema_id = cs.sistema_id
ORDER BY 
    sc.classificazione_sox,
    cs.controlli_scaduti DESC,
    sc.data_ultima_validazione ASC;
            """,

            'referenti_con_dettagli.sql': """
-- Query Oracle complessa per referenti
SELECT 
    r.id as referente_id,
    r.nome || ' ' || r.cognome as nome_completo,
    r.email,
    r.telefono,
    r.data_creazione,
    r.stato,
    -- Calcoli aggregati
    COUNT(DISTINCT p.id) as progetti_totali,
    COUNT(DISTINCT CASE WHEN p.stato = 'ATTIVO' THEN p.id END) as progetti_attivi,
    MAX(p.data_ultima_modifica) as ultimo_progetto_aggiornato,
    -- Indicatori di performance
    CASE 
        WHEN COUNT(p.id) = 0 THEN 'INATTIVO'
        WHEN COUNT(DISTINCT CASE WHEN p.stato = 'ATTIVO' THEN p.id END) > 3 THEN 'MOLTO_ATTIVO'
        WHEN COUNT(DISTINCT CASE WHEN p.stato = 'ATTIVO' THEN p.id END) > 0 THEN 'ATTIVO'
        ELSE 'DORMIENTE'
    END as livello_attivita
FROM IAM.REFERENTE r
LEFT JOIN IAM.PROGETTI p ON r.id = p.referente_id
WHERE r.data_creazione >= ADD_MONTHS(SYSDATE, -24)
  AND r.email IS NOT NULL
  AND r.stato IN ('ATTIVO', 'SOSPESO')
GROUP BY 
    r.id, r.nome, r.cognome, r.email, r.telefono, r.data_creazione, r.stato
HAVING 
    COUNT(p.id) >= 0  -- Include anche referenti senza progetti per analisi complete
ORDER BY 
    progetti_attivi DESC,
    ultimo_progetto_aggiornato DESC NULLS LAST,
    r.data_creazione DESC
FETCH FIRST 2000 ROWS ONLY;
            """
        }

        for filename, content in sample_queries.items():
            file_path = self.query_directory / filename
            if not file_path.exists():
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content.strip())
                self.logger.info(f"SAMPLE: File SQL creato: {file_path}")

    def execute_all_queries(self) -> Dict[str, Any]:
        """Esegue tutte le query configurate con supporto avanzato"""
        self.logger.info("AVVIO: Pipeline multi-database avanzata")

        # Genera file di esempio se la directory è vuota
        if not any(self.query_directory.glob('*.sql')):
            self.generate_sample_query_files()

        results = {
            'executed_queries': {},
            'written_tables': [],
            'errors': []
        }

        try:
            for query_config in self.queries:
                try:
                    query_name = query_config['name']

                    # Esegue query dalla sorgente (con SQL risolto)
                    df, dest_db, full_table_name = self.execute_query(query_config)
                    results['executed_queries'][query_name] = {
                        'rows': len(df),
                        'source': query_config['source_database'],
                        'destination': dest_db,
                        'table': full_table_name,
                        'sql_type': self._get_sql_source_type(query_config)
                    }

                    # Scrive nella destinazione
                    if len(df) > 0:
                        self.write_dataframe_to_destination(df, dest_db, full_table_name)
                        results['written_tables'].append({
                            'query': query_name,
                            'table': full_table_name,
                            'database': dest_db
                        })
                    else:
                        self.logger.warning(f"WARNING: Query {query_name} non ha prodotto dati")

                except Exception as e:
                    error_msg = f"Query {query_config.get('name', 'unnamed')}: {e}"
                    self.logger.error(f"ERRORE: {error_msg}")
                    results['errors'].append(error_msg)
                    continue

            self.logger.info("OK: Pipeline multi-database avanzata completata")

        except Exception as e:
            self.logger.error(f"ERRORE: Pipeline generale: {e}")
            results['errors'].append(str(e))

        return results

    def _get_sql_source_type(self, query_config: Dict[str, Any]) -> str:
        """Determina il tipo di sorgente SQL usata"""
        if 'sql' in query_config and isinstance(query_config['sql'], list):
            return "multiline_array"
        elif 'sql' in query_config:
            return "inline_string"
        elif 'sql_file' in query_config:
            return "external_file"
        elif 'sql_template' in query_config:
            return "template_with_params"
        else:
            return "unknown"

    def get_table_info(self, dest_db: str, full_table_name: str) -> Dict[str, Any]:
        """Ottiene informazioni tabella di destinazione (eredita dalla versione base)"""
        try:
            with self.db_manager.get_mssql_connection(dest_db) as conn:
                cursor = conn.cursor()

                # Estrae schema e nome tabella
                if '.' in full_table_name:
                    schema_part, table_part = full_table_name.split('.')
                    schema_name = schema_part.strip('[]')
                    table_only = table_part.strip('[]')
                else:
                    schema_name = 'dbo'
                    table_only = full_table_name.strip('[]')

                # Conta righe
                cursor.execute(f"SELECT COUNT(*) as row_count FROM {full_table_name}")
                row_count = cursor.fetchone()[0]

                # Schema colonne
                cursor.execute(f"""
                    SELECT 
                        COLUMN_NAME,
                        DATA_TYPE,
                        IS_NULLABLE,
                        CHARACTER_MAXIMUM_LENGTH
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = '{table_only}' AND TABLE_SCHEMA = '{schema_name}'
                    ORDER BY ORDINAL_POSITION
                """)

                columns = []
                for row in cursor.fetchall():
                    columns.append({
                        'name': row[0],
                        'type': row[1],
                        'nullable': row[2],
                        'max_length': row[3]
                    })

                cursor.close()

                return {
                    'table_name': full_table_name,
                    'database': dest_db,
                    'row_count': row_count,
                    'columns': columns,
                    'exists': True
                }

        except Exception as e:
            self.logger.error(f"ERRORE: Info tabella {full_table_name} su [{dest_db}]: {e}")
            return {
                'table_name': full_table_name,
                'database': dest_db,
                'exists': False,
                'error': str(e)
            }