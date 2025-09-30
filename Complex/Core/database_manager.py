# database_manager.py - Gestore Database Multi-Source/Multi-Destination (Enhanced con schema support)
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
                    self.logger.error(f"ERRORE: Username/Password Thick Mode: {e}")
                    raise

            # METODO 2: Windows Authentication (se configurato)
            elif oracle_config.get('auth_type') == 'windows':
                try:
                    self.logger.info("TENTATIVO: Windows Authentication...")
                    conn = oracledb.connect(dsn=dsn)
                    self.logger.info("OK: Connesso con Windows Authentication")
                    yield conn
                    return
                except Exception as e:
                    self.logger.error(f"ERRORE: Windows Authentication: {e}")
                    raise

            else:
                raise ValueError(f"Nessun metodo di autenticazione valido per Oracle [{db_name}]")

        except Exception as e:
            self.logger.error(f"ERRORE: connessione Oracle [{db_name}]: {e}")
            raise
        finally:
            if conn:
                try:
                    conn.close()
                    self.logger.info(f"CHIUSA: Connessione Oracle [{db_name}] chiusa")
                except:
                    pass

    @contextmanager
    def get_mssql_connection(self, db_name: str):
        """Connessione SQL Server con configurazione avanzata"""
        conn = None
        try:
            mssql_config = self.get_database_config(db_name)

            if mssql_config.get('type') != 'mssql':
                raise ValueError(f"Database '{db_name}' non è di tipo SQL Server")

            server = mssql_config['server']
            database = mssql_config['database']
            driver = mssql_config.get('driver', 'ODBC Driver 17 for SQL Server')

            self.logger.info(f"CONNESSIONE SQL Server [{db_name}]: {server}")

            # Costruisci connection string
            if mssql_config.get('auth_type') == 'windows':
                self.logger.info(f"Usando autenticazione Windows per [{db_name}]")
                conn_str = f"""
                    DRIVER={{{driver}}};
                    SERVER={server};
                    DATABASE={database};
                    Trusted_Connection=yes;
                    TrustServerCertificate=yes;
                """
            else:
                username = mssql_config.get('username')
                password = mssql_config.get('password')
                if not username or not password:
                    raise ValueError(f"Username/Password richiesti per SQL Server [{db_name}]")

                self.logger.info(f"Usando autenticazione SQL per [{db_name}] (user: {username})")
                conn_str = f"""
                    DRIVER={{{driver}}};
                    SERVER={server};
                    DATABASE={database};
                    UID={username};
                    PWD={password};
                    TrustServerCertificate=yes;
                """

            # Pulisci connection string (rimuove spazi e newline)
            conn_str = ' '.join(conn_str.split())

            conn = pyodbc.connect(conn_str, timeout=30)
            self.logger.info(f"OK: Connesso a SQL Server [{db_name}]")
            yield conn

        except Exception as e:
            self.logger.error(f"ERRORE: connessione SQL Server [{db_name}]: {e}")
            raise
        finally:
            if conn:
                try:
                    conn.close()
                    self.logger.info(f"CHIUSA: Connessione SQL Server [{db_name}] chiusa")
                except:
                    pass

    @contextmanager
    def get_connection(self, db_name: str):
        """Connessione generica che determina automaticamente il tipo"""
        db_config = self.get_database_config(db_name)
        db_type = db_config.get('type')

        if db_type == 'oracle':
            with self.get_oracle_connection(db_name) as conn:
                yield conn
        elif db_type == 'mssql':
            with self.get_mssql_connection(db_name) as conn:
                yield conn
        else:
            raise ValueError(f"Tipo database '{db_type}' non supportato per '{db_name}'")

    def test_connection(self, db_name: str) -> bool:
        """Testa una singola connessione database"""
        try:
            db_config = self.get_database_config(db_name)
            db_type = db_config.get('type')

            if db_type == 'oracle':
                with self.get_oracle_connection(db_name) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1 FROM DUAL")
                    cursor.fetchone()
                    cursor.close()
                    self.logger.info(f"OK: Test connessione Oracle [{db_name}]")
                    return True

            elif db_type == 'mssql':
                with self.get_mssql_connection(db_name) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                    cursor.close()
                    self.logger.info(f"OK: Test connessione SQL Server [{db_name}]")
                    return True

            else:
                self.logger.error(f"ERRORE: Tipo database '{db_type}' non supportato")
                return False

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

    def create_schema_if_not_exists(self, db_name: str, schema_name: str):
        """Crea schema se non esiste (metodo richiesto dal nuovo processor)"""
        db_config = self.get_database_config(db_name)

        if db_config.get('type') != 'mssql':
            self.logger.debug(f"SKIP: Creazione schema non necessaria per tipo {db_config.get('type')}")
            return  # Solo per SQL Server

        try:
            with self.get_mssql_connection(db_name) as conn:
                cursor = conn.cursor()

                # Controlla se schema esiste
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM sys.schemas 
                    WHERE name = ?
                """, schema_name)

                exists = cursor.fetchone()[0] > 0

                if not exists:
                    # Crea schema
                    cursor.execute(f"CREATE SCHEMA [{schema_name}]")
                    conn.commit()
                    self.logger.info(f"SCHEMA: Schema [{schema_name}] creato in [{db_name}]")
                else:
                    self.logger.debug(f"SCHEMA: Schema [{schema_name}] già esiste in [{db_name}]")

                cursor.close()

        except Exception as e:
            self.logger.warning(f"WARNING: Errore creazione schema [{schema_name}] in [{db_name}]: {e}")

    def ensure_schema_exists(self, db_name: str, schema_name: str):
        """Alias per compatibilità con codice esistente"""
        self.create_schema_if_not_exists(db_name, schema_name)