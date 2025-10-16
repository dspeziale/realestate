"""
OpenSearch Web Server Log Analysis
===================================

Script per inserire log di web server in OpenSearch e fare analisi
"""

from opensearchpy import OpenSearch, helpers
from datetime import datetime, timedelta
import json
import random
import re
from typing import List, Dict, Any


class WebServerLogAnalyzer:
    """
    Analizzatore di log di web server con OpenSearch
    """

    def __init__(self, host='localhost', port=9200,
                 auth=('admin', 'admin'), use_ssl=False):
        """Inizializza la connessione a OpenSearch"""
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            http_auth=auth,
            use_ssl=use_ssl,
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30,
            max_retries=3,
            retry_on_timeout=True
        )

        try:
            info = self.client.info()
            print(f"✓ Connesso a OpenSearch {info['version']['number']}")
        except Exception as e:
            print(f"✗ Errore connessione: {e}")
            raise

    def create_logs_index(self, index_name='webserver-logs'):
        """Crea l'indice per i log con mappings appropriati"""
        mappings = {
            'properties': {
                'timestamp': {'type': 'date'},
                'ip': {'type': 'ip'},
                'method': {'type': 'keyword'},
                'path': {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},
                'status_code': {'type': 'integer'},
                'response_time_ms': {'type': 'integer'},
                'bytes_sent': {'type': 'integer'},
                'user_agent': {'type': 'text'},
                'referer': {'type': 'keyword'},
                'error_message': {'type': 'text'},
                'host': {'type': 'keyword'},
                'protocol': {'type': 'keyword'},
                'request_size': {'type': 'integer'}
            }
        }

        settings = {
            'number_of_shards': 2,
            'number_of_replicas': 0,
            'index': {
                'refresh_interval': '5s'
            }
        }

        try:
            if self.client.indices.exists(index=index_name):
                print(f"⚠ Indice '{index_name}' già esistente, cancello...")
                self.client.indices.delete(index=index_name)

            self.client.indices.create(
                index=index_name,
                body={'mappings': mappings, 'settings': settings}
            )
            print(f"✓ Indice '{index_name}' creato")
            return True
        except Exception as e:
            print(f"✗ Errore creazione indice: {e}")
            return False

    def generate_sample_logs(self, count=1000) -> List[Dict]:
        """Genera log di esempio realistici"""

        # Dati realistici
        ips = [
            '192.168.1.100', '192.168.1.101', '192.168.1.102',
            '203.0.113.45', '203.0.113.46', '203.0.113.47',
            '198.51.100.12', '198.51.100.13', '198.51.100.14'
        ]

        paths = [
            '/', '/api/users', '/api/products', '/api/login', '/static/style.css',
            '/static/script.js', '/images/logo.png', '/downloads/file.pdf',
            '/api/orders', '/dashboard', '/admin', '/api/search', '/blog',
            '/about', '/contact'
        ]

        methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']

        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) Firefox/89.0',
            'curl/7.68.0',
            'python-requests/2.26.0'
        ]

        hosts = ['example.com', 'api.example.com', 'cdn.example.com']

        referers = [
            'https://google.com', 'https://facebook.com', 'https://example.com',
            'https://example.com/blog', '-'
        ]

        logs = []
        now = datetime.now()

        for i in range(count):
            # Distribuisci i log nell'ultimo giorno
            offset_minutes = random.randint(0, 24 * 60 - 1)
            timestamp = now - timedelta(minutes=offset_minutes)

            # Status code distribuito realisticamente
            # 80% successo, 15% client error, 5% server error
            status_chance = random.random()
            if status_chance < 0.80:
                status_code = random.choices(
                    [200, 201, 204, 304],
                    weights=[70, 15, 10, 5]
                )[0]
            elif status_chance < 0.95:
                status_code = random.choices(
                    [400, 401, 403, 404, 409],
                    weights=[40, 30, 20, 5, 5]
                )[0]
            else:
                status_code = random.choices(
                    [500, 502, 503, 504],
                    weights=[40, 30, 20, 10]
                )[0]

            method = random.choice(methods)
            path = random.choice(paths)

            # Tempo di risposta correlato allo status code
            if status_code >= 500:
                response_time = random.randint(500, 5000)
            elif status_code >= 400:
                response_time = random.randint(100, 1000)
            else:
                response_time = random.randint(50, 500)

            bytes_sent = random.randint(100, 50000)

            log_entry = {
                'timestamp': timestamp.isoformat(),
                'ip': random.choice(ips),
                'method': method,
                'path': path,
                'status_code': status_code,
                'response_time_ms': response_time,
                'bytes_sent': bytes_sent,
                'user_agent': random.choice(user_agents),
                'referer': random.choice(referers),
                'host': random.choice(hosts),
                'protocol': 'HTTP/1.1' if random.random() > 0.3 else 'HTTP/2',
                'request_size': random.randint(200, 5000),
                'error_message': None
            }

            # Aggiungi messaggio di errore se errore
            if status_code >= 400:
                error_msgs = {
                    400: 'Bad Request - Invalid parameter',
                    401: 'Unauthorized - Authentication required',
                    403: 'Forbidden - Access denied',
                    404: 'Not Found',
                    409: 'Conflict - Resource exists',
                    500: 'Internal Server Error',
                    502: 'Bad Gateway',
                    503: 'Service Unavailable',
                    504: 'Gateway Timeout'
                }
                log_entry['error_message'] = error_msgs.get(status_code, 'Unknown error')

            logs.append(log_entry)

        return logs

    def insert_logs(self, logs: List[Dict], index_name='webserver-logs'):
        """Inserisce i log in bulk"""
        try:
            actions = [
                {
                    '_index': index_name,
                    '_source': log
                }
                for log in logs
            ]

            success, failed = helpers.bulk(
                self.client,
                actions,
                raise_on_error=False,
                refresh=True
            )

            print(f"✓ Inseriti {success} log ({len(failed)} fallimenti)")
            return success
        except Exception as e:
            print(f"✗ Errore inserimento: {e}")
            return 0

    # ========== ANALISI ==========

    def analisi_generale(self, index_name='webserver-logs'):
        """Analisi generale dei log"""
        print("\n" + "=" * 60)
        print("ANALISI GENERALE")
        print("=" * 60)

        # Conteggio totale
        response = self.client.count(index=index_name)
        total_logs = response['count']
        print(f"\nTotale log: {total_logs}")

        # Statistiche tempi di risposta
        stats_response = self.client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'response_time_stats': {
                        'stats': {'field': 'response_time_ms'}
                    }
                }
            }
        )

        stats = stats_response['aggregations']['response_time_stats']
        print(f"\nTempi di risposta (ms):")
        print(f"  Media: {stats['avg']:.2f}")
        print(f"  Min: {stats['min']:.0f}")
        print(f"  Max: {stats['max']:.0f}")
        print(f"  P95: richiede percentile agg")

    def analisi_status_codes(self, index_name='webserver-logs'):
        """Distribuzione status code"""
        print("\n" + "=" * 60)
        print("DISTRIBUZIONE STATUS CODE")
        print("=" * 60 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'status_codes': {
                        'terms': {
                            'field': 'status_code',
                            'size': 20
                        }
                    }
                }
            }
        )

        for bucket in response['aggregations']['status_codes']['buckets']:
            code = bucket['key']
            count = bucket['doc_count']
            percentage = (count / response['hits']['total']['value']) * 100

            # Colore basato su status
            if code < 300:
                indicator = "✓"
            elif code < 400:
                indicator = "→"
            elif code < 500:
                indicator = "⚠"
            else:
                indicator = "✗"

            print(f"  {indicator} {code}: {count:5d} ({percentage:5.1f}%)")

    def analisi_errori_top(self, index_name='webserver-logs', limit=10):
        """Top errori"""
        print("\n" + "=" * 60)
        print(f"TOP {limit} ERRORI PIÙ FREQUENTI")
        print("=" * 60 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'query': {'range': {'status_code': {'gte': 400}}},
                'size': 0,
                'aggs': {
                    'error_paths': {
                        'terms': {
                            'field': 'path.keyword',
                            'size': limit
                        }
                    }
                }
            }
        )

        for i, bucket in enumerate(response['aggregations']['error_paths']['buckets'], 1):
            path = bucket['key']
            count = bucket['doc_count']
            print(f"  {i}. {path}: {count} errori")

    def analisi_ip_top(self, index_name='webserver-logs', limit=10):
        """Top IP richiedenti"""
        print("\n" + "=" * 60)
        print(f"TOP {limit} IP RICHIEDENTI")
        print("=" * 60 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'top_ips': {
                        'terms': {
                            'field': 'ip',
                            'size': limit
                        }
                    }
                }
            }
        )

        for i, bucket in enumerate(response['aggregations']['top_ips']['buckets'], 1):
            ip = bucket['key']
            count = bucket['doc_count']
            print(f"  {i}. {ip}: {count} richieste")

    def analisi_richieste_lente(self, index_name='webserver-logs', threshold_ms=1000):
        """Richieste lente (sopra threshold)"""
        print("\n" + "=" * 60)
        print(f"RICHIESTE LENTE (>{threshold_ms}ms)")
        print("=" * 60 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'query': {
                    'range': {'response_time_ms': {'gte': threshold_ms}}
                },
                'size': 0,
                'aggs': {
                    'by_path': {
                        'terms': {
                            'field': 'path.keyword',
                            'size': 10
                        },
                        'aggs': {
                            'avg_time': {
                                'avg': {'field': 'response_time_ms'}
                            }
                        }
                    }
                }
            }
        )

        total_slow = response['hits']['total']['value']
        print(f"Totale richieste lente: {total_slow}\n")

        for bucket in response['aggregations']['by_path']['buckets']:
            path = bucket['key']
            count = bucket['doc_count']
            avg_time = bucket['avg_time']['value']
            print(f"  {path}:")
            print(f"    Conteggio: {count}, Tempo medio: {avg_time:.2f}ms")

    def analisi_per_metodo_http(self, index_name='webserver-logs'):
        """Richieste per metodo HTTP"""
        print("\n" + "=" * 60)
        print("RICHIESTE PER METODO HTTP")
        print("=" * 60 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'by_method': {
                        'terms': {'field': 'method'},
                        'aggs': {
                            'avg_response': {
                                'avg': {'field': 'response_time_ms'}
                            },
                            'success_rate': {
                                'terms': {'field': 'status_code'}
                            }
                        }
                    }
                }
            }
        )

        for bucket in response['aggregations']['by_method']['buckets']:
            method = bucket['key']
            count = bucket['doc_count']
            avg_response = bucket['avg_response']['value']

            print(f"  {method}: {count} richieste, tempo medio: {avg_response:.2f}ms")

    def analisi_timeline(self, index_name='webserver-logs', interval='5m'):
        """Richieste nel tempo"""
        print("\n" + "=" * 60)
        print(f"TIMELINE RICHIESTE (intervallo: {interval})")
        print("=" * 60 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'size': 0,
                'aggs': {
                    'timeline': {
                        'date_histogram': {
                            'field': 'timestamp',
                            'fixed_interval': interval
                        }
                    }
                }
            }
        )

        buckets = response['aggregations']['timeline']['buckets']

        if not buckets:
            print("  Nessun dato disponibile")
            return

        max_count = max(b['doc_count'] for b in buckets)

        for bucket in buckets[-20:]:  # Ultimi 20 intervalli
            timestamp = bucket['key_as_string']
            count = bucket['doc_count']
            bar_width = int((count / max_count) * 30) if max_count > 0 else 0
            bar = '█' * bar_width

            print(f"  {timestamp}: {bar} {count}")

    def analisi_errori_5xx(self, index_name='webserver-logs'):
        """Dettagli errori server (5xx)"""
        print("\n" + "=" * 60)
        print("ERRORI SERVER (5xx)")
        print("=" * 60 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'query': {'range': {'status_code': {'gte': 500}}},
                'size': 5
            }
        )

        total = response['hits']['total']['value']
        print(f"Totale errori 5xx: {total}\n")

        if response['hits']['hits']:
            print("Ultimi errori:")
            for hit in response['hits']['hits']:
                doc = hit['_source']
                print(f"  {doc['timestamp']} - {doc['ip']} - {doc['status_code']}: {doc.get('error_message', 'N/A')}")
                print(f"    {doc['method']} {doc['path']} ({doc['response_time_ms']}ms)\n")


def main():
    """Esegue l'analisi completa"""
    print("=" * 60)
    print("OPENSEARCH WEB SERVER LOG ANALYSIS")
    print("=" * 60)

    analyzer = WebServerLogAnalyzer(
        host='localhost',
        port=9200,
        auth=('admin', 'admin'),
        use_ssl=False
    )

    # Crea indice
    print("\n1. Creazione indice...")
    analyzer.create_logs_index('webserver-logs')

    # Genera e inserisci log
    print("\n2. Generazione log di esempio...")
    logs = analyzer.generate_sample_logs(count=200000)

    print("\n3. Inserimento in OpenSearch...")
    analyzer.insert_logs(logs, 'webserver-logs')

    # Esegui analisi
    print("\n4. Esecuzione analisi...")
    analyzer.analisi_generale('webserver-logs')
    analyzer.analisi_status_codes('webserver-logs')
    analyzer.analisi_errori_top('webserver-logs', limit=10)
    analyzer.analisi_ip_top('webserver-logs', limit=10)
    analyzer.analisi_richieste_lente('webserver-logs', threshold_ms=1000)
    analyzer.analisi_per_metodo_http('webserver-logs')
    analyzer.analisi_timeline('webserver-logs', interval='5m')
    analyzer.analisi_errori_5xx('webserver-logs')

    print("\n" + "=" * 60)
    print("ANALISI COMPLETATA!")
    print("=" * 60)


if __name__ == "__main__":
    main()