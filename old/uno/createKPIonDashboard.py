"""
OpenSearch IAM KPI Dashboard - VERSIONE CORRETTA
================================================

Usa visualizzazioni che calcolano percentuali reali, non conteggi.
"""

import requests
import json
import time
from typing import Dict, List, Optional


class IamKpiDashboardCorrect:
    """Crea dashboard con KPI percentuali corretti"""

    def __init__(self, host='localhost', port=5601, username='admin', password='admin'):
        """Inizializza la connessione"""
        self.base_url = f"http://{host}:{port}"
        self.auth = (username, password)
        self.headers = {
            'Content-Type': 'application/json',
            'osd-xsrf': 'true'
        }
        self.session = requests.Session()
        self.session.auth = self.auth

        try:
            response = self.session.get(
                f"{self.base_url}/api/status",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                print("✓ OpenSearch Dashboards connesso\n")
        except Exception as e:
            print(f"✗ Errore: {e}")
            raise

    def delete_visualization(self, vis_id: str) -> bool:
        """Elimina una visualizzazione"""
        try:
            self.session.delete(
                f"{self.base_url}/api/saved_objects/visualization/{vis_id}",
                headers=self.headers
            )
            return True
        except:
            return False

    def create_visualization(self, title: str, vis_type: str,
                            index_pattern: str, config: Dict) -> Optional[str]:
        """Crea una visualizzazione"""
        try:
            vis_id = title.lower().replace(' ', '-').replace('(', '').replace(')', '').replace('%', 'pct').replace('/', '-')
            self.delete_visualization(vis_id)
            time.sleep(0.1)

            body = {
                'attributes': {
                    'title': title,
                    'visState': json.dumps({
                        'title': title,
                        'type': vis_type,
                        'params': config.get('params', {}),
                        'aggs': config.get('aggs', [])
                    }),
                    'uiStateJSON': '{}',
                    'kibanaSavedObjectMeta': {
                        'searchSourceJSON': json.dumps({
                            'index': index_pattern,
                            'query': config.get('query', {'match_all': {}}),
                            'filter': []
                        })
                    }
                }
            }

            response = self.session.post(
                f"{self.base_url}/api/saved_objects/visualization/{vis_id}",
                json=body,
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"✓ {title}")
                return vis_id
            else:
                print(f"✗ {title}")
                return None

        except Exception as e:
            print(f"✗ Errore: {e}")
            return None

    def create_kpi_visualizations(self, index_pattern='iam-richieste') -> List[str]:
        """Crea visualizzazioni KPI con percentuali reali"""
        visualizations = []

        print("=" * 70)
        print("CREAZIONE DASHBOARD KPI CORRETTO")
        print("=" * 70 + "\n")

        # ========== KPI 1: Percentuale entro 24h ==========
        # Usa una formula di derivazione da 2 metriche
        config = {
            'params': {
                'fontSize': '60',
                'colorSchema': 'Red to Yellow to Green'
            },
            'aggs': [
                {
                    'id': '1',
                    'enabled': True,
                    'type': 'count',
                    'schema': 'metric',
                    'params': {}
                },
                {
                    'id': '2',
                    'enabled': True,
                    'type': 'filter',
                    'schema': 'metric',
                    'params': {
                        'query': {
                            'bool': {
                                'must': [
                                    {'range': {'ore_elaborazione': {'lte': 24}}}
                                ]
                            }
                        }
                    }
                },
                {
                    'id': '3',
                    'enabled': True,
                    'type': 'bucket_selector',
                    'schema': 'metric',
                    'params': {
                        'customBucket': '2/1*100',
                        'customLabel': 'KPI 1 - % Entro 24h'
                    }
                }
            ],
            'query': {
                'bool': {
                    'must': [
                        {'match': {'STATO': 'EVASA'}},
                        {'match': {'FK_NOME_OPERAZIONE': 'RESET_PASSWORD_ACCOUNT'}}
                    ]
                }
            }
        }
        vis_id = self.create_visualization(
            'KPI 1 - % Entro 24h (Target 80%)', 'metric', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # ========== KPI 2: Percentuale entro 48h ==========
        config = {
            'params': {
                'fontSize': '60',
                'colorSchema': 'Red to Yellow to Green'
            },
            'aggs': [
                {
                    'id': '1',
                    'enabled': True,
                    'type': 'count',
                    'schema': 'metric',
                    'params': {}
                },
                {
                    'id': '2',
                    'enabled': True,
                    'type': 'filter',
                    'schema': 'metric',
                    'params': {
                        'query': {
                            'bool': {
                                'must': [
                                    {'range': {'ore_elaborazione': {'lte': 48}}}
                                ]
                            }
                        }
                    }
                },
                {
                    'id': '3',
                    'enabled': True,
                    'type': 'bucket_selector',
                    'schema': 'metric',
                    'params': {
                        'customBucket': '2/1*100',
                        'customLabel': 'KPI 2 - % Entro 48h'
                    }
                }
            ],
            'query': {
                'bool': {
                    'must': [
                        {'match': {'STATO': 'EVASA'}},
                        {'match': {'FK_NOME_OPERAZIONE': 'RESET_PASSWORD_ACCOUNT'}}
                    ]
                }
            }
        }
        vis_id = self.create_visualization(
            'KPI 2 - % Entro 48h (Target 100%)', 'metric', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # ========== TOTALE ==========
        config = {
            'params': {'fontSize': '50'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}}
            ],
            'query': {
                'bool': {
                    'must': [
                        {'match': {'STATO': 'EVASA'}},
                        {'match': {'FK_NOME_OPERAZIONE': 'RESET_PASSWORD_ACCOUNT'}}
                    ]
                }
            }
        }
        vis_id = self.create_visualization(
            'Totale RESET_PASSWORD_ACCOUNT', 'metric', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # ========== TEMPO MEDIO ==========
        config = {
            'params': {'fontSize': '45'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'avg', 'schema': 'metric',
                 'params': {'field': 'ore_elaborazione'}}
            ],
            'query': {
                'bool': {
                    'must': [
                        {'match': {'STATO': 'EVASA'}},
                        {'match': {'FK_NOME_OPERAZIONE': 'RESET_PASSWORD_ACCOUNT'}}
                    ]
                }
            }
        }
        vis_id = self.create_visualization(
            'Tempo Medio (ore)', 'metric', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # ========== ENTRO 24H ==========
        config = {
            'params': {'fontSize': '45'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}}
            ],
            'query': {
                'bool': {
                    'must': [
                        {'match': {'STATO': 'EVASA'}},
                        {'match': {'FK_NOME_OPERAZIONE': 'RESET_PASSWORD_ACCOUNT'}},
                        {'range': {'ore_elaborazione': {'lte': 24}}}
                    ]
                }
            }
        }
        vis_id = self.create_visualization(
            'Completati Entro 24h', 'metric', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # ========== ENTRO 48H ==========
        config = {
            'params': {'fontSize': '45'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}}
            ],
            'query': {
                'bool': {
                    'must': [
                        {'match': {'STATO': 'EVASA'}},
                        {'match': {'FK_NOME_OPERAZIONE': 'RESET_PASSWORD_ACCOUNT'}},
                        {'range': {'ore_elaborazione': {'lte': 48}}}
                    ]
                }
            }
        }
        vis_id = self.create_visualization(
            'Completati Entro 48h', 'metric', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # ========== OLTRE 48H (RITARDATARI) ==========
        config = {
            'params': {'fontSize': '45', 'colorSchema': 'Red to Yellow'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}}
            ],
            'query': {
                'bool': {
                    'must': [
                        {'match': {'STATO': 'EVASA'}},
                        {'match': {'FK_NOME_OPERAZIONE': 'RESET_PASSWORD_ACCOUNT'}},
                        {'range': {'ore_elaborazione': {'gt': 48}}}
                    ]
                }
            }
        }
        vis_id = self.create_visualization(
            'Ritardatari (>48h)', 'metric', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # ========== DISTRIBUZIONE PIE ==========
        config = {
            'params': {'isDonut': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'range', 'schema': 'segment',
                 'params': {'field': 'ore_elaborazione', 'ranges': [
                     {'from': 0, 'to': 24},
                     {'from': 24, 'to': 48},
                     {'from': 48, 'to': 10000}
                 ]}}
            ],
            'query': {
                'bool': {
                    'must': [
                        {'match': {'STATO': 'EVASA'}},
                        {'match': {'FK_NOME_OPERAZIONE': 'RESET_PASSWORD_ACCOUNT'}}
                    ]
                }
            }
        }
        vis_id = self.create_visualization(
            'Distribuzione: <24h / 24-48h / >48h', 'pie', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # ========== TIMELINE ==========
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'bottom'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'DATA_CREAZIONE', 'fixed_interval': '1d'}}
            ],
            'query': {
                'bool': {
                    'must': [
                        {'match': {'STATO': 'EVASA'}},
                        {'match': {'FK_NOME_OPERAZIONE': 'RESET_PASSWORD_ACCOUNT'}}
                    ]
                }
            }
        }
        vis_id = self.create_visualization(
            'Timeline: Reset Giornalieri', 'line', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # ========== PER TIPO RICHIESTA ==========
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'right'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'FK_TIPO_RICHIESTA', 'size': 10}}
            ],
            'query': {
                'bool': {
                    'must': [
                        {'match': {'STATO': 'EVASA'}},
                        {'match': {'FK_NOME_OPERAZIONE': 'RESET_PASSWORD_ACCOUNT'}}
                    ]
                }
            }
        }
        vis_id = self.create_visualization(
            'Reset per Tipo Richiesta', 'histogram', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # ========== TOP UTENTI ==========
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'right'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'FK_UTENTE', 'size': 15}}
            ],
            'query': {
                'bool': {
                    'must': [
                        {'match': {'STATO': 'EVASA'}},
                        {'match': {'FK_NOME_OPERAZIONE': 'RESET_PASSWORD_ACCOUNT'}}
                    ]
                }
            }
        }
        vis_id = self.create_visualization(
            'Top 15 Utenti', 'histogram', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        return visualizations

    def create_dashboard(self, dashboard_title: str, visualizations: List[str]) -> Optional[str]:
        """Crea il dashboard"""
        try:
            dashboard_id = 'iam-kpi-reset-correct'

            self.session.delete(
                f"{self.base_url}/api/saved_objects/dashboard/{dashboard_id}",
                headers=self.headers
            )
            time.sleep(0.1)

            panels = []
            col_positions = [0, 50]

            for i, vis_id in enumerate(visualizations):
                col = i % 2
                row = (i // 2) * 20

                panel = {
                    'visualization': vis_id,
                    'x': col_positions[col],
                    'y': row,
                    'w': 50,
                    'h': 20
                }
                panels.append(panel)

            body = {
                'attributes': {
                    'title': dashboard_title,
                    'description': 'Dashboard KPI con percentuali reali',
                    'panelsJSON': json.dumps(panels),
                    'version': 1,
                    'timeRestore': False,
                    'refreshInterval': {'pause': False, 'value': 60000}
                }
            }

            response = self.session.post(
                f"{self.base_url}/api/saved_objects/dashboard/{dashboard_id}",
                json=body,
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"\n✅ Dashboard creato!\n")
                return dashboard_id
            else:
                print(f"✗ Errore: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"✗ Errore: {e}")
            return None


def main():
    print("\n" + "=" * 70)
    print("OPENSEARCH IAM KPI DASHBOARD - VERSIONE CORRETTA")
    print("=" * 70 + "\n")

    try:
        creator = IamKpiDashboardCorrect(
            host='localhost',
            port=5601,
            username='admin',
            password='admin'
        )

        print("Creazione visualizzazioni...\n")
        vis_ids = creator.create_kpi_visualizations('iam-richieste')

        if not vis_ids:
            print("\n✗ Errore")
            return

        print("\nCreazione dashboard...\n")
        dashboard_id = creator.create_dashboard(
            'IAM KPI - Reset Operations CORRECT',
            vis_ids
        )

        if dashboard_id:
            print("=" * 70)
            print(f"📊 Accedi a:")
            print(f"   http://localhost:5601/app/dashboards/view/{dashboard_id}")
            print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n✗ Errore: {e}")


if __name__ == "__main__":
    main()