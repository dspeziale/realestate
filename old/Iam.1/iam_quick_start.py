#!/usr/bin/env python3
"""
Quick Start - Configurazione e Esecuzione Rapida
=================================================

Script per configurare rapidamente il sistema IAM Analytics
Perfetto per fare bella figura! 🎉

Utilizzo:
    python iam_quick_start.py --setup       # Setup iniziale
    python iam_quick_start.py --full        # Esecuzione completa
    python iam_quick_start.py --analyze     # Solo analisi
    python iam_quick_start.py --dashboard   # Solo dashboard
    python iam_quick_start.py --report      # Solo report
"""

import argparse
import sys
import os
from datetime import datetime
from pathlib import Path


class Colors:
    """Colori per output terminale"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_banner():
    """Stampa banner intro"""
    banner = f"""
{Colors.CYAN}
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║         🚀 OPENSEARCH IAM ANALYTICS - PROFESSIONAL SYSTEM 🚀                ║
║                                                                              ║
║              Monitoraggio Professionale Richieste IAM                        ║
║              con KPI, Dashboard e Report Automatici                         ║
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


def print_success(message: str):
    """Stampa messaggio successo"""
    print(f"{Colors.GREEN}✓{Colors.RESET} {message}")


def print_error(message: str):
    """Stampa messaggio errore"""
    print(f"{Colors.RED}✗{Colors.RESET} {message}")


def print_warning(message: str):
    """Stampa messaggio avvertenza"""
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {message}")


def print_info(message: str):
    """Stampa messaggio informativo"""
    print(f"{Colors.CYAN}ℹ{Colors.RESET} {message}")


def check_dependencies():
    """Verifica dipendenze Python"""
    print_section("Verifica Dipendenze")

    required = [
        'opensearchpy',
        'oracledb',
        'requests',
        'jinja2',
        'plotly'
    ]

    missing = []
    for pkg in required:
        try:
            __import__(pkg.replace('-', '_'))
            print_success(f"{pkg}")
        except ImportError:
            print_error(f"{pkg} mancante")
            missing.append(pkg)

    if missing:
        print(f"\n{Colors.YELLOW}Installa le dipendenze mancanti con:{Colors.RESET}")
        print(f"  pip install {' '.join(missing)}")
        return False

    return True


def check_services():
    """Verifica servizi in esecuzione"""
    print_section("Verifica Servizi")

    import socket

    services = {
        'Oracle DB': ('10.22.112.70', 1551),
        'OpenSearch': ('localhost', 9200),
        'Dashboards': ('localhost', 5601)
    }

    for service, (host, port) in services.items():
        try:
            socket.create_connection((host, port), timeout=2)
            print_success(f"{service} ({host}:{port})")
        except (socket.timeout, socket.error):
            print_warning(f"{service} ({host}:{port}) - Non raggiungibile")

    return True


def show_configuration():
    """Mostra configurazione"""
    print_section("Configurazione Attuale")

    config = f"""
{Colors.BOLD}Database Oracle:{Colors.RESET}
  Host: 10.22.112.70
  Port: 1551
  Service: iam.griffon.local
  User: X1090405

{Colors.BOLD}OpenSearch:{Colors.RESET}
  Host: localhost
  Port: 9200
  Auth: admin/admin

{Colors.BOLD}Dashboards:{Colors.RESET}
  Host: localhost
  Port: 5601
  Auth: admin/admin
"""
    print(config)


def run_analysis():
    """Esegue analisi e KPI"""
    print_section("Esecuzione Analisi e KPI")

    try:
        from iam_kpi_dashboard import IamActivityAnalyzer

        print_info("Connessione ai sistemi...")
        analyzer = IamActivityAnalyzer(
            oracle_host='10.22.112.70',
            oracle_port=1551,
            oracle_service_name='iam.griffon.local',
            oracle_user='X1090405',
            oracle_password='Fhdf!K42retwH',
            os_host='localhost',
            os_port=9200
        )

        print_info("Lettura dati da Oracle (ultimi 30 giorni)...")
        richieste = analyzer.fetch_richieste(days=30)

        if not richieste:
            print_error("Nessun dato disponibile")
            return False

        print_success(f"Lette {len(richieste)} richieste")

        print_info("Creazione indice OpenSearch...")
        analyzer.create_iam_index('iam-richieste')
        print_success("Indice creato")

        print_info("Inserimento dati...")
        analyzer.insert_richieste(richieste, 'iam-richieste')
        print_success("Dati inseriti")

        print_info("Calcolo KPI...")
        analyzer.kpi_manager.calculate_all_kpis('iam-richieste')
        analyzer.kpi_manager.print_kpi_summary()

        print_info("Esecuzione analisi avanzate...")
        analyzer.analisi_richieste_per_operazione('iam-richieste', limit=10)
        analyzer.analisi_performance_per_utente('iam-richieste', limit=15)
        analyzer.analisi_trend_temporale('iam-richieste', interval='1d')

        print_success("Analisi completate")
        return True

    except Exception as e:
        print_error(f"Errore: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_dashboard():
    """Crea dashboard"""
    print_section("Creazione Dashboard Professionali")

    try:
        from iam_dashboard_creator import IamDashboardCreator

        print_info("Connessione a OpenSearch Dashboards...")
        creator = IamDashboardCreator(
            host='localhost',
            port=5601,
            username='admin',
            password='admin'
        )

        print_info("Creazione index pattern...")
        creator.create_index_pattern('iam-richieste*', 'DATA_CREAZIONE')
        print_success("Index pattern creato")

        print_info("Creazione visualizzazioni (14 visualizzazioni)...")
        vis_ids = creator.create_all_visualizations('iam-richieste*')
        print_success(f"{len(vis_ids)} visualizzazioni create")

        print_info("Creazione dashboard...")
        creator.create_dashboard(
            'iam-dashboard-main',
            'IAM System - Main Dashboard',
            vis_ids,
            'iam-richieste*'
        )
        print_success("Dashboard creato")

        print(f"\n{Colors.BOLD}📊 ACCEDI ALLA DASHBOARD:{Colors.RESET}")
        print(f"   {Colors.CYAN}http://localhost:5601/app/dashboards/view/iam-dashboard-main{Colors.RESET}")

        return True

    except Exception as e:
        print_error(f"Errore: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_report():
    """Genera report"""
    print_section("Generazione Report Professionali")

    try:
        from opensearchpy import OpenSearch
        from iam_report_generator import IamReportGenerator

        print_info("Connessione a OpenSearch...")
        os_client = OpenSearch(
            hosts=[{'host': 'localhost', 'port': 9200}],
            http_auth=('admin', 'admin'),
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
            timeout=30
        )
        print_success("Connesso")

        print_info("Creazione generatore report...")
        generator = IamReportGenerator(os_client)

        print_info("Estrazione dati (ultimi 30 giorni)...")
        generator.fetch_dashboard_data('iam-richieste', days=30)
        print_success("Dati estratti")

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        print_info("Generazione HTML report...")
        html_file = generator.generate_html_report(f'iam_report_{timestamp}.html')
        print_success(f"Report HTML: {html_file}")

        print_info("Generazione CSV export...")
        csv_file = generator.generate_csv_export(f'iam_data_{timestamp}.csv')
        print_success(f"CSV export: {csv_file}")

        print(f"\n{Colors.BOLD}📄 FILE GENERATI:{Colors.RESET}")
        print(f"   HTML: {Colors.GREEN}{html_file}{Colors.RESET}")
        print(f"   CSV:  {Colors.GREEN}{csv_file}{Colors.RESET}")

        return True

    except Exception as e:
        print_error(f"Errore: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_full():
    """Esecuzione completa"""
    print_banner()

    start_time = datetime.now()

    if not check_dependencies():
        return 1

    check_services()
    show_configuration()

    steps = [
        ("Analisi e KPI", run_analysis),
        ("Dashboard", run_dashboard),
        ("Report", run_report)
    ]

    results = []
    for step_name, step_func in steps:
        result = step_func()
        results.append((step_name, result))
        if not result:
            print_warning(f"❌ {step_name} fallito - Continuando...")

    # Riepilogo finale
    print_section("Riepilogo Esecuzione")

    for step_name, result in results:
        status = f"{Colors.GREEN}✓ Completato{Colors.RESET}" if result else f"{Colors.RED}✗ Fallito{Colors.RESET}"
        print(f"  {step_name}: {status}")

    elapsed = (datetime.now() - start_time).total_seconds()

    print(f"\n{Colors.BOLD}Tempo totale: {Colors.CYAN}{elapsed:.1f}s{Colors.RESET}")

    if all(r for _, r in results):
        print_banner()
        print(
            f"\n{Colors.GREEN}{Colors.BOLD}╔════════════════════════════════════════════════════════════════════════════════╗")
        print(f"║  ✨ SISTEMA PRONTO! ✨                                                           ║")
        print(f"║                                                                                ║")
        print(f"║  Dashboard:  http://localhost:5601/app/dashboards/view/iam-dashboard-main    ║")
        print(f"║  Discover:   http://localhost:5601/app/discover                              ║")
        print(f"╚════════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}")
        return 0
    else:
        print_error("Alcuni step hanno fallito")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description='Quick Start - OpenSearch IAM Analytics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi di utilizzo:
  python iam_quick_start.py --setup        Verifica setup iniziale
  python iam_quick_start.py --full         Esecuzione completa
  python iam_quick_start.py --analyze      Solo analisi
  python iam_quick_start.py --dashboard    Solo dashboard
  python iam_quick_start.py --report       Solo report
  python iam_quick_start.py --check        Verifica servizi
        """
    )

    parser.add_argument('--setup', action='store_true', help='Setup iniziale')
    parser.add_argument('--full', default="--full",action='store_true', help='Esecuzione completa')
    parser.add_argument('--analyze', action='store_true', help='Solo analisi')
    parser.add_argument('--dashboard', action='store_true', help='Solo dashboard')
    parser.add_argument('--report', action='store_true', help='Solo report')
    parser.add_argument('--check', action='store_true', help='Verifica servizi')

    args = parser.parse_args()

    if args.setup:
        check_dependencies()
        check_services()
        show_configuration()
        return 0

    elif args.full:
        return run_full()

    elif args.analyze:
        print_banner()
        return 0 if run_analysis() else 1

    elif args.dashboard:
        print_banner()
        return 0 if run_dashboard() else 1

    elif args.report:
        print_banner()
        return 0 if run_report() else 1

    elif args.check:
        print_banner()
        check_dependencies()
        check_services()
        return 0

    else:
        # Default: mostra help
        print_banner()
        print("\n" + "=" * 80)
        print("Uso: python iam_quick_start.py [opzione]")
        print("=" * 80)
        print("\nOpzioni disponibili:")
        print("  --setup        Verifica dipendenze e configurazione")
        print("  --full         Esecuzione completa (analisi + dashboard + report)")
        print("  --analyze      Solo analisi e KPI")
        print("  --dashboard    Solo creazione dashboard")
        print("  --report       Solo generazione report")
        print("  --check        Verifica servizi in esecuzione")
        print("  --help         Mostra questo aiuto")
        print("\nEsempi:")
        print("  python iam_quick_start.py --full")
        print("  python iam_quick_start.py --check")
        print("\n" + "=" * 80)
        return 0


if __name__ == "__main__":
    sys.exit(main())