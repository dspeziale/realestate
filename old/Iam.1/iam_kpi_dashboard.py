"""
OpenSearch IAM Activity Analysis - Sistema KPI e Dashboard Avanzato
====================================================================

Sistema professionale per monitoraggio IAM con:
- KPI calcolati automaticamente
- Visualizzazioni dashboard
- Analisi approfondite
- Export report

pip install oracledb opensearch-py requests
"""

from opensearchpy import OpenSearch, helpers
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import oracledb
import json
import sys
import requests


# ========== KPI DEFINITIONS ==========

class KPIStatus(Enum):
    """Stato del KPI"""
    EXCELLENT = "🟢"
    GOOD = "🟡"
    WARNING = "🟠"
    CRITICAL = "🔴"


@dataclass
class KPI:
    """Definizione di un KPI"""
    name: str
    description: str
    value: float
    unit: str
    status: KPIStatus
    target: float
    threshold_excellent: float
    threshold_warning: float
    trend: str = "stable"  # up, down, stable

    def get_status(self):
        """Determina lo stato basato sul valore"""
        if self.threshold_excellent is not None:
            if self.value >= self.threshold_excellent:
                return KPIStatus.EXCELLENT
            elif self.value >= self.threshold_warning:
                return KPIStatus.GOOD
            elif self.value >= (self.threshold_warning * 0.8):
                return KPIStatus.WARNING
            else:
                return KPIStatus.CRITICAL
        return KPIStatus.GOOD

    def to_dict(self):
        return {
            'name': self.name,
            'description': self.description,
            'value': round(self.value, 2),
            'unit': self.unit,
            'status': self.get_status().name,
            'status_icon': self.get_status().value,
            'target': self.target,
            'achievement': round((self.value / self.target * 100), 2) if self.target > 0 else 0,
            'trend': self.trend
        }


class KPIManager:
    """Gestisce il calcolo dei KPI"""

    def __init__(self, os_client: OpenSearch):
        self.os_client = os_client
        self.kpis: Dict[str, KPI] = {}

    def calculate_success_rate(self, index_name='iam-richieste') -> KPI:
        """KPI 1: Success Rate"""
        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'completate': {'filter': {'term': {'is_completed': True}}},
                    'totale': {'filter': {'match_all': {}}}
                }
            }
        )

        aggs = response['aggregations']
        completate = aggs['completate']['doc_count']
        totale = aggs['totale']['doc_count']

        success_rate = (completate / totale * 100) if totale > 0 else 0

        kpi = KPI(
            name="Success Rate",
            description="Percentuale di richieste completate con successo",
            value=success_rate,
            unit="%",
            status=KPIStatus.EXCELLENT,
            target=95,
            threshold_excellent=90,
            threshold_warning=80
        )
        self.kpis['success_rate'] = kpi
        return kpi

    def calculate_failure_rate(self, index_name='iam-richieste') -> KPI:
        """KPI 2: Failure Rate"""
        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'fallite': {'filter': {'term': {'is_failed': True}}},
                    'totale': {'filter': {'match_all': {}}}
                }
            }
        )

        aggs = response['aggregations']
        fallite = aggs['fallite']['doc_count']
        totale = aggs['totale']['doc_count']

        failure_rate = (fallite / totale * 100) if totale > 0 else 0

        kpi = KPI(
            name="Failure Rate",
            description="Percentuale di richieste fallite",
            value=failure_rate,
            unit="%",
            status=KPIStatus.EXCELLENT,
            target=5,
            threshold_excellent=5,
            threshold_warning=10
        )
        self.kpis['failure_rate'] = kpi
        return kpi

    def calculate_avg_processing_time(self, index_name='iam-richieste') -> KPI:
        """KPI 3: Average Processing Time"""
        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'avg_ore': {'avg': {'field': 'ore_elaborazione'}}
                }
            }
        )

        avg_ore = response['aggregations']['avg_ore']['value'] or 0

        kpi = KPI(
            name="Avg Processing Time",
            description="Tempo medio di elaborazione richieste",
            value=avg_ore,
            unit="ore",
            status=KPIStatus.EXCELLENT,
            target=24,
            threshold_excellent=24,
            threshold_warning=48
        )
        self.kpis['avg_processing_time'] = kpi
        return kpi

    def calculate_sla_compliance(self, index_name='iam-richieste', sla_hours=48) -> KPI:
        """KPI 4: SLA Compliance"""
        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'entro_sla': {
                        'filter': {'range': {'ore_elaborazione': {'lte': sla_hours}}}
                    },
                    'totale': {'filter': {'match_all': {}}}
                }
            }
        )

        aggs = response['aggregations']
        entro_sla = aggs['entro_sla']['doc_count']
        totale = aggs['totale']['doc_count']

        sla_compliance = (entro_sla / totale * 100) if totale > 0 else 0

        kpi = KPI(
            name="SLA Compliance",
            description=f"Percentuale richieste elaborate entro {sla_hours}h",
            value=sla_compliance,
            unit="%",
            status=KPIStatus.EXCELLENT,
            target=99,
            threshold_excellent=99,
            threshold_warning=95
        )
        self.kpis['sla_compliance'] = kpi
        return kpi

    def calculate_pending_requests(self, index_name='iam-richieste') -> KPI:
        """KPI 5: Pending Requests"""
        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'in_attesa': {'filter': {'term': {'is_pending': True}}}
                }
            }
        )

        in_attesa = response['aggregations']['in_attesa']['doc_count']

        kpi = KPI(
            name="Pending Requests",
            description="Numero di richieste ancora in elaborazione",
            value=in_attesa,
            unit="richieste",
            status=KPIStatus.EXCELLENT,
            target=0,
            threshold_excellent=10,
            threshold_warning=50
        )
        self.kpis['pending_requests'] = kpi
        return kpi

    def calculate_user_activity(self, index_name='iam-richieste') -> KPI:
        """KPI 6: Active Users"""
        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'unique_users': {'cardinality': {'field': 'FK_UTENTE'}}
                }
            }
        )

        unique_users = response['aggregations']['unique_users']['value']

        kpi = KPI(
            name="Active Users",
            description="Numero di utenti attivi nel sistema",
            value=unique_users,
            unit="utenti",
            status=KPIStatus.GOOD,
            target=100,
            threshold_excellent=50,
            threshold_warning=30
        )
        self.kpis['active_users'] = kpi
        return kpi

    def calculate_all_kpis(self, index_name='iam-richieste') -> Dict[str, KPI]:
        """Calcola tutti i KPI"""
        self.calculate_success_rate(index_name)
        self.calculate_failure_rate(index_name)
        self.calculate_avg_processing_time(index_name)
        self.calculate_sla_compliance(index_name)
        self.calculate_pending_requests(index_name)
        self.calculate_user_activity(index_name)
        return self.kpis

    def print_kpi_summary(self):
        """Stampa il riassunto KPI"""
        print("\n" + "=" * 80)
        print("📊 KPI SUMMARY - IAM SYSTEM HEALTH")
        print("=" * 80 + "\n")

        for kpi_name, kpi in self.kpis.items():
            kpi_dict = kpi.to_dict()
            print(f"{kpi_dict['status_icon']} {kpi_dict['name']}")
            print(f"   Valore: {kpi_dict['value']} {kpi_dict['unit']}")
            print(f"   Target: {kpi_dict['target']} | Raggiungimento: {kpi_dict['achievement']}%")
            print(f"   {kpi_dict['description']}")
            print()


class IamActivityAnalyzer:
    """Analizzatore IAM con KPI e visualizzazioni dashboard"""

    def __init__(self, oracle_host='localhost', oracle_port=1521,
                 oracle_service_name='ORCL', oracle_user='admin', oracle_password='password',
                 os_host='localhost', os_port=9200):
        """Inizializza connessioni a Oracle e OpenSearch"""
        self.db_connection = self._connect_oracle(
            oracle_host, oracle_port, oracle_service_name, oracle_user, oracle_password
        )
        self.os_client = self._connect_opensearch(os_host, os_port)
        self.kpi_manager = KPIManager(self.os_client)

    def _connect_oracle(self, host, port, service_name, user, password):
        """Connessione a Oracle"""
        try:
            dsn = oracledb.makedsn(host, port, service_name=service_name)
            connection = oracledb.connect(user=user, password=password, dsn=dsn)
            print(f"✓ Oracle connesso: {user}@{service_name}")
            return connection
        except Exception as e:
            print(f"✗ Errore connessione Oracle: {e}")
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
        """Legge richieste da IAM.STORICO_RICHIESTE"""
        try:
            cursor = self.db_connection.cursor()
            query = f"""
                SELECT ID_RICHIESTA, FK_ID_OGGETTO, NOME_UTENZA, FK_TIPO_RICHIESTA,
                       FK_TIPO_UTENZA, FK_NOME_OPERAZIONE, DATA_CREAZIONE, DATA_CHIUSURA,
                       FK_UTENTE, FK_UTENTE_RICHIEDENTE, STATO, NOTA,
                       FLAG_TRANSAZIONE, MODALITA_LAV_MASS, TOOL_GENERAZIONE
                FROM IAM.STORICO_RICHIESTE
                WHERE DATA_CREAZIONE >= TRUNC(SYSDATE) - {days}
                ORDER BY DATA_CREAZIONE DESC
            """

            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = []

            for row in cursor.fetchall():
                row_dict = dict(zip(columns, row))

                for key, value in row_dict.items():
                    if isinstance(value, datetime):
                        row_dict[key] = value.isoformat()

                if row_dict.get('DATA_CREAZIONE') and row_dict.get('DATA_CHIUSURA'):
                    try:
                        data_c = datetime.fromisoformat(row_dict['DATA_CREAZIONE'])
                        data_ch = datetime.fromisoformat(row_dict['DATA_CHIUSURA'])
                        row_dict['ore_elaborazione'] = (data_ch - data_c).total_seconds() / 3600
                    except:
                        row_dict['ore_elaborazione'] = 0
                else:
                    row_dict['ore_elaborazione'] = 0

                stato = (row_dict.get('STATO') or '').upper()
                row_dict['is_completed'] = 'COMPLETATA' in stato or 'CHIUSA' in stato
                row_dict['is_failed'] = 'ERRORE' in stato or 'FALLITA' in stato
                row_dict['is_pending'] = 'ATTESA' in stato or 'PENDING' in stato or 'ELABORAZIONE' in stato

                rows.append(row_dict)

            cursor.close()
            print(f"✓ Lette {len(rows)} richieste")
            return rows
        except Exception as e:
            print(f"✗ Errore query Oracle: {e}")
            return []

    def create_iam_index(self, index_name='iam-richieste'):
        """Crea indice per IAM con mappings ottimizzati"""
        if self.os_client.indices.exists(index=index_name):
            self.os_client.indices.delete(index=index_name)

        mappings = {
            'properties': {
                'ID_RICHIESTA': {'type': 'keyword'},
                'FK_ID_OGGETTO': {'type': 'keyword'},
                'NOME_UTENZA': {'type': 'keyword'},
                'FK_TIPO_RICHIESTA': {'type': 'keyword'},
                'FK_TIPO_UTENZA': {'type': 'keyword'},
                'FK_NOME_OPERAZIONE': {'type': 'keyword'},
                'DATA_CREAZIONE': {'type': 'date'},
                'DATA_CHIUSURA': {'type': 'date'},
                'FK_UTENTE': {'type': 'keyword'},
                'FK_UTENTE_RICHIEDENTE': {'type': 'keyword'},
                'STATO': {'type': 'keyword'},
                'NOTA': {'type': 'text'},
                'FLAG_TRANSAZIONE': {'type': 'keyword'},
                'MODALITA_LAV_MASS': {'type': 'keyword'},
                'TOOL_GENERAZIONE': {'type': 'keyword'},
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
        """Inserisce richieste in bulk"""
        actions = [
            {'_index': index_name, '_source': r}
            for r in richieste
        ]

        success, failed = helpers.bulk(self.os_client, actions, raise_on_error=False, refresh=True)
        print(f"✓ Inserite {success} richieste")
        return success

    # ========== ANALISI AVANZATE ==========

    def analisi_richieste_per_operazione(self, index_name='iam-richieste', limit=15):
        """Analisi dettagliata per operazione"""
        print("\n" + "=" * 80)
        print(f"📋 TOP {limit} OPERAZIONI - DETTAGLIO COMPLETO")
        print("=" * 80 + "\n")

        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_op': {
                        'terms': {'field': 'FK_NOME_OPERAZIONE', 'size': limit},
                        'aggs': {
                            'completate': {'filter': {'term': {'is_completed': True}}},
                            'fallite': {'filter': {'term': {'is_failed': True}}},
                            'in_attesa': {'filter': {'term': {'is_pending': True}}},
                            'tempo_medio': {'avg': {'field': 'ore_elaborazione'}},
                            'tempo_max': {'max': {'field': 'ore_elaborazione'}},
                            'tempo_percentile_95': {
                                'percentiles': {'field': 'ore_elaborazione', 'percents': [95]}
                            }
                        }
                    }
                }
            }
        )

        total = response['hits']['total']['value']
        for i, bucket in enumerate(response['aggregations']['by_op']['buckets'], 1):
            op = bucket['key'] or 'N/A'
            count = bucket['doc_count']
            completate = bucket['completate']['doc_count']
            fallite = bucket['fallite']['doc_count']
            in_attesa = bucket['in_attesa']['doc_count']
            tempo_medio = bucket['tempo_medio']['value'] or 0
            tempo_max = bucket['tempo_max']['value'] or 0
            p95 = bucket['tempo_percentile_95']['values'].get('95.0', 0)

            success_rate = (completate / count * 100) if count > 0 else 0
            pct = (count / total * 100) if total > 0 else 0

            print(f"{i}. {op}")
            print(f"   Totale: {count:5d} ({pct:5.1f}%) | Success: {success_rate:6.1f}%")
            print(f"   Completate: {completate} | Fallite: {fallite} | In attesa: {in_attesa}")
            print(f"   Tempo medio: {tempo_medio:7.2f}h | P95: {p95:7.2f}h | Max: {tempo_max:7.2f}h")
            print()

    def analisi_matrice_tipo_stato(self, index_name='iam-richieste'):
        """Matrice Tipo Richiesta vs Stato"""
        print("\n" + "=" * 80)
        print("📊 MATRICE TIPO RICHIESTA vs STATO")
        print("=" * 80 + "\n")

        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_tipo': {
                        'terms': {'field': 'FK_TIPO_RICHIESTA', 'size': 20},
                        'aggs': {
                            'by_stato': {
                                'terms': {'field': 'STATO', 'size': 10}
                            }
                        }
                    }
                }
            }
        )

        print(f"{'Tipo Richiesta':<30} | {'COMPLETATA':<12} | {'FALLITA':<12} | {'ATTESA':<12} | {'TOTALE':<12}")
        print("-" * 90)

        for tipo_bucket in response['aggregations']['by_tipo']['buckets']:
            tipo = tipo_bucket['key'] or 'N/A'
            tipo = tipo[:28]

            stati = {s['key']: s['doc_count'] for s in tipo_bucket['by_stato']['buckets']}
            completate = sum(c for s, c in stati.items() if 'COMPLET' in str(s).upper())
            fallita = sum(c for s, c in stati.items() if 'FALLITA' in str(s).upper())
            attesa = sum(c for s, c in stati.items() if 'ATTESA' in str(s).upper())
            totale = tipo_bucket['doc_count']

            print(f"{tipo:<30} | {completate:<12} | {fallita:<12} | {attesa:<12} | {totale:<12}")

    def analisi_performance_per_utente(self, index_name='iam-richieste', limit=20):
        """Performance e capacità per utente"""
        print("\n" + "=" * 80)
        print(f"👤 PERFORMANCE PER UTENTE - TOP {limit}")
        print("=" * 80 + "\n")

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
                            'tempo_medio': {'avg': {'field': 'ore_elaborazione'}}
                        }
                    }
                }
            }
        )

        print(f"{'Rank':<6} {'Utente':<20} {'Richieste':<12} {'Success %':<12} {'Errori':<8} {'Tempo Medio':<12}")
        print("-" * 80)

        for i, bucket in enumerate(response['aggregations']['by_user']['buckets'], 1):
            user = (bucket['key'] or 'N/A')[:18]
            count = bucket['doc_count']
            completate = bucket['completate']['doc_count']
            fallite = bucket['fallite']['doc_count']
            tempo = bucket['tempo_medio']['value'] or 0

            success_rate = (completate / count * 100) if count > 0 else 0

            print(f"{i:<6} {user:<20} {count:<12} {success_rate:>10.1f}% {fallite:<8} {tempo:>10.2f}h")

    def analisi_trend_temporale(self, index_name='iam-richieste', interval='1d'):
        """Trend temporale con previsioni"""
        print("\n" + "=" * 80)
        print(f"📈 TREND TEMPORALE (intervallo: {interval})")
        print("=" * 80 + "\n")

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
                            'fallite': {'filter': {'term': {'is_failed': True}}},
                            'tempo_medio': {'avg': {'field': 'ore_elaborazione'}}
                        }
                    }
                }
            }
        )

        buckets = response['aggregations']['timeline']['buckets']
        if not buckets:
            print("Nessun dato")
            return

        max_count = max(b['doc_count'] for b in buckets)

        print(f"{'Data':<20} {'Richieste':<12} {'Graph':<35} {'Success%':<10} {'Tempo Medio':<12}")
        print("-" * 90)

        for bucket in buckets[-15:]:
            timestamp = bucket['key_as_string'][:10]
            count = bucket['doc_count']
            completate = bucket['completate']['doc_count']
            fallite = bucket['fallite']['doc_count']
            tempo = bucket['tempo_medio']['value'] or 0

            bar_width = int((count / max_count) * 20) if max_count > 0 else 0
            bar = '█' * bar_width

            success_rate = (completate / count * 100) if count > 0 else 0

            print(f"{timestamp:<20} {count:<12} {bar:<35} {success_rate:>8.1f}% {tempo:>10.2f}h")

    def analisi_efficienza_operativa(self, index_name='iam-richieste'):
        """Analisi di efficienza operativa globale"""
        print("\n" + "=" * 80)
        print("⚙️  EFFICIENZA OPERATIVA")
        print("=" * 80 + "\n")

        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_tool': {
                        'terms': {'field': 'TOOL_GENERAZIONE', 'size': 20},
                        'aggs': {
                            'completate': {'filter': {'term': {'is_completed': True}}},
                            'fallite': {'filter': {'term': {'is_failed': True}}},
                            'tempo_medio': {'avg': {'field': 'ore_elaborazione'}}
                        }
                    }
                }
            }
        )

        print("Efficienza per strumento di generazione:\n")
        for bucket in response['aggregations']['by_tool']['buckets']:
            tool = bucket['key'] or 'N/A'
            count = bucket['doc_count']
            completate = bucket['completate']['doc_count']
            fallite = bucket['fallite']['doc_count']
            tempo = bucket['tempo_medio']['value'] or 0

            success_rate = (completate / count * 100) if count > 0 else 0
            efficiency_score = (success_rate / (1 + tempo / 24)) * 100

            print(f"  {tool}")
            print(f"    Richieste: {count} | Success: {success_rate:.1f}% | Errori: {fallite}")
            print(f"    Tempo medio: {tempo:.2f}h | Efficiency Score: {efficiency_score:.1f}")
            print()


def main():
    """Esecuzione completa"""
    print("=" * 80)
    print("🚀 OPENSEARCH IAM ANALYSIS - KPI E DASHBOARD AVANZATO")
    print("=" * 80 + "\n")

    try:
        # CONNESSIONE
        print("1️⃣  Connessione ai sistemi...\n")
        analyzer = IamActivityAnalyzer(
            oracle_host='10.22.112.70',
            oracle_port=1551,
            oracle_service_name='iam.griffon.local',
            oracle_user='X1090405',
            oracle_password='Fhdf!K42retwH',
            os_host='localhost',
            os_port=9200
        )

        # LETTURA DATI
        print("\n2️⃣  Lettura richieste da IAM.STORICO_RICHIESTE...\n")
        richieste = analyzer.fetch_richieste(days=30)

        if not richieste:
            print("✗ Nessun dato letto")
            return

        # CREAZIONE E INSERIMENTO
        print("\n3️⃣  Creazione indice e inserimento dati...\n")
        analyzer.create_iam_index('iam-richieste')
        analyzer.insert_richieste(richieste, 'iam-richieste')

        # CALCOLO KPI
        print("\n4️⃣  Calcolo KPI...\n")
        analyzer.kpi_manager.calculate_all_kpis('iam-richieste')
        analyzer.kpi_manager.print_kpi_summary()

        # ANALISI AVANZATE
        print("\n5️⃣  Esecuzione analisi avanzate...\n")
        analyzer.analisi_richieste_per_operazione('iam-richieste', limit=15)
        analyzer.analisi_matrice_tipo_stato('iam-richieste')
        analyzer.analisi_performance_per_utente('iam-richieste', limit=20)
        analyzer.analisi_trend_temporale('iam-richieste', interval='1d')
        analyzer.analisi_efficienza_operativa('iam-richieste')

        print("\n" + "=" * 80)
        print("✅ ANALISI COMPLETATA!")
        print("=" * 80)
        print("\n📊 Visualizza in OpenSearch Dashboards: http://localhost:5601")
        print("   Index Pattern: iam-richieste")
        print("   Discover → Esplora i dati")

    except Exception as e:
        print(f"\n✗ Errore: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()