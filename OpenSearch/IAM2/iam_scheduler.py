"""
IAM RICHIESTE - Scheduler e Orchestrazione
=============================================

Script per schedulare l'aggiornamento automatico del dashboard
Esegue il caricamento periodicamente mantenendo la dashboard sempre aggiornata

Python 3.13
"""

import schedule
import time
import logging
from datetime import datetime
from pathlib import Path
import sys
import json
from typing import Dict
import oracledb

# ============================================================================
# CONFIGURAZIONE ORACLE - THIN/THICK MODE AUTO-DETECTION
# ============================================================================
# Thin Mode: Default, no dipendenze esterne ✅
# Thick Mode: Se Oracle Client disponibile ⚡

try:
    # Tenta thick mode se Oracle Client è disponibile
    oracledb.init_oracle_client()
    ORACLE_MODE = "THICK"
except Exception:
    # Ricaduta a thin mode (default, no dipendenze)
    ORACLE_MODE = "THIN"


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Configura logging"""
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"iam_scheduler_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    return logging.getLogger(__name__)


logger = setup_logging()


# ============================================================================
# CONFIGURAZIONE
# ============================================================================

class IAMConfig:
    """Gestione configurazione centralizzata"""

    CONFIG_FILE = 'iam_config.json'

    ORACLE_DEFAULT = {
        'host': 'localhost',
        'port': 1521,
        'service_name': 'ORCL',
        'user': 'iam_user',
        'password': 'iam_password'
    }

    OPENSEARCH_DEFAULT = {
        'host': 'localhost',
        'port': 9200,
        'auth': ['admin', 'admin'],
        'use_ssl': False
    }

    DASHBOARDS_DEFAULT = {
        'host': 'localhost',
        'port': 5601,
        'username': 'admin',
        'password': 'admin'
    }

    SCHEDULE_DEFAULT = {
        'tipo': 'daily',  # daily, hourly, weekly
        'ora': '02:00',   # Per daily
        'minuti': 0,      # Per hourly
        'giorno': 'monday'  # Per weekly
    }

    @classmethod
    def carica_config(cls) -> Dict:
        """Carica configurazione da file o crea predefinita"""
        config_file = Path(cls.CONFIG_FILE)

        if config_file.exists():
            logger.info(f"Caricando configurazione da {cls.CONFIG_FILE}")
            with open(config_file, 'r') as f:
                return json.load(f)
        else:
            logger.warning(f"File {cls.CONFIG_FILE} non trovato. Creando configurazione predefinita...")
            config = {
                'oracle': cls.ORACLE_DEFAULT,
                'opensearch': cls.OPENSEARCH_DEFAULT,
                'dashboards': cls.DASHBOARDS_DEFAULT,
                'schedule': cls.SCHEDULE_DEFAULT,
                'giorni_indietro': 90,
                'ricrea_indici': False,
                'ricrea_visualizzazioni': False
            }
            cls.salva_config(config)
            return config

    @classmethod
    def salva_config(cls, config: Dict):
        """Salva configurazione su file"""
        with open(cls.CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Configurazione salvata in {cls.CONFIG_FILE}")

    @classmethod
    def stampa_config_template(cls):
        """Stampa template configurazione"""
        print("\n" + "=" * 70)
        print("TEMPLATE CONFIGURAZIONE - iam_config.json")
        print("=" * 70 + "\n")

        template = {
            'oracle': cls.ORACLE_DEFAULT,
            'opensearch': cls.OPENSEARCH_DEFAULT,
            'dashboards': cls.DASHBOARDS_DEFAULT,
            'schedule': cls.SCHEDULE_DEFAULT,
            'giorni_indietro': 90,
            'ricrea_indici': False,
            'ricrea_visualizzazioni': False
        }

        print(json.dumps(template, indent=2))
        print("\n" + "=" * 70)


# ============================================================================
# TASK SCHEDULER
# ============================================================================

class IAMScheduler:
    """Scheduler per aggiornamenti periodici"""

    def __init__(self):
        """Inizializza scheduler"""
        self.config = IAMConfig.carica_config()
        self.logger = logger

    def schedula_job(self, tipo_schedule: str, ora: str = None, minuti: int = 0, giorno: str = None):
        """Schedula il job"""
        if tipo_schedule == 'daily':
            schedule.every().day.at(ora).do(self.esegui_job)
            self.logger.info(f"Job schedulato DAILY alle {ora}")

        elif tipo_schedule == 'hourly':
            schedule.every(minuti if minuti > 0 else 60).minutes.do(self.esegui_job)
            self.logger.info(f"Job schedulato ogni {minuti if minuti > 0 else 60} minuti")

        elif tipo_schedule == 'weekly':
            getattr(schedule.every(), giorno).at(ora).do(self.esegui_job)
            self.logger.info(f"Job schedulato settimanale ({giorno}) alle {ora}")

    def esegui_job(self):
        """Esegue il job di aggiornamento"""
        self.logger.info("=" * 70)
        self.logger.info("INIZIO AGGIORNAMENTO IAM DASHBOARD")
        self.logger.info(f"Modalità Oracle: {ORACLE_MODE}")
        self.logger.info("=" * 70)

        start_time = time.time()

        try:
            # Import lazy per evitare dipendenze circolari
            from iam_opensearch_dashboard import (
                IAMOracleLoader, IAMOpenSearchManager,
                IAMKPIAnalyzer, INDEX_RICHIESTE, INDEX_KPI
            )

            # 1. Caricamento dati Oracle
            self.logger.info("[1] Caricamento dati da Oracle...")
            loader = IAMOracleLoader(self.config['oracle'])
            richieste = loader.carica_richieste(self.config['giorni_indietro'])
            loader.chiudi()

            if not richieste:
                self.logger.warning("Nessuna richiesta caricata")
                return

            # 2. Inserimento OpenSearch
            self.logger.info("[2] Inserimento in OpenSearch...")
            manager = IAMOpenSearchManager(self.config['opensearch'])

            if self.config.get('ricrea_indici', False):
                manager.crea_indice_richieste()
                manager.crea_indice_kpi()

            inserted = manager.inserisci_richieste(richieste)

            # 3. Calcolo e inserimento KPI
            self.logger.info("[3] Calcolo KPI...")
            analyzer = IAMKPIAnalyzer(manager.client)
            kpi_list = analyzer.calcola_tutti_kpi(richieste)
            manager.inserisci_kpi(kpi_list)

            # 4. Ricreazione visualizzazioni (opzionale)
            if self.config.get('ricrea_visualizzazioni', False):
                self.logger.info("[4] Ricreazione visualizzazioni...")
                self._ricrea_visualizzazioni()

            elapsed = time.time() - start_time
            self.logger.info("=" * 70)
            self.logger.info(f"✓ AGGIORNAMENTO COMPLETATO in {elapsed:.2f} secondi")
            self.logger.info(f"  • Richieste inserite: {inserted}")
            self.logger.info(f"  • KPI calcolati: {len(kpi_list)}")
            self.logger.info("=" * 70)

        except Exception as e:
            self.logger.error(f"✗ ERRORE durante aggiornamento: {e}", exc_info=True)

    def _ricrea_visualizzazioni(self):
        """Ricrea visualizzazioni su Dashboard"""
        try:
            from iam_opensearch_visualizations import IAMVisualizationsCreator

            creator = IAMVisualizationsCreator(
                host=self.config['dashboards']['host'],
                port=self.config['dashboards']['port'],
                username=self.config['dashboards']['username'],
                password=self.config['dashboards']['password']
            )

            creator.crea_index_pattern('iam-richieste', 'data_creazione')
            visualizzazioni = creator.crea_tutte_visualizzazioni('iam-richieste*')
            dashboard_id = creator.crea_dashboard(visualizzazioni, 'IAM - Main Dashboard')

            self.logger.info(f"✓ Dashboard aggiornato: {dashboard_id}")

        except Exception as e:
            self.logger.error(f"✗ Errore ricreazione visualizzazioni: {e}", exc_info=True)

    def avvia_scheduler(self):
        """Avvia lo scheduler in esecuzione continua"""
        schedule_config = self.config['schedule']

        self.schedula_job(
            tipo_schedule=schedule_config.get('tipo', 'daily'),
            ora=schedule_config.get('ora', '02:00'),
            minuti=schedule_config.get('minuti', 0),
            giorno=schedule_config.get('giorno', 'monday')
        )

        self.logger.info("Scheduler avviato. In attesa di job...")
        self.logger.info("Premi CTRL+C per fermare\n")

        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            self.logger.info("\nScheduler fermato dall'utente")

    def esegui_una_volta(self):
        """Esegue il job una sola volta (per test)"""
        self.logger.info("Esecuzione test (una volta)...")
        self.esegui_job()


# ============================================================================
# SCRIPT PRINCIPALE
# ============================================================================

def main():
    """Punto di ingresso principale"""
    print("\n" + "=" * 70)
    print("IAM OPENSEARCH DASHBOARD - SCHEDULER")
    print("=" * 70)

    import argparse

    parser = argparse.ArgumentParser(description='IAM Dashboard Scheduler')
    parser.add_argument(
        '--mode',
        choices=['daemon', 'once', 'config'],
        default='once',
        help='Modalità esecuzione'
    )
    parser.add_argument(
        '--config',
        type=str,
        help='Percorso file configurazione'
    )

    args = parser.parse_args()

    if args.mode == 'config':
        # Mostra template configurazione
        IAMConfig.stampa_config_template()
        print("\n💡 ISTRUZIONI:")
        print("1. Copia il JSON sopra")
        print("2. Crea file 'iam_config.json'")
        print("3. Modifica le credenziali Oracle e OpenSearch")
        print("4. Salva il file")
        print("5. Esegui: python iam_scheduler.py --mode once")
        return

    # Carica scheduler
    scheduler = IAMScheduler()

    if args.mode == 'once':
        # Esecuzione singola (test)
        logger.info("Modalità: ESECUZIONE SINGOLA")
        scheduler.esegui_una_volta()

    elif args.mode == 'daemon':
        # Modalità daemon (background)
        logger.info("Modalità: DAEMON (background)")
        logger.info(f"Schedule: {scheduler.config['schedule']}")
        scheduler.avvia_scheduler()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def genera_report_stato():
    """Genera report dello stato del sistema"""
    print("\n" + "=" * 70)
    print("REPORT STATO IAM DASHBOARD")
    print("=" * 70 + "\n")

    try:
        from opensearchpy import OpenSearch

        config = IAMConfig.carica_config()
        client = OpenSearch(
            hosts=[{'host': config['opensearch']['host'], 'port': config['opensearch']['port']}],
            http_auth=tuple(config['opensearch']['auth']),
            use_ssl=config['opensearch']['use_ssl'],
            verify_certs=False,
            ssl_show_warn=False
        )

        # Verifica indici
        print("📊 INDICI:")
        for index_name in ['iam-richieste', 'iam-kpi']:
            if client.indices.exists(index=index_name):
                stats = client.indices.stats(index=index_name)
                docs = stats['_all']['primaries']['docs']['count']
                size_mb = stats['_all']['primaries']['store']['size_in_bytes'] / 1024 / 1024
                print(f"   ✓ {index_name}: {docs:,} documenti ({size_mb:.2f} MB)")
            else:
                print(f"   ✗ {index_name}: NON PRESENTE")

        # Statistiche richieste
        print("\n📈 STATISTICHE RICHIESTE:")
        response = client.search(
            index='iam-richieste',
            body={
                'size': 0,
                'aggs': {
                    'by_state': {
                        'terms': {'field': 'stato'}
                    },
                    'avg_time': {
                        'avg': {'field': 'tempo_evasione_ore'}
                    }
                }
            }
        )

        total = response['hits']['total']['value']
        print(f"   Totale richieste: {total:,}")

        for bucket in response['aggregations']['by_state']['buckets']:
            perc = (bucket['doc_count'] / total) * 100
            print(f"   • {bucket['key']}: {bucket['doc_count']:,} ({perc:.1f}%)")

        avg_time = response['aggregations']['avg_time']['value']
        if avg_time:
            print(f"   Tempo medio evasione: {avg_time:.2f} ore")

        # KPI
        print("\n🎯 KPI:")
        response = client.search(
            index='iam-kpi',
            body={
                'size': 100,
                'sort': [{'timestamp': {'order': 'desc'}}]
            }
        )

        if response['hits']['hits']:
            print("   Ultimi KPI calcolati:")
            for hit in response['hits']['hits'][:10]:
                kpi = hit['_source']
                print(f"   • {kpi['nome_kpi']}: {kpi['valore']} {kpi['unita_misura']} [{kpi['stato_kpi']}]")

        # Log ultimo aggiornamento
        print("\n🕐 ULTIMO AGGIORNAMENTO:")
        log_dir = Path('logs')
        if log_dir.exists():
            log_files = sorted(log_dir.glob('iam_scheduler_*.log'), reverse=True)
            if log_files:
                with open(log_files[0], 'r') as f:
                    lines = f.readlines()
                    if lines:
                        print(f"   File: {log_files[0].name}")
                        print(f"   Ultimi eventi:")
                        for line in lines[-5:]:
                            print(f"   {line.strip()}")

    except Exception as e:
        print(f"✗ Errore: {e}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()