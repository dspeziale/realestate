"""
OpenSearch Activity Analysis - Lettura da MSSQL
================================================

Script per estrarre dati di attività da MSSQL e analizzarli in OpenSearch
"""

import pyodbc
from opensearchpy import OpenSearch, helpers
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json

class MSSQLActivityReader:
    """
    Legge i dati di attività da MSSQL
    """

    def __init__(self, server: str, database: str, username: str, password: str):
        """
        Inizializza connessione a MSSQL

        Args:
            server: Server MSSQL (es: 'localhost' o 'SERVER\\INSTANCE')
            database: Nome database
            username: Utente
            password: Password
        """
        self.connection_string = (
            f'DRIVER={{ODBC Driver 17 for SQL Server}};'
            f'SERVER={server};'
            f'DATABASE={database};'
            f'UID={username};'
            f'PWD={password}'
        )

        try:
            self.conn = pyodbc.connect(self.connection_string)
            self.cursor = self.conn.cursor()
            print(f"✓ Connesso a MSSQL: {server}/{database}")
        except Exception as e:
            print(f"✗ Errore connessione MSSQL: {e}")
            raise

    def fetch_activities(self, days: int = 30) -> List[Dict]:
        """
        Estrae le attività dalle ultime N giorni

        La query assume questa struttura di tabelle:
        - Activities: id, user_id, action, timestamp, status, resource_type
        - Users: id, username, email, department, role
        - Resources: id, name, type, category
        """
        query = f"""
        SELECT 
            a.ActivityID as activity_id,
            a.UserID as user_id,
            u.Username as username,
            u.Email as email,
            u.Department as department,
            u.Role as role,
            a.Action as action,
            a.ResourceType as resource_type,
            r.ResourceName as resource_name,
            r.ResourceCategory as resource_category,
            a.Status as status,
            a.Duration as duration_ms,
            a.Timestamp as timestamp,
            a.Details as details,
            a.IPAddress as ip_address,
            DATEDIFF(DAY, a.Timestamp, GETDATE()) as days_ago
        FROM Activities a
        INNER JOIN Users u ON a.UserID = u.UserID
        LEFT JOIN Resources r ON a.ResourceID = r.ResourceID
        WHERE a.Timestamp >= DATEADD(DAY, -{days}, CAST(GETDATE() AS DATE))
        ORDER BY a.Timestamp DESC
        """

        try:
            self.cursor.execute(query)
            columns = [desc[0] for desc in self.cursor.description]
            activities = []

            for row in self.cursor.fetchall():
                activity = dict(zip(columns, row))
                # Converti timestamp a ISO format per OpenSearch
                if activity['timestamp']:
                    activity['timestamp'] = activity['timestamp'].isoformat()
                activities.append(activity)

            print(f"✓ Estratte {len(activities)} attività da MSSQL")
            return activities

        except Exception as e:
            print(f"✗ Errore lettura attività: {e}")
            return []

    def fetch_activities_by_user(self, user_id: int) -> List[Dict]:
        """Attività specifiche di un utente"""
        query = """
        SELECT TOP 1000
            a.ActivityID as activity_id,
            a.Action as action,
            a.Status as status,
            a.Duration as duration_ms,
            a.Timestamp as timestamp,
            a.ResourceType as resource_type,
            r.ResourceName as resource_name
        FROM Activities a
        LEFT JOIN Resources r ON a.ResourceID = r.ResourceID
        WHERE a.UserID = ?
        ORDER BY a.Timestamp DESC
        """

        try:
            self.cursor.execute(query, user_id)
            columns = [desc[0] for desc in self.cursor.description]
            activities = []

            for row in self.cursor.fetchall():
                activity = dict(zip(columns, row))
                if activity['timestamp']:
                    activity['timestamp'] = activity['timestamp'].isoformat()
                activities.append(activity)

            return activities
        except Exception as e:
            print(f"✗ Errore: {e}")
            return []

    def close(self):
        """Chiude la connessione"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

class ActivityAnalyzer:
    """
    Analizza le attività in OpenSearch
    """

    def __init__(self, host='localhost', port=9200):
        """Inizializza connessione OpenSearch"""
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            http_auth=('admin', 'admin'),
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30
        )

        try:
            info = self.client.info()
            print(f"✓ Connesso a OpenSearch {info['version']['number']}")
        except Exception as e:
            print(f"✗ Errore connessione OpenSearch: {e}")
            raise

    def create_activity_index(self, index_name='activities'):
        """Crea indice con mappings appropriati"""
        mappings = {
            'properties': {
                'activity_id': {'type': 'keyword'},
                'user_id': {'type': 'integer'},
                'username': {'type': 'keyword'},
                'email': {'type': 'keyword'},
                'department': {'type': 'keyword'},
                'role': {'type': 'keyword'},
                'action': {'type': 'keyword'},
                'resource_type': {'type': 'keyword'},
                'resource_name': {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},
                'resource_category': {'type': 'keyword'},
                'status': {'type': 'keyword'},
                'duration_ms': {'type': 'integer'},
                'timestamp': {'type': 'date'},
                'details': {'type': 'text'},
                'ip_address': {'type': 'ip'},
                'days_ago': {'type': 'integer'}
            }
        }

        settings = {
            'number_of_shards': 2,
            'number_of_replicas': 0,
            'index': {
                'refresh_interval': '5s'
            }
        }

        try:
            if self.client.indices.exists(index=index_name):
                self.client.indices.delete(index=index_name)
                print(f"⚠ Indice '{index_name}' eliminato")

            self.client.indices.create(
                index=index_name,
                body={'mappings': mappings, 'settings': settings}
            )
            print(f"✓ Indice '{index_name}' creato")
            return True
        except Exception as e:
            print(f"✗ Errore creazione indice: {e}")
            return False

    def insert_activities(self, activities: List[Dict], index_name='activities') -> int:
        """Inserisce attività con bulk"""
        try:
            actions = [
                {
                    '_index': index_name,
                    '_id': activity['activity_id'],
                    '_source': activity
                }
                for activity in activities
            ]

            success, failed = helpers.bulk(
                self.client,
                actions,
                raise_on_error=False,
                refresh=True
            )

            print(f"✓ Inserite {success} attività ({len(failed)} errori)")
            return success
        except Exception as e:
            print(f"✗ Errore inserimento: {e}")
            return 0

    # ========== ANALISI ==========

    def analisi_generale(self, index_name='activities'):
        """Statistiche generali"""
        print("\n" + "=" * 60)
        print("ANALISI GENERALE ATTIVITÀ")
        print("=" * 60)

        response = self.client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'total_count': {'value_count': {'field': 'activity_id'}},
                    'unique_users': {'cardinality': {'field': 'user_id'}},
                    'avg_duration': {'avg': {'field': 'duration_ms'}},
                    'status_dist': {'terms': {'field': 'status', 'size': 10}},
                    'action_dist': {'terms': {'field': 'action', 'size': 20}}
                }
            }
        )

        aggs = response['aggregations']
        print(f"\nTotale attività: {int(aggs['total_count']['value'])}")
        print(f"Utenti unici: {aggs['unique_users']['value']}")
        print(f"Durata media (ms): {aggs['avg_duration']['value']:.2f}")

        print("\nDistribuzione Status:")
        for bucket in aggs['status_dist']['buckets']:
            print(f"  {bucket['key']}: {bucket['doc_count']}")

        print("\nTop 10 Azioni:")
        for i, bucket in enumerate(aggs['action_dist']['buckets'][:10], 1):
            print(f"  {i}. {bucket['key']}: {bucket['doc_count']}")

    def analisi_per_utente(self, index_name='activities', top_n=15):
        """Top utenti per attività"""
        print("\n" + "=" * 60)
        print(f"TOP {top_n} UTENTI PIÙ ATTIVI")
        print("=" * 60 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_user': {
                        'terms': {'field': 'user_id', 'size': top_n},
                        'aggs': {
                            'username': {'terms': {'field': 'username', 'size': 1}},
                            'department': {'terms': {'field': 'department', 'size': 1}},
                            'avg_duration': {'avg': {'field': 'duration_ms'}}
                        }
                    }
                }
            }
        )

        for i, bucket in enumerate(response['aggregations']['by_user']['buckets'], 1):
            user_id = bucket['key']
            count = bucket['doc_count']
            username = bucket['username']['buckets'][0]['key'] if bucket['username']['buckets'] else 'Unknown'
            dept = bucket['department']['buckets'][0]['key'] if bucket['department']['buckets'] else 'N/A'
            avg_dur = bucket['avg_duration']['value']

            print(f"{i}. {username} (ID: {user_id})")
            print(f"   Attività: {count}, Durata media: {avg_dur:.0f}ms, Dipartimento: {dept}")

    def analisi_errori(self, index_name='activities'):
        """Analisi errori e fallimenti"""
        print("\n" + "=" * 60)
        print("ANALISI ERRORI E ANOMALIE")
        print("=" * 60)

        response = self.client.search(
            index=index_name,
            body={
                'query': {'term': {'status': 'error'}},
                'size': 0,
                'aggs': {
                    'error_by_action': {
                        'terms': {'field': 'action', 'size': 10}
                    },
                    'error_by_user': {
                        'terms': {'field': 'username', 'size': 10}
                    },
                    'error_by_resource': {
                        'terms': {'field': 'resource_type', 'size': 10}
                    }
                }
            }
        )

        total_errors = response['hits']['total']['value']
        print(f"\nTotale errori: {total_errors}\n")

        print("Errori per azione:")
        for bucket in response['aggregations']['error_by_action']['buckets']:
            print(f"  {bucket['key']}: {bucket['doc_count']}")

        print("\nUtenti con più errori:")
        for bucket in response['aggregations']['error_by_user']['buckets']:
            print(f"  {bucket['key']}: {bucket['doc_count']}")

    def analisi_performance(self, index_name='activities', threshold_ms=5000):
        """Attività lente (sopra threshold)"""
        print("\n" + "=" * 60)
        print(f"ATTIVITÀ LENTE (>{threshold_ms}ms)")
        print("=" * 60 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'query': {'range': {'duration_ms': {'gte': threshold_ms}}},
                'size': 0,
                'aggs': {
                    'by_action': {
                        'terms': {'field': 'action', 'size': 10},
                        'aggs': {
                            'avg_time': {'avg': {'field': 'duration_ms'}},
                            'max_time': {'max': {'field': 'duration_ms'}},
                            'users': {'terms': {'field': 'username', 'size': 3}}
                        }
                    }
                }
            }
        )

        total = response['hits']['total']['value']
        print(f"Totale attività lente: {total}\n")

        for bucket in response['aggregations']['by_action']['buckets']:
            action = bucket['key']
            count = bucket['doc_count']
            avg = bucket['avg_time']['value']
            max_val = bucket['max_time']['value']

            print(f"{action}:")
            print(f"  Conteggio: {count}, Media: {avg:.0f}ms, Max: {max_val:.0f}ms")

    def analisi_timeline(self, index_name='activities', interval='1h'):
        """Attività nel tempo"""
        print("\n" + "=" * 60)
        print(f"TIMELINE ATTIVITÀ (intervallo: {interval})")
        print("=" * 60 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'timeline': {
                        'date_histogram': {
                            'field': 'timestamp',
                            'fixed_interval': interval
                        }
                    }
                }
            }
        )

        buckets = response['aggregations']['timeline']['buckets']
        if not buckets:
            print("Nessun dato disponibile")
            return

        max_count = max(b['doc_count'] for b in buckets)

        for bucket in buckets[-24:]:  # Ultimi 24 intervalli
            ts = bucket['key_as_string']
            count = bucket['doc_count']
            bar = '█' * int((count / max_count) * 25) if max_count > 0 else ''

            print(f"{ts}: {bar} {count}")

    def analisi_per_dipartimento(self, index_name='activities'):
        """Attività per dipartimento"""
        print("\n" + "=" * 60)
        print("ATTIVITÀ PER DIPARTIMENTO")
        print("=" * 60 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_dept': {
                        'terms': {'field': 'department', 'size': 20},
                        'aggs': {
                            'users_count': {'cardinality': {'field': 'user_id'}},
                            'avg_duration': {'avg': {'field': 'duration_ms'}},
                            'error_rate': {
                                'value_count': {
                                    'field': 'activity_id'
                                }
                            }
                        }
                    }
                }
            }
        )

        for bucket in response['aggregations']['by_dept']['buckets']:
            dept = bucket['key']
            count = bucket['doc_count']
            users = bucket['users_count']['value']
            avg_dur = bucket['avg_duration']['value']

            print(f"{dept}:")
            print(f"  Attività: {count}, Utenti: {users}, Durata media: {avg_dur:.0f}ms")

    def get_recent_activities(self, index_name='activities', limit=10):
        """Ultime attività"""
        print("\n" + "=" * 60)
        print(f"ULTIME {limit} ATTIVITÀ")
        print("=" * 60 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'size': limit,
                'sort': [{'timestamp': 'desc'}],
                '_source': ['username', 'action', 'resource_name', 'status', 'duration_ms', 'timestamp']
            }
        )

        for hit in response['hits']['hits']:
            doc = hit['_source']
            print(f"{doc['timestamp']}")
            print(f"  {doc['username']} → {doc['action']} ({doc['status']})")
            print(f"  Resource: {doc.get('resource_name', 'N/A')}, Duration: {doc['duration_ms']}ms\n")

def main():
    """Esecuzione principale"""
    print("=" * 60)
    print("OPENSEARCH ACTIVITY ANALYSIS - MSSQL INTEGRATION")
    print("=" * 60)

    # CONFIGURAZIONE MSSQL
    mssql_config = {
        'server': 'sl-3863\\replica',  # Modifica con il tuo server
        'database': 'monitoraggi',            # Modifica con il tuo database
        'username': 'sa',                    # Modifica con il tuo utente
        'password': 'stella*20'           # Modifica con la tua password
    }

    try:
        # 1. LETTURA DA MSSQL
        print("\n1. Lettura dati da MSSQL...")
        reader = MSSQLActivityReader(**mssql_config)
        activities = reader.fetch_activities(days=30)
        reader.close()

        if not activities:
            print("⚠ Nessun dato estratto da MSSQL")
            return

        # 2. INIZIALIZZAZIONE OPENSEARCH
        print("\n2. Inizializzazione OpenSearch...")
        analyzer = ActivityAnalyzer(host='localhost', port=9200)

        # 3. CREAZIONE INDICE
        print("\n3. Creazione indice...")
        analyzer.create_activity_index('activities')

        # 4. INSERIMENTO DATI
        print("\n4. Inserimento attività in OpenSearch...")
        analyzer.insert_activities(activities, 'activities')

        # 5. ESECUZIONE ANALISI
        print("\n5. Esecuzione analisi...")
        analyzer.analisi_generale('activities')
        analyzer.analisi_per_utente('activities', top_n=10)
        analyzer.analisi_errori('activities')
        analyzer.analisi_performance('activities', threshold_ms=1000)
        analyzer.analisi_per_dipartimento('activities')
        analyzer.analisi_timeline('activities', interval='1h')
        analyzer.get_recent_activities('activities', limit=5)

        print("\n" + "=" * 60)
        print("✅ ANALISI COMPLETATA!")
        print("=" * 60)
        print("\n📊 Accedi a OpenSearch Dashboards:")
        print("   http://localhost:5601")
        print("\n📝 Crea visualizzazioni basate sull'indice: activities")

    except Exception as e:
        print(f"\n✗ Errore: {e}")


if __name__ == "__main__":
    main()