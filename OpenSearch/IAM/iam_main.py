"""
================================================================================
FILE: iam_main.py
================================================================================
IAM Main Orchestrator - Script Principale

Sistema completo per:
1. Caricare richieste IAM (generate o da CSV)
2. Eseguire analisi strategiche
3. Calcolare KPI configurabili
4. Creare visualizzazioni dashboard
5. Rigenerare periodicamente

UTILIZZO VELOCE:
    python iam_main.py --full           # Esecuzione completa (⭐ START HERE)
    python iam_main.py --load-only      # Solo caricamento dati
    python iam_main.py --analyze-only   # Solo analisi
    python iam_main.py --kpi-only       # Solo KPI
    python iam_main.py --dashboard-only # Solo visualizzazioni
    python iam_main.py --update         # Ricarica periodico

CONFIGURAZIONE:
    Modifica iam_kpi_config.json per i KPI

DATABASE:
    OpenSearch: http://localhost:9200
    Dashboards: http://localhost:5601

REQUIREMENTS:
    pip install opensearch-py requests
================================================================================
"""

import argparse
import sys
import time
import json
from datetime import datetime
from pathlib import Path
import subprocess


class Colors:
    """ANSI color codes"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


def print_banner():
    """Stampa banner colorato"""
    banner = f"""
{Colors.CYAN}
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║               🚀 IAM REQUESTS MONITORING SYSTEM 🚀                          ║
║                                                                              ║
║           OpenSearch Analytics & Professional KPI Dashboard                 ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
{Colors.RESET}
"""
    print(banner)


def print_section(title: str):
    """Stampa titolo sezione"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'═' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}► {title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'═' * 80}{Colors.RESET}\n")


def print_success(msg: str):
    """Stampa successo"""
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def print_error(msg: str):
    """Stampa errore"""
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def print_info(msg: str):
    """Stampa info"""
    print(f"{Colors.CYAN}ℹ{Colors.RESET} {msg}")


def print_timer(msg: str, seconds: float):
    """Stampa con timer"""
    print(f"⏱  {msg}: {seconds:.2f}s")


class IAMOrchestrator:
    """Orchestratore del sistema IAM"""

    def __init__(self):
        """Inizializza orchestratore"""
        self.timers = {}

    def check_dependencies(self):
        """Verifica dipendenze Python"""
        print_section("1. VERIFICA DIPENDENZE")

        required = ['opensearchpy', 'requests']
        missing = []

        for package in required:
            try:
                __import__(package)
                print_success(f"{package}")
            except ImportError:
                print_error(f"{package} mancante")
                missing.append(package)

        if missing:
            print(f"\n{Colors.YELLOW}Installa dipendenze:{Colors.RESET}")
            print(f"  pip install {' '.join(missing)}")
            return False

        print_success("Tutte le dipendenze presenti")
        return True

    def check_services(self):
        """Verifica servizi in esecuzione"""
        print_section("2. VERIFICA SERVIZI")

        # Check OpenSearch
        try:
            import requests
            response = requests.get(
                'http://localhost:9200',
                auth=('admin', 'admin'),
                timeout=5,
                verify=False
            )
            if response.status_code == 200:
                print_success("OpenSearch: http://localhost:9200")
            else:
                print_error("OpenSearch: non risponde")
                return False
        except Exception as e:
            print_error(f"OpenSearch: {str(e)[:50]}")
            return False

        # Check Dashboards
        try:
            response = requests.get(
                'http://localhost:5601/api/status',
                timeout=5
            )
            if response.status_code == 200:
                print_success("OpenSearch Dashboards: http://localhost:5601")
            else:
                print_error("Dashboards: non risponde")
                return False
        except Exception as e:
            print_error(f"Dashboards: {str(e)[:50]}")
            return False

        return True

    def load_data(self):
        """Carica dati in OpenSearch"""
        print_section("3. CARICAMENTO DATI DA ORACLE")

        try:
            from iam_loader import IAMRequestsLoader

            start = time.time()

            # Configurazione Oracle - MODIFICA QUESTI PARAMETRI!
            loader = IAMRequestsLoader(
                host='localhost',
                port=9200,
                oracle_host='10.22.112.70',              # ← MODIFICA
                oracle_port=1551,
                oracle_service_name='iam.griffon.local', # ← MODIFICA
                oracle_user='X1090405',                  # ← MODIFICA
                oracle_password='Fhdf!K42retwH'         # ← MODIFICA
            )

            # Crea indice
            loader.create_iam_index()

            # Leggi ultimi 30 giorni
            print_info("Lettura ultimi 30 giorni da Oracle...")
            richieste = loader.fetch_from_oracle(days=30)

            if not richieste:
                print_error("Nessun dato letto da Oracle")
                return False

            # Inserisci in bulk
            print_info(f"Inserimento {len(richieste)} richieste in OpenSearch...")
            result = loader.bulk_insert(richieste)

            elapsed = time.time() - start
            self.timers['load_data'] = elapsed

            print_success(f"Caricamento completato ({result['success']} documenti)")
            print_timer("Tempo impiegato", elapsed)

            return True
        except Exception as e:
            print_error(f"Caricamento fallito: {e}")
            return False

    def analyze_data(self):
        """Esegue analisi"""
        print_section("4. ANALISI DATI")

        try:
            from iam_analyzer import IAMAnalyzer

            start = time.time()

            analyzer = IAMAnalyzer()
            analyzer.esegui_tutte_analisi()

            elapsed = time.time() - start
            self.timers['analyze'] = elapsed

            print_timer("Analisi completata", elapsed)
            return True
        except Exception as e:
            print_error(f"Analisi fallita: {e}")
            return False

    def calculate_kpi(self):
        """Calcola KPI"""
        print_section("5. CALCOLO KPI")

        try:
            from iam_kpi_engine import KPIEngine

            start = time.time()

            engine = KPIEngine()
            kpis = engine.calcola_tutti_kpi()

            print(engine.genera_report_kpi(kpis))

            engine.esporta_kpi_json(kpis)

            elapsed = time.time() - start
            self.timers['kpi'] = elapsed

            print_timer("KPI calcolati", elapsed)
            return True
        except Exception as e:
            print_error(f"KPI falliti: {e}")
            return False

    def create_dashboard(self):
        """Crea visualizzazioni dashboard"""
        print_section("6. CREAZIONE DASHBOARD")

        try:
            from iam_dashboard_visualizations import IAMDashboardCreator

            start = time.time()

            creator = IAMDashboardCreator()
            creator.create_index_pattern()

            print_info("Creazione visualizzazioni...")
            vis_ids = creator.create_all_visualizations()

            print_info("Assembly dashboard...")
            dashboard_id = creator.create_dashboard(vis_ids)

            creator.print_instructions(dashboard_id)

            elapsed = time.time() - start
            self.timers['dashboard'] = elapsed

            print_timer("Dashboard creata", elapsed)
            return True
        except Exception as e:
            print_error(f"Dashboard fallita: {e}")
            return False

    def print_summary(self):
        """Stampa riepilogo esecuzione"""
        print_section("✓ SISTEMA PRONTO!")

        total_time = sum(self.timers.values())

        print(f"{Colors.BOLD}Tempi esecuzione:{Colors.RESET}")
        for operation, elapsed in self.timers.items():
            pct = (elapsed / total_time * 100) if total_time > 0 else 0
            bar = '█' * int(pct / 5)
            print(f"  {operation:20s}: {bar:20s} {elapsed:7.2f}s ({pct:5.1f}%)")

        print(f"\n{Colors.BOLD}Totale:{Colors.RESET} {total_time:.2f}s\n")

        print(f"{Colors.BOLD}{Colors.GREEN}📊 ACCEDI ALLA DASHBOARD:{Colors.RESET}")
        print(f"   http://localhost:5601/app/dashboards/view/iam-dashboard-main\n")

        print(f"{Colors.BOLD}🔄 AGGIORNAMENTO PERIODICO:{Colors.RESET}")
        print(f"   python iam_main.py --update\n")

    def run_full(self):
        """Esecuzione completa"""
        print_banner()

        # Verifiche
        if not self.check_dependencies():
            return False

        if not self.check_services():
            print(f"\n{Colors.YELLOW}⚠ Avvia i servizi con:{Colors.RESET}")
            print(f"   docker-compose up -d opensearch opensearch-dashboards")
            return False

        # Esecuzione
        if not self.load_data():
            return False

        if not self.analyze_data():
            return False

        if not self.calculate_kpi():
            return False

        if not self.create_dashboard():
            return False

        self.print_summary()
        return True

    def run_load_only(self):
        """Solo caricamento"""
        print_banner()
        print_section("CARICAMENTO DATI")
        return self.load_data()

    def run_analyze_only(self):
        """Solo analisi"""
        print_banner()
        print_section("ANALISI DATI")
        return self.analyze_data()

    def run_kpi_only(self):
        """Solo KPI"""
        print_banner()
        print_section("CALCOLO KPI")
        return self.calculate_kpi()

    def run_dashboard_only(self):
        """Solo dashboard"""
        print_banner()
        print_section("CREAZIONE DASHBOARD")
        return self.create_dashboard()

    def run_periodic_update(self, interval_minutes=60):
        """Aggiornamento periodico"""
        print_banner()
        print_section(f"AGGIORNAMENTO PERIODICO (ogni {interval_minutes} min)")

        counter = 1
        while True:
            print(f"\n{Colors.BOLD}Esecuzione #{counter} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.RESET}\n")

            # Ricarica dati
            self.load_data()

            # Analisi
            self.analyze_data()

            # KPI
            self.calculate_kpi()

            counter += 1

            print(f"\n{Colors.YELLOW}Prossimo aggiornamento tra {interval_minutes} minuti...{Colors.RESET}")
            print(f"(Premi Ctrl+C per fermare)\n")

            try:
                time.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                print(f"\n{Colors.GREEN}✓ Aggiornamento interrotto{Colors.RESET}")
                break


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='IAM Requests Monitoring System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{Colors.BOLD}CONFIGURAZIONE ORACLE:{Colors.RESET}
  Modifica questi parametri in iam_main.py (funzione load_data):
  - oracle_host='10.22.112.70'
  - oracle_port=1551
  - oracle_service_name='iam.griffon.local'
  - oracle_user='X1090405'
  - oracle_password='Fhdf!K42retwH'

{Colors.BOLD}EXAMPLES:{Colors.RESET}
  python iam_main.py --full              # Esecuzione completa ⭐
  python iam_main.py --load-only         # Solo caricamento da Oracle
  python iam_main.py --analyze-only      # Solo analisi
  python iam_main.py --kpi-only          # Solo KPI
  python iam_main.py --dashboard-only    # Solo dashboard
  python iam_main.py --update            # Aggiornamento periodico (ogni ora)
  python iam_main.py --update --interval 30  # Aggiornamento ogni 30 minuti

{Colors.BOLD}FIRST TIME:{Colors.RESET}
  1. Verifica che OpenSearch sia in esecuzione
  2. Configura credenziali Oracle in iam_main.py
  3. Esegui: python iam_main.py --full
  4. Apri: http://localhost:5601/app/dashboards/view/iam-dashboard-main
        """
    )

    parser.add_argument('--full', action='store_true',
                        help='Esecuzione completa (default)')
    parser.add_argument('--load-only', action='store_true',
                        help='Solo caricamento dati')
    parser.add_argument('--analyze-only', action='store_true',
                        help='Solo analisi')
    parser.add_argument('--kpi-only', action='store_true',
                        help='Solo calcolo KPI')
    parser.add_argument('--dashboard-only', action='store_true',
                        help='Solo creazione dashboard')
    parser.add_argument('--update', action='store_true',
                        help='Aggiornamento periodico')
    parser.add_argument('--interval', type=int, default=60,
                        help='Intervallo aggiornamento in minuti (default: 60)')

    args = parser.parse_args()

    orchestrator = IAMOrchestrator()

    try:
        if args.load_only:
            success = orchestrator.run_load_only()
        elif args.analyze_only:
            success = orchestrator.run_analyze_only()
        elif args.kpi_only:
            success = orchestrator.run_kpi_only()
        elif args.dashboard_only:
            success = orchestrator.run_dashboard_only()
        elif args.update:
            orchestrator.run_periodic_update(args.interval)
            success = True
        else:  # default: --full
            success = orchestrator.run_full()

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}\n⚠ Interrotto dall'utente{Colors.RESET}\n")
        sys.exit(130)
    except Exception as e:
        print_error(f"Errore: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()