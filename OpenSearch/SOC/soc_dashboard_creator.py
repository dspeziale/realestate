"""
SOC Dashboard Creator - Auto-generazione Visualizzazioni
==========================================================

Crea automaticamente visualizzazioni e dashboard su OpenSearch Dashboards
per il SOC case study
"""

import requests
import json
from typing import List, Dict, Optional
import time


class OpenSearchDashboardCreator:
    """Crea visualizzazioni su OpenSearch Dashboards"""

    def __init__(self, host='localhost', port=5601,
                 username='admin', password='admin'):
        self.base_url = f"http://{host}:{port}"
        self.auth = (username, password)
        self.headers = {
            'Content-Type': 'application/json',
            'osd-xsrf': 'true'
        }
        self.session = requests.Session()
        self.session.auth = self.auth
        self.viz_ids = []

        try:
            response = self.session.get(
                f"{self.base_url}/api/status",
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                print("✓ Connesso a OpenSearch Dashboards")
            else:
                raise Exception("Impossibile connettersi")
        except Exception as e:
            print(f"✗ Errore: {e}")
            print("  Assicurati che OpenSearch Dashboards sia su http://localhost:5601")
            raise

    def create_index_pattern(self, pattern_name='soc-*',
                            time_field='timestamp') -> bool:
        """Crea index pattern"""
        try:
            # Verifica se esiste
            response = self.session.get(
                f"{self.base_url}/api/saved_objects/index-pattern/{pattern_name}",
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"⚠ Index pattern '{pattern_name}' già esistente")
                return True

            data = {
                'attributes': {
                    'title': pattern_name,
                    'timeFieldName': time_field,
                    'fields': '[]'
                }
            }

            response = self.session.post(
                f"{self.base_url}/api/saved_objects/index-pattern/{pattern_name}",
                json=data,
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"✓ Index pattern '{pattern_name}' creato")
                return True
            else:
                print(f"✗ Errore: {response.text[:100]}")
                return False

        except Exception as e:
            print(f"✗ Errore: {e}")
            return False

    def delete_visualization(self, vis_id: str) -> bool:
        """Elimina una visualizzazione se esiste"""
        try:
            self.session.delete(
                f"{self.base_url}/api/saved_objects/visualization/{vis_id}",
                headers=self.headers
            )
            return True
        except:
            return False

    def create_visualization(self, title: str, viz_type: str,
                            index_pattern: str, config: Dict) -> Optional[str]:
        """Crea una visualizzazione"""
        try:
            vis_id = title.lower().replace(' ', '-').replace('(', '').replace(')', '')

            # Elimina se esiste
            self.delete_visualization(vis_id)
            time.sleep(0.1)

            body = {
                'attributes': {
                    'title': title,
                    'visState': json.dumps({
                        'title': title,
                        'type': viz_type,
                        'params': config.get('params', {}),
                        'aggs': config.get('aggs', [])
                    }),
                    'uiStateJSON': '{}',
                    'kibanaSavedObjectMeta': {
                        'searchSourceJSON': json.dumps({
                            'index': index_pattern,
                            'query': config.get('query', {'match_all': {}}),
                            'filter': config.get('filters', [])
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
                result = response.json()
                self.viz_ids.append(result['id'])
                print(f"✓ Visualizzazione '{title}' creata")
                return result['id']
            else:
                print(f"✗ Errore '{title}': {response.text[:100]}")
                return None

        except Exception as e:
            print(f"✗ Errore: {e}")
            return None

    # ========== VISUALIZZAZIONI CASE STUDY 1: DDoS ==========

    def create_ddos_visualizations(self):
        """Case Study 1: Rilevamento DDoS"""
        print("\n📊 Case Study 1: DDoS Detection")
        print("-" * 50)

        # Viz 1: Top IP Attaccanti
        config = {
            'params': {
                'addTooltip': True,
                'addLegend': True,
                'legendPosition': 'right',
                'isDonut': False
            },
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'src_ip', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ],
            'query': {'term': {'action': 'DENY'}},
            'filters': [{'range': {'timestamp': {'gte': 'now-60m'}}}]
        }
        self.create_visualization(
            'DDoS: Top 10 IP Attaccanti',
            'histogram',
            'soc-*',
            config
        )

        # Viz 2: Connessioni DENY nel tempo
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'bottom'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'timestamp', 'interval': 'auto', 'customInterval': '5m'}}
            ],
            'query': {'term': {'action': 'DENY'}}
        }
        self.create_visualization(
            'DDoS: Timeline Connessioni DENY',
            'line',
            'soc-*',
            config
        )

        # Viz 3: Porte bersagliate
        config = {
            'params': {'addTooltip': True, 'isDonut': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'dst_port', 'size': 10}}
            ],
            'query': {'term': {'is_suspicious': True}}
        }
        self.create_visualization(
            'DDoS: Porte Bersagliate',
            'pie',
            'soc-*',
            config
        )

    # ========== VISUALIZZAZIONI CASE STUDY 2: Data Exfiltration ==========

    def create_exfiltration_visualizations(self):
        """Case Study 2: Data Exfiltration Detection"""
        print("\n📊 Case Study 2: Data Exfiltration Detection")
        print("-" * 50)

        # Viz 1: Accessi a C2/Malware
        config = {
            'params': {'perPage': 10},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'bucket',
                 'params': {'field': 'category.keyword', 'size': 10}}
            ],
            'query': {'terms': {'category': ['command-control', 'malware', 'phishing']}},
            'filters': [{'term': {'action': 'BLOCKED'}}]
        }
        self.create_visualization(
            'Exfil: Categorie Bloccate (C2/Malware)',
            'table',
            'soc-*',
            config
        )

        # Viz 2: IP interni sospetti
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'client_ip', 'size': 15}}
            ],
            'query': {'term': {'is_blocked': True}}
        }
        self.create_visualization(
            'Exfil: IP Interni con Accessi Bloccati',
            'histogram',
            'soc-*',
            config
        )

        # Viz 3: Trend accessi bloccati
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'timestamp', 'interval': 'auto', 'customInterval': '10m'}}
            ],
            'query': {'term': {'is_blocked': True}}
        }
        self.create_visualization(
            'Exfil: Trend Accessi Bloccati',
            'area',
            'soc-*',
            config
        )

        # Viz 4: Domini bloccati top
        config = {
            'params': {'isDonut': True, 'addTooltip': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'domain.keyword', 'size': 15}}
            ],
            'query': {'term': {'is_blocked': True}}
        }
        self.create_visualization(
            'Exfil: Top Domini Bloccati',
            'pie',
            'soc-*',
            config
        )

    # ========== VISUALIZZAZIONI CASE STUDY 3: Web Attack ==========

    def create_web_attack_visualizations(self):
        """Case Study 3: Web Attack Detection"""
        print("\n📊 Case Study 3: Web Attack Detection")
        print("-" * 50)

        # Viz 1: Attacchi web nel tempo
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'timestamp', 'interval': 'auto', 'customInterval': '5m'}}
            ],
            'query': {'term': {'is_suspicious': True}}
        }
        self.create_visualization(
            'WebAttack: Timeline Attacchi Rilevati',
            'line',
            'soc-*',
            config
        )

        # Viz 2: Distribuzione status code
        config = {
            'params': {'isDonut': False, 'addTooltip': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'status_code', 'size': 10}}
            ],
            'query': {'term': {'source_type': 'webserver'}}
        }
        self.create_visualization(
            'WebAttack: Status Code Distribution',
            'pie',
            'soc-*',
            config
        )

        # Viz 3: Percorsi attaccati
        config = {
            'params': {'perPage': 15},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'bucket',
                 'params': {'field': 'path.keyword', 'size': 15}}
            ],
            'query': {'term': {'is_suspicious': True}}
        }
        self.create_visualization(
            'WebAttack: Percorsi Attaccati',
            'table',
            'soc-*',
            config
        )

        # Viz 4: User agent attacker
        config = {
            'params': {'isDonut': True, 'addTooltip': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'user_agent.keyword', 'size': 8}}
            ],
            'query': {'term': {'is_suspicious': True}}
        }
        self.create_visualization(
            'WebAttack: User Agent Attacker',
            'pie',
            'soc-*',
            config
        )

        # Viz 5: Response time anomali
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'avg', 'schema': 'metric',
                 'params': {'field': 'response_time_ms'}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'timestamp', 'interval': 'auto', 'customInterval': '10m'}}
            ],
            'query': {'term': {'source_type': 'webserver'}}
        }
        self.create_visualization(
            'WebAttack: Response Time Trend',
            'line',
            'soc-*',
            config
        )

    # ========== VISUALIZZAZIONI CASE STUDY 4: Insider Threat ==========

    def create_insider_threat_visualizations(self):
        """Case Study 4: Insider Threat Detection"""
        print("\n📊 Case Study 4: Insider Threat Detection")
        print("-" * 50)

        # Viz 1: Attività IP 10.0.1.50
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'timestamp', 'interval': 'auto', 'customInterval': '5m'}}
            ],
            'query': {
                'bool': {
                    'should': [
                        {'term': {'client_ip': '10.0.1.50'}},
                        {'term': {'src_ip': '10.0.1.50'}}
                    ]
                }
            }
        }
        self.create_visualization(
            'InsiderThreat: Timeline IP Compromesso (10.0.1.50)',
            'line',
            'soc-*',
            config
        )

        # Viz 2: Percorsi acceduti da IP interno
        config = {
            'params': {'perPage': 15},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'bucket',
                 'params': {'field': 'path.keyword', 'size': 15}}
            ],
            'query': {'term': {'client_ip': '10.0.1.50'}}
        }
        self.create_visualization(
            'InsiderThreat: Percorsi Acceduti (Admin/Config)',
            'table',
            'soc-*',
            config
        )

        # Viz 3: IP interni anomali
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'client_ip', 'size': 20}}
            ],
            'query': {'term': {'is_suspicious': True}}
        }
        self.create_visualization(
            'InsiderThreat: IP Interni Sospetti',
            'histogram',
            'soc-*',
            config
        )

    # ========== VISUALIZZAZIONI CASE STUDY 5: Router Anomaly ==========

    def create_router_visualizations(self):
        """Case Study 5: Router Anomaly Detection"""
        print("\n📊 Case Study 5: Router Anomaly Detection")
        print("-" * 50)

        # Viz 1: CPU/Memory trend
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'avg', 'schema': 'metric',
                 'params': {'field': 'value'}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'timestamp', 'interval': 'auto', 'customInterval': '5m'}}
            ],
            'query': {'terms': {'log_type': ['cpu_high', 'memory_high']}}
        }
        self.create_visualization(
            'Router: CPU/Memory Trend',
            'line',
            'soc-*',
            config
        )

        # Viz 2: Tipi di alert
        config = {
            'params': {'isDonut': True, 'addTooltip': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'log_type.keyword', 'size': 10}}
            ],
            'query': {'term': {'is_alert': True}}
        }
        self.create_visualization(
            'Router: Tipi di Alert',
            'pie',
            'soc-*',
            config
        )

        # Viz 3: Alert severity nel tempo
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'timestamp', 'interval': 'auto', 'customInterval': '10m'}}
            ],
            'query': {'term': {'severity': 'WARNING'}}
        }
        self.create_visualization(
            'Router: Warning Timeline',
            'area',
            'soc-*',
            config
        )

    # ========== VISUALIZZAZIONI GENERALI SOC ==========

    def create_general_soc_visualizations(self):
        """Visualizzazioni generali SOC"""
        print("\n📊 Visualizzazioni Generali SOC")
        print("-" * 50)

        # Viz 1: Riassunto attività sospetta
        config = {
            'params': {'fontSize': '36'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}}
            ],
            'query': {
                'bool': {
                    'should': [
                        {'term': {'is_suspicious': True}},
                        {'term': {'is_alert': True}},
                        {'term': {'is_blocked': True}}
                    ]
                }
            }
        }
        self.create_visualization(
            'SOC: Totale Incidenti (Ultimi 60m)',
            'metric',
            'soc-*',
            config
        )

        # Viz 2: Incidenti per fonte
        config = {
            'params': {'isDonut': False, 'addTooltip': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'source_type', 'size': 10}}
            ]
        }
        self.create_visualization(
            'SOC: Incidenti per Fonte',
            'pie',
            'soc-*',
            config
        )

        # Viz 3: Timeline generale
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'timestamp', 'interval': 'auto', 'customInterval': '5m'}}
            ]
        }
        self.create_visualization(
            'SOC: Timeline Attività Complessiva',
            'line',
            'soc-*',
            config
        )

        # Viz 4: Log count per source
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'source_type', 'size': 5}}
            ]
        }
        self.create_visualization(
            'SOC: Volume Log per Fonte',
            'histogram',
            'soc-*',
            config
        )

    def create_all_visualizations(self):
        """Crea tutte le visualizzazioni"""
        print("\n" + "="*70)
        print("CREAZIONE VISUALIZZAZIONI SOC")
        print("="*70)

        self.create_ddos_visualizations()
        self.create_exfiltration_visualizations()
        self.create_web_attack_visualizations()
        self.create_insider_threat_visualizations()
        self.create_router_visualizations()
        self.create_general_soc_visualizations()

        print(f"\n✓ Totale visualizzazioni create: {len(self.viz_ids)}")

    def create_dashboard(self, dashboard_name='SOC Security Monitoring',
                        description='Dashboard di Monitoring SOC Completo'):
        """Crea dashboard con tutte le visualizzazioni"""
        try:
            # Pulisci nome dashboard
            dash_id = dashboard_name.lower().replace(' ', '-')

            # Elimina se esiste
            try:
                self.session.delete(
                    f"{self.base_url}/api/saved_objects/dashboard/{dash_id}",
                    headers=self.headers
                )
            except:
                pass

            time.sleep(0.2)

            # Crea structure del dashboard
            panels = []
            panel_positions = [
                {'x': 0, 'y': 0, 'w': 24, 'h': 4},    # Titolo
                {'x': 0, 'y': 4, 'w': 8, 'h': 3},     # Metrica top
                {'x': 8, 'y': 4, 'w': 8, 'h': 3},     # Metrica
                {'x': 16, 'y': 4, 'w': 8, 'h': 3},    # Metrica
                {'x': 0, 'y': 7, 'w': 12, 'h': 4},    # Timeline
                {'x': 12, 'y': 7, 'w': 12, 'h': 4},   # Timeline
                {'x': 0, 'y': 11, 'w': 12, 'h': 3},   # Chart
                {'x': 12, 'y': 11, 'w': 12, 'h': 3},  # Chart
                {'x': 0, 'y': 14, 'w': 8, 'h': 3},    # Pie/Donut
                {'x': 8, 'y': 14, 'w': 8, 'h': 3},    # Pie/Donut
                {'x': 16, 'y': 14, 'w': 8, 'h': 3},   # Pie/Donut
                {'x': 0, 'y': 17, 'w': 24, 'h': 3},   # Table
                {'x': 0, 'y': 20, 'w': 12, 'h': 3},   # Chart
                {'x': 12, 'y': 20, 'w': 12, 'h': 3},  # Chart
                {'x': 0, 'y': 23, 'w': 12, 'h': 3},   # Area
                {'x': 12, 'y': 23, 'w': 12, 'h': 3},  # Area
                {'x': 0, 'y': 26, 'w': 8, 'h': 3},    # Pie
                {'x': 8, 'y': 26, 'w': 8, 'h': 3},    # Pie
                {'x': 16, 'y': 26, 'w': 8, 'h': 3},   # Pie
                {'x': 0, 'y': 29, 'w': 24, 'h': 4},   # Timeline
            ]

            for i, viz_id in enumerate(self.viz_ids):
                if i < len(panel_positions):
                    pos = panel_positions[i]
                    panels.append({
                        'version': '7.13.0',
                        'gridData': {
                            'x': pos['x'],
                            'y': pos['y'],
                            'w': pos['w'],
                            'h': pos['h'],
                            'i': str(i)
                        },
                        'panelIndex': str(i),
                        'embeddableConfig': {},
                        'panelRefName': f"panel_{i}"
                    })

            # Crea request per dashboard
            body = {
                'attributes': {
                    'title': dashboard_name,
                    'description': description,
                    'panels': panels,
                    'timeRestore': False,
                    'timeFrom': 'now-24h',
                    'timeTo': 'now',
                    'refreshInterval': {
                        'pause': False,
                        'value': 10000
                    }
                },
                'references': [
                    {
                        'name': f"panel_{i}",
                        'type': 'visualization',
                        'id': self.viz_ids[i]
                    }
                    for i in range(len(self.viz_ids))
                ]
            }

            response = self.session.post(
                f"{self.base_url}/api/saved_objects/dashboard/{dash_id}",
                json=body,
                headers=self.headers
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✓ Dashboard '{dashboard_name}' creato")
                print(f"  ID: {result['id']}")
                return result['id']
            else:
                print(f"✗ Errore creazione dashboard: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"✗ Errore: {e}")
            return None

    def print_final_instructions(self):
        """Stampa istruzioni finali"""
        print("\n" + "="*70)
        print("✅ SETUP COMPLETATO!")
        print("="*70)

        print("\n📊 ACCEDI AL DASHBOARD:")
        print("   👉 http://localhost:5601/app/dashboards")
        print("      oppure")
        print("   👉 http://localhost:5601/app/dashboards?title=SOC")

        print("\n📈 VISUALIZZAZIONI CREATE:")
        print("\n   🎯 Case Study 1 - DDoS Detection:")
        print("      • Top 10 IP Attaccanti")
        print("      • Timeline Connessioni DENY")
        print("      • Porte Bersagliate")

        print("\n   🎯 Case Study 2 - Data Exfiltration:")
        print("      • Categorie Bloccate (C2/Malware)")
        print("      • IP Interni con Accessi Bloccati")
        print("      • Trend Accessi Bloccati")
        print("      • Top Domini Bloccati")

        print("\n   🎯 Case Study 3 - Web Attack:")
        print("      • Timeline Attacchi Rilevati")
        print("      • Status Code Distribution")
        print("      • Percorsi Attaccati")
        print("      • User Agent Attacker")
        print("      • Response Time Trend")

        print("\n   🎯 Case Study 4 - Insider Threat:")
        print("      • Timeline IP Compromesso")
        print("      • Percorsi Acceduti (Admin/Config)")
        print("      • IP Interni Sospetti")

        print("\n   🎯 Case Study 5 - Router Anomaly:")
        print("      • CPU/Memory Trend")
        print("      • Tipi di Alert")
        print("      • Warning Timeline")

        print("\n   🎯 Visualizzazioni Generali SOC:")
        print("      • Totale Incidenti (Ultimi 60m)")
        print("      • Incidenti per Fonte")
        print("      • Timeline Attività Complessiva")
        print("      • Volume Log per Fonte")

        print("\n🔍 COSA FARE DOPO:")
        print("\n   1. Attendi che il dashboard si carichi")
        print("   2. Le visualizzazioni si aggiornano ogni 10 secondi")
        print("   3. Filtra per timeframe differenti (1h, 24h, 7d)")
        print("   4. Clicca sulle visualizzazioni per drill-down")
        print("   5. Usa Discover per analisi approfondite")

        print("\n💡 QUERY UTILI NEL DEV TOOLS:")
        print("\n   Per trovare tutti gli incidenti:")
        print("   GET soc-*/_search")
        print("   { \"query\": { \"term\": { \"is_suspicious\": true } } }")
        print("\n   Per correlazione tra sorgenti:")
        print("   GET soc-*/_search")
        print("   { \"query\": { \"term\": { \"client_ip\": \"10.0.1.50\" } } }")

        print("\n⚠️  TROUBLESHOOTING:")
        print("\n   Se le visualizzazioni sono vuote:")
        print("   • Verifica che i dati siano in OpenSearch:")
        print("     GET _cat/indices | grep soc")
        print("   • Assicurati che timestamp sia in formato ISO")
        print("   • Ricrea gli index pattern in Management")

        print("\n" + "="*70)


def main():
    """Esegui creazione dashboard"""

    print("="*70)
    print("SOC DASHBOARD CREATOR - Auto-generazione Visualizzazioni")
    print("="*70)

    try:
        # 1. Connetti a OpenSearch Dashboards
        print("\n1️⃣  Connessione a OpenSearch Dashboards...")
        creator = OpenSearchDashboardCreator(
            host='localhost',
            port=5601,
            username='admin',
            password='admin'
        )

        # 2. Crea index pattern
        print("\n2️⃣  Creazione Index Pattern...")
        creator.create_index_pattern('soc-*', 'timestamp')

        # 3. Crea tutte le visualizzazioni
        print("\n3️⃣  Creazione Visualizzazioni...")
        creator.create_all_visualizations()

        # 4. Assembla dashboard
        print("\n4️⃣  Creazione Dashboard...")
        dashboard_id = creator.create_dashboard(
            'SOC Security Monitoring',
            'Dashboard di Monitoring SOC Completo - 5 Case Study'
        )

        # 5. Mostra istruzioni finali
        print("\n5️⃣  Setup Dashboard...")
        creator.print_final_instructions()

        if dashboard_id:
            print(f"\n🎉 Dashboard URL:")
            print(f"   http://localhost:5601/app/dashboards/{dashboard_id}")

    except Exception as e:
        print(f"\n✗ Errore: {e}")
        print("\nAssicurati che:")
        print("  • OpenSearch Dashboards sia in esecuzione su http://localhost:5601")
        print("  • I dati siano stati inseriti con: python soc_log_generator.py")
        print("  • Le credenziali siano corrette (admin:admin)")


if __name__ == "__main__":
    main()