"""
OpenSearch IAM Dashboard Creator - Visualizzazioni Professionali
==============================================================

Sistema per creare visualizzazioni dashboard professionali
e export report HTML/PDF

pip install requests jinja2 weasyprint
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class DashboardVisualization:
    """Definizione visualizzazione dashboard"""
    vis_id: str
    title: str
    description: str
    vis_type: str  # pie, bar, line, metric, table, gauge, heatmap
    aggs: List[Dict]
    params: Dict
    width: int = 12  # 1-12 per responsive grid
    height: int = 4


class IamDashboardCreator:
    """Crea dashboard visualizzazioni IAM su OpenSearch"""

    def __init__(self, host='localhost', port=5601, username='admin', password='admin'):
        """Inizializza connessione a OpenSearch Dashboards"""
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
                timeout=5
            )
            if response.status_code == 200:
                print("✓ Connesso a OpenSearch Dashboards")
            else:
                raise Exception("Impossibile connettersi")
        except Exception as e:
            print(f"✗ Errore: {e}")
            print("  Verifica che OpenSearch Dashboards sia su http://localhost:5601")
            raise

    def create_index_pattern(self, pattern='iam-richieste*', time_field='DATA_CREAZIONE') -> bool:
        """Crea index pattern"""
        try:
            # Verifica se esiste
            response = self.session.get(
                f"{self.base_url}/api/saved_objects/index-pattern/{pattern}",
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"⚠ Index pattern '{pattern}' già esistente")
                return True

            # Crea nuovo
            data = {
                'attributes': {
                    'title': pattern,
                    'timeFieldName': time_field,
                    'fields': '[]'
                }
            }

            response = self.session.post(
                f"{self.base_url}/api/saved_objects/index-pattern/{pattern}",
                json=data,
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"✓ Index pattern '{pattern}' creato")
                return True
            else:
                print(f"✗ Errore: {response.text[:200]}")
                return False

        except Exception as e:
            print(f"✗ Errore: {e}")
            return False

    def delete_visualization(self, vis_id: str) -> bool:
        """Elimina visualizzazione se esiste"""
        try:
            self.session.delete(
                f"{self.base_url}/api/saved_objects/visualization/{vis_id}",
                headers=self.headers
            )
            return True
        except:
            return False

    def create_visualization(self, vis: DashboardVisualization, index_pattern: str) -> Optional[str]:
        """Crea una visualizzazione"""
        try:
            self.delete_visualization(vis.vis_id)

            body = {
                'attributes': {
                    'title': vis.title,
                    'description': vis.description,
                    'visState': json.dumps({
                        'title': vis.title,
                        'type': vis.vis_type,
                        'params': vis.params,
                        'aggs': vis.aggs
                    }),
                    'uiStateJSON': json.dumps({'vis': {}}),
                    'kibanaSavedObjectMeta': {
                        'searchSourceJSON': json.dumps({
                            'index': index_pattern,
                            'query': {'match_all': {}},
                            'filter': []
                        })
                    }
                }
            }

            response = self.session.post(
                f"{self.base_url}/api/saved_objects/visualization/{vis.vis_id}",
                json=body,
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                print(f"✓ {vis.title}")
                return vis.vis_id
            else:
                print(f"✗ {vis.title}: {response.text[:100]}")
                return None

        except Exception as e:
            print(f"✗ Errore {vis.title}: {e}")
            return None

    def create_all_visualizations(self, index_pattern='iam-richieste*') -> List[str]:
        """Crea tutte le visualizzazioni IAM"""
        print("\n" + "=" * 70)
        print("📊 CREAZIONE VISUALIZZAZIONI DASHBOARD")
        print("=" * 70 + "\n")

        visualizations = []

        # 1. KPI Success Rate (Gauge)
        vis = DashboardVisualization(
            vis_id='iam-success-rate',
            title='Success Rate %',
            description='Percentuale di richieste completate con successo',
            vis_type='gauge',
            aggs=[
                {
                    'id': '1',
                    'enabled': True,
                    'type': 'count',
                    'schema': 'metric',
                    'params': {}
                }
            ],
            params={
                'type': 'gauge',
                'gauge': {
                    'alignment': 'automatic',
                    'autoExtend': False,
                    'extendRange': True,
                    'percentageMode': True,
                    'gaugeType': 'Arc',
                    'style': {'fontSize': '60'},
                    'backStyle': 'Full',
                    'orientation': 'vertical',
                    'useGaugeStyle': True
                },
                'valueAxes': [{
                    'id': 'ValueAxis-1',
                    'position': 'front',
                    'scale': {
                        'type': 'linear',
                        'mode': 'normal',
                        'min': 0,
                        'max': 100,
                        'tickPosition': 'inside',
                        'ticks': []
                    }
                }]
            },
            width=6,
            height=4
        )
        vid = self.create_visualization(vis, index_pattern)
        if vid:
            visualizations.append(vid)

        # 2. Richieste per Stato (Pie)
        vis = DashboardVisualization(
            vis_id='iam-richieste-stato',
            title='Distribuzione per Stato',
            description='Suddivisione richieste per stato di elaborazione',
            vis_type='pie',
            aggs=[
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'STATO', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ],
            params={'isDonut': False},
            width=6,
            height=4
        )
        vid = self.create_visualization(vis, index_pattern)
        if vid:
            visualizations.append(vid)

        # 3. Top 10 Operazioni (Bar)
        vis = DashboardVisualization(
            vis_id='iam-top-operazioni',
            title='Top 10 Operazioni',
            description='Operazioni più frequenti nel sistema',
            vis_type='histogram',
            aggs=[
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'FK_NOME_OPERAZIONE', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ],
            params={'addTooltip': True, 'addLegend': True, 'legendPosition': 'right'},
            width=12,
            height=4
        )
        vid = self.create_visualization(vis, index_pattern)
        if vid:
            visualizations.append(vid)

        # 4. Timeline Richieste (Line)
        vis = DashboardVisualization(
            vis_id='iam-timeline',
            title='Timeline Richieste - 30 Giorni',
            description='Andamento richieste nel tempo',
            vis_type='line',
            aggs=[
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'DATA_CREAZIONE', 'interval': 'auto', 'customInterval': '2h'}}
            ],
            params={
                'addTooltip': True,
                'addLegend': True,
                'legendPosition': 'bottom',
                'isAreaChart': True
            },
            width=12,
            height=4
        )
        vid = self.create_visualization(vis, index_pattern)
        if vid:
            visualizations.append(vid)

        # 5. Tipo Richiesta (Donut)
        vis = DashboardVisualization(
            vis_id='iam-tipo-richiesta',
            title='Richieste per Tipo',
            description='Suddivisione per tipo di richiesta IAM',
            vis_type='pie',
            aggs=[
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'FK_TIPO_RICHIESTA', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ],
            params={'isDonut': True},
            width=6,
            height=4
        )
        vid = self.create_visualization(vis, index_pattern)
        if vid:
            visualizations.append(vid)

        # 6. Top Utenti (Bar)
        vis = DashboardVisualization(
            vis_id='iam-top-utenti',
            title='Top 15 Utenti Attivi',
            description='Utenti con più richieste elaborate',
            vis_type='histogram',
            aggs=[
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'FK_UTENTE', 'size': 15, 'order': 'desc', 'orderBy': '1'}}
            ],
            params={'addTooltip': True, 'addLegend': False},
            width=6,
            height=4
        )
        vid = self.create_visualization(vis, index_pattern)
        if vid:
            visualizations.append(vid)

        # 7. Tempo Medio Elaborazione per Tipo (Bar)
        vis = DashboardVisualization(
            vis_id='iam-tempo-medio-tipo',
            title='Tempo Medio per Tipo Richiesta',
            description='Performance per tipo di operazione',
            vis_type='histogram',
            aggs=[
                {'id': '1', 'enabled': True, 'type': 'avg', 'schema': 'metric',
                 'params': {'field': 'ore_elaborazione'}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'FK_TIPO_RICHIESTA', 'size': 10}}
            ],
            params={'addTooltip': True, 'addLegend': False},
            width=6,
            height=4
        )
        vid = self.create_visualization(vis, index_pattern)
        if vid:
            visualizations.append(vid)

        # 8. Errori per Tipo Utenza (Bar)
        vis = DashboardVisualization(
            vis_id='iam-errori-tipo-utenza',
            title='Errori per Tipo Utenza',
            description='Distribuzione errori per categoria utente',
            vis_type='histogram',
            aggs=[
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'FK_TIPO_UTENZA', 'size': 10}}
            ],
            params={'addTooltip': True, 'addLegend': False},
            width=6,
            height=4
        )
        vid = self.create_visualization(vis, index_pattern)
        if vid:
            visualizations.append(vid)

        # 9. Tabella Richieste Recenti (Table)
        vis = DashboardVisualization(
            vis_id='iam-richieste-recenti',
            title='Richieste Recenti',
            description='Ultimi record elaborati',
            vis_type='table',
            aggs=[
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}}
            ],
            params={'perPage': 10, 'showPartialRows': False},
            width=12,
            height=4
        )
        vid = self.create_visualization(vis, index_pattern)
        if vid:
            visualizations.append(vid)

        # 10. Heatmap Ore Elaborazione (Heatmap)
        vis = DashboardVisualization(
            vis_id='iam-heatmap-ore',
            title='Distribuzione Tempo Elaborazione',
            description='Heatmap dei tempi di elaborazione',
            vis_type='histogram',
            aggs=[
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'histogram', 'schema': 'segment',
                 'params': {'field': 'ore_elaborazione', 'interval': 5}}
            ],
            params={'addTooltip': True, 'addLegend': True},
            width=6,
            height=4
        )
        vid = self.create_visualization(vis, index_pattern)
        if vid:
            visualizations.append(vid)

        # 11. Metric - Totale Richieste
        vis = DashboardVisualization(
            vis_id='iam-metric-totale',
            title='Totale Richieste',
            description='Numero totale di richieste nel periodo',
            vis_type='metric',
            aggs=[
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}}
            ],
            params={'fontSize': '60'},
            width=3,
            height=3
        )
        vid = self.create_visualization(vis, index_pattern)
        if vid:
            visualizations.append(vid)

        # 12. Metric - Fallite
        vis = DashboardVisualization(
            vis_id='iam-metric-fallite',
            title='Richieste Fallite',
            description='Numero richieste con errore',
            vis_type='metric',
            aggs=[
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {},
                 'filter': {'term': {'is_failed': True}}}
            ],
            params={'fontSize': '60'},
            width=3,
            height=3
        )
        vid = self.create_visualization(vis, index_pattern)
        if vid:
            visualizations.append(vid)

        # 13. Metric - In Attesa
        vis = DashboardVisualization(
            vis_id='iam-metric-attesa',
            title='In Elaborazione',
            description='Richieste ancora in corso',
            vis_type='metric',
            aggs=[
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {},
                 'filter': {'term': {'is_pending': True}}}
            ],
            params={'fontSize': '60'},
            width=3,
            height=3
        )
        vid = self.create_visualization(vis, index_pattern)
        if vid:
            visualizations.append(vid)

        # 14. Metric - Tempo Medio
        vis = DashboardVisualization(
            vis_id='iam-metric-tempo-medio',
            title='Tempo Medio (ore)',
            description='Tempo medio di elaborazione',
            vis_type='metric',
            aggs=[
                {'id': '1', 'enabled': True, 'type': 'avg', 'schema': 'metric',
                 'params': {'field': 'ore_elaborazione'}}
            ],
            params={'fontSize': '60'},
            width=3,
            height=3
        )
        vid = self.create_visualization(vis, index_pattern)
        if vid:
            visualizations.append(vid)

        return visualizations

    def create_dashboard(self, dashboard_id: str, title: str,
                         visualization_ids: List[str], index_pattern: str) -> bool:
        """Crea dashboard con visualizzazioni"""
        try:
            # Elimina se esiste
            self.session.delete(
                f"{self.base_url}/api/saved_objects/dashboard/{dashboard_id}",
                headers=self.headers
            )

            # Layout 3x4 per dashboard responsive
            panels = []
            panel_height = 4
            cols = 4

            for idx, vis_id in enumerate(visualization_ids):
                row = (idx // cols)
                col = (idx % cols)

                panels.append({
                    'visualization': {
                        'savedVizId': vis_id
                    },
                    'x': col * 3,
                    'y': row * panel_height,
                    'w': 3,
                    'h': panel_height
                })

            body = {
                'attributes': {
                    'title': title,
                    'description': 'Dashboard IAM con KPI, analisi e visualizzazioni professionali',
                    'panels': panels,
                    'timeRestore': True,
                    'timeFrom': 'now-30d',
                    'timeTo': 'now',
                    'refreshInterval': {
                        'pause': False,
                        'value': 60000
                    }
                }
            }

            response = self.session.post(
                f"{self.base_url}/api/saved_objects/dashboard/{dashboard_id}",
                json=body,
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                print(f"✓ Dashboard '{title}' creato")
                return True
            else:
                print(f"✗ Errore creazione dashboard: {response.text[:200]}")
                return False

        except Exception as e:
            print(f"✗ Errore: {e}")
            return False

    def print_instructions(self, dashboard_id: str):
        """Stampa istruzioni di accesso"""
        print("\n" + "=" * 70)
        print("✅ SETUP DASHBOARD COMPLETATO!")
        print("=" * 70)

        print(f"\n🎯 ACCEDI ALLA DASHBOARD:")
        print(f"\n   👉 http://localhost:5601/app/dashboards/view/{dashboard_id}")

        print(f"\n📊 VISUALIZZAZIONI DISPONIBILI:")
        print(f"""
   1. Success Rate % - Indicatore principale di salute
   2. Distribuzione per Stato - Stati delle richieste
   3. Top 10 Operazioni - Operazioni più frequenti
   4. Timeline Richieste - Andamento temporale
   5. Richieste per Tipo - Tipi di richiesta
   6. Top 15 Utenti - Utenti più attivi
   7. Tempo Medio per Tipo - Performance per tipo
   8. Errori per Tipo Utenza - Distribuzione errori
   9. Richieste Recenti - Ultimi record
   10. Distribuzione Tempo - Heatmap tempi
   11. Totale Richieste - KPI principale
   12. Richieste Fallite - KPI errori
   13. In Elaborazione - KPI pending
   14. Tempo Medio - KPI performance
        """)

        print(f"\n🔧 PER PERSONALIZZARE:")
        print(f"""
   1. Clicca su "Edit" per modificare il layout
   2. Aggiungi filtri temporali
   3. Personalizza i colori e le dimensioni
   4. Salva le modifiche
        """)

        print(f"\n💾 PER SCARICARE REPORT:")
        print(f"""
   1. Clicca il menu "..." in alto a destra
   2. Seleziona "Download as PDF"
   3. O usa "Generate CSV" per i dati
        """)


def main():
    """Setup dashboard IAM"""
    print("=" * 70)
    print("🚀 OPENSEARCH IAM DASHBOARD CREATOR")
    print("=" * 70 + "\n")

    try:
        # Crea creator
        creator = IamDashboardCreator(
            host='localhost',
            port=5601,
            username='admin',
            password='admin'
        )

        # Setup index pattern
        print("\n1️⃣  Creazione index pattern...")
        creator.create_index_pattern('iam-richieste*', 'DATA_CREAZIONE')

        # Crea visualizzazioni
        print("\n2️⃣  Creazione visualizzazioni...")
        vis_ids = creator.create_all_visualizations('iam-richieste*')

        # Crea dashboard
        print("\n3️⃣  Creazione dashboard...")
        creator.create_dashboard(
            'iam-dashboard-main',
            'IAM System - Main Dashboard',
            vis_ids,
            'iam-richieste*'
        )

        # Istruzioni
        creator.print_instructions('iam-dashboard-main')

        print("\n" + "=" * 70)

    except Exception as e:
        print(f"\n✗ Errore: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()