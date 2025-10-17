"""
OpenSearch IAM Dashboard Creator
================================

Crea automaticamente visualizzazioni e dashboard per IAM.STORICO_RICHIESTE
"""

import requests
import json
from typing import Dict, List, Optional
import time


class IamDashboardCreator:
    """Crea visualizzazioni e dashboard in OpenSearch Dashboards"""

    def __init__(self, host='localhost', port=5601, username='admin', password='admin'):
        """Inizializza la connessione a OpenSearch Dashboards"""
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
                print("✓ OpenSearch Dashboards connesso")
            else:
                raise Exception(f"Status code: {response.status_code}")
        except Exception as e:
            print(f"✗ Errore: {e}")
            print("  Verifica che OpenSearch Dashboards sia su http://localhost:5601")
            raise

    def create_index_pattern(self, index_pattern='iam-richieste',
                           time_field='DATA_CREAZIONE') -> bool:
        """Crea index pattern"""
        try:
            # Verifica se esiste già
            response = self.session.get(
                f"{self.base_url}/api/saved_objects/index-pattern/{index_pattern}",
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"⚠ Index pattern '{index_pattern}' già esistente")
                return True

            # Crea nuovo
            data = {
                'attributes': {
                    'title': index_pattern,
                    'timeFieldName': time_field,
                    'fields': '[]'
                }
            }

            response = self.session.post(
                f"{self.base_url}/api/saved_objects/index-pattern/{index_pattern}",
                json=data,
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"✓ Index pattern '{index_pattern}' creato")
                return True
            else:
                print(f"✗ Errore: {response.text[:200]}")
                return False

        except Exception as e:
            print(f"✗ Errore: {e}")
            return False

    def delete_visualization(self, vis_id: str) -> bool:
        """Elimina una visualizzazione se esiste"""
        try:
            response = self.session.delete(
                f"{self.base_url}/api/saved_objects/visualization/{vis_id}",
                headers=self.headers
            )
            return response.status_code == 200
        except:
            return False

    def create_visualization(self, title: str, vis_type: str,
                            index_pattern: str, config: Dict) -> Optional[str]:
        """Crea una visualizzazione"""
        try:
            vis_id = title.lower().replace(' ', '-').replace('(', '').replace(')', '').replace('_', '-')

            # Elimina se esiste
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
                            'filter': config.get('filter', [])
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
                print(f"✓ Visualizzazione '{title}' creata")
                return vis_id
            else:
                print(f"✗ Errore '{title}': {response.text[:150]}")
                return None

        except Exception as e:
            print(f"✗ Errore: {e}")
            return None

    def create_all_visualizations(self, index_pattern='iam-richieste') -> List[str]:
        """Crea tutte le visualizzazioni per IAM"""
        visualizations = []

        print("\n" + "=" * 70)
        print("CREAZIONE VISUALIZZAZIONI IAM")
        print("=" * 70 + "\n")

        # 1. Status Code Distribution - Pie Chart
        config = {
            'params': {'isDonut': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'STATO', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self.create_visualization(
            'IAM Richieste per Stato', 'pie', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # 2. Top Users - Bar Chart
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'right'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'FK_UTENTE', 'size': 15, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self.create_visualization(
            'IAM Top 15 Utenti Attivi', 'histogram', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # 3. Timeline Richieste - Line Chart
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'bottom'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'DATA_CREAZIONE', 'fixed_interval': '1d'}}
            ]
        }
        vis_id = self.create_visualization(
            'IAM Timeline Richieste Giornaliere', 'line', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # 4. Tipo Richiesta Distribution
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'right'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'FK_TIPO_RICHIESTA', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self.create_visualization(
            'IAM Richieste per Tipo', 'histogram', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # 5. Operazioni Top 10
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'FK_NOME_OPERAZIONE', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self.create_visualization(
            'IAM Top 10 Operazioni', 'histogram', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # 6. Success Rate - Metric
        config = {
            'params': {'fontSize': '60'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'filter', 'schema': 'metric',
                 'params': {'query': {'match': {'is_completed': True}}}}
            ],
            'query': {'match_all': {}}
        }
        vis_id = self.create_visualization(
            'IAM Richieste Completate', 'metric', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # 7. Tipo Utenza Distribution
        config = {
            'params': {'isDonut': False},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'FK_TIPO_UTENZA', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self.create_visualization(
            'IAM Richieste per Tipo Utenza', 'pie', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # 8. Tempo Elaborazione medio - Metric
        config = {
            'params': {'fontSize': '50'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'avg', 'schema': 'metric',
                 'params': {'field': 'ore_elaborazione'}}
            ]
        }
        vis_id = self.create_visualization(
            'IAM Tempo Medio Elaborazione (ore)', 'metric', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # 9. Richieste Fallite - Metric
        config = {
            'params': {'fontSize': '60', 'colorSchema': 'Red to Yellow to Green'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'filter', 'schema': 'metric',
                 'params': {'query': {'match': {'is_failed': True}}}}
            ],
            'query': {'match_all': {}}
        }
        vis_id = self.create_visualization(
            'IAM Richieste Fallite', 'metric', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # 10. Richieste per Dipartimento (se disponibile)
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'right'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'NOME_UTENZA', 'size': 15, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self.create_visualization(
            'IAM Top Utenze', 'histogram', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # 11. Richieste Lente - Data Table
        config = {
            'params': {'perPage': 10},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'bucket',
                 'params': {'field': 'FK_TIPO_RICHIESTA', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ],
            'query': {'range': {'ore_elaborazione': {'gte': 24}}}
        }
        vis_id = self.create_visualization(
            'IAM Richieste Lente (>24h)', 'table', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # 12. Tool Generazione Distribution
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'TOOL_GENERAZIONE', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self.create_visualization(
            'IAM Tool Generazione', 'histogram', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # 13. Timeline con Success Rate - Area Chart
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'bottom'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'DATA_CREAZIONE', 'fixed_interval': '1d'}},
                {'id': '3', 'enabled': True, 'type': 'filter', 'schema': 'metric',
                 'params': {'query': {'match': {'is_completed': True}}}}
            ]
        }
        vis_id = self.create_visualization(
            'IAM Trend Richieste Completate', 'area', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # 14. Modalità Lavoro Distribution
        config = {
            'params': {'isDonut': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'MODALITA_LAV_MASS', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self.create_visualization(
            'IAM Modalità Lavoro', 'pie', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        # 15. Tabella Dettagli Ultimi Errori
        config = {
            'params': {'perPage': 15},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'bucket',
                 'params': {'field': 'FK_UTENTE', 'size': 15}},
                {'id': '3', 'enabled': True, 'type': 'terms', 'schema': 'bucket',
                 'params': {'field': 'STATO', 'size': 5}}
            ],
            'query': {'match_all': {}}
        }
        vis_id = self.create_visualization(
            'IAM Dettagli per Utente e Stato', 'table', index_pattern, config
        )
        if vis_id:
            visualizations.append(vis_id)

        return visualizations

    def create_dashboard(self, dashboard_title: str, visualizations: List[str],
                        description: str = '') -> Optional[str]:
        """Crea un dashboard con le visualizzazioni"""
        try:
            dashboard_id = dashboard_title.lower().replace(' ', '-')

            # Elimina se esiste
            self.session.delete(
                f"{self.base_url}/api/saved_objects/dashboard/{dashboard_id}",
                headers=self.headers
            )
            time.sleep(0.1)

            # Crea pannelli
            panels = []
            for i, vis_id in enumerate(visualizations):
                panel = {
                    'visualization': vis_id,
                    'x': (i % 3) * 33,
                    'y': (i // 3) * 20,
                    'w': 33,
                    'h': 20
                }
                panels.append(panel)

            body = {
                'attributes': {
                    'title': dashboard_title,
                    'description': description,
                    'panelsJSON': json.dumps(panels),
                    'version': 1,
                    'timeRestore': False,
                    'refreshInterval': {'pause': False, 'value': 30000}
                }
            }

            response = self.session.post(
                f"{self.base_url}/api/saved_objects/dashboard/{dashboard_id}",
                json=body,
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"\n✓ Dashboard '{dashboard_title}' creato!")
                return dashboard_id
            else:
                print(f"✗ Errore dashboard: {response.text[:200]}")
                return None

        except Exception as e:
            print(f"✗ Errore: {e}")
            return None

    def print_dashboard_link(self, dashboard_id: str):
        """Stampa il link per accedere al dashboard"""
        print("\n" + "=" * 70)
        print("✅ DASHBOARD CREATO!")
        print("=" * 70)
        print(f"\n📊 Accedi al dashboard:")
        print(f"   👉 {self.base_url}/app/dashboards/view/{dashboard_id}")
        print("\n💡 Oppure da OpenSearch Dashboards:")
        print("   1. Menu → Dashboards")
        print("   2. Cerca: IAM Richieste")
        print("=" * 70 + "\n")


def main():
    """Esegue la creazione della dashboard"""
    print("=" * 70)
    print("OPENSEARCH IAM DASHBOARD CREATOR")
    print("=" * 70 + "\n")

    try:
        # Connessione
        creator = IamDashboardCreator(
            host='localhost',
            port=5601,
            username='admin',
            password='admin'
        )

        # Crea index pattern
        print("\n1. Creazione index pattern...\n")
        creator.create_index_pattern('iam-richieste', time_field='DATA_CREAZIONE')

        # Crea visualizzazioni
        print("\n2. Creazione visualizzazioni...\n")
        vis_ids = creator.create_all_visualizations('iam-richieste')

        if not vis_ids:
            print("\n✗ Nessuna visualizzazione creata")
            return

        # Crea dashboard
        print("\n3. Creazione dashboard...\n")
        dashboard_id = creator.create_dashboard(
            'IAM Richieste',
            vis_ids,
            'Dashboard di monitoraggio per IAM.STORICO_RICHIESTE'
        )

        if dashboard_id:
            creator.print_dashboard_link(dashboard_id)
            print(f"✓ {len(vis_ids)} visualizzazioni create e inserite")
        else:
            print("✗ Errore nella creazione del dashboard")

    except Exception as e:
        print(f"\n✗ Errore: {e}")


if __name__ == "__main__":
    main()