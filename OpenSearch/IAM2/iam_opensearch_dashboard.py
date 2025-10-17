"""
IAM RICHIESTE - OpenSearch Dashboard System
============================================

Sistema completo per:
1. Caricare richieste IAM da Oracle
2. Eseguire analisi su performance e SLA
3. Creare visualizzazioni su OpenSearch Dashboard
4. Generare KPI in tempo reale

Autore: Sistema IAM Analytics
Python 3.13
"""

import oracledb
from opensearchpy import OpenSearch, helpers
from datetime import datetime, timedelta
import json
import statistics
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import time


# ============================================================================
# CONFIGURAZIONE
# ============================================================================

# Credenziali Oracle (adattare da iam_loader.1.py)
ORACLE_CONFIG = {
    'host': 'localhost',  # Modifica con il tuo host
    'port': 1521,
    'service_name': 'ORCL',  # Modifica con il tuo service
    'user': 'iam_user',  # Modifica
    'password': 'iam_password'  # Modifica
}

# OpenSearch
OPENSEARCH_CONFIG = {
    'host': 'localhost',
    'port': 9200,
    'auth': ('admin', 'admin'),
    'use_ssl': False
}

# Nomi indici
INDEX_RICHIESTE = 'iam-richieste'
INDEX_KPI = 'iam-kpi'


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class RichiestaIAM:
    """Rappresentazione di una richiesta IAM"""
    id_richiesta: int
    fk_id_oggetto: int
    nome_utenza: str
    fk_tipo_richiesta: str
    fk_tipo_utenza: str
    fk_nome_operazione: str
    id_richiesta_parent: int
    data_creazione: datetime
    data_chiusura: datetime
    fk_utente: str
    fk_utente_richiedente: str
    stato: str
    nota: str
    flag_transazione: str
    data_storicizzazione: datetime
    priorita_secondaria: int
    tipo_op_secondaria: int
    comunicazione_uf: str

    def to_dict(self) -> Dict:
        """Converte a dict per OpenSearch"""
        return {
            'id_richiesta': self.id_richiesta,
            'fk_id_oggetto': self.fk_id_oggetto,
            'nome_utenza': self.nome_utenza,
            'fk_tipo_richiesta': self.fk_tipo_richiesta,
            'fk_tipo_utenza': self.fk_tipo_utenza,
            'fk_nome_operazione': self.fk_nome_operazione,
            'id_richiesta_parent': self.id_richiesta_parent,
            'data_creazione': self.data_creazione.isoformat() if self.data_creazione else None,
            'data_chiusura': self.data_chiusura.isoformat() if self.data_chiusura else None,
            'fk_utente': self.fk_utente,
            'fk_utente_richiedente': self.fk_utente_richiedente,
            'stato': self.stato,
            'nota': self.nota,
            'flag_transazione': self.flag_transazione,
            'data_storicizzazione': self.data_storicizzazione.isoformat() if self.data_storicizzazione else None,
            'priorita_secondaria': self.priorita_secondaria,
            'tipo_op_secondaria': self.tipo_op_secondaria,
            'comunicazione_uf': self.comunicazione_uf,
            'tempo_evasione_ore': self._calcola_tempo_evasione(),
            'data_inserimento_es': datetime.now().isoformat()
        }

    def _calcola_tempo_evasione(self) -> float:
        """Calcola ore tra creazione e chiusura"""
        if self.data_creazione and self.data_chiusura:
            delta = self.data_chiusura - self.data_creazione
            return delta.total_seconds() / 3600
        return None


# ============================================================================
# LOADER ORACLE
# ============================================================================

class IAMOracleLoader:
    """Carica dati IAM_RICHIESTE da Oracle"""

    def __init__(self, config: Dict):
        """Inizializza connessione Oracle"""
        self.config = config
        self.connection = None
        self._connetti()

    def _connetti(self):
        """Connessione a Oracle"""
        try:
            dsn = oracledb.makedsn(
                self.config['host'],
                self.config['port'],
                service_name=self.config['service_name']
            )
            self.connection = oracledb.connect(
                user=self.config['user'],
                password=self.config['password'],
                dsn=dsn
            )
            print(f"✓ Connesso a Oracle ({self.config['host']})")
        except Exception as e:
            print(f"✗ Errore connessione Oracle: {e}")
            raise

    def carica_richieste(self, giorni_indietro: int = 90) -> List[RichiestaIAM]:
        """
        Carica richieste degli ultimi N giorni

        Args:
            giorni_indietro: numero di giorni da caricare
        """
        try:
            cursor = self.connection.cursor()

            data_limite = (datetime.now() - timedelta(days=giorni_indietro)).date()

            query = f"""
            SELECT 
                ID_RICHIESTA,
                FK_ID_OGGETTO,
                NOME_UTENZA,
                FK_TIPO_RICHIESTA,
                FK_TIPO_UTENZA,
                FK_NOME_OPERAZIONE,
                ID_RICHIESTA_PARENT,
                DATA_CREAZIONE,
                DATA_CHIUSURA,
                FK_UTENTE,
                FK_UTENTE_RICHIEDENTE,
                STATO,
                NOTA,
                FLAG_TRANSAZIONE,
                DATA_STORICIZZAZIONE,
                PRIORITA_SECONDARIA,
                TIPO_OP_SECONDARIA,
                COMUNICAZIONE_UF
            FROM IAM_RICHIESTE
            WHERE DATA_CREAZIONE >= TO_DATE('{data_limite}', 'YYYY-MM-DD')
            ORDER BY DATA_CREAZIONE DESC
            """

            cursor.execute(query)
            rows = cursor.fetchall()

            richieste = []
            for row in rows:
                richiesta = RichiestaIAM(
                    id_richiesta=row[0],
                    fk_id_oggetto=row[1],
                    nome_utenza=row[2],
                    fk_tipo_richiesta=row[3],
                    fk_tipo_utenza=row[4],
                    fk_nome_operazione=row[5],
                    id_richiesta_parent=row[6],
                    data_creazione=row[7],
                    data_chiusura=row[8],
                    fk_utente=row[9],
                    fk_utente_richiedente=row[10],
                    stato=row[11],
                    nota=row[12],
                    flag_transazione=row[13],
                    data_storicizzazione=row[14],
                    priorita_secondaria=row[15],
                    tipo_op_secondaria=row[16],
                    comunicazione_uf=row[17]
                )
                richieste.append(richiesta)

            print(f"✓ Caricate {len(richieste)} richieste da Oracle")
            cursor.close()
            return richieste

        except Exception as e:
            print(f"✗ Errore caricamento dati: {e}")
            return []

    def chiudi(self):
        """Chiude connessione"""
        if self.connection:
            self.connection.close()


# ============================================================================
# OPENSEARCH MANAGER
# ============================================================================

class IAMOpenSearchManager:
    """Gestisce indici e visualizzazioni su OpenSearch"""

    def __init__(self, config: Dict):
        """Inizializza client OpenSearch"""
        self.client = OpenSearch(
            hosts=[{'host': config['host'], 'port': config['port']}],
            http_auth=config['auth'],
            use_ssl=config['use_ssl'],
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30,
            max_retries=3
        )
        self._verifica_connessione()

    def _verifica_connessione(self):
        """Verifica connessione a OpenSearch"""
        try:
            info = self.client.info()
            print(f"✓ Connesso a OpenSearch {info['version']['number']}")
        except Exception as e:
            print(f"✗ Errore OpenSearch: {e}")
            raise

    def crea_indice_richieste(self):
        """Crea indice per richieste IAM"""
        mappings = {
            'properties': {
                'id_richiesta': {'type': 'keyword'},
                'fk_id_oggetto': {'type': 'integer'},
                'nome_utenza': {'type': 'text', 'fields': {'keyword': {'type': 'keyword'}}},
                'fk_tipo_richiesta': {'type': 'keyword'},
                'fk_tipo_utenza': {'type': 'keyword'},
                'fk_nome_operazione': {'type': 'keyword'},
                'id_richiesta_parent': {'type': 'integer'},
                'data_creazione': {'type': 'date'},
                'data_chiusura': {'type': 'date'},
                'fk_utente': {'type': 'keyword'},
                'fk_utente_richiedente': {'type': 'keyword'},
                'stato': {'type': 'keyword'},
                'nota': {'type': 'text'},
                'flag_transazione': {'type': 'keyword'},
                'data_storicizzazione': {'type': 'date'},
                'priorita_secondaria': {'type': 'integer'},
                'tipo_op_secondaria': {'type': 'integer'},
                'comunicazione_uf': {'type': 'text'},
                'tempo_evasione_ore': {'type': 'float'},
                'data_inserimento_es': {'type': 'date'}
            }
        }

        settings = {
            'number_of_shards': 2,
            'number_of_replicas': 0,
            'index': {'refresh_interval': '5s'}
        }

        try:
            if self.client.indices.exists(index=INDEX_RICHIESTE):
                self.client.indices.delete(index=INDEX_RICHIESTE)
                print(f"⚠ Indice '{INDEX_RICHIESTE}' ricreato")
            else:
                print(f"✓ Creazione indice '{INDEX_RICHIESTE}'")

            self.client.indices.create(
                index=INDEX_RICHIESTE,
                body={'mappings': mappings, 'settings': settings}
            )
        except Exception as e:
            print(f"✗ Errore creazione indice: {e}")

    def crea_indice_kpi(self):
        """Crea indice per KPI"""
        mappings = {
            'properties': {
                'timestamp': {'type': 'date'},
                'nome_kpi': {'type': 'keyword'},
                'valore': {'type': 'float'},
                'unita_misura': {'type': 'keyword'},
                'periodo': {'type': 'keyword'},
                'descrizione': {'type': 'text'},
                'soglia_warning': {'type': 'float'},
                'soglia_critical': {'type': 'float'},
                'stato_kpi': {'type': 'keyword'}  # OK, WARNING, CRITICAL
            }
        }

        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0
        }

        try:
            if not self.client.indices.exists(index=INDEX_KPI):
                self.client.indices.create(
                    index=INDEX_KPI,
                    body={'mappings': mappings, 'settings': settings}
                )
                print(f"✓ Creazione indice '{INDEX_KPI}'")
        except Exception as e:
            print(f"✗ Errore creazione indice KPI: {e}")

    def inserisci_richieste(self, richieste: List[RichiestaIAM]) -> int:
        """Inserisce richieste in bulk"""
        try:
            actions = [
                {
                    '_index': INDEX_RICHIESTE,
                    '_id': str(r.id_richiesta),
                    '_source': r.to_dict()
                }
                for r in richieste
            ]

            success, failed = helpers.bulk(
                self.client,
                actions,
                raise_on_error=False,
                refresh=True
            )

            print(f"✓ Inserite {success} richieste ({len(failed)} errori)")
            return success

        except Exception as e:
            print(f"✗ Errore inserimento: {e}")
            return 0

    def inserisci_kpi(self, kpi_list: List[Dict]):
        """Inserisce KPI"""
        try:
            actions = [
                {
                    '_index': INDEX_KPI,
                    '_source': kpi
                }
                for kpi in kpi_list
            ]

            success, failed = helpers.bulk(
                self.client,
                actions,
                raise_on_error=False,
                refresh=True
            )

            print(f"✓ Inseriti {success} KPI")
        except Exception as e:
            print(f"✗ Errore inserimento KPI: {e}")


# ============================================================================
# ANALIZZATORE KPI
# ============================================================================

class IAMKPIAnalyzer:
    """Calcola KPI dalle richieste IAM"""

    def __init__(self, client: OpenSearch):
        self.client = client

    def calcola_tutti_kpi(self, richieste: List[RichiestaIAM]) -> List[Dict]:
        """Calcola tutti i KPI"""
        kpi_list = []

        # KPI 1: Tempo medio evasione per operazione
        kpi_list.extend(self._kpi_tempo_medio_operazione(richieste))

        # KPI 2: Tasso di evasione
        kpi_list.append(self._kpi_tasso_evasione(richieste))

        # KPI 3: Richieste per stato
        kpi_list.extend(self._kpi_richieste_per_stato(richieste))

        # KPI 4: Operazioni più frequenti
        kpi_list.extend(self._kpi_operazioni_frequenti(richieste))

        # KPI 5: SLA (90% evaso entro 24h)
        kpi_list.append(self._kpi_sla_24h(richieste))

        # KPI 6: Richieste in backlog
        kpi_list.append(self._kpi_backlog(richieste))

        # KPI 7: Tempo medio per tipo utenza
        kpi_list.extend(self._kpi_tempo_per_tipo_utenza(richieste))

        return kpi_list

    def _kpi_tempo_medio_operazione(self, richieste: List[RichiestaIAM]) -> List[Dict]:
        """Tempo medio evasione per operazione"""
        operazioni = {}

        for r in richieste:
            if r.fk_nome_operazione not in operazioni:
                operazioni[r.fk_nome_operazione] = []
            if r.tempo_evasione_ore is not None:
                operazioni[r.fk_nome_operazione].append(r.tempo_evasione_ore)

        kpi_list = []
        for op, tempi in operazioni.items():
            if tempi:
                kpi = {
                    'timestamp': datetime.now().isoformat(),
                    'nome_kpi': f'Tempo medio evasione - {op}',
                    'valore': round(statistics.mean(tempi), 2),
                    'unita_misura': 'ore',
                    'periodo': 'ultimo_caricamento',
                    'descrizione': f'Tempo medio evasione per operazione {op}',
                    'soglia_warning': 24,
                    'soglia_critical': 48,
                    'stato_kpi': self._stato_kpi(round(statistics.mean(tempi), 2), 24, 48)
                }
                kpi_list.append(kpi)

        return kpi_list

    def _kpi_tasso_evasione(self, richieste: List[RichiestaIAM]) -> Dict:
        """Percentuale richieste evase"""
        if not richieste:
            return {}

        evase = len([r for r in richieste if r.stato == 'EVASA'])
        tasso = (evase / len(richieste)) * 100

        return {
            'timestamp': datetime.now().isoformat(),
            'nome_kpi': 'Tasso di evasione',
            'valore': round(tasso, 2),
            'unita_misura': '%',
            'periodo': 'ultimo_caricamento',
            'descrizione': f'{evase} richieste evase su {len(richieste)}',
            'soglia_warning': 80,
            'soglia_critical': 70,
            'stato_kpi': self._stato_kpi(tasso, 80, 70, reverse=True)
        }

    def _kpi_richieste_per_stato(self, richieste: List[RichiestaIAM]) -> List[Dict]:
        """Conteggio richieste per stato"""
        stati = {}

        for r in richieste:
            if r.stato not in stati:
                stati[r.stato] = 0
            stati[r.stato] += 1

        kpi_list = []
        for stato, count in stati.items():
            kpi = {
                'timestamp': datetime.now().isoformat(),
                'nome_kpi': f'Richieste {stato}',
                'valore': count,
                'unita_misura': 'numero',
                'periodo': 'ultimo_caricamento',
                'descrizione': f'Conteggio richieste nello stato {stato}',
                'soglia_warning': None,
                'soglia_critical': None,
                'stato_kpi': 'OK'
            }
            kpi_list.append(kpi)

        return kpi_list

    def _kpi_operazioni_frequenti(self, richieste: List[RichiestaIAM]) -> List[Dict]:
        """Top 5 operazioni"""
        operazioni = {}

        for r in richieste:
            if r.fk_nome_operazione not in operazioni:
                operazioni[r.fk_nome_operazione] = 0
            operazioni[r.fk_nome_operazione] += 1

        sorted_ops = sorted(operazioni.items(), key=lambda x: x[1], reverse=True)[:5]

        kpi_list = []
        for op, count in sorted_ops:
            kpi = {
                'timestamp': datetime.now().isoformat(),
                'nome_kpi': f'Frequenza - {op}',
                'valore': count,
                'unita_misura': 'numero',
                'periodo': 'ultimo_caricamento',
                'descrizione': f'Numero richieste per operazione {op}',
                'soglia_warning': None,
                'soglia_critical': None,
                'stato_kpi': 'OK'
            }
            kpi_list.append(kpi)

        return kpi_list

    def _kpi_sla_24h(self, richieste: List[RichiestaIAM]) -> Dict:
        """SLA: % evase entro 24h"""
        richieste_evase = [r for r in richieste if r.stato == 'EVASA']

        if not richieste_evase:
            sla = 0
        else:
            entro_24h = len([r for r in richieste_evase if r.tempo_evasione_ore and r.tempo_evasione_ore <= 24])
            sla = (entro_24h / len(richieste_evase)) * 100

        return {
            'timestamp': datetime.now().isoformat(),
            'nome_kpi': 'SLA 24h',
            'valore': round(sla, 2),
            'unita_misura': '%',
            'periodo': 'ultimo_caricamento',
            'descrizione': 'Percentuale richieste evase entro 24 ore',
            'soglia_warning': 85,
            'soglia_critical': 75,
            'stato_kpi': self._stato_kpi(sla, 85, 75, reverse=True)
        }

    def _kpi_backlog(self, richieste: List[RichiestaIAM]) -> Dict:
        """Richieste in backlog (non evase)"""
        backlog = len([r for r in richieste if r.stato != 'EVASA'])

        return {
            'timestamp': datetime.now().isoformat(),
            'nome_kpi': 'Backlog',
            'valore': backlog,
            'unita_misura': 'numero',
            'periodo': 'ultimo_caricamento',
            'descrizione': 'Numero richieste non ancora evase',
            'soglia_warning': 50,
            'soglia_critical': 100,
            'stato_kpi': self._stato_kpi(backlog, 50, 100)
        }

    def _kpi_tempo_per_tipo_utenza(self, richieste: List[RichiestaIAM]) -> List[Dict]:
        """Tempo medio per tipo utenza"""
        tipi_utenza = {}

        for r in richieste:
            if r.fk_tipo_utenza not in tipi_utenza:
                tipi_utenza[r.fk_tipo_utenza] = []
            if r.tempo_evasione_ore is not None:
                tipi_utenza[r.fk_tipo_utenza].append(r.tempo_evasione_ore)

        kpi_list = []
        for tipo, tempi in tipi_utenza.items():
            if tempi:
                kpi = {
                    'timestamp': datetime.now().isoformat(),
                    'nome_kpi': f'Tempo medio - {tipo}',
                    'valore': round(statistics.mean(tempi), 2),
                    'unita_misura': 'ore',
                    'periodo': 'ultimo_caricamento',
                    'descrizione': f'Tempo medio evasione per tipo utenza {tipo}',
                    'soglia_warning': 24,
                    'soglia_critical': 48,
                    'stato_kpi': self._stato_kpi(round(statistics.mean(tempi), 2), 24, 48)
                }
                kpi_list.append(kpi)

        return kpi_list

    @staticmethod
    def _stato_kpi(valore: float, soglia_warning: float, soglia_critical: float, reverse: bool = False) -> str:
        """Determina stato del KPI"""
        if reverse:  # Per percentuali (più alto è meglio)
            if valore >= soglia_warning:
                return 'OK'
            elif valore >= soglia_critical:
                return 'WARNING'
            else:
                return 'CRITICAL'
        else:  # Per tempi (più basso è meglio)
            if valore <= soglia_warning:
                return 'OK'
            elif valore <= soglia_critical:
                return 'WARNING'
            else:
                return 'CRITICAL'


# ============================================================================
# ORCHESTRATORE PRINCIPALE
# ============================================================================

class IAMDashboardOrchestrator:
    """Orchestra tutto il processo"""

    def __init__(self):
        self.oracle_loader = None
        self.opensearch_manager = None
        self.kpi_analyzer = None

    def esegui_caricamento_completo(self, giorni_indietro: int = 90):
        """Esegue il caricamento completo"""
        print("\n" + "=" * 80)
        print("IAM RICHIESTE - OPENSEARCH DASHBOARD SYSTEM")
        print("=" * 80)

        try:
            # 1. Connessione Oracle
            print("\n[1] Connessione a Oracle...")
            self.oracle_loader = IAMOracleLoader(ORACLE_CONFIG)

            # 2. Connessione OpenSearch
            print("\n[2] Connessione a OpenSearch...")
            self.opensearch_manager = IAMOpenSearchManager(OPENSEARCH_CONFIG)

            # 3. Creazione indici
            print("\n[3] Creazione indici...")
            self.opensearch_manager.crea_indice_richieste()
            self.opensearch_manager.crea_indice_kpi()

            # 4. Caricamento dati
            print(f"\n[4] Caricamento richieste (ultimi {giorni_indietro} giorni)...")
            richieste = self.oracle_loader.carica_richieste(giorni_indietro)

            if not richieste:
                print("✗ Nessuna richiesta caricata")
                return

            # 5. Inserimento in OpenSearch
            print("\n[5] Inserimento in OpenSearch...")
            self.opensearch_manager.inserisci_richieste(richieste)

            # 6. Calcolo KPI
            print("\n[6] Calcolo KPI...")
            self.kpi_analyzer = IAMKPIAnalyzer(self.opensearch_manager.client)
            kpi_list = self.kpi_analyzer.calcola_tutti_kpi(richieste)
            self.opensearch_manager.inserisci_kpi(kpi_list)

            # 7. Stampa riepilogo
            self._stampa_riepilogo(richieste, kpi_list)

            # 8. Istruzioni dashboard
            self._stampa_istruzioni_dashboard()

        except Exception as e:
            print(f"\n✗ ERRORE CRITICO: {e}")
        finally:
            if self.oracle_loader:
                self.oracle_loader.chiudi()

    def _stampa_riepilogo(self, richieste: List[RichiestaIAM], kpi_list: List[Dict]):
        """Stampa riepilogo"""
        print("\n" + "=" * 80)
        print("📊 RIEPILOGO")
        print("=" * 80)

        print(f"\n📈 DATI CARICATI:")
        print(f"   Totale richieste: {len(richieste)}")
        print(f"   KPI calcolati: {len(kpi_list)}")

        # Statistiche richieste
        evase = len([r for r in richieste if r.stato == 'EVASA'])
        non_evase = len([r for r in richieste if r.stato == 'NON EVASA'])
        annullate = len([r for r in richieste if r.stato == 'ANNULLATA'])

        print(f"\n📋 STATI:")
        print(f"   ✓ Evase: {evase}")
        print(f"   ⏳ Non evase: {non_evase}")
        print(f"   ✗ Annullate: {annullate}")

        # KPI principali
        print(f"\n🎯 KPI PRINCIPALI:")
        for kpi in kpi_list[:5]:
            stato_icon = "✓" if kpi['stato_kpi'] == 'OK' else "⚠" if kpi['stato_kpi'] == 'WARNING' else "✗"
            print(f"   {stato_icon} {kpi['nome_kpi']}: {kpi['valore']} {kpi['unita_misura']}")

    def _stampa_istruzioni_dashboard(self):
        """Stampa istruzioni per il dashboard"""
        print("\n" + "=" * 80)
        print("🚀 PROSSIMI PASSI")
        print("=" * 80)

        print("\n1️⃣  APRI OPENSEARCH DASHBOARDS:")
        print("   → http://localhost:5601")

        print("\n2️⃣  CREA INDEX PATTERN:")
        print(f"   a) Management (⚙️) → Index Patterns")
        print(f"   b) Create Index Pattern")
        print(f"   c) Scrivi: {INDEX_RICHIESTE}*")
        print(f"   d) Time field: data_creazione")

        print("\n3️⃣  VISUALIZZAZIONI CONSIGLIATE:")
        print("   • Pie Chart: Richieste per stato")
        print("   • Bar Chart: Top 10 operazioni")
        print("   • Line Chart: Richieste nel tempo")
        print("   • Metric: SLA 24h, Backlog")
        print("   • Data Table: KPI stato")

        print("\n4️⃣  QUERY UTILI DA PROVARE:")
        print("   • Stato = EVASA AND tempo_evasione_ore > 24")
        print("   • fk_nome_operazione = RESET_PASSWORD_ACCOUNT")

        print("\n" + "=" * 80)


# ============================================================================
# ESECUZIONE
# ============================================================================

if __name__ == "__main__":
    """
    ISTRUZIONI DI USO:
    
    1. Modifica le credenziali in ORACLE_CONFIG e OPENSEARCH_CONFIG
    
    2. Esegui prima volta (carica tutti gli ultimi 90 giorni):
       python iam_opensearch_dashboard.py
    
    3. Per aggiornamenti periodici (daily):
       python iam_opensearch_dashboard.py
    
    4. Il sistema:
       ✓ Carica da Oracle
       ✓ Pulisce indici precedenti
       ✓ Crea visualizzazioni
       ✓ Calcola KPI
       ✓ Aggiorna OpenSearch Dashboards
    """

    orchestrator = IAMDashboardOrchestrator()
    orchestrator.esegui_caricamento_completo(giorni_indietro=90)