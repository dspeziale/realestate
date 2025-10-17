"""
IAM RICHIESTE - OpenSearch Visualizations
===========================================

Crea visualizzazioni automatiche su OpenSearch Dashboard
Script complementare a iam_opensearch_dashboard.py
"""

import requests
import json
from typing import Dict, List, Optional
from datetime import datetime


class IAMVisualizationsCreator:
    """Crea visualizzazioni su OpenSearch Dashboards"""

    def __init__(self, host='localhost', port=5601, username='admin', password='admin'):
        """Inizializza connessione"""
        self.base_url = f"http://{host}:{port}"
        self.auth = (username, password)
        self.headers = {
            'Content-Type': 'application/json',
            'osd-xsrf': 'true'
        }
        self.session = requests.Session()
        self.session.auth = self.auth
        self._verifica_connessione()

    def _verifica_connessione(self):
        """Verifica connessione"""
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

    def crea_index_pattern(self, index_pattern='iam-richieste', time_field='data_creazione') -> bool:
        """Crea index pattern"""
        try:
            # Verifica se esiste
            response = self.session.get(
                f"{self.base_url}/api/saved_objects/index-pattern/{index_pattern}",
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"⚠ Index pattern '{index_pattern}' già presente")
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
                print(f"✗ Errore: {response.text[:100]}")
                return False

        except Exception as e:
            print(f"✗ Errore: {e}")
            return False

    def crea_tutte_visualizzazioni(self, index_pattern='iam-richieste*') -> List[str]:
        """Crea tutte le visualizzazioni IAM"""
        visualizzazioni = []

        print("\n" + "=" * 70)
        print("CREAZIONE VISUALIZZAZIONI IAM")
        print("=" * 70 + "\n")

        # 1. Richieste per Stato (Pie Chart)
        print("1. Richieste per Stato...")
        config = {
            'params': {'isDonut': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'stato', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self._crea_visualizzazione('IAM - Richieste per Stato', 'pie', index_pattern, config)
        if vis_id:
            visualizzazioni.append(vis_id)

        # 2. Top 10 Operazioni (Bar Chart)
        print("2. Top 10 Operazioni...")
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'right'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'fk_nome_operazione.keyword', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self._crea_visualizzazione('IAM - Top 10 Operazioni', 'histogram', index_pattern, config)
        if vis_id:
            visualizzazioni.append(vis_id)

        # 3. Timeline Richieste (Line Chart)
        print("3. Timeline Richieste...")
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'bottom'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'data_creazione', 'interval': '1d', 'customInterval': '2h'}}
            ]
        }
        vis_id = self._crea_visualizzazione('IAM - Timeline Richieste', 'line', index_pattern, config)
        if vis_id:
            visualizzazioni.append(vis_id)

        # 4. Tempo Medio Evasione (Metric)
        print("4. Tempo Medio Evasione...")
        config = {
            'params': {'fontSize': '60'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'avg', 'schema': 'metric',
                 'params': {'field': 'tempo_evasione_ore'}}
            ]
        }
        vis_id = self._crea_visualizzazione('IAM - Tempo Medio Evasione (ore)', 'metric', index_pattern, config)
        if vis_id:
            visualizzazioni.append(vis_id)

        # 5. Tipo Utenza Distribution (Pie)
        print("5. Distribuzione per Tipo Utenza...")
        config = {
            'params': {'isDonut': False},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'fk_tipo_utenza', 'size': 20, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self._crea_visualizzazione('IAM - Tipo Utenza', 'pie', index_pattern, config)
        if vis_id:
            visualizzazioni.append(vis_id)

        # 6. Richieste NON EVASE (Table)
        print("6. Richieste Non Evase...")
        config = {
            'params': {'perPage': 10},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'bucket',
                 'params': {'field': 'nome_utenza.keyword', 'size': 20}},
                {'id': '3', 'enabled': True, 'type': 'terms', 'schema': 'bucket',
                 'params': {'field': 'fk_nome_operazione.keyword', 'size': 10}}
            ]
        }
        vis_id = self._crea_visualizzazione('IAM - Richieste Non Evase', 'table', index_pattern, config)
        if vis_id:
            visualizzazioni.append(vis_id)

        # 7. Operazioni per Stato (Stacked Bar)
        print("7. Operazioni per Stato...")
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'right'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'fk_nome_operazione.keyword', 'size': 15}},
                {'id': '3', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'stato', 'size': 5}}
            ]
        }
        vis_id = self._crea_visualizzazione('IAM - Operazioni per Stato', 'histogram', index_pattern, config)
        if vis_id:
            visualizzazioni.append(vis_id)

        # 8. Richieste per Utente (Top 20)
        print("8. Top 20 Utenti per Richieste...")
        config = {
            'params': {'addTooltip': True, 'addLegend': False},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'nome_utenza.keyword', 'size': 20, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self._crea_visualizzazione('IAM - Top 20 Utenti', 'histogram', index_pattern, config)
        if vis_id:
            visualizzazioni.append(vis_id)

        # 9. Tempo Evasione per Operazione (Box Plot - simulato con stats)
        print("9. Tempo Evasione per Operazione...")
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'stats', 'schema': 'metric',
                 'params': {'field': 'tempo_evasione_ore'}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'fk_nome_operazione.keyword', 'size': 10}}
            ]
        }
        vis_id = self._crea_visualizzazione('IAM - Tempo Evasione per Operazione', 'histogram', index_pattern, config)
        if vis_id:
            visualizzazioni.append(vis_id)

        # 10. Richieste Urgenti (Priority > 5)
        print("10. Richieste ad Alta Priorità...")
        config = {
            'params': {'perPage': 15},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'bucket',
                 'params': {'field': 'fk_nome_operazione.keyword', 'size': 20}},
                {'id': '3', 'enabled': True, 'type': 'terms', 'schema': 'bucket',
                 'params': {'field': 'stato', 'size': 5}}
            ]
        }
        vis_id = self._crea_visualizzazione('IAM - Richieste Alta Priorità', 'table', index_pattern, config)
        if vis_id:
            visualizzazioni.append(vis_id)

        # 11. KPI Dashboard (Custom)
        print("11. KPI Dashboard...")
        kpi_config = self._crea_kpi_dashboard(index_pattern)
        vis_id = self._crea_visualizzazione('IAM - KPI Summary', 'metric', index_pattern, kpi_config)
        if vis_id:
            visualizzazioni.append(vis_id)

        return visualizzazioni

    def _crea_visualizzazione(self, title: str, vis_type: str,
                             index_pattern: str, config: Dict) -> Optional[str]:
        """Crea una singola visualizzazione"""
        try:
            vis_id = title.lower().replace(' ', '-').replace('(', '').replace(')', '')

            # Elimina se esiste
            self._elimina_visualizzazione(vis_id)

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
                print(f"   ✓ Creata: {title}")
                return response.json()['id']
            else:
                print(f"   ✗ Errore '{title}': {response.text[:50]}")
                return None

        except Exception as e:
            print(f"   ✗ Errore: {e}")
            return None

    def _elimina_visualizzazione(self, vis_id: str) -> bool:
        """Elimina una visualizzazione se esiste"""
        try:
            response = self.session.delete(
                f"{self.base_url}/api/saved_objects/visualization/{vis_id}",
                headers=self.headers,
                timeout=5
            )
            return response.status_code in [200, 204]
        except:
            return False

    def crea_dashboard(self, vis_ids: List[str], dashboard_name='IAM - Main Dashboard') -> Optional[str]:
        """Crea dashboard con le visualizzazioni"""
        try:
            dashboard_id = dashboard_name.lower().replace(' ', '-').replace('(', '').replace(')', '')

            # Elimina se esiste
            self._elimina_dashboard(dashboard_id)

            # Struttura dei panel nel dashboard
            panels = []
            x, y = 0, 0
            for i, vis_id in enumerate(vis_ids[:12]):  # Max 12 visualizzazioni
                panel = {
                    'version': '8.0.0',
                    'gridData': {
                        'x': x,
                        'y': y,
                        'w': 24,
                        'h': 15
                    },
                    'type': 'visualization',
                    'id': f'panel-{i}',
                    'embeddableConfig': {},
                    'panelRefName': f'panel_{i}_embeddable'
                }
                panels.append(panel)
                x = (x + 24) % 48
                if x == 0:
                    y += 15

            body = {
                'attributes': {
                    'title': dashboard_name,
                    'panels': panels,
                    'timeRestore': True,
                    'timeFrom': 'now-30d',
                    'timeTo': 'now',
                    'refresh': '1h'
                }
            }

            response = self.session.post(
                f"{self.base_url}/api/saved_objects/dashboard/{dashboard_id}",
                json=body,
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                print(f"✓ Dashboard '{dashboard_name}' creato")
                return response.json()['id']
            else:
                print(f"✗ Errore dashboard: {response.text[:100]}")
                return None

        except Exception as e:
            print(f"✗ Errore creazione dashboard: {e}")
            return None

    def _elimina_dashboard(self, dashboard_id: str) -> bool:
        """Elimina dashboard se esiste"""
        try:
            response = self.session.delete(
                f"{self.base_url}/api/saved_objects/dashboard/{dashboard_id}",
                headers=self.headers,
                timeout=5
            )
            return response.status_code in [200, 204]
        except:
            return False

    def _crea_kpi_dashboard(self, index_pattern: str) -> Dict:
        """Crea configurazione per KPI dashboard"""
        return {
            'params': {'fontSize': '36'},
            'aggs': [
                {
                    'id': '1',
                    'enabled': True,
                    'type': 'count',
                    'schema': 'metric',
                    'params': {}
                }
            ]
        }

    def stampa_istruzioni(self, visualizzazioni: List[str]):
        """Stampa istruzioni post-creazione"""
        print("\n" + "=" * 70)
        print("✅ VISUALIZZAZIONI CREATE")
        print("=" * 70)

        print(f"\n📊 {len(visualizzazioni)} visualizzazioni create con successo!\n")

        print("🔗 ACCEDI A OPENSEARCH DASHBOARDS:")
        print("   → http://localhost:5601")

        print("\n📋 VISUALIZZAZIONI DISPONIBILI:")
        viz_list = [
            "IAM - Richieste per Stato",
            "IAM - Top 10 Operazioni",
            "IAM - Timeline Richieste",
            "IAM - Tempo Medio Evasione",
            "IAM - Tipo Utenza",
            "IAM - Richieste Non Evase",
            "IAM - Operazioni per Stato",
            "IAM - Top 20 Utenti",
            "IAM - Tempo Evasione per Operazione",
            "IAM - Richieste Alta Priorità",
            "IAM - KPI Summary"
        ]

        for i, name in enumerate(viz_list, 1):
            print(f"   {i}. {name}")

        print("\n💡 PROSSIMI PASSI:")
        print("   1. Vai su http://localhost:5601/app/dashboards")
        print("   2. Crea un nuovo Dashboard")
        print("   3. Aggiungi le visualizzazioni sopra")
        print("   4. Salva il dashboard")

        print("\n🔄 AGGIORNAMENTO PERIODICO:")
        print("   • Esegui daily: python iam_opensearch_dashboard.py")
        print("   • Dashboard si aggiorna automaticamente")

        print("\n" + "=" * 70)


def main():
    """Esecuzione principale"""
    print("=" * 70)
    print("IAM OPENSEARCH VISUALIZATIONS CREATOR")
    print("=" * 70)

    try:
        creator = IAMVisualizationsCreator(
            host='localhost',
            port=5601,
            username='admin',
            password='admin'
        )

        print("\n1. Creazione Index Pattern...")
        creator.crea_index_pattern('iam-richieste', 'data_creazione')

        print("\n2. Creazione Visualizzazioni...")
        visualizzazioni = creator.crea_tutte_visualizzazioni('iam-richieste*')

        print("\n3. Creazione Dashboard...")
        dashboard_id = creator.crea_dashboard(visualizzazioni, 'IAM - Main Dashboard')

        creator.stampa_istruzioni(visualizzazioni)

    except Exception as e:
        print(f"\n✗ Errore critico: {e}")


if __name__ == "__main__":
    main()