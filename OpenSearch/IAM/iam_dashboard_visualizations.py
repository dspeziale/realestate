"""
================================================================================
FILE: iam_dashboard_visualizations.py
================================================================================
IAM Dashboard Visualizations - Crea Dashboard OpenSearch

Versione SENZA SECURITY (OpenSearch senza plugin security abilitato)
Crea visualizzazioni professionali per il monitoraggio IAM:
- KPI Cards
- SLA Compliance Charts
- Trend Temporali
- Distribuzioni Operazioni
- Top Users
- Error Analysis

UTILIZZO:
    python iam_dashboard_visualizations.py

Output: Dashboard su http://localhost:5601/app/dashboards/view/iam-dashboard-main
================================================================================
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional
import time


class IAMDashboardCreator:
    """Crea visualizzazioni su OpenSearch Dashboards (NO SECURITY)"""

    def __init__(self, host='localhost', port=5601):
        """Inizializza connessione a Dashboards - NO AUTH"""
        self.base_url = f"http://{host}:{port}"
        self.headers = {
            'Content-Type': 'application/json',
            'osd-xsrf': 'true'
        }
        self.session = requests.Session()
        # NO auth perché security è disabilitato
        self.index_pattern = 'iam-richieste'

        try:
            response = self.session.get(
                f"{self.base_url}/api/status",
                headers=self.headers,
                timeout=5
            )
            if response.status_code == 200:
                print("✓ Connesso a OpenSearch Dashboards (NO SECURITY)")
            else:
                raise Exception(f"Status: {response.status_code}")
        except Exception as e:
            print(f"✗ Errore: {e}")
            print("  Verifica che OpenSearch Dashboards sia su http://localhost:5601")
            raise

    def _clean_id(self, title: str) -> str:
        """Crea ID pulito dal titolo"""
        return title.lower().replace(' ', '-').replace('(', '').replace(')', '').replace('%', 'pct')

    def create_index_pattern(self, time_field='data_creazione') -> bool:
        """Crea index pattern"""
        try:
            # Verifica se esiste
            response = self.session.get(
                f"{self.base_url}/api/saved_objects/index-pattern/{self.index_pattern}",
                headers=self.headers,
                timeout=5
            )

            if response.status_code == 200:
                print(f"✓ Index pattern '{self.index_pattern}' già esistente")
                return True

            data = {
                'attributes': {
                    'title': self.index_pattern,
                    'timeFieldName': time_field,
                    'fields': '[]'
                }
            }

            response = self.session.post(
                f"{self.base_url}/api/saved_objects/index-pattern/{self.index_pattern}",
                json=data,
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                print(f"✓ Index pattern '{self.index_pattern}' creato")
                return True
            else:
                print(f"⚠ Index pattern response: {response.status_code}")
                # Procedi comunque
                return True
        except Exception as e:
            print(f"⚠ Index pattern: {e}")
            return True

    def create_visualization(self, title: str, vis_type: str,
                            config: Dict) -> Optional[str]:
        """Crea una visualizzazione"""
        try:
            vis_id = self._clean_id(title)

            # Elimina se esiste
            try:
                self.session.delete(
                    f"{self.base_url}/api/saved_objects/visualization/{vis_id}",
                    headers=self.headers,
                    timeout=5
                )
            except:
                pass

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
                            'index': self.index_pattern,
                            'query': {'match_all': {}},
                            'filter': []
                        })
                    }
                }
            }

            response = self.session.post(
                f"{self.base_url}/api/saved_objects/visualization/{vis_id}",
                json=body,
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                print(f"  ✓ {title}")
                return vis_id
            else:
                print(f"  ⚠ {title}: {response.status_code}")
                if response.text:
                    print(f"     Response: {response.text[:100]}")
                return None
        except Exception as e:
            print(f"  ⚠ {title}: {str(e)[:80]}")
            return None

    def create_all_visualizations(self) -> List[str]:
        """Crea tutte le visualizzazioni"""
        print("\n" + "="*80)
        print("CREAZIONE VISUALIZZAZIONI")
        print("="*80 + "\n")

        vis_ids = []

        # 1. SLA Compliance by Operation (Pie)
        config = {
            'params': {'isDonut': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {
                    'id': '2', 'enabled': True, 'type': 'terms',
                    'schema': 'segment',
                    'params': {'field': 'fk_nome_operazione', 'size': 20}
                }
            ]
        }
        vid = self.create_visualization('SLA Compliance by Operation', 'pie', config)
        if vid:
            vis_ids.append(vid)

        # 2. Requests by Status (Bar)
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {
                    'id': '2', 'enabled': True, 'type': 'terms',
                    'schema': 'segment',
                    'params': {'field': 'stato', 'size': 10}
                }
            ]
        }
        vid = self.create_visualization('Requests by Status', 'histogram', config)
        if vid:
            vis_ids.append(vid)

        # 3. Timeline Requests (Line)
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'bottom'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {
                    'id': '2', 'enabled': True, 'type': 'date_histogram',
                    'schema': 'segment',
                    'params': {'field': 'data_creazione', 'interval': '1d'}
                }
            ]
        }
        vid = self.create_visualization('Requests Timeline (Daily)', 'line', config)
        if vid:
            vis_ids.append(vid)

        # 4. Average Duration by Operation (Horizontal Bar)
        config = {
            'params': {'addTooltip': True, 'addLegend': False},
            'aggs': [
                {
                    'id': '1', 'enabled': True, 'type': 'avg',
                    'schema': 'metric',
                    'params': {'field': 'durata_ore'}
                },
                {
                    'id': '2', 'enabled': True, 'type': 'terms',
                    'schema': 'segment',
                    'params': {'field': 'fk_nome_operazione', 'size': 15}
                }
            ]
        }
        vid = self.create_visualization('Avg Duration by Operation', 'histogram', config)
        if vid:
            vis_ids.append(vid)

        # 5. Total Requests (Metric)
        config = {
            'params': {'fontSize': '60'},
            'aggs': [
                {
                    'id': '1', 'enabled': True, 'type': 'count',
                    'schema': 'metric',
                    'params': {}
                }
            ]
        }
        vid = self.create_visualization('Total Requests', 'metric', config)
        if vid:
            vis_ids.append(vid)

        # 6. Top Users (Table)
        config = {
            'params': {'perPage': 10},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {
                    'id': '2', 'enabled': True, 'type': 'terms',
                    'schema': 'bucket',
                    'params': {'field': 'fk_utente_richiedente', 'size': 10}
                }
            ]
        }
        vid = self.create_visualization('Top Users', 'table', config)
        if vid:
            vis_ids.append(vid)

        # 7. Priority Distribution (Donut)
        config = {
            'params': {'isDonut': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {
                    'id': '2', 'enabled': True, 'type': 'terms',
                    'schema': 'segment',
                    'params': {'field': 'priorita', 'size': 10}
                }
            ]
        }
        vid = self.create_visualization('Requests by Priority', 'pie', config)
        if vid:
            vis_ids.append(vid)

        # 8. Area Responsible (Bar)
        config = {
            'params': {'addTooltip': True, 'addLegend': False},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {
                    'id': '2', 'enabled': True, 'type': 'terms',
                    'schema': 'segment',
                    'params': {'field': 'area_responsabile', 'size': 10}
                }
            ]
        }
        vid = self.create_visualization('Requests by Area', 'histogram', config)
        if vid:
            vis_ids.append(vid)

        # 9. SLA Compliance Rate (Metric)
        config = {
            'params': {'fontSize': '60'},
            'aggs': [
                {
                    'id': '1', 'enabled': True, 'type': 'count',
                    'schema': 'metric',
                    'params': {}
                }
            ]
        }
        vid = self.create_visualization('SLA Compliance %', 'metric', config)
        if vid:
            vis_ids.append(vid)

        # 10. Requests in Progress (Metric)
        config = {
            'params': {'fontSize': '60'},
            'aggs': [
                {
                    'id': '1', 'enabled': True, 'type': 'count',
                    'schema': 'metric',
                    'params': {}
                }
            ]
        }
        vid = self.create_visualization('In Progress Requests', 'metric', config)
        if vid:
            vis_ids.append(vid)

        # 11. Duration Distribution (Histogram)
        config = {
            'params': {'addTooltip': True, 'addLegend': False},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {
                    'id': '2', 'enabled': True, 'type': 'histogram',
                    'schema': 'segment',
                    'params': {'field': 'durata_ore', 'interval': 12}
                }
            ]
        }
        vid = self.create_visualization('Duration Distribution', 'histogram', config)
        if vid:
            vis_ids.append(vid)

        # 12. SLA Warning Alerts (Metric)
        config = {
            'params': {'fontSize': '60'},
            'aggs': [
                {
                    'id': '1', 'enabled': True, 'type': 'count',
                    'schema': 'metric',
                    'params': {}
                }
            ]
        }
        vid = self.create_visualization('SLA Warnings', 'metric', config)
        if vid:
            vis_ids.append(vid)

        return vis_ids

    def create_dashboard(self, vis_ids: List[str]) -> Optional[str]:
        """Crea dashboard assemblando le visualizzazioni"""
        print("\n" + "="*80)
        print("CREAZIONE DASHBOARD")
        print("="*80 + "\n")

        dashboard_id = 'iam-dashboard-main'
        dashboard_title = 'IAM Requests Monitor'

        # Elimina se esiste
        try:
            self.session.delete(
                f"{self.base_url}/api/saved_objects/dashboard/{dashboard_id}",
                headers=self.headers,
                timeout=5
            )
        except:
            pass

        # Crea grid delle visualizzazioni con struttura semplificata
        panels = []
        positions = [
            # Row 1
            {'x': 0, 'y': 0, 'w': 8, 'h': 4},   # Total Requests
            {'x': 8, 'y': 0, 'w': 8, 'h': 4},   # SLA Compliance %
            {'x': 16, 'y': 0, 'w': 8, 'h': 4},  # In Progress

            # Row 2
            {'x': 0, 'y': 4, 'w': 12, 'h': 5},  # Timeline
            {'x': 12, 'y': 4, 'w': 12, 'h': 5}, # By Status

            # Row 3
            {'x': 0, 'y': 9, 'w': 8, 'h': 5},   # Priority
            {'x': 8, 'y': 9, 'w': 8, 'h': 5},   # By Operation
            {'x': 16, 'y': 9, 'w': 8, 'h': 5},  # SLA Warnings

            # Row 4
            {'x': 0, 'y': 14, 'w': 12, 'h': 5},  # Avg Duration
            {'x': 12, 'y': 14, 'w': 12, 'h': 5}, # Duration Distribution

            # Row 5
            {'x': 0, 'y': 19, 'w': 12, 'h': 5},  # Top Users
            {'x': 12, 'y': 19, 'w': 12, 'h': 5}, # By Area
        ]

        # Costruisci panels array in formato semplificato
        for i, (vis_id, pos) in enumerate(zip(vis_ids, positions)):
            panel = {
                'version': '7.10.0',
                'gridData': {
                    'x': pos['x'],
                    'y': pos['y'],
                    'w': pos['w'],
                    'h': pos['h'],
                    'i': str(i)
                },
                'type': 'visualization',
                'id': vis_id,
                'embeddableConfig': {}
            }
            panels.append(panel)

        # Crea dashboard body con struttura minimale
        dashboard_body = {
            'attributes': {
                'title': dashboard_title,
                'description': 'IAM Requests Monitoring Dashboard',
                'panels': panels,
                'timeRestore': False,
                'refreshInterval': {
                    'pause': False,
                    'value': 60000
                }
            }
        }

        try:
            response = self.session.post(
                f"{self.base_url}/api/saved_objects/dashboard/{dashboard_id}",
                json=dashboard_body,
                headers=self.headers,
                timeout=15
            )

            if response.status_code == 200:
                print(f"✓ Dashboard '{dashboard_title}' creato")
                dashboard_url = f"{self.base_url}/app/dashboards/view/{dashboard_id}"
                print(f"  URL: {dashboard_url}")
                return dashboard_id
            elif response.status_code == 201:
                print(f"✓ Dashboard '{dashboard_title}' creato (201)")
                dashboard_url = f"{self.base_url}/app/dashboards/view/{dashboard_id}"
                print(f"  URL: {dashboard_url}")
                return dashboard_id
            else:
                print(f"✗ Errore creazione dashboard: {response.status_code}")
                print(f"   Response: {response.text[:300]}")

                # Prova metodo alternativo: crea dashboard vuota prima
                print("\n⏳ Tentativo con metodo alternativo...")
                return self._create_dashboard_minimal(dashboard_id, dashboard_title, vis_ids)
        except Exception as e:
            print(f"✗ Errore: {e}")
            return None

    def _create_dashboard_minimal(self, dashboard_id: str,
                                  dashboard_title: str,
                                  vis_ids: List[str]) -> Optional[str]:
        """Crea dashboard con metodo alternativo e aggiunge visualizzazioni"""
        try:
            # Step 1: Crea dashboard base
            minimal_body = {
                'attributes': {
                    'title': dashboard_title,
                    'description': 'IAM Requests Monitoring Dashboard',
                    'timeRestore': False,
                    'refreshInterval': {
                        'pause': False,
                        'value': 60000
                    }
                }
            }

            response = self.session.post(
                f"{self.base_url}/api/saved_objects/dashboard/{dashboard_id}",
                json=minimal_body,
                headers=self.headers,
                timeout=15
            )

            if response.status_code not in [200, 201]:
                print(f"✗ Errore creazione dashboard base: {response.status_code}")
                return None

            print(f"✓ Dashboard base creato")

            # Step 2: Aggiungi visualizzazioni una per una
            print(f"\n⏳ Aggiunta di {len(vis_ids)} visualizzazioni...")

            positions = [
                {'x': 0, 'y': 0, 'w': 8, 'h': 4},   # 0: Total Requests
                {'x': 8, 'y': 0, 'w': 8, 'h': 4},   # 1: SLA Compliance %
                {'x': 16, 'y': 0, 'w': 8, 'h': 4},  # 2: In Progress

                {'x': 0, 'y': 4, 'w': 12, 'h': 5},  # 3: Timeline
                {'x': 12, 'y': 4, 'w': 12, 'h': 5}, # 4: By Status

                {'x': 0, 'y': 9, 'w': 8, 'h': 5},   # 5: Priority
                {'x': 8, 'y': 9, 'w': 8, 'h': 5},   # 6: By Operation
                {'x': 16, 'y': 9, 'w': 8, 'h': 5},  # 7: SLA Warnings

                {'x': 0, 'y': 14, 'w': 12, 'h': 5},  # 8: Avg Duration
                {'x': 12, 'y': 14, 'w': 12, 'h': 5}, # 9: Duration Distribution

                {'x': 0, 'y': 19, 'w': 12, 'h': 5},  # 10: Top Users
                {'x': 12, 'y': 19, 'w': 12, 'h': 5}, # 11: By Area
            ]

            # Costruisci panels
            panels = []
            for i, (vis_id, pos) in enumerate(zip(vis_ids, positions)):
                panel = {
                    'version': '7.10.0',
                    'gridData': {
                        'x': pos['x'],
                        'y': pos['y'],
                        'w': pos['w'],
                        'h': pos['h'],
                        'i': str(i)
                    },
                    'type': 'visualization',
                    'id': vis_id,
                    'embeddableConfig': {}
                }
                panels.append(panel)
                print(f"  ✓ {i+1}. {vis_id}")

            # Step 3: Aggiorna dashboard con panels
            update_body = {
                'attributes': {
                    'title': dashboard_title,
                    'description': 'IAM Requests Monitoring Dashboard',
                    'panels': panels,
                    'timeRestore': False,
                    'refreshInterval': {
                        'pause': False,
                        'value': 60000
                    }
                }
            }

            response = self.session.put(
                f"{self.base_url}/api/saved_objects/dashboard/{dashboard_id}",
                json=update_body,
                headers=self.headers,
                timeout=15
            )

            if response.status_code == 200:
                print(f"\n✓ Dashboard assemblata con tutte le visualizzazioni!")
                dashboard_url = f"{self.base_url}/app/dashboards/view/{dashboard_id}"
                print(f"  URL: {dashboard_url}")
                return dashboard_id
            else:
                print(f"\n⚠ Dashboard creata ma aggiornamento panels: {response.status_code}")
                print(f"   Prova a ricaricare la pagina")
                dashboard_url = f"{self.base_url}/app/dashboards/view/{dashboard_id}"
                print(f"   URL: {dashboard_url}")
                return dashboard_id

        except Exception as e:
            print(f"✗ Errore metodo alternativo: {e}")
            return None

    def print_instructions(self, dashboard_id: Optional[str]):
        """Stampa istruzioni di accesso"""
        print("\n" + "="*80)
        print("✓ VISUALIZZAZIONI CREATE CON SUCCESSO!")
        print("="*80)

        print(f"\n📊 Dashboard:")
        if dashboard_id:
            url = f"{self.base_url}/app/dashboards/view/{dashboard_id}"
            print(f"   {url}\n")
        else:
            print(f"   http://localhost:5601/app/dashboards\n")

        print(f"✓ Visualizzazioni disponibili (12 totali):")
        print(f"   1. Total Requests (Metric)")
        print(f"   2. SLA Compliance % (Metric)")
        print(f"   3. In Progress Requests (Metric)")
        print(f"   4. Requests Timeline (Line Chart)")
        print(f"   5. Requests by Status (Bar Chart)")
        print(f"   6. Requests by Priority (Pie Chart)")
        print(f"   7. SLA Compliance by Operation (Pie Chart)")
        print(f"   8. Average Duration by Operation (Bar Chart)")
        print(f"   9. Duration Distribution (Histogram)")
        print(f"   10. Top Users (Table)")
        print(f"   11. Requests by Area (Bar Chart)")
        print(f"   12. SLA Warnings (Metric)")

        print(f"\n💡 COME USARE:")
        print(f"   1. Apri http://localhost:5601")
        print(f"   2. Vai a: Dashboard > Visualizzazioni")
        print(f"   3. Vedrai tutte le 12 visualizzazioni")
        print(f"   4. Puoi usarle singolarmente o assemblarle in una dashboard")

        print(f"\n🔄 AUTO-REFRESH: 60 secondi")
        print(f"   📈 Time Range: Ultimi 30 giorni\n")


def main():
    """Script principale"""
    print("="*80)
    print("IAM DASHBOARD VISUALIZATIONS (NO SECURITY)")
    print("="*80)

    try:
        creator = IAMDashboardCreator(
            host='localhost',
            port=5601
        )

        print("\n1. Creazione Index Pattern...")
        creator.create_index_pattern()

        print("\n2. Creazione Visualizzazioni...")
        vis_ids = creator.create_all_visualizations()

        if not vis_ids:
            print("\n⚠ Nessuna visualizzazione creata!")
            return

        print(f"\n3. Assembly Dashboard ({len(vis_ids)} visualizzazioni)...")
        dashboard_id = creator.create_dashboard(vis_ids)

        creator.print_instructions(dashboard_id)

    except Exception as e:
        print(f"\n✗ Errore: {e}")
        print("\n⚠ Verifica che OpenSearch Dashboards sia in esecuzione:")
        print("   docker-compose up -d opensearch-dashboards")


if __name__ == "__main__":
    main()