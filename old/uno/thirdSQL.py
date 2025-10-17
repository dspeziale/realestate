"""
OpenSearch IAM Activity Analysis - Oracle STORICO_RICHIESTE
===========================================================

Script per monitorare la tabella IAM.STORICO_RICHIESTE da Oracle
e analizzare le richieste di accesso nel sistema IAM

Installazione: pip install oracledb opensearch-py
"""

from opensearchpy import OpenSearch, helpers
from datetime import datetime, timedelta
from typing import List, Dict, Any
import oracledb
import json
import sys

# Disabilita thick mode se non hai Oracle Client installato
oracledb.init_oracle_client(lib_dir=None)  # Usa thin mode (no Oracle Client needed)


class IamActivityAnalyzer:
    """
    Analizza le richieste IAM dalla tabella STORICO_RICHIESTE
    """

    def __init__(self, oracle_host='localhost', oracle_port=1521,
                 oracle_service_name='ORCL', oracle_user='admin', oracle_password='password',
                 os_host='localhost', os_port=9200):
        """
        Inizializza connessioni a Oracle e OpenSearch

        Args:
            oracle_host: host Oracle
            oracle_port: porta Oracle (default 1521)
            oracle_service_name: Service Name Oracle (non SID!)
            oracle_user: utente Oracle
            oracle_password: password Oracle
            os_host: host OpenSearch
            os_port: porta OpenSearch
        """
        self.db_connection = self._connect_oracle(
            oracle_host, oracle_port, oracle_service_name, oracle_user, oracle_password
        )
        self.os_client = self._connect_opensearch(os_host, os_port)

    def _connect_oracle(self, host, port, service_name, user, password):
        """Connessione a Oracle con Service Name"""
        try:
            dsn = oracledb.makedsn(host, port, service_name=service_name)
            connection = oracledb.connect(user=user, password=password, dsn=dsn)
            print(f"✓ Oracle connesso: {user}@{service_name}")
            return connection
        except Exception as e:
            print(f"✗ Errore connessione Oracle: {e}")
            print("\n🔧 Verifica:")
            print("   1. Oracle DB è in esecuzione?")
            print("   2. Service Name corretto?")
            print("   3. Credentials corretti (user/password)?")
            print("   4. Host e port corretti?")
            print("   5. oracledb installato? pip install oracledb")
            raise

    def _connect_opensearch(self, host, port):
        """Connessione a OpenSearch"""
        try:
            client = OpenSearch(
                hosts=[{'host': host, 'port': port}],
                http_auth=('admin', 'admin'),
                use_ssl=False,
                verify_certs=False,
                ssl_show_warn=False,
                timeout=30,
                max_retries=3
            )
            info = client.info()
            print(f"✓ OpenSearch: {info['version']['number']}")
            return client
        except Exception as e:
            print(f"✗ Errore connessione OpenSearch: {e}")
            raise

    def fetch_richieste(self, days=7) -> List[Dict]:
        """
        Legge le richieste da IAM.STORICO_RICHIESTE

        Args:
            days: numero di giorni indietro da leggere (default 7)

        Returns:
            Lista di richieste come dict
        """
        try:
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
                    elif value is None:
                        row_dict[key] = None

                # Calcola giorni di elaborazione
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

                # Determina se richiesta completata
                row_dict['is_completed'] = row_dict['STATO'] in ['COMPLETATA', 'CLOSED', 'CHIUSA']
                row_dict['is_failed'] = row_dict['STATO'] in ['ERRORE', 'FALLITA', 'REJECTED']
                row_dict['is_pending'] = row_dict['STATO'] in ['IN ATTESA', 'PENDING', 'IN ELABORAZIONE']

                rows.append(row_dict)

            cursor.close()
            print(f"✓ Lette {len(rows)} richieste da IAM.STORICO_RICHIESTE")
            return rows

        except Exception as e:
            print(f"✗ Errore query Oracle: {e}")
            return []

    def create_iam_index(self, index_name='iam-richieste'):
        """Crea indice per le richieste IAM"""
        if self.os_client.indices.exists(index=index_name):
            self.os_client.indices.delete(index=index_name)
            print(f"⚠ Indice '{index_name}' eliminato")

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

        self.os_client.indices.create(
            index=index_name,
            body={'mappings': mappings, 'settings': settings}
        )
        print(f"✓ Indice '{index_name}' creato")

    def insert_richieste(self, richieste: List[Dict], index_name='iam-richieste'):
        """Inserisce le richieste in OpenSearch"""
        try:
            actions = [
                {'_index': index_name, '_source': richiesta}
                for richiesta in richieste
            ]

            success, failed = helpers.bulk(
                self.os_client,
                actions,
                raise_on_error=False,
                refresh=True
            )

            print(f"✓ Inserite {success} richieste ({len(failed)} fallimenti)")
            return success

        except Exception as e:
            print(f"✗ Errore inserimento: {e}")
            return 0

    # ========== ANALISI ==========

    def analisi_generale(self, index_name='iam-richieste'):
        """Analisi generale"""
        print("\n" + "=" * 70)
        print("ANALISI GENERALE RICHIESTE IAM")
        print("=" * 70)

        response = self.os_client.count(index=index_name)
        total = response['count']

        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'completate': {'filter': {'term': {'is_completed': True}}},
                    'fallite': {'filter': {'term': {'is_failed': True}}},
                    'in_attesa': {'filter': {'term': {'is_pending': True}}},
                    'ore_medio_proc': {'avg': {'field': 'ore_elaborazione'}}
                }
            }
        )

        aggs = response['aggregations']
        completate = aggs['completate']['doc_count']
        fallite = aggs['fallite']['doc_count']
        in_attesa = aggs['in_attesa']['doc_count']
        ore_medio = aggs['ore_medio_proc']['value'] or 0

        print(f"\nTotale richieste: {total}")
        print(f"  ✓ Completate: {completate} ({completate/total*100:.1f}%)")
        print(f"  ✗ Fallite: {fallite} ({fallite/total*100:.1f}%)")
        print(f"  ⏳ In attesa: {in_attesa} ({in_attesa/total*100:.1f}%)")
        print(f"\nTempo medio elaborazione: {ore_medio:.2f} ore")

    def analisi_tipo_richiesta(self, index_name='iam-richieste'):
        """Distribuzione tipo richiesta"""
        print("\n" + "=" * 70)
        print("DISTRIBUZIONE TIPO RICHIESTA")
        print("=" * 70 + "\n")

        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_tipo': {
                        'terms': {'field': 'FK_TIPO_RICHIESTA', 'size': 20},
                        'aggs': {
                            'completate': {'filter': {'term': {'is_completed': True}}},
                            'fallite': {'filter': {'term': {'is_failed': True}}},
                            'ore_medio': {'avg': {'field': 'ore_elaborazione'}}
                        }
                    }
                }
            }
        )

        total = response['hits']['total']['value']
        for bucket in response['aggregations']['by_tipo']['buckets']:
            tipo = bucket['key']
            count = bucket['doc_count']
            completate = bucket['completate']['doc_count']
            fallite = bucket['fallite']['doc_count']
            ore_medio = bucket['ore_medio']['value'] or 0

            success_rate = (completate / count * 100) if count > 0 else 0
            pct = (count / total * 100) if total > 0 else 0

            print(f"  {tipo}")
            print(f"    Richieste: {count} ({pct:.1f}%)")
            print(f"    Success: {success_rate:.1f}% | Errori: {fallite} | Tempo medio: {ore_medio:.2f}h")

    def analisi_per_utente(self, index_name='iam-richieste', limit=15):
        """Utenti più attivi"""
        print("\n" + "=" * 70)
        print(f"TOP {limit} UTENTI PIÙ ATTIVI")
        print("=" * 70 + "\n")

        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_user': {
                        'terms': {'field': 'FK_UTENTE', 'size': limit},
                        'aggs': {
                            'completate': {'filter': {'term': {'is_completed': True}}},
                            'fallite': {'filter': {'term': {'is_failed': True}}},
                            'ore_medio': {'avg': {'field': 'ore_elaborazione'}}
                        }
                    }
                }
            }
        )

        for i, bucket in enumerate(response['aggregations']['by_user']['buckets'], 1):
            user = bucket['key']
            count = bucket['doc_count']
            completate = bucket['completate']['doc_count']
            fallite = bucket['fallite']['doc_count']
            ore_medio = bucket['ore_medio']['value'] or 0

            success_rate = (completate / count * 100) if count > 0 else 0

            print(f"  {i}. {user}")
            print(f"     Richieste: {count} | Success: {success_rate:.1f}% | Errori: {fallite} | Tempo: {ore_medio:.2f}h")

    def analisi_per_stato(self, index_name='iam-richieste'):
        """Richieste per stato"""
        print("\n" + "=" * 70)
        print("RICHIESTE PER STATO")
        print("=" * 70 + "\n")

        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_stato': {
                        'terms': {'field': 'STATO', 'size': 30}
                    }
                }
            }
        )

        total = response['hits']['total']['value']
        for bucket in response['aggregations']['by_stato']['buckets']:
            stato = bucket['key']
            count = bucket['doc_count']
            pct = (count / total * 100) if total > 0 else 0

            if 'COMPLETATA' in stato.upper() or 'CHIUSA' in stato.upper():
                icon = "✓"
            elif 'ERRORE' in stato.upper() or 'FALLITA' in stato.upper():
                icon = "✗"
            elif 'ATTESA' in stato.upper() or 'PENDING' in stato.upper():
                icon = "⏳"
            else:
                icon = "→"

            print(f"  {icon} {stato}: {count} ({pct:.1f}%)")

    def analisi_operazioni(self, index_name='iam-richieste', limit=10):
        """Top operazioni"""
        print("\n" + "=" * 70)
        print(f"TOP {limit} OPERAZIONI PIÙ FREQUENTI")
        print("=" * 70 + "\n")

        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_op': {
                        'terms': {'field': 'FK_NOME_OPERAZIONE', 'size': limit},
                        'aggs': {
                            'completate': {'filter': {'term': {'is_completed': True}}},
                            'fallite': {'filter': {'term': {'is_failed': True}}}
                        }
                    }
                }
            }
        )

        for i, bucket in enumerate(response['aggregations']['by_op']['buckets'], 1):
            operazione = bucket['key'] or 'N/A'
            count = bucket['doc_count']
            completate = bucket['completate']['doc_count']
            fallite = bucket['fallite']['doc_count']

            success_rate = (completate / count * 100) if count > 0 else 0

            print(f"  {i}. {operazione}")
            print(f"     Totale: {count} | Success: {success_rate:.1f}% | Errori: {fallite}")

    def analisi_timeline(self, index_name='iam-richieste', interval='1d'):
        """Timeline richieste nel tempo"""
        print("\n" + "=" * 70)
        print(f"TIMELINE RICHIESTE (intervallo: {interval})")
        print("=" * 70 + "\n")

        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'timeline': {
                        'date_histogram': {
                            'field': 'DATA_CREAZIONE',
                            'fixed_interval': interval
                        },
                        'aggs': {
                            'completate': {'filter': {'term': {'is_completed': True}}},
                            'fallite': {'filter': {'term': {'is_failed': True}}}
                        }
                    }
                }
            }
        )

        buckets = response['aggregations']['timeline']['buckets']
        if not buckets:
            print("  Nessun dato")
            return

        max_count = max(b['doc_count'] for b in buckets)

        print()
        for bucket in buckets[-30:]:  # Ultimi 30 intervalli
            timestamp = bucket['key_as_string']
            count = bucket['doc_count']
            fallite = bucket['fallite']['doc_count']
            bar_width = int((count / max_count) * 25) if max_count > 0 else 0
            bar = '█' * bar_width

            print(f"  {timestamp}: {bar} {count:4d} (✗ {fallite})")

    def analisi_errori(self, index_name='iam-richieste', limit=10):
        """Richieste fallite"""
        print("\n" + "=" * 70)
        print(f"RICHIESTE FALLITE - ULTIMI {limit} ERRORI")
        print("=" * 70 + "\n")

        response = self.os_client.search(
            index=index_name,
            body={
                'query': {'term': {'is_failed': True}},
                'size': limit,
                'sort': [{'DATA_CREAZIONE': 'desc'}]
            }
        )

        if not response['hits']['hits']:
            print("  Nessuna richiesta fallita")
            return

        for hit in response['hits']['hits']:
            doc = hit['_source']
            print(f"  ID: {doc['ID_RICHIESTA']} | {doc['DATA_CREAZIONE']}")
            print(f"    Utente: {doc['FK_UTENTE']}")
            print(f"    Tipo: {doc['FK_TIPO_RICHIESTA']}")
            print(f"    Stato: {doc['STATO']}")
            if doc.get('NOTA'):
                print(f"    Nota: {doc['NOTA'][:100]}...")
            print()

    def analisi_richieste_lente(self, index_name='iam-richieste', ore_soglia=24, limit=10):
        """Richieste che impiegano troppo tempo"""
        print("\n" + "=" * 70)
        print(f"RICHIESTE LENTE (>{ore_soglia} ore) - TOP {limit}")
        print("=" * 70 + "\n")

        response = self.os_client.search(
            index=index_name,
            body={
                'query': {
                    'range': {'ore_elaborazione': {'gte': ore_soglia}}
                },
                'size': limit,
                'sort': [{'ore_elaborazione': 'desc'}]
            }
        )

        total_lente = response['hits']['total']['value']
        print(f"Totale richieste lente: {total_lente}\n")

        for hit in response['hits']['hits']:
            doc = hit['_source']
            ore = doc.get('ore_elaborazione', 0)
            giorni = doc.get('giorni_elaborazione', 0)

            print(f"  ID: {doc['ID_RICHIESTA']}")
            print(f"    Tempo: {giorni}g {ore-int(giorni)*24:.1f}h ({ore:.1f}h totali)")
            print(f"    Tipo: {doc['FK_TIPO_RICHIESTA']}")
            print(f"    Utente: {doc['FK_UTENTE']}")
            print(f"    Stato: {doc['STATO']}")
            print()

    def analisi_per_tipo_utenza(self, index_name='iam-richieste'):
        """Richieste per tipo di utenza"""
        print("\n" + "=" * 70)
        print("RICHIESTE PER TIPO DI UTENZA")
        print("=" * 70 + "\n")

        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_tipo_utenza': {
                        'terms': {'field': 'FK_TIPO_UTENZA', 'size': 20},
                        'aggs': {
                            'completate': {'filter': {'term': {'is_completed': True}}},
                            'fallite': {'filter': {'term': {'is_failed': True}}}
                        }
                    }
                }
            }
        )

        total = response['hits']['total']['value']
        for bucket in response['aggregations']['by_tipo_utenza']['buckets']:
            tipo = bucket['key'] or 'N/A'
            count = bucket['doc_count']
            completate = bucket['completate']['doc_count']
            fallite = bucket['fallite']['doc_count']

            success_rate = (completate / count * 100) if count > 0 else 0
            pct = (count / total * 100) if total > 0 else 0

            print(f"  {tipo}")
            print(f"    Richieste: {count} ({pct:.1f}%) | Success: {success_rate:.1f}% | Errori: {fallite}")


def main():
    """Esegue l'analisi completa"""
    print("=" * 70)
    print("OPENSEARCH IAM ANALYSIS - STORICO_RICHIESTE")
    print("=" * 70 + "\n")

    try:
        # 1. CONNESSIONE
        print("1. Connessione ai sistemi...\n")

        analyzer = IamActivityAnalyzer(
            oracle_host='10.22.112.70',           # Cambia con il tuo host Oracle
            oracle_port=1551,
            oracle_service_name='iam.griffon.local',        # 👈 SERVICE NAME (non SID!)
            oracle_user='X1090405',               # Cambia con il tuo utente
            oracle_password='Fhdf!K42retwH',        # Cambia con la tua password
            os_host='localhost',
            os_port=9200
        )

        # 2. LETTURA DATI
        print("\n2. Lettura richieste da IAM.STORICO_RICHIESTE...\n")
        richieste = analyzer.fetch_richieste(days=10)  # Ultimi 30 giorni

        if not richieste:
            print("✗ Nessun dato letto")
            return

        # 3. CREAZIONE INDICE
        print("\n3. Creazione indice OpenSearch...\n")
        analyzer.create_iam_index('iam-richieste')

        # 4. INSERIMENTO
        print("\n4. Inserimento in OpenSearch...\n")
        analyzer.insert_richieste(richieste, 'iam-richieste')

        # 5. ANALISI
        print("\n5. Esecuzione analisi...\n")
        analyzer.analisi_generale('iam-richieste')
        analyzer.analisi_tipo_richiesta('iam-richieste')
        analyzer.analisi_per_utente('iam-richieste', limit=20)
        analyzer.analisi_per_stato('iam-richieste')
        analyzer.analisi_operazioni('iam-richieste', limit=15)
        analyzer.analisi_timeline('iam-richieste', interval='1d')
        analyzer.analisi_per_tipo_utenza('iam-richieste')
        analyzer.analisi_errori('iam-richieste', limit=10)
        analyzer.analisi_richieste_lente('iam-richieste', ore_soglia=24, limit=10)

        print("\n" + "=" * 70)
        print("✅ ANALISI COMPLETATA!")
        print("=" * 70)
        print("\n📊 Visualizza i dati: http://localhost:5601")
        print("   Menu → Discover → Seleziona 'iam-richieste'")

    except Exception as e:
        print(f"\n✗ Errore fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()