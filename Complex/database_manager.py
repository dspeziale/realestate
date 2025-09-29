# database_manager.py - Gestore Database Multi-Source/Multi-Destination (Senza Windows Auth Thick Mode)
import oracledb
import pyodbc
import logging
import os
from typing import Dict, Any, List
from contextlib import contextmanager


class DatabaseManager:
    """Gestore per multiple connessioni database"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.databases = config.get('databases', {})

        # Setup directory logs
        self.setup_logging_directory()

    def setup_logging_directory(self):
        """Crea directory logs se non esiste"""
        log_dir = self.config.get('execution', {}).get('log_directory', '../logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            self.logger.info(f"SETUP: Directory logs creata: {log_dir}")

    def get_database_config(self, db_name: str) -> Dict[str, Any]:
        """Ottiene configurazione database per nome"""
        if db_name not in self.databases:
            raise ValueError(f"Database '{db_name}' non trovato nella configurazione")
        return self.databases[db_name]

    @contextmanager
    def get_oracle_connection(self, db_name: str):
        """Connessione Oracle con nome database specifico (senza Windows Auth Thick Mode)"""
        conn = None
        try:
            oracle_config = self.get_database_config(db_name)

            if oracle_config.get('type') != 'oracle':
                raise ValueError(f"Database '{db_name}' non è di tipo Oracle")

            service_name = oracle_config.get('service_name') or oracle_config.get('sid')
            dsn = f"{oracle_config['host']}:{oracle_config['port']}/{service_name}"

            self.logger.info(f"CONNESSIONE Oracle [{db_name}]: {oracle_config['host']}:{oracle_config['port']}")
            self.logger.info(f"Service Name: {service_name}")

            # METODO 1: Username/Password Thick Mode (salta Windows Auth)
            if oracle_config.get('username') and oracle_config.get('password'):
                try:
                    self.logger.info("TENTATIVO: Username/Password Thick Mode...")
                    if not hasattr(oracledb, '_thick_mode_initialized'):
                        oracledb.init_oracle_client()
                        oracledb._thick_mode_initialized = True

                    conn = oracledb.connect(
                        user=oracle_config['username'],
                        password=oracle_config['password'],
                        dsn=dsn
                    )
                    self.logger.info("OK: Connesso con Username/Password (Thick Mode)")
                    yield conn
                    return
                except Exception as e:
                    self.logger.warning(f"WARNING: Username/Password Thick Mode fallita: {e}")

            # METODO 2: Thin Mode con Username/Password
            if oracle_config.get('username') and oracle_config.get('password'):
                try:
                    self.logger.info("TENTATIVO: Username/Password Thin Mode...")
                    conn = oracledb.connect(
                        user=oracle_config['username'],
                        password=oracle_config['password'],
                        host=oracle_config['host'],
                        port=oracle_config['port'],
                        service_name=service_name
                    )
                    self.logger.info("OK: Connesso con Username/Password (Thin Mode)")
                    yield conn
                    return
                except Exception as e:
                    self.logger.error(f"ERRORE: Username/Password Thin Mode fallita: {e}")

            # METODO 3: Ultimo tentativo generico
            try:
                self.logger.info("TENTATIVO: Ultimo tentativo Thin Mode...")
                conn = oracledb.connect(dsn=dsn)
                self.logger.info("OK: Connesso in Thin Mode generico")
                yield conn
                return
            except Exception as e:
                error_msg = f"""
ERRORE CONNESSIONE ORACLE [{db_name}]:

SOLUZIONI POSSIBILI:
   1. Verifica username e password nel config.json
   2. Installa Oracle Instant Client se necessario
   3. Controlla connettività di rete:
      - Host: {oracle_config['host']}
      - Port: {oracle_config['port']}
      - Service Name: {service_name}

Errore tecnico: {e}
"""
                raise Exception(error_msg)

        finally:
            if conn:
                try:
                    conn.close()
                    self.logger.info(f"CHIUSA: Connessione Oracle [{db_name}] chiusa")
                except:
                    pass

    @contextmanager
    def get_mssql_connection(self, db_name: str):
        """Connessione SQL Server con nome database specifico"""
        conn = None
        try:
            mssql_config = self.get_database_config(db_name)

            if mssql_config.get('type') != 'mssql':
                raise ValueError(f"Database '{db_name}' non è di tipo SQL Server")

            self.logger.info(f"CONNESSIONE SQL Server [{db_name}]: {mssql_config['server']}")

            # Connection string basato sul tipo di autenticazione
            if mssql_config.get('auth_type') == 'windows':
                # Autenticazione Windows
                conn_str = (
                    f"DRIVER={{{mssql_config['driver']}}};"
                    f"SERVER={mssql_config['server']},{mssql_config['port']};"
                    f"DATABASE={mssql_config['database']};"
                    f"Trusted_Connection=yes;"
                )
                self.logger.info(f"Usando autenticazione Windows per [{db_name}]")
            else:
                # Autenticazione SQL Server
                conn_str = (
                    f"DRIVER={{{mssql_config['driver']}}};"
                    f"SERVER={mssql_config['server']},{mssql_config['port']};"
                    f"DATABASE={mssql_config['database']};"
                    f"UID={mssql_config['username']};"
                    f"PWD={mssql_config['password']};"
                )
                self.logger.info(f"Usando autenticazione SQL Server per [{db_name}]")

            conn = pyodbc.connect(conn_str)
            self.logger.info(f"OK: Connesso a SQL Server [{db_name}]")
            yield conn

        except Exception as e:
            self.logger.error(f"ERRORE: connessione SQL Server [{db_name}]: {e}")
            raise
        finally:
            if conn:
                conn.close()
                self.logger.info(f"CHIUSA: Connessione SQL Server [{db_name}] chiusa")

    def get_connection(self, db_name: str):
        """Ottiene connessione appropriata basata sul tipo database"""
        db_config = self.get_database_config(db_name)
        db_type = db_config.get('type')

        if db_type == 'oracle':
            return self.get_oracle_connection(db_name)
        elif db_type == 'mssql':
            return self.get_mssql_connection(db_name)
        else:
            raise ValueError(f"Tipo database '{db_type}' non supportato per '{db_name}'")

    def test_connection(self, db_name: str) -> bool:
        """Testa una singola connessione database"""
        try:
            db_config = self.get_database_config(db_name)
            db_type = db_config.get('type')

            with self.get_connection(db_name) as conn:
                cursor = conn.cursor()

                if db_type == 'oracle':
                    cursor.execute("SELECT 1 FROM DUAL")
                elif db_type == 'mssql':
                    cursor.execute("SELECT 1")

                result = cursor.fetchone()
                cursor.close()

                self.logger.info(f"OK: Test connessione [{db_name}]")
                return True

        except Exception as e:
            self.logger.error(f"ERRORE: Test connessione [{db_name}]: {e}")
            return False

    def test_all_connections(self) -> Dict[str, bool]:
        """Testa tutte le connessioni configurate"""
        results = {}

        for db_name in self.databases.keys():
            self.logger.info(f"TEST: Connessione {db_name}...")
            results[db_name] = self.test_connection(db_name)

        return results

    def list_databases(self) -> Dict[str, str]:
        """Lista tutti i database configurati con tipo"""
        return {name: config.get('type', 'unknown') for name, config in self.databases.items()}

    def get_schema_for_destination(self, db_name: str, query_config: Dict[str, Any]) -> str:
        """Ottiene schema per tabella di destinazione"""
        # Schema specifico nella query
        if 'destination_schema' in query_config:
            return query_config['destination_schema']

        # Schema default del database
        db_config = self.get_database_config(db_name)
        return db_config.get('default_schema', 'dbo')

    def ensure_schema_exists(self, db_name: str, schema_name: str):
        """Crea schema se non esiste (solo SQL Server)"""
        db_config = self.get_database_config(db_name)

        if db_config.get('type') != 'mssql':
            return  # Solo per SQL Server

        try:
            with self.get_connection(db_name) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = '{schema_name}')
                    BEGIN
                        EXEC('CREATE SCHEMA [{schema_name}]')
                    END
                """)
                conn.commit()
                cursor.close()
                self.logger.info(f"SCHEMA: Schema [{schema_name}] verificato/creato in [{db_name}]")
        except Exception as e:
            self.logger.warning(f"WARNING: Errore creazione schema {schema_name} in [{db_name}]: {e}")