"""
OpenSearch IAM KPI Calculator - Reset Operations
================================================

Calcola KPI specifici per operazioni di reset:
- 80% completate in 1 giorno
- 100% completate in 2 giorni

Basato sulla tabella IAM.STORICO_RICHIESTE
"""

from opensearchpy import OpenSearch
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json


class IamResetKpiCalculator:
    """Calcola KPI per operazioni di reset"""

    def __init__(self, os_host='localhost', os_port=9200):
        """Inizializza connessione a OpenSearch"""
        self.client = OpenSearch(
            hosts=[{'host': os_host, 'port': os_port}],
            http_auth=('admin', 'admin'),
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30,
            max_retries=3
        )

        try:
            info = self.client.info()
            print(f"✓ OpenSearch connesso: {info['version']['number']}\n")
        except Exception as e:
            print(f"✗ Errore connessione: {e}")
            raise

    def calcola_kpi_reset(self, index_name='iam-richieste',
                         nome_operazione='RESET', stato_completato='COMPLETATA'):
        """
        Calcola KPI per operazioni di reset
        - 80% completate entro 1 giorno
        - 100% completate entro 2 giorni

        Args:
            index_name: nome indice OpenSearch
            nome_operazione: nome dell'operazione (es: 'RESET', 'PASSWORD_RESET')
            stato_completato: stato che indica completamento (es: 'COMPLETATA', 'CHIUSA')
        """
        print("=" * 70)
        print(f"KPI - OPERAZIONI DI {nome_operazione}")
        print("=" * 70 + "\n")

        # Query per tutte le operazioni di reset completate
        query_body = {
            'query': {
                'bool': {
                    'must': [
                        {'match': {'STATO': stato_completato}},
                        {'match': {'FK_NOME_OPERAZIONE': nome_operazione}},
                        {'exists': {'field': 'DATA_CREAZIONE'}},
                        {'exists': {'field': 'DATA_CHIUSURA'}}
                    ]
                }
            },
            'size': 10000,
            '_source': ['ID_RICHIESTA', 'DATA_CREAZIONE', 'DATA_CHIUSURA',
                       'FK_UTENTE', 'FK_TIPO_RICHIESTA', 'STATO', 'NOME_UTENZA',
                       'FK_UTENTE_RICHIEDENTE', 'NOTA']
        }

        response = self.client.search(index=index_name, body=query_body)
        resets = response['hits']['hits']
        total_reset = len(resets)

        if total_reset == 0:
            print(f"⚠ Nessuna operazione di {nome_operazione} trovata con stato {stato_completato}")
            return {}

        print(f"Totale operazioni di {nome_operazione} completate: {total_reset}\n")

        # Calcola tempi di elaborazione
        entro_1gg = 0
        entro_2gg = 0
        sopra_2gg = 0
        ore_totali = 0

        reset_details = []
        reset_ritardatari = []

        for hit in resets:
            doc = hit['_source']

            try:
                # Estrai date
                data_creazione = datetime.fromisoformat(doc['DATA_CREAZIONE'])
                data_chiusura = datetime.fromisoformat(doc['DATA_CHIUSURA'])

                # Calcola differenza
                differenza = data_chiusura - data_creazione
                ore = differenza.total_seconds() / 3600
                giorni = differenza.days

            except (KeyError, ValueError, TypeError):
                continue

            ore_totali += ore

            reset_details.append({
                'id': doc['ID_RICHIESTA'],
                'ore': ore,
                'giorni': giorni,
                'utente': doc.get('FK_UTENTE', 'N/A'),
                'tipo': doc.get('FK_TIPO_RICHIESTA', 'N/A'),
                'utenza': doc.get('NOME_UTENZA', 'N/A')
            })

            if ore <= 24:
                entro_1gg += 1
            elif ore <= 48:
                entro_2gg += 1
            else:
                sopra_2gg += 1
                reset_ritardatari.append({
                    'id': doc['ID_RICHIESTA'],
                    'ore': ore,
                    'utente': doc.get('FK_UTENTE', 'N/A'),
                    'nota': doc.get('NOTA', '')
                })

        # Calcola percentuali e statistiche
        pct_1gg = (entro_1gg / total_reset * 100) if total_reset > 0 else 0
        pct_2gg = ((entro_1gg + entro_2gg) / total_reset * 100) if total_reset > 0 else 0
        ore_media = ore_totali / total_reset if total_reset > 0 else 0

        # Verifiche KPI
        kpi_1gg_ok = pct_1gg >= 80
        kpi_2gg_ok = pct_2gg >= 100

        print("📊 RISULTATI KPI\n")

        # KPI 1 giorno (80%)
        print("┌─ KPI 1: Completamento entro 1 giorno (target: 80%)")
        status_1gg = "✅ RAGGIUNTO" if kpi_1gg_ok else "❌ NON RAGGIUNTO"
        print(f"│  {status_1gg}")
        print(f"│  Completate entro 24h: {entro_1gg}/{total_reset} ({pct_1gg:.1f}%)")
        print(f"│  Differenza target: {pct_1gg - 80:+.1f}%")
        print(f"└─\n")

        # KPI 2 giorni (100%)
        print("┌─ KPI 2: Completamento entro 2 giorni (target: 100%)")
        status_2gg = "✅ RAGGIUNTO" if kpi_2gg_ok else "❌ NON RAGGIUNTO"
        print(f"│  {status_2gg}")
        print(f"│  Completate entro 48h: {entro_1gg + entro_2gg}/{total_reset} ({pct_2gg:.1f}%)")
        print(f"│  Non completate in tempo: {sopra_2gg}")
        print(f"└─\n")

        # Statistiche dettagliate
        if reset_details:
            ore_list = [r['ore'] for r in reset_details]
            ore_media = sum(ore_list) / len(ore_list)
            ore_min = min(ore_list)
            ore_max = max(ore_list)
            ore_mediana = sorted(ore_list)[len(ore_list)//2]

            print("📈 STATISTICHE TEMPI DI ELABORAZIONE\n")
            print(f"  Tempo medio:    {ore_media:.2f} ore ({ore_media/24:.2f} giorni)")
            print(f"  Tempo mediano:  {ore_mediana:.2f} ore")
            print(f"  Tempo minimo:   {ore_min:.2f} ore")
            print(f"  Tempo massimo:  {ore_max:.2f} ore")
            print(f"\n  Distribuzione:")
            print(f"    • Entro 24h:   {entro_1gg} ({pct_1gg:.1f}%)")
            print(f"    • 24-48h:      {entro_2gg} ({(entro_2gg/total_reset*100):.1f}%)")
            print(f"    • Oltre 48h:   {sopra_2gg} ({(sopra_2gg/total_reset*100):.1f}%)\n")

        return {
            'total': total_reset,
            'entro_1gg': entro_1gg,
            'pct_1gg': pct_1gg,
            'kpi_1gg_ok': kpi_1gg_ok,
            'entro_2gg': entro_1gg + entro_2gg,
            'pct_2gg': pct_2gg,
            'kpi_2gg_ok': kpi_2gg_ok,
            'sopra_2gg': sopra_2gg,
            'ore_media': ore_media,
            'details': reset_details,
            'ritardatari': reset_ritardatari
        }

    def calcola_kpi_reset_per_tipo(self, index_name='iam-richieste',
                                  nome_operazione='RESET', stato_completato='COMPLETATA'):
        """Calcola KPI per tipo di richiesta"""
        print("\n" + "=" * 70)
        print(f"KPI - {nome_operazione} PER TIPO DI RICHIESTA")
        print("=" * 70 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'query': {
                    'bool': {
                        'must': [
                            {'term': {'STATO.keyword': stato_completato}},
                            {'term': {'FK_NOME_OPERAZIONE.keyword': nome_operazione}},
                            {'exists': {'field': 'DATA_CREAZIONE'}},
                            {'exists': {'field': 'DATA_CHIUSURA'}}
                        ]
                    }
                },
                'size': 0,
                'aggs': {
                    'per_tipo': {
                        'terms': {'field': 'FK_TIPO_RICHIESTA.keyword', 'size': 20},
                        'aggs': {
                            'tempo_medio': {
                                'avg': {'field': 'ore_elaborazione'}
                            },
                            'count_1gg': {
                                'filter': {'range': {'ore_elaborazione': {'lte': 24}}}
                            },
                            'count_2gg': {
                                'filter': {'range': {'ore_elaborazione': {'lte': 48}}}
                            },
                            'percentili': {
                                'percentiles': {'field': 'ore_elaborazione',
                                              'percents': [50, 80, 95, 100]}
                            }
                        }
                    }
                }
            }
        )

        buckets = response['aggregations']['per_tipo']['buckets']

        if not buckets:
            print("⚠ Nessun dato disponibile")
            return

        print("Tipo Richiesta              | Tot | 24h  | % 24h | 48h  | % 48h | Tempo Medio | P95\n")
        print("-" * 95)

        for bucket in buckets:
            tipo = bucket['key'][:25].ljust(25)
            total = bucket['doc_count']
            count_1gg = bucket['count_1gg']['doc_count']
            count_2gg = bucket['count_2gg']['doc_count']
            tempo_medio = bucket['tempo_medio']['value'] or 0
            p95 = bucket['percentili']['values'].get('95.0', 0)

            pct_1gg = (count_1gg / total * 100) if total > 0 else 0
            pct_2gg = (count_2gg / total * 100) if total > 0 else 0

            status_1gg = "✅" if pct_1gg >= 80 else "❌"

            print(f"{tipo} | {total:3d} | {count_1gg:4d} | {pct_1gg:5.1f}% {status_1gg} | {count_2gg:4d} | {pct_2gg:5.1f}% | {tempo_medio:10.1f}h | {p95:6.1f}h")

    def calcola_kpi_reset_per_utente(self, index_name='iam-richieste',
                                    nome_operazione='RESET', stato_completato='COMPLETATA', limit=15):
        """Calcola KPI per utente"""
        print("\n" + "=" * 70)
        print(f"KPI - {nome_operazione} PER UTENTE (TOP {limit})")
        print("=" * 70 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'query': {
                    'bool': {
                        'must': [
                            {'term': {'STATO.keyword': stato_completato}},
                            {'term': {'FK_NOME_OPERAZIONE.keyword': nome_operazione}},
                            {'exists': {'field': 'DATA_CREAZIONE'}},
                            {'exists': {'field': 'DATA_CHIUSURA'}}
                        ]
                    }
                },
                'size': 0,
                'aggs': {
                    'per_utente': {
                        'terms': {'field': 'FK_UTENTE.keyword', 'size': limit},
                        'aggs': {
                            'tempo_medio': {
                                'avg': {'field': 'ore_elaborazione'}
                            },
                            'count_1gg': {
                                'filter': {'range': {'ore_elaborazione': {'lte': 24}}}
                            },
                            'count_2gg': {
                                'filter': {'range': {'ore_elaborazione': {'lte': 48}}}
                            }
                        }
                    }
                }
            }
        )

        buckets = response['aggregations']['per_utente']['buckets']

        if not buckets:
            print("⚠ Nessun dato disponibile")
            return

        print("Pos | Utente                         | Richieste | Tempo Medio | 24h % | 48h %\n")
        print("-" * 80)

        for i, bucket in enumerate(buckets, 1):
            utente = bucket['key'][:30].ljust(30)
            total = bucket['doc_count']
            tempo_medio = bucket['tempo_medio']['value'] or 0
            count_1gg = bucket['count_1gg']['doc_count']
            count_2gg = bucket['count_2gg']['doc_count']

            pct_1gg = (count_1gg / total * 100) if total > 0 else 0
            pct_2gg = (count_2gg / total * 100) if total > 0 else 0

            print(f"{i:3d} | {utente} | {total:9d} | {tempo_medio:10.1f}h | {pct_1gg:5.1f}% | {pct_2gg:5.1f}%")

    def calcola_kpi_reset_timeline(self, index_name='iam-richieste',
                                  nome_operazione='RESET', stato_completato='COMPLETATA', days=30):
        """Timeline giornaliera dei KPI"""
        print("\n" + "=" * 70)
        print(f"KPI - TIMELINE {nome_operazione} (Ultimi {days} giorni)")
        print("=" * 70 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'query': {
                    'bool': {
                        'must': [
                            {'term': {'STATO.keyword': stato_completato}},
                            {'term': {'FK_NOME_OPERAZIONE.keyword': nome_operazione}},
                            {'range': {'DATA_CREAZIONE': {'gte': f'now-{days}d'}}},
                            {'exists': {'field': 'DATA_CREAZIONE'}},
                            {'exists': {'field': 'DATA_CHIUSURA'}}
                        ]
                    }
                },
                'size': 0,
                'aggs': {
                    'timeline': {
                        'date_histogram': {
                            'field': 'DATA_CREAZIONE',
                            'fixed_interval': '1d'
                        },
                        'aggs': {
                            'entro_1gg': {
                                'filter': {'range': {'ore_elaborazione': {'lte': 24}}}
                            },
                            'entro_2gg': {
                                'filter': {'range': {'ore_elaborazione': {'lte': 48}}}
                            },
                            'tempo_medio': {
                                'avg': {'field': 'ore_elaborazione'}
                            }
                        }
                    }
                }
            }
        )

        print("Data       | Totale | Entro 24h | %24h | Entro 48h | %48h | Tempo Medio | KPI 1gg | KPI 2gg\n")
        print("-" * 100)

        for bucket in response['aggregations']['timeline']['buckets']:
            data = bucket['key_as_string'][:10]
            total = bucket['doc_count']
            entro_1gg = bucket['entro_1gg']['doc_count']
            entro_2gg = bucket['entro_2gg']['doc_count']
            tempo_medio = bucket['tempo_medio']['value'] or 0

            pct_1gg = (entro_1gg / total * 100) if total > 0 else 0
            pct_2gg = (entro_2gg / total * 100) if total > 0 else 0

            status_1gg = "✅" if pct_1gg >= 80 else "❌"
            status_2gg = "✅" if pct_2gg >= 100 else "⚠️"

            print(f"{data}    | {total:6d} | {entro_1gg:9d} | {pct_1gg:5.1f}% | {entro_2gg:9d} | {pct_2gg:5.1f}% | {tempo_medio:10.1f}h | {status_1gg}      | {status_2gg}")

    def calcola_kpi_reset_ritardatari(self, index_name='iam-richieste',
                                     nome_operazione='RESET', stato_completato='COMPLETATA', limit=15):
        """Dettagli delle richieste che hanno superato il tempo limite"""
        print("\n" + "=" * 70)
        print(f"⚠️  {nome_operazione} CON RITARDO (>48 ore) - ULTIMI {limit}")
        print("=" * 70 + "\n")

        response = self.client.search(
            index=index_name,
            body={
                'query': {
                    'bool': {
                        'must': [
                            {'term': {'STATO.keyword': stato_completato}},
                            {'term': {'FK_NOME_OPERAZIONE.keyword': nome_operazione}},
                            {'range': {'ore_elaborazione': {'gt': 48}}},
                            {'exists': {'field': 'DATA_CREAZIONE'}},
                            {'exists': {'field': 'DATA_CHIUSURA'}}
                        ]
                    }
                },
                'size': limit,
                'sort': [{'ore_elaborazione': 'desc'}],
                '_source': ['ID_RICHIESTA', 'DATA_CREAZIONE', 'DATA_CHIUSURA',
                           'ore_elaborazione', 'FK_UTENTE', 'FK_TIPO_RICHIESTA',
                           'STATO', 'NOTA', 'NOME_UTENZA']
            }
        )

        richieste_ritardo = response['hits']['total']['value']

        if richieste_ritardo == 0:
            print("✅ Nessun reset con ritardo! Tutti completati entro 48 ore.\n")
            return

        print(f"Totale richieste con ritardo: {richieste_ritardo}\n")

        for i, hit in enumerate(response['hits']['hits'], 1):
            doc = hit['_source']
            ore = doc.get('ore_elaborazione', 0) or 0
            giorni = int(ore / 24)
            ore_residue = ore - (giorni * 24)
            ritardo = ore - 48

            print(f"{i}. ID: {doc['ID_RICHIESTA']}")
            print(f"   Tipo: {doc.get('FK_TIPO_RICHIESTA', 'N/A')}")
            print(f"   Utente: {doc.get('FK_UTENTE', 'N/A')}")
            print(f"   Utenza: {doc.get('NOME_UTENZA', 'N/A')}")
            print(f"   Tempo totale: {giorni}g {ore_residue:.1f}h ({ore:.1f}h)")
            print(f"   ⏱️  RITARDO: +{ritardo:.1f} ore oltre il limite di 48h")
            if doc.get('NOTA'):
                print(f"   Nota: {doc['NOTA'][:100]}...")
            print()


def main():
    """Esegue tutti i calcoli KPI"""
    print("\n" + "=" * 70)
    print("OPENSEARCH IAM - KPI CALCULATOR RESET OPERATIONS")
    print("=" * 70 + "\n")

    try:
        calculator = IamResetKpiCalculator(
            os_host='localhost',
            os_port=9200
        )

        # ⚠️ ADATTA QUESTI PARAMETRI SECONDO I TUOI DATI ⚠️
        nome_operazione = 'RESET_PASSWORD_ACCOUNT'  # ← CAMBIATO
        stato_completato = 'EVASA'  # ← CAMBIATO

        # Calcola KPI principale
        kpi = calculator.calcola_kpi_reset(
            'iam-richieste',
            nome_operazione=nome_operazione,
            stato_completato=stato_completato
        )

        # Analisi per tipo di richiesta
        calculator.calcola_kpi_reset_per_tipo(
            'iam-richieste',
            nome_operazione=nome_operazione,
            stato_completato=stato_completato
        )

        # Analisi per utente
        calculator.calcola_kpi_reset_per_utente(
            'iam-richieste',
            nome_operazione=nome_operazione,
            stato_completato=stato_completato,
            limit=20
        )

        # Timeline giornaliera
        calculator.calcola_kpi_reset_timeline(
            'iam-richieste',
            nome_operazione=nome_operazione,
            stato_completato=stato_completato,
            days=30
        )

        # Dettagli ritardatari
        calculator.calcola_kpi_reset_ritardatari(
            'iam-richieste',
            nome_operazione=nome_operazione,
            stato_completato=stato_completato,
            limit=15
        )

        print("\n" + "=" * 70)
        print("✅ ANALISI KPI COMPLETATA!")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n✗ Errore: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()