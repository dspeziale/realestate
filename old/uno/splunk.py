"""
Script per Leggere Dati da Splunk
=================================

Legge dati da Splunk via REST API e:
1. Esporta i risultati
2. Analizza i dati
3. Opzionale: invia a OpenSearch

Installazione:
pip install splunk-sdk requests pandas
"""

import requests
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import time


class SplunkDataReader:
    """
    Legge dati da Splunk via REST API
    """

    def __init__(self, host='localhost', port=8089,
                 username='admin', password='changeme',
                 verify_ssl=False):
        """
        Inizializza connessione a Splunk

        Args:
            host: hostname Splunk
            port: porta REST API (default 8089)
            username: username admin
            password: password admin
            verify_ssl: verifica certificato SSL
        """
        self.host = host
        self.port = port
        self.base_url = f"https://{host}:{port}"
        self.auth = HTTPBasicAuth(username, password)
        self.verify_ssl = verify_ssl

        # Disabilita warning SSL se necessario
        if not verify_ssl:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.verify = verify_ssl

        # Test connessione
        if self._test_connection():
            print(f"✓ Connesso a Splunk ({host}:{port})")
        else:
            raise Exception("Impossibile connettersi a Splunk")

    def _test_connection(self) -> bool:
        """Testa la connessione a Splunk"""
        try:
            response = self.session.get(f"{self.base_url}/services/server/info")
            return response.status_code == 200
        except Exception as e:
            print(f"✗ Errore connessione: {e}")
            return False

    def search(self, query: str, earliest_time: str = '-24h',
               latest_time: str = 'now',
               max_count: int = 0) -> List[Dict]:
        """
        Esegue una ricerca Splunk

        Args:
            query: SPL query
            earliest_time: tempo inizio (es: '-24h', '-7d@d', '2024-01-01T00:00:00')
            latest_time: tempo fine (default 'now')
            max_count: numero massimo risultati (0 = tutti)

        Returns:
            Lista di risultati
        """
        print(f"\n🔍 Esecuzione query Splunk...")
        print(f"   Query: {query[:60]}...")

        payload = {
            'search': query,
            'earliest_time': earliest_time,
            'latest_time': latest_time,
            'output_mode': 'json',
            'count': max_count if max_count > 0 else 1000
        }

        try:
            # Crea job di ricerca
            response = self.session.post(
                f"{self.base_url}/services/search/jobs",
                data=payload
            )
            response.raise_for_status()

            job_data = response.json()
            job_id = job_data['sid']
            print(f"   Job ID: {job_id}")

            # Attendi completamento
            return self._wait_job(job_id)

        except Exception as e:
            print(f"✗ Errore ricerca: {e}")
            return []

    def _wait_job(self, job_id: str, timeout: int = 300,
                  poll_interval: int = 2) -> List[Dict]:
        """Aspetta che il job di ricerca sia completato"""
        start_time = time.time()

        while True:
            try:
                response = self.session.get(
                    f"{self.base_url}/services/search/jobs/{job_id}",
                    params={'output_mode': 'json'}
                )
                response.raise_for_status()

                job_info = response.json()['entry'][0]['content']

                # Verifica stato
                if job_info['isDone'] == True:
                    print(f"✓ Job completato")
                    return self._get_results(job_id)

                # Progress
                progress = job_info.get('scanCount', 0)
                print(f"   Progress: {progress} eventi scansionati...", end='\r')

                # Timeout check
                if time.time() - start_time > timeout:
                    print(f"\n✗ Timeout raggiunto")
                    return []

                time.sleep(poll_interval)

            except Exception as e:
                print(f"\n✗ Errore: {e}")
                return []

    def _get_results(self, job_id: str) -> List[Dict]:
        """Estrae i risultati dal job completato"""
        try:
            response = self.session.get(
                f"{self.base_url}/services/search/jobs/{job_id}/results",
                params={'output_mode': 'json', 'count': 0}
            )
            response.raise_for_status()

            data = response.json()
            results = data.get('results', [])
            print(f"✓ Estratti {len(results)} risultati")
            return results

        except Exception as e:
            print(f"✗ Errore estrazione risultati: {e}")
            return []

    def search_saved(self, saved_search_name: str,
                     earliest_time: str = '-24h',
                     latest_time: str = 'now') -> List[Dict]:
        """
        Esegue una ricerca salvata in Splunk

        Args:
            saved_search_name: nome della ricerca salvata
            earliest_time: override tempo inizio
            latest_time: override tempo fine
        """
        print(f"\n🔍 Esecuzione ricerca salvata: {saved_search_name}")

        try:
            # Estrai nome app dalla ricerca salvata (format: app/search_name)
            if '/' in saved_search_name:
                app, search_name = saved_search_name.split('/')
            else:
                app = 'search'
                search_name = saved_search_name

            # Esegui ricerca salvata
            payload = {
                'output_mode': 'json',
                'earliest_time': earliest_time,
                'latest_time': latest_time
            }

            response = self.session.post(
                f"{self.base_url}/services/saved/searches/{search_name}/dispatch",
                data=payload
            )
            response.raise_for_status()

            job_data = response.json()
            job_id = job_data['sid']
            print(f"   Job ID: {job_id}")

            return self._wait_job(job_id)

        except Exception as e:
            print(f"✗ Errore: {e}")
            return []

    def list_saved_searches(self, app: str = '-') -> List[Dict]:
        """Lista tutte le ricerche salvate"""
        try:
            response = self.session.get(
                f"{self.base_url}/services/saved/searches",
                params={'output_mode': 'json', 'count': 0}
            )
            response.raise_for_status()

            searches = []
            for entry in response.json()['entry']:
                search_info = {
                    'name': entry['name'],
                    'title': entry['content'].get('title', entry['name']),
                    'search': entry['content'].get('search', ''),
                    'app': entry['acl'].get('app', 'unknown')
                }
                searches.append(search_info)

            return searches

        except Exception as e:
            print(f"✗ Errore listing: {e}")
            return []

    def export_to_json(self, results: List[Dict],
                       filename: str = 'splunk_export.json'):
        """Esporta risultati in JSON"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"✓ Esportato in {filename}")
            return True
        except Exception as e:
            print(f"✗ Errore export: {e}")
            return False

    def export_to_csv(self, results: List[Dict],
                      filename: str = 'splunk_export.csv'):
        """Esporta risultati in CSV"""
        try:
            import csv

            if not results:
                print("✗ Nessun risultato da esportare")
                return False

            keys = results[0].keys()

            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(results)

            print(f"✓ Esportato in {filename}")
            return True
        except Exception as e:
            print(f"✗ Errore export CSV: {e}")
            return False

    # ========== ANALISI DATI ==========

    def analyze_results(self, results: List[Dict]):
        """Analizza i risultati estratti"""
        if not results:
            print("✗ Nessun risultato da analizzare")
            return

        print("\n" + "="*60)
        print("ANALISI RISULTATI")
        print("="*60)

        print(f"\n📊 Totale risultati: {len(results)}")

        # Struttura risultati
        if results:
            print(f"\n📋 Campi disponibili:")
            fields = list(results[0].keys())
            for field in fields[:20]:  # Mostra primi 20 campi
                print(f"   - {field}")
            if len(fields) > 20:
                print(f"   ... e altri {len(fields) - 20} campi")

        # Statistiche campi numerici
        print(f"\n📈 Statistiche campi numerici:")
        for field in list(results[0].keys())[:10]:
            values = []
            for result in results:
                try:
                    val = float(result.get(field, 0))
                    values.append(val)
                except (ValueError, TypeError):
                    pass

            if values:
                print(f"   {field}:")
                print(f"     - Min: {min(values):.2f}")
                print(f"     - Max: {max(values):.2f}")
                print(f"     - Media: {sum(values)/len(values):.2f}")

    def search_web_logs(self, earliest_time: str = '-24h') -> List[Dict]:
        """
        Esempio: ricerca log web
        """
        query = """
        index=_internal source=*splunkd.log* level=ERROR
        | stats count by host, level
        | sort - count
        """
        return self.search(query, earliest_time=earliest_time, max_count=1000)

    def search_authentication(self, earliest_time: str = '-7d') -> List[Dict]:
        """
        Esempio: ricerca tentativi autenticazione falliti
        """
        query = """
        index=main sourcetype=linux_auth "Failed password"
        | stats count by src_ip, user
        | where count > 5
        | sort - count
        """
        return self.search(query, earliest_time=earliest_time, max_count=500)

    def search_performance(self, earliest_time: str = '-24h') -> List[Dict]:
        """
        Esempio: ricerca problemi di performance
        """
        query = """
        index=main source=/var/log/app.log
        | search response_time > 1000
        | stats avg(response_time) as avg_time, 
                 max(response_time) as max_time,
                 count by endpoint
        | sort - avg_time
        """
        return self.search(query, earliest_time=earliest_time, max_count=500)

    def search_errors(self, earliest_time: str = '-24h') -> List[Dict]:
        """
        Esempio: ricerca errori applicazione
        """
        query = """
        index=main level=ERROR OR level=CRITICAL
        | stats count as error_count by source, level
        | where error_count > 10
        | sort - error_count
        """
        return self.search(query, earliest_time=earliest_time, max_count=500)


# ========== INTEGRAZIONI ==========

class SplunkToOpenSearch:
    """
    Trasferisce dati da Splunk a OpenSearch
    """

    def __init__(self, splunk_reader: SplunkDataReader,
                 opensearch_host='localhost', opensearch_port=9200):
        """Inizializza integratore"""
        self.splunk = splunk_reader

        try:
            from opensearchpy import OpenSearch
            self.os_client = OpenSearch(
                hosts=[{'host': opensearch_host, 'port': opensearch_port}],
                http_auth=('admin', 'admin'),
                use_ssl=False,
                verify_certs=False,
                ssl_show_warn=False
            )
            print("✓ Connesso a OpenSearch")
        except Exception as e:
            print(f"✗ Errore OpenSearch: {e}")
            self.os_client = None

    def transfer_results(self, results: List[Dict],
                        index_name: str = 'splunk-import'):
        """Trasferisce risultati Splunk a OpenSearch"""
        if not self.os_client:
            print("✗ OpenSearch non disponibile")
            return False

        try:
            from opensearchpy import helpers

            actions = [
                {
                    '_index': index_name,
                    '_source': result
                }
                for result in results
            ]

            success, failed = helpers.bulk(
                self.os_client,
                actions,
                raise_on_error=False,
                refresh=True
            )

            print(f"✓ Trasferiti {success} documenti a OpenSearch")
            if failed:
                print(f"⚠ {len(failed)} fallimenti")
            return True

        except Exception as e:
            print(f"✗ Errore trasferimento: {e}")
            return False


# ========== ESEMPI ==========

def main():
    """Esempi di utilizzo"""
    print("="*60)
    print("SPLUNK DATA READER")
    print("="*60)

    try:
        # Connessione a Splunk
        print("\n1. Connessione a Splunk...")
        reader = SplunkDataReader(
            host='localhost',
            port=8089,
            username='admin',
            password='changeme',
            verify_ssl=False
        )

        # Esempio 1: List ricerche salvate
        print("\n2. Ricerche salvate disponibili:")
        saved_searches = reader.list_saved_searches()
        for search in saved_searches[:5]:
            print(f"   - {search['name']} ({search['app']})")

        # Esempio 2: Ricerca semplice
        print("\n3. Ricerca semplice: errori nelle ultime 24 ore...")
        results = reader.search_errors(earliest_time='-24h')

        # Analizza risultati
        if results:
            reader.analyze_results(results)

            # Esporta in JSON
            reader.export_to_json(results, 'errors_24h.json')

            # Esporta in CSV
            reader.export_to_csv(results, 'errors_24h.csv')

            # Trasferisci a OpenSearch (opzionale)
            print("\n4. Trasferimento a OpenSearch...")
            transfer = SplunkToOpenSearch(reader)
            transfer.transfer_results(results, 'splunk-errors')

        # Esempio 3: Performance
        print("\n5. Ricerca performance...")
        perf_results = reader.search_performance(earliest_time='-7d')
        if perf_results:
            reader.analyze_results(perf_results)

        # Esempio 4: Autenticazioni fallite
        print("\n6. Ricerca autenticazioni fallite...")
        auth_results = reader.search_authentication(earliest_time='-7d')
        if auth_results:
            print(f"✓ Trovati {len(auth_results)} tentativi sospetti")

        print("\n" + "="*60)
        print("✅ COMPLETATO!")
        print("="*60)

    except Exception as e:
        print(f"\n✗ Errore: {e}")


if __name__ == "__main__":
    main()
