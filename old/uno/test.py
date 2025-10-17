"""
OpenSearch Debug Script - Scopri i valori REALI dei tuoi dati
"""

from opensearchpy import OpenSearch
import json


def debug_opensearch():
    """Debug per trovare i valori reali"""

    client = OpenSearch(
        hosts=[{'host': 'localhost', 'port': 9200}],
        http_auth=('admin', 'admin'),
        use_ssl=False,
        verify_certs=False,
        ssl_show_warn=False
    )

    try:
        info = client.info()
        print(f"✓ OpenSearch connesso: {info['version']['number']}\n")
    except Exception as e:
        print(f"✗ Errore: {e}")
        return

    index_name = 'iam-richieste'

    # ========== 1. CONTA TOTALI ==========
    print("=" * 70)
    print("1. CONTEGGIO TOTALE RECORD")
    print("=" * 70)

    response = client.count(index=index_name)
    print(f"Totale record in '{index_name}': {response['count']}\n")

    # ========== 2. LEGGI PRIMO RECORD ==========
    print("=" * 70)
    print("2. PRIMO RECORD (per vedere la struttura)")
    print("=" * 70)

    response = client.search(index=index_name, body={'size': 1})
    if response['hits']['hits']:
        primo = response['hits']['hits'][0]['_source']
        print(json.dumps(primo, indent=2, default=str))
        print()

    # ========== 3. VALORI UNICI DI FK_NOME_OPERAZIONE ==========
    print("=" * 70)
    print("3. VALORI UNICI DI FK_NOME_OPERAZIONE")
    print("=" * 70)

    response = client.search(
        index=index_name,
        body={
            'size': 0,
            'aggs': {
                'operazioni': {
                    'terms': {'field': 'FK_NOME_OPERAZIONE', 'size': 100}
                }
            }
        }
    )

    if response['aggregations']['operazioni']['buckets']:
        print("Operazioni trovate:\n")
        for bucket in response['aggregations']['operazioni']['buckets']:
            print(f"  • '{bucket['key']}' = {bucket['doc_count']} record")
    else:
        print("  ⚠ Nessun valore trovato con FK_NOME_OPERAZIONE")

    print()

    # ========== 4. VALORI UNICI DI STATO ==========
    print("=" * 70)
    print("4. VALORI UNICI DI STATO")
    print("=" * 70)

    response = client.search(
        index=index_name,
        body={
            'size': 0,
            'aggs': {
                'stati': {
                    'terms': {'field': 'STATO', 'size': 100}
                }
            }
        }
    )

    if response['aggregations']['stati']['buckets']:
        print("Stati trovati:\n")
        for bucket in response['aggregations']['stati']['buckets']:
            print(f"  • '{bucket['key']}' = {bucket['doc_count']} record")
    else:
        print("  ⚠ Nessun valore trovato con STATO")

    print()

    # ========== 5. COMBINAZIONE FK_NOME_OPERAZIONE + STATO ==========
    print("=" * 70)
    print("5. COMBINAZIONI FK_NOME_OPERAZIONE + STATO")
    print("=" * 70)

    response = client.search(
        index=index_name,
        body={
            'size': 0,
            'aggs': {
                'per_operazione': {
                    'terms': {'field': 'FK_NOME_OPERAZIONE', 'size': 100},
                    'aggs': {
                        'per_stato': {
                            'terms': {'field': 'STATO', 'size': 100}
                        }
                    }
                }
            }
        }
    )

    print("Combinazioni trovate:\n")
    for op_bucket in response['aggregations']['per_operazione']['buckets']:
        operazione = op_bucket['key']
        print(f"  FK_NOME_OPERAZIONE = '{operazione}'")
        for stato_bucket in op_bucket['per_stato']['buckets']:
            stato = stato_bucket['key']
            count = stato_bucket['doc_count']
            print(f"    └─ STATO = '{stato}' ({count} record)")

    print()

    # ========== 6. CERCA SPECIFICAMENTE RESET_PASSWORD_ACCOUNT ==========
    print("=" * 70)
    print("6. RICERCA DIRETTA: RESET_PASSWORD_ACCOUNT + EVASA")
    print("=" * 70)

    response = client.search(
        index=index_name,
        body={
            'query': {
                'bool': {
                    'must': [
                        {'match': {'FK_NOME_OPERAZIONE': 'RESET_PASSWORD_ACCOUNT'}},
                        {'match': {'STATO': 'EVASA'}}
                    ]
                }
            },
            'size': 1
        }
    )

    count_match = response['hits']['total']['value']
    print(f"Record trovati con MATCH: {count_match}")

    if count_match > 0:
        record = response['hits']['hits'][0]['_source']
        print(f"  FK_NOME_OPERAZIONE: '{record.get('FK_NOME_OPERAZIONE')}'")
        print(f"  STATO: '{record.get('STATO')}'")
        print(f"  DATA_CREAZIONE: {record.get('DATA_CREAZIONE')}")
        print(f"  DATA_CHIUSURA: {record.get('DATA_CHIUSURA')}")
        print(f"  ore_elaborazione: {record.get('ore_elaborazione')}")

    print()

    # ========== 7. PROVA CON TERM QUERY ==========
    print("=" * 70)
    print("7. RICERCA CON TERM (esatta)")
    print("=" * 70)

    response = client.search(
        index=index_name,
        body={
            'query': {
                'bool': {
                    'must': [
                        {'term': {'FK_NOME_OPERAZIONE.keyword': 'RESET_PASSWORD_ACCOUNT'}},
                        {'term': {'STATO.keyword': 'EVASA'}}
                    ]
                }
            },
            'size': 1
        }
    )

    count_term = response['hits']['total']['value']
    print(f"Record trovati con TERM .keyword: {count_term}")

    if count_term > 0:
        print("  ✅ I filtri .keyword funzionano!")
    else:
        print("  ⚠️  I filtri .keyword NON trovano nulla")
        print("     Proverò altre varianti...")

    print()

    # ========== 8. STATISTICHE ore_elaborazione ==========
    print("=" * 70)
    print("8. STATISTICHE ore_elaborazione")
    print("=" * 70)

    response = client.search(
        index=index_name,
        body={
            'size': 0,
            'aggs': {
                'stats': {
                    'stats': {'field': 'ore_elaborazione'}
                }
            }
        }
    )

    stats = response['aggregations']['stats']
    print(f"Conteggio: {stats['count']}")
    print(f"Media: {stats.get('avg', 0):.2f} ore")
    print(f"Min: {stats.get('min', 0):.2f} ore")
    print(f"Max: {stats.get('max', 0):.2f} ore")
    print(f"Sum: {stats.get('sum', 0):.2f} ore")

    if stats['count'] == 0:
        print("\n  ⚠️  ore_elaborazione NON CALCOLATO!")
        print("     Devi ricalcolare il campo ore_elaborazione!")

    print()

    # ========== 9. MAPPINGS ==========
    print("=" * 70)
    print("9. MAPPINGS DELL'INDICE")
    print("=" * 70)

    mappings = client.indices.get_mapping(index=index_name)
    props = mappings[index_name]['mappings']['properties']

    print("Campi principali:\n")
    for field_name in ['FK_NOME_OPERAZIONE', 'STATO', 'DATA_CREAZIONE',
                       'DATA_CHIUSURA', 'ore_elaborazione']:
        if field_name in props:
            field_type = props[field_name].get('type', 'unknown')
            print(f"  {field_name}: {field_type}")
            if 'fields' in props[field_name]:
                print(f"    Sub-fields: {list(props[field_name]['fields'].keys())}")
        else:
            print(f"  {field_name}: ⚠️  NON ESISTE!")

    print()


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("OPENSEARCH DEBUG - FIND YOUR REAL DATA")
    print("=" * 70 + "\n")

    debug_opensearch()