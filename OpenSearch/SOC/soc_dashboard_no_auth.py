"""
SOC Dashboard Creator - Versione SENZA SICUREZZA (No Auth)
===========================================================

Crea automaticamente visualizzazioni su OpenSearch Dashboards
senza autenticazione
"""

import requests
import json
from typing import List, Dict, Optional
import time


class OpenSearchDashboardCreator:
    """Crea visualizzazioni su OpenSearch Dashboards - NO AUTH"""

    def __init__(self, host='localhost', port=5601):
        self.base_url = f"http://{host}:{port}"
        # Senza autenticazione
        self.headers = {
            'Content-Type': 'application/json',
            'osd-xsrf': 'true'
        }
        self.session = requests.Session()
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
            raise

    def create_index_pattern(self, pattern_name='soc-*',
                            time_field='timestamp') -> bool:
        """Crea index pattern"""
        try:
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

    def create_all_visualizations(self):
        """Crea tutte le visualizzazioni"""
        print("\n" + "="*70)
        print("CREAZIONE VISUALIZZAZIONI SOC")
        print("="*70)

        print("\n📊 Case Study 1: DDoS Detection")
        print("-" * 50)

        # DDoS - Top IP
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'right'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'src_ip', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ],
            'query': {'term': {'action': 'DENY'}}
        }
        self.create_visualization('DDoS: Top 10 IP Attaccanti', 'histogram', 'soc-*', config)

        # DDoS - Timeline
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'timestamp', 'interval': 'auto', 'customInterval': '5m'}}
            ],
            'query': {'term': {'action': 'DENY'}}
        }
        self.create_visualization('DDoS: Timeline Connessioni DENY', 'line', 'soc-*', config)

        # DDoS - Porte
        config = {
            'params': {'addTooltip': True, 'isDonut': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'dst_port', 'size': 10}}
            ]
        }
        self.create_visualization('DDoS: Porte Bersagliate', 'pie', 'soc-*', config)

        print("\n📊 Case Study 2: Data Exfiltration")
        print("-" * 50)

        # Exfil - IP interni
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'client_ip', 'size': 15}}
            ],
            'query': {'term': {'is_blocked': True}}
        }
        self.create_visualization('Exfil: IP Interni con Accessi Bloccati', 'histogram', 'soc-*', config)

        # Exfil - Trend
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'timestamp', 'interval': 'auto', 'customInterval': '10m'}}
            ],
            'query': {'term': {'is_blocked': True}}
        }
        self.create_visualization('Exfil: Trend Accessi Bloccati', 'area', 'soc-*', config)

        # Exfil - Domini bloccati
        config = {
            'params': {'isDonut': True, 'addTooltip': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'domain', 'size': 15}}
            ],
            'query': {'term': {'is_blocked': True}}
        }
        self.create_visualization('Exfil: Top Domini Bloccati', 'pie', 'soc-*', config)

        print("\n📊 Case Study 3: Web Attack")
        print("-" * 50)

        # Web - Timeline
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'timestamp', 'interval': 'auto', 'customInterval': '5m'}}
            ],
            'query': {'term': {'is_suspicious': True}}
        }
        self.create_visualization('WebAttack: Timeline Attacchi Rilevati', 'line', 'soc-*', config)

        # Web - Status code
        config = {
            'params': {'isDonut': False, 'addTooltip': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'status_code', 'size': 10}}
            ],
            'query': {'term': {'source_type': 'webserver'}}
        }
        self.create_visualization('WebAttack: Status Code Distribution', 'pie', 'soc-*', config)

        # Web - Percorsi
        config = {
            'params': {'perPage': 15},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'bucket',
                 'params': {'field': 'path', 'size': 15}}
            ],
            'query': {'term': {'is_suspicious': True}}
        }
        self.create_visualization('WebAttack: Percorsi Attaccati', 'table', 'soc-*', config)

        # Web - User agent
        config = {
            'params': {'isDonut': True, 'addTooltip': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'user_agent', 'size': 8}}
            ],
            'query': {'term': {'is_suspicious': True}}
        }
        self.create_visualization('WebAttack: User Agent Attacker', 'pie', 'soc-*', config)

        # Web - Response time
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
        self.create_visualization('WebAttack: Response Time Trend', 'line', 'soc-*', config)

        print("\n📊 Case Study 4: Insider Threat")
        print("-" * 50)

        # Insider - Timeline
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
        self.create_visualization('InsiderThreat: Timeline IP 10.0.1.50', 'line', 'soc-*', config)

        # Insider - Percorsi
        config = {
            'params': {'perPage': 15},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'bucket',
                 'params': {'field': 'path', 'size': 15}}
            ],
            'query': {'term': {'client_ip': '10.0.1.50'}}
        }
        self.create_visualization('InsiderThreat: Percorsi Acceduti', 'table', 'soc-*', config)

        # Insider - IP sospetti
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'client_ip', 'size': 20}}
            ],
            'query': {'term': {'is_suspicious': True}}
        }
        self.create_visualization('InsiderThreat: IP Interni Sospetti', 'histogram', 'soc-*', config)

        print("\n📊 Case Study 5: Router Anomaly")
        print("-" * 50)

        # Router - CPU/Memory
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
        self.create_visualization('Router: CPU/Memory Trend', 'line', 'soc-*', config)

        # Router - Alert types
        config = {
            'params': {'isDonut': True, 'addTooltip': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'log_type', 'size': 10}}
            ],
            'query': {'term': {'is_alert': True}}
        }
        self.create_visualization('Router: Tipi di Alert', 'pie', 'soc-*', config)

        # Router - Warning timeline
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'timestamp', 'interval': 'auto', 'customInterval': '10m'}}
            ],
            'query': {'term': {'severity': 'WARNING'}}
        }
        self.create_visualization('Router: Warning Timeline', 'area', 'soc-*', config)

        print("\n📊 Visualizzazioni Generali SOC")
        print("-" * 50)

        # Generale - Totale incidenti
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
        self.create_visualization('SOC: Totale Incidenti', 'metric', 'soc-*', config)

        # Generale - Incidenti per fonte
        config = {
            'params': {'isDonut': False, 'addTooltip': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'source_type', 'size': 10}}
            ]
        }
        self.create_visualization('SOC: Incidenti per Fonte', 'pie', 'soc-*', config)

        # Generale - Timeline
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'timestamp', 'interval': 'auto', 'customInterval': '5m'}}
            ]
        }
        self.create_visualization('SOC: Timeline Attività', 'line', 'soc-*', config)

        # Generale - Volume per fonte
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'source_type', 'size': 5}}
            ]
        }
        self.create_visualization('SOC: Volume Log per Fonte', 'histogram', 'soc-*', config)

        print(f"\n✓ Totale visualizzazioni create: {len(self.viz_ids)}")

    def create_dashboard(self, dashboard_name='SOC Security Monitoring'):
        """Crea dashboard con tutte le visualizzazioni"""
        try:
            dash_id = dashboard_name.lower().replace(' ', '-')

            try:
                self.session.delete(
                    f"{self.base_url}/api/saved_objects/dashboard/{dash_id}",
                    headers=self.headers
                )
            except:
                pass

            time.sleep(0.2)

            panels = []
            panel_positions = [
                {'x': 0, 'y': 0, 'w': 24, 'h': 3},
                {'x': 0, 'y': 3, 'w': 8, 'h': 3},
                {'x': 8, 'y': 3, 'w': 8, 'h': 3},
                {'x': 16, 'y': 3, 'w': 8, 'h': 3},
                {'x': 0, 'y': 6, 'w': 12, 'h': 3},
                {'x': 12, 'y': 6, 'w': 12, 'h': 3},
                {'x': 0, 'y': 9, 'w': 12, 'h': 3},
                {'x': 12, 'y': 9, 'w': 12, 'h': 3},
                {'x': 0, 'y': 12, 'w': 8, 'h': 3},
                {'x': 8, 'y': 12, 'w': 8, 'h': 3},
                {'x': 16, 'y': 12, 'w': 8, 'h': 3},
                {'x': 0, 'y': 15, 'w': 24, 'h': 3},
                {'x': 0, 'y': 18, 'w': 12, 'h': 3},
                {'x': 12, 'y': 18, 'w': 12, 'h': 3},
                {'x': 0, 'y': 21, 'w': 12, 'h': 3},
                {'x': 12, 'y': 21, 'w': 12, 'h': 3},
                {'x': 0, 'y': 24, 'w': 8, 'h': 3},
                {'x': 8, 'y': 24, 'w': 8, 'h': 3},
                {'x': 16, 'y': 24, 'w': 8, 'h': 3},
                {'x': 0, 'y': 27, 'w': 24, 'h': 3},
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

            body = {
                'attributes': {
                    'title': dashboard_name,
                    'description': 'Dashboard SOC Completo - 5 Case Study',
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
                return result['id']
            else:
                print(f"✗ Errore: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"✗ Errore: {e}")
            return None

    def print_summary(self):
        """Stampa riassunto finale"""
        print("\n" + "="*70)
        print("✅ SETUP DASHBOARD COMPLETATO!")
        print("="*70)

        print("\n📊 ACCEDI AL DASHBOARD:")
        print("   👉 http://localhost:5601/app/dashboards")

        print("\n📈 VISUALIZZAZIONI DISPONIBILI:")
        print("\n   🎯 DDoS Detection (3):")
        print("      • Top 10 IP Attaccanti")
        print("      • Timeline Connessioni DENY")
        print("      • Porte Bersagliate")

        print("\n   🎯 Data Exfiltration (4):")
        print("      • IP Interni con Accessi Bloccati")
        print("      • Trend Accessi Bloccati")
        print("      • Top Domini Bloccati")

        print("\n   🎯 Web Attack (5):")
        print("      • Timeline Attacchi Rilevati")
        print("      • Status Code Distribution")
        print("      • Percorsi Attaccati")
        print("      • User Agent Attacker")
        print("      • Response Time Trend")

        print("\n   🎯 Insider Threat (3):")
        print("      • Timeline IP 10.0.1.50")
        print("      • Percorsi Acceduti")
        print("      • IP Interni Sospetti")

        print("\n   🎯 Router Anomaly (3):")
        print("      • CPU/Memory Trend")
        print("      • Tipi di Alert")
        print("      • Warning Timeline")

        print("\n   🎯 Monitoraggio SOC (4):")
        print("      • Totale Incidenti")
        print("      • Incidenti per Fonte")
        print("      • Timeline Attività")
        print("      • Volume Log per Fonte")

        print("\n" + "="*70)


def main():
    """Esegui creazione dashboard"""

    print("="*70)
    print("SOC DASHBOARD CREATOR - No Auth")
    print("="*70)

    try:
        print("\n1️⃣  Connessione a OpenSearch Dashboards...")
        creator = OpenSearchDashboardCreator()

        print("\n2️⃣  Creazione Index Pattern...")
        creator.create_index_pattern('soc-*', 'timestamp')

        print("\n3️⃣  Creazione Visualizzazioni...")
        creator.create_all_visualizations()

        print("\n4️⃣  Creazione Dashboard...")
        creator.create_dashboard('SOC Security Monitoring')

        print("\n5️⃣  Riepilogo...")
        creator.print_summary()

    except Exception as e:
        print(f"\n✗ Errore: {e}")
        print("\nAssicurati che:")
        print("  • OpenSearch Dashboards sia in esecuzione su http://localhost:5601")
        print("  • I dati siano stati inseriti con: python soc_log_generator_no_auth.py")

if __name__ == "__main__":
    main()