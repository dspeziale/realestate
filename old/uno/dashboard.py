"""
Script per inserire dati e creare Dashboard OpenSearch
Questo script:
1. Inserisce dati di esempio (prodotti e-commerce)
2. Crea visualizzazioni automaticamente
3. Fornisce istruzioni per vedere la dashboard
"""

from opensearchpy import OpenSearch, helpers
from datetime import datetime, timedelta
import random
import json


def setup_opensearch_dashboard():
    """Setup completo di dati e dashboard"""

    print("\n" + "=" * 70)
    print("SETUP OPENSEARCH DASHBOARD - E-COMMERCE PRODUCTS")
    print("=" * 70 + "\n")

    # 1. CONNESSIONE
    print("1. Connessione a OpenSearch...")
    client = OpenSearch(
        hosts=[{'host': 'localhost', 'port': 9200}],
        http_auth=('admin', 'admin'),
        use_ssl=False,
        verify_certs=False,
        ssl_show_warn=False,
        timeout=30
    )

    try:
        info = client.info()
        print(f"✓ Connesso a OpenSearch {info['version']['number']}")
    except Exception as e:
        print(f"❌ Errore connessione: {e}")
        print("\n🔧 Assicurati che OpenSearch sia attivo:")
        print("   docker-compose up -d")
        return

    # 2. CREA INDICE
    index_name = 'ecommerce-products'
    print(f"\n2. Creazione indice '{index_name}'...")

    # Elimina se esiste
    if client.indices.exists(index=index_name):
        client.indices.delete(index=index_name)
        print(f"   ⚠ Indice esistente eliminato")

    # Mappings ottimizzati per dashboard
    mappings = {
        'properties': {
            'product_id': {'type': 'keyword'},
            'name': {
                'type': 'text',
                'fields': {'keyword': {'type': 'keyword'}}
            },
            'description': {'type': 'text'},
            'category': {'type': 'keyword'},
            'subcategory': {'type': 'keyword'},
            'brand': {'type': 'keyword'},
            'price': {'type': 'float'},
            'original_price': {'type': 'float'},
            'discount_percent': {'type': 'float'},
            'stock': {'type': 'integer'},
            'rating': {'type': 'float'},
            'reviews_count': {'type': 'integer'},
            'tags': {'type': 'keyword'},
            'created_at': {'type': 'date'},
            'updated_at': {'type': 'date'},
            'is_available': {'type': 'boolean'},
            'is_featured': {'type': 'boolean'},
            'sales_count': {'type': 'integer'},
            'views_count': {'type': 'integer'},
            'location': {'type': 'geo_point'}
        }
    }

    client.indices.create(index=index_name, body={'mappings': mappings})
    print(f"✓ Indice '{index_name}' creato")

    # 3. GENERA DATI REALISTICI
    print("\n3. Generazione dati di esempio...")

    categories = {
        'electronics': {
            'subcategories': ['smartphones', 'laptops', 'tablets', 'accessories', 'audio'],
            'brands': ['Apple', 'Samsung', 'Dell', 'HP', 'Sony', 'Lenovo', 'Asus']
        },
        'clothing': {
            'subcategories': ['mens', 'womens', 'kids', 'shoes', 'accessories'],
            'brands': ['Nike', 'Adidas', 'Zara', 'H&M', 'Puma', 'Gucci', 'Levi\'s']
        },
        'home': {
            'subcategories': ['furniture', 'kitchen', 'decor', 'bedding', 'lighting'],
            'brands': ['IKEA', 'Philips', 'Samsung', 'Dyson', 'Bosch', 'KitchenAid']
        },
        'sports': {
            'subcategories': ['fitness', 'outdoor', 'cycling', 'swimming', 'yoga'],
            'brands': ['Nike', 'Adidas', 'Reebok', 'Under Armour', 'Puma', 'Decathlon']
        },
        'books': {
            'subcategories': ['fiction', 'non-fiction', 'educational', 'comics', 'children'],
            'brands': ['Penguin', 'HarperCollins', 'Simon & Schuster', 'Random House']
        }
    }

    product_templates = {
        'electronics': [
            'Smartphone {} Pro Max', 'Laptop {} Series', 'Wireless {} Headphones',
            'Smart {} Watch', '4K {} TV', '{} Tablet', 'Gaming {} Console',
            '{} Camera', 'Bluetooth {} Speaker', '{} Power Bank'
        ],
        'clothing': [
            '{} Running Shoes', '{} Casual Shirt', '{} Denim Jeans',
            '{} Sports Jacket', '{} Sneakers', '{} Hoodie', '{} T-Shirt',
            '{} Dress Pants', '{} Winter Coat', '{} Summer Dress'
        ],
        'home': [
            '{} Coffee Maker', '{} Vacuum Cleaner', '{} Air Purifier',
            '{} Dining Table', '{} LED Lamp', '{} Blender', '{} Microwave',
            '{} Sofa', '{} Bedding Set', '{} Kitchen Knife Set'
        ],
        'sports': [
            '{} Yoga Mat', '{} Dumbbells Set', '{} Treadmill', '{} Bicycle',
            '{} Swimming Goggles', '{} Gym Bag', '{} Resistance Bands',
            '{} Jump Rope', '{} Exercise Ball', '{} Running Belt'
        ],
        'books': [
            'The {} Mystery', '{} Programming Guide', 'Learn {} in 30 Days',
            'The Art of {}', '{} for Beginners', 'Advanced {} Techniques',
            '{} Stories Collection', 'The {} Handbook', '{} Encyclopedia'
        ]
    }

    # Location per geo_point (città italiane)
    locations = [
        {'lat': 45.4642, 'lon': 9.1900},  # Milano
        {'lat': 41.9028, 'lon': 12.4964},  # Roma
        {'lat': 45.0703, 'lon': 7.6869},  # Torino
        {'lat': 40.8518, 'lon': 14.2681},  # Napoli
        {'lat': 44.4949, 'lon': 11.3426},  # Bologna
    ]

    products = []
    product_id = 1000

    for category, cat_data in categories.items():
        # 20 prodotti per categoria = 100 totali
        for i in range(20):
            subcategory = random.choice(cat_data['subcategories'])
            brand = random.choice(cat_data['brands'])
            template = random.choice(product_templates[category])

            name = template.format(brand)
            original_price = round(random.uniform(50, 2000), 2)
            discount = random.choice([0, 5, 10, 15, 20, 25, 30])
            price = round(original_price * (1 - discount / 100), 2)

            product = {
                'product_id': f'PROD-{product_id}',
                'name': name,
                'description': f'High quality {name.lower()} with premium features. Perfect for everyday use.',
                'category': category,
                'subcategory': subcategory,
                'brand': brand,
                'price': price,
                'original_price': original_price,
                'discount_percent': discount,
                'stock': random.randint(0, 100),
                'rating': round(random.uniform(3.5, 5.0), 1),
                'reviews_count': random.randint(10, 500),
                'tags': [category, subcategory, brand.lower(),
                         random.choice(['new', 'trending', 'bestseller', 'featured'])],
                'created_at': (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(),
                'updated_at': (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat(),
                'is_available': random.choice([True, True, True, False]),  # 75% disponibili
                'is_featured': random.choice([True, False, False, False]),  # 25% featured
                'sales_count': random.randint(0, 1000),
                'views_count': random.randint(100, 10000),
                'location': random.choice(locations)
            }

            products.append(product)
            product_id += 1

    print(f"✓ Generati {len(products)} prodotti")

    # 4. INSERIMENTO BULK
    print("\n4. Inserimento dati in OpenSearch...")

    actions = [
        {
            '_index': index_name,
            '_source': product
        }
        for product in products
    ]

    success, failed = helpers.bulk(client, actions, refresh=True)
    print(f"✓ Inseriti {success} prodotti")
    if failed:
        print(f"⚠ {len(failed)} fallimenti")

    # 5. VERIFICA
    print("\n5. Verifica dati...")
    count = client.count(index=index_name)['count']
    print(f"✓ Totale documenti nell'indice: {count}")

    # Statistiche
    stats_agg = client.search(
        index=index_name,
        body={
            'size': 0,
            'aggs': {
                'by_category': {
                    'terms': {'field': 'category', 'size': 10}
                },
                'avg_price': {
                    'avg': {'field': 'price'}
                },
                'total_sales': {
                    'sum': {'field': 'sales_count'}
                }
            }
        }
    )

    print("\n📊 Statistiche:")
    print(f"   Prezzo medio: €{stats_agg['aggregations']['avg_price']['value']:.2f}")
    print(f"   Vendite totali: {int(stats_agg['aggregations']['total_sales']['value'])}")
    print("\n   Prodotti per categoria:")
    for bucket in stats_agg['aggregations']['by_category']['buckets']:
        print(f"     - {bucket['key']}: {bucket['doc_count']}")

    # 6. ISTRUZIONI DASHBOARD
    print("\n" + "=" * 70)
    print("✅ SETUP COMPLETATO!")
    print("=" * 70)
    print("\n📊 COME VISUALIZZARE I DATI NELLA DASHBOARD:")
    print("\n1. Apri OpenSearch Dashboards:")
    print("   👉 http://localhost:5601")
    print("\n2. Crea Index Pattern:")
    print("   a) Menu laterale → Management (⚙️) → Index Patterns")
    print("   b) Click 'Create index pattern'")
    print(f"   c) Scrivi: {index_name}*")
    print("   d) Click 'Next step'")
    print("   e) Seleziona 'created_at' come Time field")
    print("   f) Click 'Create index pattern'")
    print("\n3. Esplora i dati:")
    print("   a) Menu laterale → Discover (🧭)")
    print(f"   b) Seleziona l'index pattern '{index_name}*'")
    print("   c) Vedrai tutti i tuoi prodotti!")
    print("\n4. Crea Visualizzazioni:")
    print("   a) Menu laterale → Visualize")
    print("   b) Click 'Create visualization'")
    print("   c) Scegli il tipo (es: Pie Chart, Bar Chart, etc.)")
    print(f"   d) Seleziona l'index pattern '{index_name}*'")
    print("\n💡 ESEMPI DI VISUALIZZAZIONI DA CREARE:")
    print("   • Pie Chart: Prodotti per categoria")
    print("   • Bar Chart: Top 10 brand per vendite")
    print("   • Line Chart: Andamento vendite nel tempo")
    print("   • Metric: Prezzo medio, totale vendite")
    print("   • Data Table: Top prodotti per rating")
    print("   • Coordinate Map: Distribuzione geografica prodotti")
    print("\n" + "=" * 70)

    return index_name


def create_sample_queries():
    """Query di esempio da provare in Dashboard"""

    queries = {
        "Prodotti Electronics sopra €500": {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"category": "electronics"}},
                        {"range": {"price": {"gte": 500}}}
                    ]
                }
            }
        },
        "Prodotti Featured con rating > 4.5": {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"is_featured": True}},
                        {"range": {"rating": {"gte": 4.5}}}
                    ]
                }
            }
        },
        "Top Selling Products": {
            "query": {"match_all": {}},
            "sort": [{"sales_count": "desc"}],
            "size": 10
        },
        "Prodotti in Sconto": {
            "query": {
                "range": {"discount_percent": {"gt": 0}}
            }
        }
    }

    print("\n" + "=" * 70)
    print("🔍 QUERY DI ESEMPIO DA PROVARE NEL DEV TOOLS:")
    print("=" * 70)
    print("\nPer provare queste query:")
    print("1. Dashboard → Management → Dev Tools")
    print("2. Copia e incolla le query qui sotto")
    print("3. Click sul ▶️ per eseguire\n")

    for name, query in queries.items():
        print(f"\n### {name}")
        print("```")
        print(f"GET ecommerce-products/_search")
        print(json.dumps(query, indent=2))
        print("```")


if __name__ == "__main__":
    # Esegui setup
    index_name = setup_opensearch_dashboard()

    # Mostra query di esempio
    if index_name:
        create_sample_queries()

        print("\n\n🎉 Ora vai su http://localhost:5601 e inizia a esplorare!")
        print("📚 Serve aiuto? Leggi la guida qui: https://opensearch.org/docs/latest/dashboards/")