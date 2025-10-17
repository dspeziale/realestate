"""
Sistema KPI Operazionali IAM - SLA Management
==============================================

KPI Specifici per Lavorazioni IAM:
- Operazioni Reset
- Operazioni Riattivazione
- Operazioni Utenti

Con tracking SLA in tempo reale
"""

from opensearchpy import OpenSearch, helpers
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import oracledb
import json
import sys


class SLAStatus(Enum):
    """Stato SLA"""
    ON_TIME = "✓ In Orario"  # Verde
    WARNING = "⚠ Attenzione"  # Giallo
    AT_RISK = "⚠ A Rischio"  # Arancione
    BREACHED = "✗ Violato"  # Rosso


@dataclass
class OperationSLA:
    """Definizione SLA per un'operazione"""
    operation_type: str  # reset, riattivazione, utenti
    description: str
    target_percentage: float  # es. 80%, 100%
    sla_hours: float  # tempo massimo in ore

    def __str__(self):
        return f"{self.operation_type}: {self.target_percentage:.0f}% entro {self.sla_hours}h"


class OperationalKPIManager:
    """Gestisce KPI operazionali IAM"""

    # Definizione SLA dal documento
    OPERATIONAL_SLA = {
        'reset': OperationSLA(
            operation_type='Lavorazione operazioni di reset',
            description='Percentuale di lavorazioni o eventuali smistamento operazioni provenienti da WEB, e-Mail e Telefono',
            target_percentage=80.0,
            sla_hours=24.0
        ),
        'riattivazione': OperationSLA(
            operation_type='Lavorazione operazioni di riattivazione',
            description='Percentuale di lavorazioni o eventuali smistamento operazioni di riattivazione per inattività provenienti da WEB, e-Mail e Telefono',
            target_percentage=100.0,
            sla_hours=48.0
        ),
        'utenti': OperationSLA(
            operation_type='Lavorazione operazioni utenti',
            description='Creazione, cancellazione, modifica utenza, riabilitazione/riattivazione, gestione profili, esport info utenza, supporto utente, reset password',
            target_percentage=100.0,
            sla_hours=120.0  # 5 giorni
        ),
        'elenchi_account': OperationSLA(
            operation_type='Produzione elenchi di account',
            description='Produzione elenchi con rimando massimo entro 7 giorni',
            target_percentage=100.0,
            sla_hours=168.0  # 7 giorni
        )
    }

    def __init__(self, os_client: OpenSearch):
        self.os_client = os_client
        self.kpis: Dict[str, Dict] = {}

    def calculate_operation_sla(self, index_name='iam-operations',
                                operation_type: str = 'reset') -> Dict:
        """Calcola SLA per un tipo di operazione"""

        sla_config = self.OPERATIONAL_SLA.get(operation_type)
        if not sla_config:
            return {}

        # Query per calcolare SLA
        response = self.os_client.search(
            index=index_name,
            body={
                'size': 0,
                'query': {'term': {'operation_type': operation_type}},
                'aggs': {
                    'total': {'filter': {'match_all': {}}},
                    'within_sla': {
                        'filter': {
                            'range': {'hours_to_complete': {'lte': sla_config.sla_hours}}
                        }
                    },
                    'within_warning': {
                        'filter': {
                            'range': {'hours_to_complete': {
                                'gte': sla_config.sla_hours * 0.8,
                                'lt': sla_config.sla_hours
                            }}
                        }
                    },
                    'at_risk': {
                        'filter': {
                            'range': {'hours_to_complete': {
                                'gte': sla_config.sla_hours * 0.5,
                                'lt': sla_config.sla_hours * 0.8
                            }}
                        }
                    },
                    'breached': {
                        'filter': {
                            'range': {'hours_to_complete': {'lt': sla_config.sla_hours * 0.5}}
                        }
                    },
                    'avg_time': {'avg': {'field': 'hours_to_complete'}},
                    'percentile_95': {
                        'percentiles': {'field': 'hours_to_complete', 'percents': [95]}
                    }
                }
            }
        )

        aggs = response['aggregations']
        total = aggs['total']['doc_count']
        within_sla = aggs['within_sla']['doc_count']

        sla_percentage = (within_sla / total * 100) if total > 0 else 0

        # Determina status SLA
        if sla_percentage >= sla_config.target_percentage:
            status = SLAStatus.ON_TIME
        elif sla_percentage >= (sla_config.target_percentage * 0.95):
            status = SLAStatus.WARNING
        elif sla_percentage >= (sla_config.target_percentage * 0.90):
            status = SLAStatus.AT_RISK
        else:
            status = SLAStatus.BREACHED

        kpi_data = {
            'operation_type': operation_type,
            'description': sla_config.description,
            'sla_config': sla_config,
            'total_operations': total,
            'within_sla': within_sla,
            'sla_percentage': round(sla_percentage, 2),
            'target_percentage': sla_config.target_percentage,
            'achievement': round((sla_percentage / sla_config.target_percentage * 100), 2),
            'status': status,
            'status_icon': status.value,
            'avg_time_hours': round(aggs['avg_time']['value'] or 0, 2),
            'p95_time_hours': round(aggs['percentile_95']['values'].get('95.0', 0), 2),
            'sla_hours': sla_config.sla_hours,
            'at_risk_count': aggs['at_risk']['doc_count'],
            'warning_count': aggs['within_warning']['doc_count'],
            'breached_count': aggs['breached']['doc_count']
        }

        self.kpis[operation_type] = kpi_data
        return kpi_data

    def calculate_all_operational_kpis(self, index_name='iam-operations') -> Dict:
        """Calcola tutti i KPI operazionali"""
        for op_type in self.OPERATIONAL_SLA.keys():
            self.calculate_operation_sla(index_name, op_type)
        return self.kpis

    def print_operational_dashboard(self):
        """Stampa dashboard KPI operazionali"""
        print("\n" + "=" * 100)
        print("📊 DASHBOARD KPI OPERAZIONALI IAM - SLA MANAGEMENT")
        print("=" * 100 + "\n")

        # Header con timestamp
        print(f"📅 Data Report: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")

        for op_type, kpi in self.kpis.items():
            self._print_kpi_card(kpi)

    def _print_kpi_card(self, kpi: Dict):
        """Stampa singola card KPI"""

        status_icon = kpi['status_icon']
        operation = kpi['operation_type']
        sla_pct = kpi['sla_percentage']
        target_pct = kpi['target_percentage']
        achievement = kpi['achievement']

        # Colore basato su status
        if kpi['status'] == SLAStatus.ON_TIME:
            color_start = "\033[92m"  # Verde
        elif kpi['status'] == SLAStatus.WARNING:
            color_start = "\033[93m"  # Giallo
        elif kpi['status'] == SLAStatus.AT_RISK:
            color_start = "\033[96m"  # Ciano
        else:
            color_start = "\033[91m"  # Rosso

        color_reset = "\033[0m"
        bold = "\033[1m"

        print(
            f"{bold}┌─────────────────────────────────────────────────────────────────────────────────────────────────┐{color_reset}")
        print(f"{status_icon} {bold}{operation}{color_reset}")
        print(
            f"{bold}├─────────────────────────────────────────────────────────────────────────────────────────────────┤{color_reset}")
        print(f"  📋 Descrizione: {kpi['description'][:80]}...")
        print(f"  🎯 SLA Target: {bold}{target_pct:.0f}%{color_reset} entro {bold}{kpi['sla_hours']:.0f}h{color_reset}")
        print(
            f"  ✅ Risultato: {bold}{color_start}{sla_pct:.1f}%{color_reset} ({kpi['within_sla']}/{kpi['total_operations']} operazioni)")
        print(f"  📈 Raggiungimento: {bold}{achievement:.1f}%{color_reset}")
        print(f"  ⏱️  Tempo Medio: {kpi['avg_time_hours']:.1f}h | P95: {kpi['p95_time_hours']:.1f}h")
        print(f"  ⚠️  Status: {color_start}{bold}{kpi['status'].value}{color_reset}")

        # Breakdown
        if kpi['warning_count'] > 0:
            print(f"     • {kpi['warning_count']} in attenzione")
        if kpi['at_risk_count'] > 0:
            print(f"     • {kpi['at_risk_count']} a rischio")
        if kpi['breached_count'] > 0:
            print(f"     • {kpi['breached_count']} violati")

        print(
            f"{bold}└─────────────────────────────────────────────────────────────────────────────────────────────────┘{color_reset}\n")

    def get_sla_violations(self, index_name='iam-operations',
                           operation_type: str = 'reset', limit: int = 10) -> List[Dict]:
        """Ottiene operazioni che violano SLA"""

        sla_config = self.OPERATIONAL_SLA.get(operation_type)
        if not sla_config:
            return []

        response = self.os_client.search(
            index=index_name,
            body={
                'size': limit,
                'query': {
                    'bool': {
                        'must': [
                            {'term': {'operation_type': operation_type}},
                            {'range': {'hours_to_complete': {'gt': sla_config.sla_hours}}}
                        ]
                    }
                },
                'sort': [{'hours_to_complete': 'desc'}]
            }
        )

        return [hit['_source'] for hit in response['hits']['hits']]

    def get_pending_operations(self, index_name='iam-operations',
                               operation_type: str = 'reset') -> List[Dict]:
        """Ottiene operazioni ancora in elaborazione"""

        response = self.os_client.search(
            index=index_name,
            body={
                'size': 100,
                'query': {
                    'bool': {
                        'must': [
                            {'term': {'operation_type': operation_type}},
                            {'term': {'status': 'pending'}}
                        ]
                    }
                },
                'sort': [{'created_at': 'asc'}]
            }
        )

        return [hit['_source'] for hit in response['hits']['hits']]

    def print_sla_report(self, index_name='iam-operations'):
        """Stampa report SLA dettagliato"""

        print("\n" + "=" * 100)
        print("📋 REPORT SLA DETTAGLIATO")
        print("=" * 100 + "\n")

        for op_type in self.OPERATIONAL_SLA.keys():
            print(f"\n{op_type.upper()}")
            print("-" * 100)

            # Violazioni
            violations = self.get_sla_violations(index_name, op_type, limit=5)
            if violations:
                print(f"\n  ❌ TOP 5 OPERAZIONI CON SLA VIOLATO:\n")
                for i, v in enumerate(violations, 1):
                    print(f"     {i}. ID: {v.get('operation_id')} | {v.get('hours_to_complete', 0):.1f}h " +
                          f"(SLA: {self.OPERATIONAL_SLA[op_type].sla_hours}h)")

            # Pending
            pending = self.get_pending_operations(index_name, op_type)
            if pending:
                print(f"\n  ⏳ OPERAZIONI IN ELABORAZIONE: {len(pending)}\n")
                for i, p in enumerate(pending[:5], 1):
                    created = datetime.fromisoformat(p['created_at'])
                    elapsed = (datetime.now() - created).total_seconds() / 3600
                    print(f"     {i}. ID: {p.get('operation_id')} | Trascorse {elapsed:.1f}h")

    def export_kpi_json(self, filename: str = 'kpi_operazionali.json'):
        """Esporta KPI in JSON"""

        export_data = {
            'report_date': datetime.now().isoformat(),
            'kpis': {}
        }

        for op_type, kpi in self.kpis.items():
            export_data['kpis'][op_type] = {
                'operation_type': kpi['operation_type'],
                'sla_percentage': kpi['sla_percentage'],
                'target_percentage': kpi['target_percentage'],
                'achievement': kpi['achievement'],
                'status': kpi['status'].value,
                'total_operations': kpi['total_operations'],
                'within_sla': kpi['within_sla'],
                'avg_time_hours': kpi['avg_time_hours'],
                'p95_time_hours': kpi['p95_time_hours']
            }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        print(f"✓ KPI esportati in: {filename}")
        return filename


def create_sample_operations(os_client: OpenSearch, index_name='iam-operations'):
    """Crea dati di esempio per test"""

    import random

    if os_client.indices.exists(index=index_name):
        os_client.indices.delete(index=index_name)

    mappings = {
        'properties': {
            'operation_id': {'type': 'keyword'},
            'operation_type': {'type': 'keyword'},  # reset, riattivazione, utenti
            'status': {'type': 'keyword'},  # completed, pending, failed
            'created_at': {'type': 'date'},
            'completed_at': {'type': 'date'},
            'hours_to_complete': {'type': 'float'},
            'source_channel': {'type': 'keyword'},  # WEB, EMAIL, PHONE
            'user_id': {'type': 'keyword'},
            'description': {'type': 'text'}
        }
    }

    os_client.indices.create(index=index_name, body={'mappings': mappings})
    print(f"✓ Indice '{index_name}' creato")

    # Genera operazioni di esempio
    operations = []

    for i in range(500):
        op_type = random.choice(['reset', 'riattivazione', 'utenti', 'elenchi_account'])

        # Varia la compliance SLA
        if random.random() < 0.82:  # 82% within SLA
            sla_config = {
                'reset': 24,
                'riattivazione': 48,
                'utenti': 120,
                'elenchi_account': 168
            }
            hours = random.uniform(0.5, sla_config[op_type] * 0.95)
        else:
            hours = random.uniform(24, 240)

        created_at = datetime.now() - timedelta(days=random.randint(0, 30))
        completed_at = created_at + timedelta(hours=hours)

        op = {
            'operation_id': f'OP-{i + 1:06d}',
            'operation_type': op_type,
            'status': 'completed' if random.random() > 0.05 else 'pending',
            'created_at': created_at.isoformat(),
            'completed_at': completed_at.isoformat() if random.random() > 0.05 else None,
            'hours_to_complete': hours,
            'source_channel': random.choice(['WEB', 'EMAIL', 'PHONE']),
            'user_id': f'USER-{random.randint(1000, 2000)}',
            'description': f'Operazione {op_type} via {random.choice(["WEB", "EMAIL", "PHONE"])}'
        }

        operations.append(op)

    # Bulk insert
    actions = [
        {'_index': index_name, '_source': op}
        for op in operations
    ]

    success, failed = helpers.bulk(os_client, actions, raise_on_error=False, refresh=True)
    print(f"✓ Inserite {success} operazioni di test")


def main():
    """Main"""
    print("=" * 100)
    print("🚀 OPERATIONAL KPI IAM - SLA MANAGEMENT SYSTEM")
    print("=" * 100 + "\n")

    try:
        # Connessione
        print("1️⃣  Connessione a OpenSearch...")
        os_client = OpenSearch(
            hosts=[{'host': 'localhost', 'port': 9200}],
            http_auth=('admin', 'admin'),
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30
        )

        info = os_client.info()
        print(f"✓ OpenSearch {info['version']['number']}\n")

        # Crea dati di test
        print("2️⃣  Creazione dati di esempio...")
        create_sample_operations(os_client, 'iam-operations')

        # Calcola KPI
        print("\n3️⃣  Calcolo KPI operazionali...\n")
        manager = OperationalKPIManager(os_client)
        manager.calculate_all_operational_kpis('iam-operations')

        # Stampa dashboard
        manager.print_operational_dashboard()

        # Report SLA
        manager.print_sla_report('iam-operations')

        # Export
        print("\n4️⃣  Export dati...")
        manager.export_kpi_json('kpi_operazionali.json')

        print("\n" + "=" * 100)
        print("✅ REPORT COMPLETATO!")
        print("=" * 100)

    except Exception as e:
        print(f"\n✗ Errore: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())