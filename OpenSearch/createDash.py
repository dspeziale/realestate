"""
OpenSearch Dashboard Creator - Metodo Semplificato
==================================================

Crea visualizzazioni e fornisce il link per il dashboard manuale
"""

import requests
import json
from datetime import datetime
from typing import Dict, List


class OpenSearchDashboardCreator:
    """
    Crea visualizzazioni su OpenSearch Dashboards
    """

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
                headers=self.headers
            )
            if response.status_code == 200:
                print("✓ Connesso a OpenSearch Dashboards")
            else:
                raise Exception("Impossibile connettersi")
        except Exception as e:
            print(f"✗ Errore: {e}")
            print("  Verifica che OpenSearch Dashboards sia su http://localhost:5601")
            raise

    def create_index_pattern(self, index_pattern='webserver-logs',
                           time_field='timestamp') -> bool:
        """Crea index pattern"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/saved_objects/index-pattern/{index_pattern}",
                headers=self.headers
            )

            if response.status_code == 200:
                print(f"⚠ Index pattern '{index_pattern}' già esistente")
                return True

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
                print(f"✗ Errore: {response.text}")
                return False

        except Exception as e:
            print(f"✗ Errore: {e}")
            return False

    def delete_visualization(self, vis_id: str) -> bool:
        """Elimina una visualizzazione"""
        try:
            response = self.session.delete(
                f"{self.base_url}/api/saved_objects/visualization/{vis_id}",
                headers=self.headers
            )
            return response.status_code == 200
        except:
            return False

    def create_visualization(self, title: str, visualization_type: str,
                            index_pattern: str, config: Dict) -> str:
        """Crea una visualizzazione"""
        try:
            vis_id = title.lower().replace(' ', '-').replace('(', '').replace(')', '')

            # Elimina se esiste
            self.delete_visualization(vis_id)

            body = {
                'attributes': {
                    'title': title,
                    'visState': json.dumps({
                        'title': title,
                        'type': visualization_type,
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
                headers=self.headers
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✓ Visualizzazione '{title}' creata")
                return result['id']
            else:
                print(f"✗ Errore '{title}': {response.text[:100]}")
                return None

        except Exception as e:
            print(f"✗ Errore: {e}")
            return None

    def create_all_visualizations(self, index_pattern='webserver-logs') -> List[str]:
        """Crea tutte le visualizzazioni"""
        visualizations = []

        print("\n" + "="*60)
        print("CREAZIONE VISUALIZZAZIONI")
        print("="*60 + "\n")

        # 1. Status Code Distribution
        config = {
            'params': {'isDonut': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'status_code', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self.create_visualization('Status Code Distribution', 'pie', index_pattern, config)
        if vis_id:
            visualizations.append(vis_id)

        # 2. Top IP
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'right'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'ip', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self.create_visualization('Top 10 IP Addresses', 'histogram', index_pattern, config)
        if vis_id:
            visualizations.append(vis_id)

        # 3. Timeline
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'bottom'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'date_histogram', 'schema': 'segment',
                 'params': {'field': 'timestamp', 'interval': '5m', 'customInterval': '2h'}}
            ]
        }
        vis_id = self.create_visualization('Requests Over Time', 'line', index_pattern, config)
        if vis_id:
            visualizations.append(vis_id)

        # 4. HTTP Methods
        config = {
            'params': {'addTooltip': True, 'addLegend': True, 'legendPosition': 'right'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'segment',
                 'params': {'field': 'method', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self.create_visualization('HTTP Methods', 'histogram', index_pattern, config)
        if vis_id:
            visualizations.append(vis_id)

        # 5. Average Response Time
        config = {
            'params': {'fontSize': '60'},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'avg', 'schema': 'metric',
                 'params': {'field': 'response_time_ms'}}
            ]
        }
        vis_id = self.create_visualization('Average Response Time ms', 'metric', index_pattern, config)
        if vis_id:
            visualizations.append(vis_id)

        # 6. Top Error Paths
        config = {
            'params': {'perPage': 10},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'bucket',
                 'params': {'field': 'path.keyword', 'size': 10, 'order': 'desc', 'orderBy': '1'}}
            ]
        }
        vis_id = self.create_visualization('Top Error Paths', 'table', index_pattern, config)
        if vis_id:
            visualizations.append(vis_id)

        # 7. Bytes Sent
        config = {
            'params': {'addTooltip': True, 'addLegend': True},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'histogram', 'schema': 'segment',
                 'params': {'field': 'bytes_sent', 'interval': 5000}}
            ]
        }
        vis_id = self.create_visualization('Bytes Sent Distribution', 'histogram', index_pattern, config)
        if vis_id:
            visualizations.append(vis_id)

        # 8. Status by Path
        config = {
            'params': {'perPage': 15},
            'aggs': [
                {'id': '1', 'enabled': True, 'type': 'count', 'schema': 'metric', 'params': {}},
                {'id': '2', 'enabled': True, 'type': 'terms', 'schema': 'bucket',
                 'params': {'field': 'path.keyword', 'size': 20}},
                {'id': '3', 'enabled': True, 'type': 'terms', 'schema': 'bucket',
                 'params': {'field': 'status_code', 'size': 5}}
            ]
        }
        vis_id = self.create_visualization('Status Codes by Path', 'table', index_pattern, config)
        if vis_id:
            visualizations.append(vis_id)

        return visualizations

    def print_instructions(self, vis_ids: List[str]):
        """Stampa le istruzioni per creare il dashboard manualmente"""
        print("\n" + "="*60)
        print("DASHBOARD - ISTRUZIONI MANUALI")
        print("="*60)

        print(f"\n✓ {len(vis_ids)} visualizzazioni create con successo!\n")

        print("📋 PER CREARE IL DASHBOARD MANUALMENTE:\n")
        print("1. Accedi a: http://localhost:5601")
        print("2. Vai a: Dashboard > Create Dashboard")
        print("3. Clicca: 'Add an existing' oppure 'Add'")
        print("4. Aggiungi queste visualizzazioni:\n")

        vis_names = [
            "Status Code Distribution",
            "Top 10 IP Addresses",
            "Requests Over Time",
            "HTTP Methods",
            "Average Response Time ms",
            "Top Error Paths",
            "Bytes Sent Distribution",
            "Status Codes by Path"
        ]

        for i, name in enumerate(vis_names, 1):
            print(f"   {i}. {name}")

        print("\n5. Clicca 'Save' per salvare il dashboard")

        print("\n" + "="*60)
        print("✓ OPPURE: Usa questo link diretto")
        print("="*60)
        print("\nhttp://localhost:5601/app/dashboards")

        print("\n" + "="*60)
        print("ALTERNATIVE:")
        print("="*60)
        print("\n1. Se hai permessi di admin, verifica le policy")
        print("2. Prova a disabilitare temporaneamente security plugin:")
        print("   - Modifica opensearch.yml")
        print("   - Commenta: #plugins.security.ssl.http.enabled: true")
        print("\n3. Oppure crea il dashboard dall'UI (come sopra)")


def main():
    print("="*60)
    print("OPENSEARCH DASHBOARD CREATOR")
    print("="*60)

    try:
        creator = OpenSearchDashboardCreator(
            host='localhost',
            port=5601,
            username='admin',
            password='admin'
        )

        print("\n1. Creazione index pattern...")
        creator.create_index_pattern('webserver-logs')

        print("\n2. Creazione visualizzazioni...")
        vis_ids = creator.create_all_visualizations('webserver-logs')

        creator.print_instructions(vis_ids)

    except Exception as e:
        print(f"\n✗ Errore: {e}")


if __name__ == "__main__":
    main()