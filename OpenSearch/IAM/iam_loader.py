"""
================================================================================
FILE: iam_loader.py
================================================================================
IAM Requests Loader - OpenSearch

Carica le richieste IAM da Oracle (IAM.STORICO_RICHIESTE) in OpenSearch
Legge gli ultimi 30 giorni di richieste

UTILIZZO:
    from iam_loader import IAMRequestsLoader

    loader = IAMRequestsLoader(
        oracle_host='10.22.112.70',
        oracle_port=1551,
        oracle_service_name='iam.griffon.local',
        oracle_user='X1090405',
        oracle_password='password'
    )
    loader.create_iam_index()
    richieste = loader.fetch_from_oracle(days=30)
    loader.bulk_insert(richieste)
================================================================================
"""

from opensearchpy import OpenSearch, helpers
from datetime import datetime, timedelta
import oracledb
from typing import List, Dict, Any

# Usa thin mode (no Oracle Client needed)
oracledb.init_oracle_client(lib_dir=None)


class IAMRequestsLoader:
    """Gestisce il caricamento delle richieste IAM da Oracle a OpenSearch"""

    def __init__(self, host='localhost', port=9200,
                 oracle_host='localhost', oracle_port=1521,
                 oracle_service_name='ORCL', oracle_user='admin',
                 oracle_password='password', use_ssl=False):
        """Inizializza connessioni a OpenSearch e Oracle"""

        # Connessione OpenSearch (NO SECURITY)
        self.os_client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            use_ssl=use_ssl,
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30,
            max_retries=3,
            retry_on_timeout=True
        )

        # Connessione Oracle
        self.oracle_host = oracle_host
        self.oracle_port = oracle_port
        self.oracle_service_name = oracle_service_name
        self.oracle_user = oracle_user
        self.oracle_password = oracle_password
        self.db_connection = None

        try:
            info = self.os_client.info()
            print(f"✓ Connesso a OpenSearch {info['version']['number']} (NO SECURITY)")
        except Exception as e:
            print(f"✗ Errore connessione OpenSearch: {e}")
            raise

    def _connect_oracle(self):
        """Connette a Oracle"""
        try:
            dsn = oracledb.makedsn(
                self.oracle_host,
                self.oracle_port,
                service_name=self.oracle_service_name
            )
            connection = oracledb.connect(
                user=self.oracle_user,
                password=self.oracle_password,
                dsn=dsn
            )
            print(f"✓ Connesso a Oracle: {self.oracle_user}@{self.oracle_service_name}")
            return connection
        except Exception as e:
            print(f"✗ Errore connessione Oracle: {e}")
            print("\n🔧 Verifica:")
            print("   1. Oracle DB è in esecuzione?")
            print("   2. Service Name corretto?")
            print("   3. Credentials corretti?")
            print("   4. Host e port corretti?")
            print("   5. oracledb installato? pip install oracledb")
            raise

    def create_iam_index(self, index_name='iam-richieste'):
        """Crea l'indice IAM con mappings ottimizzati"""
        mappings = {
            'properties': {
                'ID_RICHIESTA': {'type': 'keyword'},
                'FK_ID_OGGETTO': {'type': 'keyword'},
                'NOME_UTENZA': {'type': 'keyword'},
                'FK_TIPO_RICHIESTA': {'type': 'keyword'},
                'FK_TIPO_UTENZA': {'type': 'keyword'},
                'FK_NOME_OPERAZIONE': {'type': 'keyword'},
                'ID_RICHIESTA_PARENT': {'type': 'keyword'},
                'DATA_CREAZIONE': {'type': 'date'},
                'DATA_CHIUSURA': {'type': 'date'},
                'FK_UTENTE': {'type': 'keyword'},
                'FK_UTENTE_RICHIEDENTE': {'type': 'keyword'},
                'STATO': {'type': 'keyword'},
                'NOTA': {'type': 'text'},
                'FLAG_TRANSAZIONE': {'type': 'keyword'},
                'DATA_STORICIZZAZIONE': {'type': 'date'},
                'FK_ID_LAV_DETTAGLIO': {'type': 'keyword'},
                'MODALITA_LAV_MASS': {'type': 'keyword'},
                'INOLTRO_GGU': {'type': 'keyword'},
                'FLAG_INTERSEZIONE_PARAMETRI': {'type': 'keyword'},
                'TOOL_GENERAZIONE': {'type': 'keyword'},
                'FLAG_HAS_CHILDREN': {'type': 'keyword'},
                'FLAG_OP_SEC_SELEZIONATA': {'type': 'keyword'},
                'PRIORITA_SECONDARIA': {'type': 'integer'},
                'TIPO_OP_SECONDARIA': {'type': 'integer'},
                'COMUNICAZIONE_UF': {'type': 'text'},
                'giorni_elaborazione': {'type': 'integer'},
                'ore_elaborazione': {'type': 'float'},
                'is_completed': {'type': 'boolean'},
                'is_failed': {'type': 'boolean'},
                'is_pending': {'type': 'boolean'}
            }
        }

        settings = {
            'number_of_shards': 2,
            'number_of_replicas': 0,
            'index': {'refresh_interval': '5s'}
        }

        try:
            if self.os_client.indices.exists(index=index_name):
                print(f"⚠ Indice '{index_name}' già esistente")
                return True

            self.os_client.indices.create(
                index=index_name,
                body={'mappings': mappings, 'settings': settings}
            )
            print(f"✓ Indice '{index_name}' creato")
            return True
        except Exception as e:
            print(f"✗ Errore creazione indice: {e}")
            return False

    def fetch_from_oracle(self, days=30) -> List[Dict]:
        """
        Legge le richieste da IAM.STORICO_RICHIESTE degli ultimi N giorni

        Args:
            days: numero di giorni indietro da leggere (default 30)

        Returns:
            Lista di richieste come dict
        """
        try:
            self.db_connection = self._connect_oracle()
            cursor = self.db_connection.cursor()

            query = f"""
                SELECT
                    ID_RICHIESTA,
                    FK_ID_OGGETTO,
                    NOME_UTENZA,
                    FK_TIPO_RICHIESTA,
                    FK_TIPO_UTENZA,
                    FK_NOME_OPERAZIONE,
                    ID_RICHIESTA_PARENT,
                    DATA_CREAZIONE,
                    DATA_CHIUSURA,
                    FK_UTENTE,
                    FK_UTENTE_RICHIEDENTE,
                    STATO,
                    NOTA,
                    FLAG_TRANSAZIONE,
                    DATA_STORICIZZAZIONE,
                    FK_ID_LAV_DETTAGLIO,
                    MODALITA_LAV_MASS,
                    INOLTRO_GGU,
                    FLAG_INTERSEZIONE_PARAMETRI,
                    TOOL_GENERAZIONE,
                    FLAG_HAS_CHILDREN,
                    FLAG_OP_SEC_SELEZIONATA,
                    PRIORITA_SECONDARIA,
                    TIPO_OP_SECONDARIA,
                    COMUNICAZIONE_UF
                FROM IAM.STORICO_RICHIESTE
                WHERE DATA_CREAZIONE >= TRUNC(SYSDATE) - {days}
                ORDER BY DATA_CREAZIONE DESC
            """

            print(f"⏳ Lettura da Oracle (ultimi {days} giorni)...")
            start_time = datetime.now()
            cursor.execute(query)

            # Ottieni nomi colonne
            columns = [desc[0] for desc in cursor.description]

            # Costruisci lista di dict
            rows = []
            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))

                # Converti timestamp Oracle a ISO string
                for key, value in row_dict.items():
                    if isinstance(value, datetime):
                        row_dict[key] = value.isoformat()

                # Calcola metriche
                if row_dict.get('DATA_CREAZIONE') and row_dict.get('DATA_CHIUSURA'):
                    try:
                        data_c = datetime.fromisoformat(row_dict['DATA_CREAZIONE'])
                        data_ch = datetime.fromisoformat(row_dict['DATA_CHIUSURA'])
                        row_dict['giorni_elaborazione'] = (data_ch - data_c).days
                        row_dict['ore_elaborazione'] = (data_ch - data_c).total_seconds() / 3600
                    except:
                        row_dict['giorni_elaborazione'] = None
                        row_dict['ore_elaborazione'] = None
                else:
                    row_dict['giorni_elaborazione'] = None
                    row_dict['ore_elaborazione'] = None

                # Determina status (Griffon uses: EVASA, NON EVASA, ANNULLATA)
                stato = row_dict.get('STATO', '').upper()
                row_dict['is_completed'] = 'EVASA' in stato
                row_dict['is_failed'] = 'ANNULLATA' in stato
                row_dict['is_pending'] = 'NON EVASA' in stato

                rows.append(row_dict)

            cursor.close()
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"✓ Caricate {len(rows)} richieste da Oracle ({elapsed:.2f}s)")
            return rows

        except Exception as e:
            print(f"✗ Errore lettura Oracle: {e}")
            return []
        finally:
            if self.db_connection:
                self.db_connection.close()

    def bulk_insert(self, richieste: List[Dict], index_name='iam-richieste') -> Dict:
        """Inserisce le richieste in bulk"""
        try:
            actions = [
                {
                    '_index': index_name,
                    '_source': richiesta
                }
                for richiesta in richieste
            ]

            success, failed = helpers.bulk(
                self.os_client,
                actions,
                raise_on_error=False,
                refresh=True,
                chunk_size=500
            )

            print(f"✓ Inserite {success} richieste ({len(failed)} fallimenti)")
            return {
                'success': success,
                'failed': len(failed),
                'total': len(richieste)
            }
        except Exception as e:
            print(f"✗ Errore inserimento: {e}")
            return {'success': 0, 'failed': len(richieste), 'total': len(richieste)}

    def count_documents(self, index_name='iam-richieste') -> int:
        """Conta i documenti nell'indice"""
        try:
            response = self.os_client.count(index=index_name)
            count = response['count']
            print(f"✓ Totale richieste in OpenSearch: {count}")
            return count
        except Exception as e:
            print(f"✗ Errore conteggio: {e}")
            return 0


if __name__ == '__main__':
    print("="*80)
    print("IAM LOADER - Caricamento da Oracle a OpenSearch")
    print("="*80)

    try:
        loader = IAMRequestsLoader(
            host='localhost',
            port=9200,
            oracle_host='10.22.112.70',              # ← MODIFICA
            oracle_port=1551,
            oracle_service_name='iam.griffon.local', # ← MODIFICA
            oracle_user='X1090405',                  # ← MODIFICA
            oracle_password='Fhdf!K42retwH'         # ← MODIFICA
        )

        print("\n1. Creazione indice...\n")
        loader.create_iam_index()

        print("\n2. Lettura ultimi 30 giorni da Oracle...\n")
        richieste = loader.fetch_from_oracle(days=30)

        if not richieste:
            print("⚠ Nessun dato letto!")
            exit(1)

        print("\n3. Inserimento in OpenSearch...\n")
        loader.bulk_insert(richieste)

        print("\n4. Verifica...\n")
        loader.count_documents()

        print("\n✓ Caricamento completato!")

    except Exception as e:
        print(f"\n✗ Errore: {e}")