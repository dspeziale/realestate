"""
================================================================================
FILE: iam_analyzer.py
================================================================================
IAM Requests Analyzer - Analisi Strategiche

Esegue analisi attinenti al business IAM:
- Performance operazioni per tipo
- Trend temporali
- SLA compliance
- Distribuzioni utenti
- Errori e bottleneck
- Durate per operazione

UTILIZZO:
    from iam_analyzer import IAMAnalyzer

    analyzer = IAMAnalyzer()
    analyzer.analisi_sla_by_operazione()
    analyzer.analisi_durate_operazioni()
    analyzer.analisi_trend_temporale()
================================================================================
"""

from opensearchpy import OpenSearch
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json


class Colors:
    """ANSI color codes"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class IAMAnalyzer:
    """Analizzatore di richieste IAM"""

    def __init__(self, host='localhost', port=9200,
                 use_ssl=False):
        """Inizializza la connessione (NO SECURITY)"""
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            use_ssl=use_ssl,
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30,
            max_retries=3
        )
        self.index_name = 'iam-richieste'

        try:
            info = self.client.info()
            print(f"✓ Connesso a OpenSearch {info['version']['number']} (NO SECURITY)\n")
        except Exception as e:
            print(f"✗ Errore connessione: {e}")
            raise

    def _print_section(self, title: str):
        """Stampa titolo sezione"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'═' * 80}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}▶ {title}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'═' * 80}{Colors.RESET}\n")

    def _print_success(self, msg: str):
        print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")

    def analisi_sla_by_operazione(self) -> Dict:
        """Analizza SLA per tipo di operazione"""
        self._print_section("1. SLA COMPLIANCE PER OPERAZIONE")

        response = self.client.search(
            index=self.index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_operazione': {
                        'terms': {'field': 'fk_nome_operazione', 'size': 50},
                        'aggs': {
                            'total_count': {'value_count': {'field': 'id_richiesta'}},
                            'sla_passed': {'filter': {'term': {'sla_rispettato': True}}},
                            'sla_failed': {'filter': {'term': {'sla_rispettato': False}}},
                            'avg_durata': {'avg': {'field': 'durata_ore'}},
                            'max_durata': {'max': {'field': 'durata_ore'}},
                            'min_durata': {'min': {'field': 'durata_ore'}},
                            'p95_durata': {'percentiles': {'field': 'durata_ore', 'percents': [95]}}
                        }
                    }
                }
            }
        )

        results = {}
        for bucket in response['aggregations']['by_operazione']['buckets']:
            op_name = bucket['key']
            total = bucket['total_count']['value']
            sla_pass = bucket['sla_passed']['doc_count']
            sla_fail = bucket['sla_failed']['doc_count']
            sla_pct = (sla_pass / total * 100) if total > 0 else 0

            avg_dur = bucket['avg_durata']['value'] or 0
            max_dur = bucket['max_durata']['value'] or 0
            p95 = bucket['p95_durata']['values'].get('95.0', 0)

            status = f"{Colors.GREEN}✓{Colors.RESET}" if sla_pct >= 80 else f"{Colors.RED}✗{Colors.RESET}"

            print(f"{status} {op_name}")
            print(f"   Totale: {total:4d} | SLA: {sla_pass:3d}/{total:3d} ({sla_pct:5.1f}%)")
            print(f"   Durata: media {avg_dur:6.1f}h | max {max_dur:6.1f}h | p95 {p95:6.1f}h")

            results[op_name] = {
                'total': total,
                'sla_passed': sla_pass,
                'sla_failed': sla_fail,
                'sla_percentage': round(sla_pct, 2),
                'avg_hours': round(avg_dur, 2),
                'max_hours': round(max_dur, 2),
                'p95_hours': round(p95, 2)
            }

        return results

    def analisi_stato_distribution(self) -> Dict:
        """Distribuzione richieste per stato"""
        self._print_section("2. DISTRIBUZIONE RICHIESTE PER STATO")

        response = self.client.search(
            index=self.index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_stato': {
                        'terms': {'field': 'stato', 'size': 20}
                    }
                }
            }
        )

        total_docs = self.client.count(index=self.index_name)['count']
        results = {}

        for bucket in response['aggregations']['by_stato']['buckets']:
            stato = bucket['key']
            count = bucket['doc_count']
            pct = (count / total_docs * 100) if total_docs > 0 else 0
            bar = '█' * int(pct / 5)

            print(f"  {stato:25s}: {bar:20s} {count:4d} ({pct:5.1f}%)")

            results[stato] = {
                'count': count,
                'percentage': round(pct, 2)
            }

        return results

    def analisi_operazioni_lente(self, threshold_hours=24) -> List[Dict]:
        """Identifica operazioni lente"""
        self._print_section(f"3. OPERAZIONI LENTE (>{threshold_hours}h)")

        response = self.client.search(
            index=self.index_name,
            body={
                'query': {'range': {'durata_ore': {'gte': threshold_hours}}},
                'size': 0,
                'aggs': {
                    'lente_ops': {
                        'terms': {'field': 'fk_nome_operazione', 'size': 30},
                        'aggs': {
                            'count': {'value_count': {'field': 'id_richiesta'}},
                            'avg_durata': {'avg': {'field': 'durata_ore'}},
                            'max_durata': {'max': {'field': 'durata_ore'}}
                        }
                    }
                }
            }
        )

        results = []
        total_slow = response['hits']['total']['value']
        print(f"Totale richieste lente: {total_slow}\n")

        for bucket in response['aggregations']['lente_ops']['buckets']:
            op_name = bucket['key']
            count = bucket['count']['value']
            avg_dur = bucket['avg_durata']['value']
            max_dur = bucket['max_durata']['value']

            print(f"  {op_name}: {count} richieste")
            print(f"    Media: {avg_dur:.1f}h | Max: {max_dur:.1f}h")

            results.append({
                'operazione': op_name,
                'count': count,
                'avg_hours': round(avg_dur, 2),
                'max_hours': round(max_dur, 2)
            })

        return results

    def analisi_utenti_top(self, limit=10) -> List[Dict]:
        """Top utenti per richieste"""
        self._print_section(f"4. TOP {limit} UTENTI PER RICHIESTE")

        response = self.client.search(
            index=self.index_name,
            body={
                'size': 0,
                'aggs': {
                    'top_users': {
                        'terms': {'field': 'fk_utente_richiedente', 'size': limit},
                        'aggs': {
                            'user_name': {'terms': {'field': 'nome_utente.keyword', 'size': 1}},
                            'count': {'value_count': {'field': 'id_richiesta'}},
                            'avg_durata': {'avg': {'field': 'durata_ore'}},
                            'sla_rispettate': {'filter': {'term': {'sla_rispettato': True}}}
                        }
                    }
                }
            }
        )

        results = []
        for i, bucket in enumerate(response['aggregations']['top_users']['buckets'], 1):
            user_id = bucket['key']
            count = bucket['count']['value']
            avg_dur = bucket['avg_durata']['value']
            sla_ok = bucket['sla_rispettate']['doc_count']
            sla_pct = (sla_ok / count * 100) if count > 0 else 0

            user_name = bucket['user_name']['buckets'][0]['key'] if bucket['user_name']['buckets'] else user_id

            print(f"  {i}. {user_name:20s} - {count:3d} richieste | SLA: {sla_pct:5.1f}%")

            results.append({
                'rank': i,
                'user_id': user_id,
                'user_name': user_name,
                'count': count,
                'avg_hours': round(avg_dur, 2),
                'sla_percentage': round(sla_pct, 2)
            })

        return results

    def analisi_trend_temporale(self, interval='1d') -> Dict:
        """Trend richieste nel tempo"""
        self._print_section(f"5. TREND TEMPORALE (intervallo: {interval})")

        response = self.client.search(
            index=self.index_name,
            body={
                'size': 0,
                'aggs': {
                    'timeline': {
                        'date_histogram': {
                            'field': 'data_creazione',
                            'fixed_interval': interval
                        },
                        'aggs': {
                            'count': {'value_count': {'field': 'id_richiesta'}},
                            'sla_ok': {'filter': {'term': {'sla_rispettato': True}}}
                        }
                    }
                }
            }
        )

        results = {}
        print("Data          | Richieste | SLA OK | Trend")
        print("-" * 50)

        for bucket in response['aggregations']['timeline']['buckets'][-30:]:  # Ultimi 30 intervalli
            timestamp = bucket['key_as_string'][:10]
            count = bucket['count']['value']
            sla_ok = bucket['sla_ok']['doc_count']
            sla_pct = (sla_ok / count * 100) if count > 0 else 0

            bar = '█' * max(1, int(count / 5))
            print(f"{timestamp} | {count:9d} | {sla_ok:3d}/{count:3d} ({sla_pct:5.1f}%) | {bar}")

            results[timestamp] = {
                'count': count,
                'sla_ok': sla_ok,
                'sla_percentage': round(sla_pct, 2)
            }

        return results

    def analisi_priorita(self) -> Dict:
        """Analisi per priorità"""
        self._print_section("6. ANALISI PER PRIORITÀ")

        response = self.client.search(
            index=self.index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_priorita': {
                        'terms': {'field': 'priorita'},
                        'aggs': {
                            'count': {'value_count': {'field': 'id_richiesta'}},
                            'avg_durata': {'avg': {'field': 'durata_ore'}},
                            'sla_ok': {'filter': {'term': {'sla_rispettato': True}}}
                        }
                    }
                }
            }
        )

        results = {}
        for bucket in response['aggregations']['by_priorita']['buckets']:
            priorita = bucket['key']
            count = bucket['count']['value']
            avg_dur = bucket['avg_durata']['value']
            sla_ok = bucket['sla_ok']['doc_count']
            sla_pct = (sla_ok / count * 100) if count > 0 else 0

            print(f"  {priorita:10s}: {count:4d} richieste | Durata media: {avg_dur:6.1f}h | SLA: {sla_pct:5.1f}%")

            results[priorita] = {
                'count': count,
                'avg_hours': round(avg_dur, 2),
                'sla_percentage': round(sla_pct, 2)
            }

        return results

    def analisi_area_responsabile(self) -> Dict:
        """Analisi per area responsabile"""
        self._print_section("7. ANALISI PER AREA RESPONSABILE")

        response = self.client.search(
            index=self.index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_area': {
                        'terms': {'field': 'area_responsabile', 'size': 20},
                        'aggs': {
                            'count': {'value_count': {'field': 'id_richiesta'}},
                            'avg_durata': {'avg': {'field': 'durata_ore'}},
                            'sla_ok': {'filter': {'term': {'sla_rispettato': True}}}
                        }
                    }
                }
            }
        )

        results = {}
        for bucket in response['aggregations']['by_area']['buckets']:
            area = bucket['key']
            count = bucket['count']['value']
            avg_dur = bucket['avg_durata']['value']
            sla_ok = bucket['sla_ok']['doc_count']
            sla_pct = (sla_ok / count * 100) if count > 0 else 0

            print(f"  {area:30s}: {count:4d} richieste | SLA: {sla_pct:5.1f}%")

            results[area] = {
                'count': count,
                'avg_hours': round(avg_dur, 2),
                'sla_percentage': round(sla_pct, 2)
            }

        return results

    def esegui_tutte_analisi(self) -> Dict:
        """Esegue tutte le analisi e ritorna i risultati"""
        all_results = {
            'sla_by_operazione': self.analisi_sla_by_operazione(),
            'stato_distribution': self.analisi_stato_distribution(),
            'operazioni_lente': self.analisi_operazioni_lente(),
            'utenti_top': self.analisi_utenti_top(),
            'trend_temporale': self.analisi_trend_temporale(),
            'priorita': self.analisi_priorita(),
            'area_responsabile': self.analisi_area_responsabile(),
            'timestamp': datetime.now().isoformat()
        }

        self._print_section("✓ ANALISI COMPLETATA")
        print(f"Timestamp: {all_results['timestamp']}")

        return all_results


if __name__ == '__main__':
    print("="*80)
    print("IAM ANALYZER - Analisi Richieste IAM")
    print("="*80)

    analyzer = IAMAnalyzer()
    results = analyzer.esegui_tutte_analisi()

    print("\n" + "="*80)
    print("✓ Esportazione risultati...")