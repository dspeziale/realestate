"""
================================================================================
FILE: iam_kpi_engine.py
================================================================================
IAM KPI Engine - Motore KPI Configurabile SLA

Sistema per definire e calcolare KPI dinamici basati su SLA.
Leggi la configurazione da JSON e calcola i KPI in real-time.

CONFIGURAZIONE KPI (iam_kpi_config.json):
{
    "kpi": {
        "reset": {
            "operation_type": "reset%",
            "column_operation": "fk_nome_operazione",
            "sla_percentage": 80.0,
            "status": "EVASA",
            "column_status": "stato",
            "duration": 24
        }
    }
}

UTILIZZO:
    from iam_kpi_engine import KPIEngine

    engine = KPIEngine()
    kpis = engine.calcola_tutti_kpi()
    print(engine.genera_report_kpi(kpis))
================================================================================
"""

from opensearchpy import OpenSearch
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json
from pathlib import Path


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


class KPIEngine:
    """Motore per calcolo KPI configurabili"""

    def __init__(self, host='localhost', port=9200,
                 use_ssl=False, config_file='iam_kpi_config.json'):
        """Inizializza il motore KPI (NO SECURITY)"""
        # OpenSearch senza security - niente auth
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            use_ssl=use_ssl,
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30,
            max_retries=3
        )
        self.index_name = 'iam-richieste'

        # Carica configurazione
        self.config = self._load_config(config_file)

        try:
            info = self.client.info()
            print(f"✓ KPI Engine pronto - OpenSearch {info['version']['number']} (NO SECURITY)\n")
        except Exception as e:
            print(f"✗ Errore connessione: {e}")
            raise

    def _load_config(self, config_file: str) -> Dict:
        """Carica configurazione KPI da file JSON"""
        try:
            if Path(config_file).exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠ Errore caricamento config: {e}, uso config default")

        # Config di default se il file non esiste
        return self._get_config_default()

    def _get_config_default(self) -> Dict:
        """Restituisce configurazione KPI di default"""
        return {
            "kpi": {
                "reset": {
                    "operation_type": "reset%",
                    "column_operation": "fk_nome_operazione",
                    "sla_percentage": 80.0,
                    "sla_percentage_2": 100.0,
                    "status": "EVASA",
                    "column_status": "stato",
                    "duration": 24,
                    "duration_2": 48
                },
                "attivazione": {
                    "operation_type": "attivazione%",
                    "column_operation": "fk_nome_operazione",
                    "sla_percentage": 85.0,
                    "sla_percentage_2": 95.0,
                    "status": "EVASA",
                    "column_status": "stato",
                    "duration": 24,
                    "duration_2": 48
                },
                "provisioning": {
                    "operation_type": "provisioning%",
                    "column_operation": "fk_nome_operazione",
                    "sla_percentage": 75.0,
                    "sla_percentage_2": 90.0,
                    "status": "EVASA",
                    "column_status": "stato",
                    "duration": 48,
                    "duration_2": 72
                }
            }
        }

    def _salva_config(self, filepath: str = 'iam_kpi_config.json'):
        """Salva configurazione su file"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            print(f"✓ Configurazione salvata: {filepath}")
        except Exception as e:
            print(f"✗ Errore salvataggio config: {e}")

    def _build_query(self, kpi_config: Dict) -> Dict:
        """Costruisce query Elasticsearch per il KPI"""
        op_type = kpi_config['operation_type']
        status = kpi_config['status']
        duration = kpi_config['duration']
        column_op = kpi_config['column_operation']
        column_status = kpi_config['column_status']

        # Build like query for operazione
        if op_type.endswith('%'):
            op_pattern = op_type.rstrip('%')
            must_clause = {
                'wildcard': {
                    column_op: f"{op_pattern}*"
                }
            }
        else:
            must_clause = {
                'term': {
                    column_op: op_type
                }
            }

        # Query per richieste che rispettano SLA (completate entro durata)
        query = {
            'bool': {
                'must': [
                    must_clause,
                    {'term': {column_status: status}},
                    {'range': {'durata_ore': {'lte': duration}}}
                ]
            }
        }

        return query

    def calcola_kpi_singolo(self, kpi_name: str, kpi_config: Dict) -> Dict:
        """Calcola un singolo KPI"""

        try:
            # Query per totale operazioni di questo tipo
            query_total = {
                'bool': {
                    'must': [
                        {
                            'wildcard': {
                                kpi_config['column_operation']: f"{kpi_config['operation_type'].rstrip('%')}*"
                            }
                        },
                        {'term': {kpi_config['column_status']: kpi_config['status']}}
                    ]
                }
            }

            # Query per SLA rispettato
            query_sla = {
                'bool': {
                    'must': [
                        {
                            'wildcard': {
                                kpi_config['column_operation']: f"{kpi_config['operation_type'].rstrip('%')}*"
                            }
                        },
                        {'term': {kpi_config['column_status']: kpi_config['status']}},
                        {'range': {'durata_ore': {'lte': kpi_config['duration']}}}
                    ]
                }
            }

            # Query per SLA 2 (se presente)
            query_sla_2 = None
            if 'duration_2' in kpi_config and 'sla_percentage_2' in kpi_config:
                query_sla_2 = {
                    'bool': {
                        'must': [
                            {
                                'wildcard': {
                                    kpi_config['column_operation']: f"{kpi_config['operation_type'].rstrip('%')}*"
                                }
                            },
                            {'term': {kpi_config['column_status']: kpi_config['status']}},
                            {'range': {'durata_ore': {'lte': kpi_config['duration_2']}}}
                        ]
                    }
                }

            # Esegui query
            total = self.client.count(index=self.index_name, body={'query': query_total})['count']
            sla_ok = self.client.count(index=self.index_name, body={'query': query_sla})['count']

            sla_ok_2 = 0
            if query_sla_2:
                sla_ok_2 = self.client.count(index=self.index_name, body={'query': query_sla_2})['count']

            # Calcola percentuali
            sla_pct = (sla_ok / total * 100) if total > 0 else 0
            sla_pct_2 = (sla_ok_2 / total * 100) if total > 0 else 0

            # Determina status
            threshold = kpi_config['sla_percentage']
            status_kpi = 'OK' if sla_pct >= threshold else 'ALERT'

            if 'sla_percentage_2' in kpi_config:
                threshold_2 = kpi_config['sla_percentage_2']
                status_kpi_2 = 'OK' if sla_pct_2 >= threshold_2 else 'ALERT'
            else:
                status_kpi_2 = None

            return {
                'name': kpi_name,
                'operation_type': kpi_config['operation_type'],
                'total_requests': total,
                'sla_ok_24h': sla_ok,
                'sla_percentage_24h': round(sla_pct, 2),
                'sla_threshold_24h': kpi_config['sla_percentage'],
                'status_24h': status_kpi,
                'sla_ok_48h': sla_ok_2 if query_sla_2 else None,
                'sla_percentage_48h': round(sla_pct_2, 2) if query_sla_2 else None,
                'sla_threshold_48h': kpi_config.get('sla_percentage_2', None),
                'status_48h': status_kpi_2,
                'duration_hours': kpi_config['duration'],
                'duration_2_hours': kpi_config.get('duration_2', None),
                'calculated_at': datetime.now().isoformat()
            }

        except Exception as e:
            print(f"✗ Errore calcolo KPI '{kpi_name}': {e}")
            return {
                'name': kpi_name,
                'error': str(e)
            }

    def calcola_tutti_kpi(self) -> Dict[str, Dict]:
        """Calcola tutti i KPI configurati"""
        print(f"{Colors.BOLD}{Colors.CYAN}Calcolo KPI in corso...{Colors.RESET}\n")

        kpis_result = {}

        if 'kpi' not in self.config:
            print(f"{Colors.RED}✗ Nessun KPI configurato{Colors.RESET}")
            return {}

        for kpi_name, kpi_config in self.config['kpi'].items():
            print(f"  ▶ {kpi_name}...", end='', flush=True)
            result = self.calcola_kpi_singolo(kpi_name, kpi_config)
            kpis_result[kpi_name] = result
            print(f" {Colors.GREEN}✓{Colors.RESET}")

        return kpis_result

    def genera_report_kpi(self, kpis: Dict[str, Dict]) -> str:
        """Genera report testuale dei KPI"""

        report = f"\n{Colors.BOLD}{Colors.BLUE}{'═' * 100}{Colors.RESET}\n"
        report += f"{Colors.BOLD}{Colors.CYAN}KPI REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.RESET}\n"
        report += f"{Colors.BOLD}{Colors.BLUE}{'═' * 100}{Colors.RESET}\n\n"

        for kpi_name, kpi_data in kpis.items():
            if 'error' in kpi_data:
                report += f"{Colors.RED}✗ {kpi_name}: {kpi_data['error']}{Colors.RESET}\n"
                continue

            status_color = Colors.GREEN if kpi_data['status_24h'] == 'OK' else Colors.RED
            status_symbol = '✓' if kpi_data['status_24h'] == 'OK' else '✗'

            report += f"{status_color}{status_symbol}{Colors.RESET} {Colors.BOLD}{kpi_name}{Colors.RESET}\n"
            report += f"   Operazione: {kpi_data['operation_type']}\n"
            report += f"   Totale richieste: {kpi_data['total_requests']}\n"
            report += f"\n"
            report += f"   SLA 24h: {kpi_data['sla_ok_24h']}/{kpi_data['total_requests']} "
            report += f"({kpi_data['sla_percentage_24h']}% - Target: {kpi_data['sla_threshold_24h']}%) "
            report += f"[{kpi_data['status_24h']}]\n"

            if kpi_data['sla_percentage_48h'] is not None:
                status_color_2 = Colors.GREEN if kpi_data['status_48h'] == 'OK' else Colors.RED
                report += f"   SLA 48h: {kpi_data['sla_ok_48h']}/{kpi_data['total_requests']} "
                report += f"({kpi_data['sla_percentage_48h']}% - Target: {kpi_data['sla_threshold_48h']}%) "
                report += f"{status_color_2}[{kpi_data['status_48h']}]{Colors.RESET}\n"

            report += f"\n"

        return report

    def esporta_kpi_json(self, kpis: Dict[str, Dict], filepath: str = 'kpi_results.json'):
        """Esporta KPI in JSON"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(kpis, f, indent=2, ensure_ascii=False)
            print(f"✓ KPI esportati: {filepath}")
        except Exception as e:
            print(f"✗ Errore esportazione: {e}")

    def crea_config_template(self, filepath: str = 'iam_kpi_config.json'):
        """Crea file di configurazione template"""
        self._salva_config(filepath)
        return filepath


if __name__ == '__main__':
    print("="*100)
    print("IAM KPI ENGINE - Motore KPI Configurabile")
    print("="*100)

    engine = KPIEngine()

    # Calcola KPI
    kpis = engine.calcola_tutti_kpi()

    # Stampa report
    print(engine.genera_report_kpi(kpis))

    # Esporta
    engine.esporta_kpi_json(kpis)

    print("\n✓ Elaborazione KPI completata!")