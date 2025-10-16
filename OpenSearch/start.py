"""
OpenSearch Python Client - Guida Completa ed Esempi Pratici
============================================================

Questo script mostra come utilizzare OpenSearch da Python con esempi
completi per tutte le operazioni comuni.

Installazione:
pip install opensearch-py

"""

from opensearchpy import OpenSearch, helpers
from datetime import datetime, timedelta
import json
import random
from typing import List, Dict, Any


class OpenSearchManager:
    """
    Classe per gestire tutte le operazioni con OpenSearch
    """

    def __init__(self, host='localhost', port=9200,
                 auth=('admin', 'admin'), use_ssl=False,
                 max_retries=3, timeout=30):
        """
        Inizializza la connessione a OpenSearch

        Args:
            host: hostname di OpenSearch
            port: porta (default 9200)
            auth: tupla (username, password)
            use_ssl: se True usa HTTPS
            max_retries: tentativi di connessione
            timeout: timeout in secondi
        """
        self.client = OpenSearch(
            hosts=[{'host': host, 'port': port}],
            http_auth=auth,
            use_ssl=use_ssl,
            verify_certs=False,
            ssl_show_warn=False,
            timeout=timeout,
            max_retries=max_retries,
            retry_on_timeout=True
        )

        # Verifica connessione con retry
        for attempt in range(max_retries):
            try:
                info = self.client.info()
                print(f"✓ Connesso a OpenSearch {info['version']['number']}")
                print(f"  Cluster: {info['cluster_name']}")
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⏳ Tentativo {attempt + 1}/{max_retries} fallito, riprovo...")
                    import time
                    time.sleep(2)
                else:
                    print(f"\n❌ ERRORE: Impossibile connettersi a OpenSearch!")
                    print(f"   Dettagli: {e}")
                    print(f"\n🔧 Verifica che OpenSearch sia in esecuzione su {host}:{port}")
                    print("   Test rapido: curl http://localhost:9200")
                    print("   Oppure apri nel browser: http://localhost:9200")
                    raise

    # ========== GESTIONE INDICI ==========

    def create_index(self, index_name: str, mappings: Dict = None,
                     settings: Dict = None) -> bool:
        """
        Crea un nuovo indice con mappings e settings
        """
        body = {}
        if settings:
            body['settings'] = settings
        if mappings:
            body['mappings'] = mappings

        try:
            if self.client.indices.exists(index=index_name):
                print(f"⚠ Indice '{index_name}' già esistente")
                return False

            response = self.client.indices.create(
                index=index_name,
                body=body
            )
            print(f"✓ Indice '{index_name}' creato con successo")
            return True
        except Exception as e:
            print(f"✗ Errore creazione indice: {e}")
            return False

    def delete_index(self, index_name: str) -> bool:
        """Elimina un indice"""
        try:
            if not self.client.indices.exists(index=index_name):
                print(f"⚠ Indice '{index_name}' non esiste")
                return False

            self.client.indices.delete(index=index_name)
            print(f"✓ Indice '{index_name}' eliminato")
            return True
        except Exception as e:
            print(f"✗ Errore eliminazione indice: {e}")
            return False

    def list_indices(self) -> List[str]:
        """Lista tutti gli indici"""
        try:
            indices = self.client.cat.indices(format='json')
            index_names = [idx['index'] for idx in indices]
            print(f"✓ Trovati {len(index_names)} indici")
            return index_names
        except Exception as e:
            print(f"✗ Errore listing indici: {e}")
            return []

    def get_index_info(self, index_name: str) -> Dict:
        """Ottieni informazioni su un indice"""
        try:
            info = self.client.indices.get(index=index_name)
            stats = self.client.indices.stats(index=index_name)

            result = {
                'settings': info[index_name]['settings'],
                'mappings': info[index_name]['mappings'],
                'docs_count': stats['_all']['primaries']['docs']['count'],
                'store_size': stats['_all']['primaries']['store']['size_in_bytes']
            }
            return result
        except Exception as e:
            print(f"✗ Errore ottenimento info: {e}")
            return {}

    # ========== INSERIMENTO DOCUMENTI ==========

    def index_document(self, index_name: str, document: Dict,
                       doc_id: str = None) -> str:
        """
        Inserisce un singolo documento

        Returns:
            ID del documento inserito
        """
        try:
            response = self.client.index(
                index=index_name,
                body=document,
                id=doc_id,
                refresh=True  # Rende il documento immediatamente ricercabile
            )
            print(f"✓ Documento inserito: {response['_id']}")
            return response['_id']
        except Exception as e:
            print(f"✗ Errore inserimento documento: {e}")
            return None

    def bulk_index_documents(self, index_name: str,
                             documents: List[Dict]) -> Dict:
        """
        Inserimento bulk di documenti (molto più veloce)

        Returns:
            Dict con statistiche dell'operazione
        """
        try:
            # Prepara i documenti per bulk insert
            actions = [
                {
                    '_index': index_name,
                    '_source': doc
                }
                for doc in documents
            ]

            # Esegui bulk insert
            success, failed = helpers.bulk(
                self.client,
                actions,
                raise_on_error=False,
                refresh=True
            )

            print(f"✓ Bulk insert: {success} successi, {len(failed)} fallimenti")
            return {
                'success': success,
                'failed': len(failed),
                'errors': failed
            }
        except Exception as e:
            print(f"✗ Errore bulk insert: {e}")
            return {'success': 0, 'failed': len(documents), 'errors': [str(e)]}

    # ========== RICERCA DOCUMENTI ==========

    def search(self, index_name: str, query: Dict,
               size: int = 10, from_: int = 0) -> Dict:
        """
        Esegue una ricerca con Query DSL

        Args:
            index_name: nome dell'indice
            query: query in formato Query DSL
            size: numero di risultati da restituire
            from_: offset per paginazione
        """
        try:
            response = self.client.search(
                index=index_name,
                body={
                    'query': query,
                    'size': size,
                    'from': from_
                }
            )

            hits = response['hits']
            print(f"✓ Trovati {hits['total']['value']} documenti")

            return {
                'total': hits['total']['value'],
                'documents': [hit['_source'] for hit in hits['hits']],
                'ids': [hit['_id'] for hit in hits['hits']],
                'scores': [hit['_score'] for hit in hits['hits']]
            }
        except Exception as e:
            print(f"✗ Errore ricerca: {e}")
            return {'total': 0, 'documents': [], 'ids': [], 'scores': []}

    def simple_search(self, index_name: str, field: str,
                      value: str, size: int = 10) -> List[Dict]:
        """Ricerca semplice su un campo"""
        query = {
            'match': {
                field: value
            }
        }
        result = self.search(index_name, query, size)
        return result['documents']

    def multi_match_search(self, index_name: str, query_text: str,
                           fields: List[str], size: int = 10) -> List[Dict]:
        """Ricerca su più campi"""
        query = {
            'multi_match': {
                'query': query_text,
                'fields': fields
            }
        }
        result = self.search(index_name, query, size)
        return result['documents']

    def range_search(self, index_name: str, field: str,
                     gte=None, lte=None, size: int = 10) -> List[Dict]:
        """Ricerca per range (numeri o date)"""
        range_query = {}
        if gte is not None:
            range_query['gte'] = gte
        if lte is not None:
            range_query['lte'] = lte

        query = {
            'range': {
                field: range_query
            }
        }
        result = self.search(index_name, query, size)
        return result['documents']

    def bool_search(self, index_name: str, must: List[Dict] = None,
                    should: List[Dict] = None, must_not: List[Dict] = None,
                    filter_: List[Dict] = None, size: int = 10) -> List[Dict]:
        """Ricerca booleana complessa"""
        bool_query = {}
        if must:
            bool_query['must'] = must
        if should:
            bool_query['should'] = should
        if must_not:
            bool_query['must_not'] = must_not
        if filter_:
            bool_query['filter'] = filter_

        query = {'bool': bool_query}
        result = self.search(index_name, query, size)
        return result['documents']

    # ========== AGGREGAZIONI ==========

    def aggregate(self, index_name: str, query: Dict,
                  aggregations: Dict) -> Dict:
        """
        Esegue aggregazioni

        Args:
            query: query per filtrare i documenti
            aggregations: definizione delle aggregazioni
        """
        try:
            response = self.client.search(
                index=index_name,
                body={
                    'query': query,
                    'size': 0,  # Non restituire documenti, solo aggregazioni
                    'aggs': aggregations
                }
            )

            print(f"✓ Aggregazioni completate")
            return response['aggregations']
        except Exception as e:
            print(f"✗ Errore aggregazioni: {e}")
            return {}

    def terms_aggregation(self, index_name: str, field: str,
                          size: int = 10) -> Dict:
        """Aggregazione per termini (simile a GROUP BY)"""
        aggs = {
            'group_by_field': {
                'terms': {
                    'field': field,
                    'size': size
                }
            }
        }
        return self.aggregate(index_name, {'match_all': {}}, aggs)

    def stats_aggregation(self, index_name: str, field: str) -> Dict:
        """Statistiche su un campo numerico"""
        aggs = {
            'field_stats': {
                'stats': {
                    'field': field
                }
            }
        }
        return self.aggregate(index_name, {'match_all': {}}, aggs)

    def date_histogram(self, index_name: str, date_field: str,
                       interval: str = '1d') -> Dict:
        """Istogramma temporale"""
        aggs = {
            'over_time': {
                'date_histogram': {
                    'field': date_field,
                    'fixed_interval': interval
                }
            }
        }
        return self.aggregate(index_name, {'match_all': {}}, aggs)

    # ========== UPDATE E DELETE ==========

    def update_document(self, index_name: str, doc_id: str,
                        updates: Dict) -> bool:
        """Aggiorna un documento esistente"""
        try:
            response = self.client.update(
                index=index_name,
                id=doc_id,
                body={'doc': updates},
                refresh=True
            )
            print(f"✓ Documento {doc_id} aggiornato")
            return True
        except Exception as e:
            print(f"✗ Errore aggiornamento: {e}")
            return False

    def delete_document(self, index_name: str, doc_id: str) -> bool:
        """Elimina un documento"""
        try:
            self.client.delete(
                index=index_name,
                id=doc_id,
                refresh=True
            )
            print(f"✓ Documento {doc_id} eliminato")
            return True
        except Exception as e:
            print(f"✗ Errore eliminazione: {e}")
            return False

    def delete_by_query(self, index_name: str, query: Dict) -> int:
        """Elimina documenti che matchano una query"""
        try:
            response = self.client.delete_by_query(
                index=index_name,
                body={'query': query},
                refresh=True
            )
            deleted = response['deleted']
            print(f"✓ {deleted} documenti eliminati")
            return deleted
        except Exception as e:
            print(f"✗ Errore delete by query: {e}")
            return 0

    # ========== UTILITÀ ==========

    def count_documents(self, index_name: str, query: Dict = None) -> int:
        """Conta i documenti in un indice"""
        try:
            body = {'query': query} if query else None
            response = self.client.count(index=index_name, body=body)
            count = response['count']
            print(f"✓ Conteggio: {count} documenti")
            return count
        except Exception as e:
            print(f"✗ Errore conteggio: {e}")
            return 0

    def get_document(self, index_name: str, doc_id: str) -> Dict:
        """Ottieni un documento per ID"""
        try:
            response = self.client.get(index=index_name, id=doc_id)
            return response['_source']
        except Exception as e:
            print(f"✗ Errore get documento: {e}")
            return {}


# ========== ESEMPI DI UTILIZZO ==========

def esempio_completo():
    """
    Esempio completo con caso d'uso reale: E-commerce Product Catalog
    """
    print("\n" + "=" * 60)
    print("ESEMPIO COMPLETO: E-Commerce Product Catalog")
    print("=" * 60 + "\n")

    # 1. CONNESSIONE
    print("1. Connessione a OpenSearch...")
    os_manager = OpenSearchManager(
        host='localhost',
        port=9200,
        auth=('admin', 'admin'),
        use_ssl=False
    )

    # 2. CREAZIONE INDICE
    print("\n2. Creazione indice 'products'...")

    mappings = {
        'properties': {
            'name': {
                'type': 'text',
                'fields': {
                    'keyword': {'type': 'keyword'}
                }
            },
            'description': {'type': 'text'},
            'category': {'type': 'keyword'},
            'price': {'type': 'float'},
            'stock': {'type': 'integer'},
            'rating': {'type': 'float'},
            'tags': {'type': 'keyword'},
            'created_at': {'type': 'date'},
            'is_available': {'type': 'boolean'}
        }
    }

    settings = {
        'number_of_shards': 1,
        'number_of_replicas': 0
    }

    # Elimina se esiste già
    os_manager.delete_index('products')
    os_manager.create_index('products', mappings, settings)

    # 3. INSERIMENTO DATI
    print("\n3. Inserimento prodotti...")

    # Prodotti di esempio
    products = [
        {
            'name': 'Laptop Dell XPS 15',
            'description': 'Potente laptop per professionisti con schermo 4K',
            'category': 'electronics',
            'price': 1899.99,
            'stock': 15,
            'rating': 4.7,
            'tags': ['laptop', 'dell', 'premium', '4k'],
            'created_at': datetime.now().isoformat(),
            'is_available': True
        },
        {
            'name': 'iPhone 15 Pro',
            'description': 'Ultimo modello di iPhone con chip A17 Pro',
            'category': 'electronics',
            'price': 1199.99,
            'stock': 30,
            'rating': 4.8,
            'tags': ['smartphone', 'apple', 'premium'],
            'created_at': datetime.now().isoformat(),
            'is_available': True
        },
        {
            'name': 'Nike Air Max 2024',
            'description': 'Scarpe sportive con tecnologia Air Max',
            'category': 'clothing',
            'price': 159.99,
            'stock': 50,
            'rating': 4.5,
            'tags': ['shoes', 'nike', 'sport'],
            'created_at': datetime.now().isoformat(),
            'is_available': True
        },
        {
            'name': 'Sony WH-1000XM5',
            'description': 'Cuffie wireless con cancellazione del rumore',
            'category': 'electronics',
            'price': 399.99,
            'stock': 25,
            'rating': 4.9,
            'tags': ['headphones', 'sony', 'wireless', 'noise-cancelling'],
            'created_at': datetime.now().isoformat(),
            'is_available': True
        },
        {
            'name': 'Samsung 4K TV 55"',
            'description': 'Smart TV 4K con HDR e Quantum Dot',
            'category': 'electronics',
            'price': 899.99,
            'stock': 10,
            'rating': 4.6,
            'tags': ['tv', 'samsung', '4k', 'smart-tv'],
            'created_at': datetime.now().isoformat(),
            'is_available': True
        },
        {
            'name': 'Adidas Ultraboost',
            'description': 'Scarpe da corsa ad alte prestazioni',
            'category': 'clothing',
            'price': 179.99,
            'stock': 0,  # Esaurito
            'rating': 4.7,
            'tags': ['shoes', 'adidas', 'running'],
            'created_at': (datetime.now() - timedelta(days=30)).isoformat(),
            'is_available': False
        }
    ]

    # Inserimento bulk
    os_manager.bulk_index_documents('products', products)

    # 4. RICERCHE
    print("\n4. Esempi di ricerca...")

    # 4.1 Ricerca full-text
    print("\n  4.1 Ricerca full-text: 'laptop'")
    results = os_manager.simple_search('products', 'description', 'laptop', size=5)
    for doc in results:
        print(f"    - {doc['name']}: ${doc['price']}")

    # 4.2 Ricerca multi-campo
    print("\n  4.2 Multi-match: 'wireless noise'")
    results = os_manager.multi_match_search(
        'products',
        'wireless noise',
        ['name', 'description', 'tags'],
        size=5
    )
    for doc in results:
        print(f"    - {doc['name']}: ${doc['price']}")

    # 4.3 Ricerca per range di prezzo
    print("\n  4.3 Prodotti tra $100 e $500")
    results = os_manager.range_search(
        'products',
        'price',
        gte=100,
        lte=500,
        size=10
    )
    for doc in results:
        print(f"    - {doc['name']}: ${doc['price']}")

    # 4.4 Ricerca booleana complessa
    print("\n  4.4 Electronics disponibili con rating > 4.5")
    results = os_manager.bool_search(
        'products',
        must=[
            {'term': {'category': 'electronics'}},
            {'term': {'is_available': True}}
        ],
        filter_=[
            {'range': {'rating': {'gte': 4.5}}}
        ],
        size=10
    )
    for doc in results:
        print(f"    - {doc['name']}: ${doc['price']} (⭐ {doc['rating']})")

    # 5. AGGREGAZIONI
    print("\n5. Aggregazioni...")

    # 5.1 Prodotti per categoria
    print("\n  5.1 Conteggio per categoria:")
    aggs = os_manager.terms_aggregation('products', 'category.keyword')
    for bucket in aggs['group_by_field']['buckets']:
        print(f"    - {bucket['key']}: {bucket['doc_count']} prodotti")

    # 5.2 Statistiche prezzi
    print("\n  5.2 Statistiche prezzi:")
    stats = os_manager.stats_aggregation('products', 'price')
    price_stats = stats['field_stats']
    print(f"    - Media: ${price_stats['avg']:.2f}")
    print(f"    - Min: ${price_stats['min']:.2f}")
    print(f"    - Max: ${price_stats['max']:.2f}")

    # 5.3 Aggregazione complessa: media prezzi per categoria
    print("\n  5.3 Prezzo medio per categoria:")
    aggs_def = {
        'by_category': {
            'terms': {
                'field': 'category.keyword'
            },
            'aggs': {
                'avg_price': {
                    'avg': {'field': 'price'}
                },
                'max_rating': {
                    'max': {'field': 'rating'}
                }
            }
        }
    }
    result = os_manager.aggregate('products', {'match_all': {}}, aggs_def)
    for bucket in result['by_category']['buckets']:
        print(f"    - {bucket['key']}:")
        print(f"        Prezzo medio: ${bucket['avg_price']['value']:.2f}")
        print(f"        Rating max: {bucket['max_rating']['value']}")

    # 6. UPDATE
    print("\n6. Aggiornamento documento...")
    # Trova un prodotto e aggiorna il prezzo
    search_results = os_manager.search(
        'products',
        {'match': {'name': 'iPhone'}},
        size=1
    )
    if search_results['ids']:
        doc_id = search_results['ids'][0]
        os_manager.update_document(
            'products',
            doc_id,
            {'price': 1099.99, 'stock': 35}
        )

    # 7. COUNT
    print("\n7. Conteggi...")
    total = os_manager.count_documents('products')
    available = os_manager.count_documents(
        'products',
        {'term': {'is_available': True}}
    )
    print(f"  Totale prodotti: {total}")
    print(f"  Prodotti disponibili: {available}")

    # 8. DELETE BY QUERY
    print("\n8. Eliminazione prodotti esauriti...")
    deleted = os_manager.delete_by_query(
        'products',
        {'term': {'is_available': False}}
    )

    print("\n" + "=" * 60)
    print("ESEMPIO COMPLETATO!")
    print("=" * 60)


def esempio_log_analysis():
    """
    Esempio per analisi log (come nel case study precedente)
    """
    print("\n" + "=" * 60)
    print("ESEMPIO: Log Analysis")
    print("=" * 60 + "\n")

    os_manager = OpenSearchManager()

    # Crea indice per log
    mappings = {
        'properties': {
            'timestamp': {'type': 'date'},
            'level': {'type': 'keyword'},
            'service': {'type': 'keyword'},
            'message': {'type': 'text'},
            'response_time_ms': {'type': 'integer'},
            'status_code': {'type': 'integer'}
        }
    }

    os_manager.delete_index('app-logs')
    os_manager.create_index('app-logs', mappings)

    # Genera log di esempio
    services = ['api', 'frontend', 'database']
    levels = ['INFO', 'WARN', 'ERROR']

    logs = []
    for i in range(100):
        logs.append({
            'timestamp': (datetime.now() - timedelta(minutes=random.randint(0, 60))).isoformat(),
            'level': random.choices(levels, weights=[70, 20, 10])[0],
            'service': random.choice(services),
            'message': f'Processing request {i}',
            'response_time_ms': random.randint(50, 2000),
            'status_code': random.choices([200, 400, 500], weights=[80, 15, 5])[0]
        })

    os_manager.bulk_index_documents('app-logs', logs)

    # Query di esempio
    print("\n1. Errori nelle ultime 24 ore:")
    errors = os_manager.bool_search(
        'app-logs',
        must=[
            {'term': {'level': 'ERROR'}}
        ],
        filter_=[
            {'range': {'timestamp': {'gte': 'now-24h'}}}
        ]
    )
    print(f"   Trovati {len(errors)} errori")

    print("\n2. Richieste lente (>1000ms):")
    slow = os_manager.range_search('app-logs', 'response_time_ms', gte=1000)
    print(f"   Trovate {len(slow)} richieste lente")

    print("\n3. Errori per servizio:")
    aggs = os_manager.aggregate(
        'app-logs',
        {'term': {'level': 'ERROR'}},
        {
            'by_service': {
                'terms': {'field': 'service'}
            }
        }
    )
    for bucket in aggs['by_service']['buckets']:
        print(f"   - {bucket['key']}: {bucket['doc_count']}")


if __name__ == "__main__":
    # Esegui gli esempi
    esempio_completo()

    # Decommentare per eseguire esempio log analysis
    # esempio_log_analysis()