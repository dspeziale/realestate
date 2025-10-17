"""
SOC Orchestrator - Script di Setup Completo
==============================================

Orchestra l'intero setup SOC:
1. Genera i log
2. Inserisce in OpenSearch
3. Crea le visualizzazioni
4. Genera il dashboard

Eseguire questo script dopo aver fatto:
  docker-compose up -d
"""

import subprocess
import time
import sys
import json
from typing import Tuple


class SOCOrchestrator:
    """Orchestratore del setup SOC completo"""

    def __init__(self):
        self.opensearch_url = "http://localhost:9200"
        self.dashboards_url = "http://localhost:5601"
        self.step = 0

    def print_header(self, title: str):
        """Stampa intestazione"""
        self.step += 1
        print("\n" + "=" * 70)
        print(f"STEP {self.step}: {title}")
        print("=" * 70 + "\n")

    def print_section(self, title: str):
        """Stampa sottosezione"""
        print(f"\n🔹 {title}")
        print("-" * 50)

    def check_opensearch(self) -> bool:
        """Verifica che OpenSearch sia attivo"""
        print("🔍 Verifica OpenSearch...")
        try:
            import requests
            response = requests.get(
                f"{self.opensearch_url}/_cluster/health",
                auth=('admin', 'admin'),
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                print(f"✓ OpenSearch attivo")
                print(f"  Cluster: {data['cluster_name']}")
                print(f"  Status: {data['status']}")
                return True
        except Exception as e:
            print(f"✗ OpenSearch non raggiungibile")
            print(f"  Errore: {e}")
            return False

    def check_dashboards(self) -> bool:
        """Verifica che OpenSearch Dashboards sia attivo"""
        print("\n🔍 Verifica OpenSearch Dashboards...")
        try:
            import requests
            response = requests.get(
                f"{self.dashboards_url}/api/status",
                auth=('admin', 'admin'),
                headers={'osd-xsrf': 'true'},
                timeout=5
            )
            if response.status_code == 200:
                print(f"✓ OpenSearch Dashboards attivo")
                return True
        except Exception as e:
            print(f"✗ OpenSearch Dashboards non raggiungibile")
            print(f"  Errore: {e}")
            return False

    def verify_environment(self) -> bool:
        """Verifica ambiente"""
        self.print_header("Verifica Ambiente")

        checks = [
            self.check_opensearch(),
            self.check_dashboards()
        ]

        if not all(checks):
            print("\n❌ Setup non può procedere!")
            print("\nAvvia OpenSearch con:")
            print("  docker-compose up -d")
            print("\nPoi riprova questo script.")
            return False

        print("\n✅ Ambiente pronto!")
        return True

    def run_log_generator(self) -> bool:
        """Esegue generatore log"""
        self.print_header("Generazione Log da Fonti Multiple")

        self.print_section("Importazione moduli...")
        try:
            from opensearchpy import OpenSearch, helpers
            print("✓ opensearch-py importato correttamente")
        except ImportError:
            print("✗ opensearch-py non installato")
            print("  Installa con: pip install opensearch-py")
            return False

        self.print_section("Generazione dati...")
        try:
            # Import locale dello script
            import importlib.util
            spec = importlib.util.spec_from_file_location("soc_log_generator", "soc_log_generator.py")
            if spec is None:
                print("✗ Impossibile trovare soc_log_generator.py")
                return False

            generator_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(generator_module)

            # Esegui
            print("▶ Avvio generazione log...")
            generator_module.main()
            return True

        except FileNotFoundError:
            print("✗ File 'soc_log_generator.py' non trovato")
            print("  Assicurati di avere lo script nella stessa cartella")
            return False
        except Exception as e:
            print(f"✗ Errore durante generazione: {e}")
            return False

    def verify_data_inserted(self) -> Tuple[bool, dict]:
        """Verifica che i dati siano stati inseriti"""
        self.print_section("Verifica inserimento dati...")
        try:
            import requests
            response = requests.get(
                f"{self.opensearch_url}/_cat/indices?format=json",
                auth=('admin', 'admin')
            )
            indices = response.json()

            soc_indices = {
                'soc-webserver-logs': 0,
                'soc-firewall-logs': 0,
                'soc-router-logs': 0,
                'soc-proxy-logs': 0
            }

            for idx in indices:
                if idx['index'] in soc_indices:
                    soc_indices[idx['index']] = int(idx['docs.count'])

            total_docs = sum(soc_indices.values())

            print(f"\nIndici creati: {len([v for v in soc_indices.values() if v > 0])}/4")
            for index_name, count in soc_indices.items():
                if count > 0:
                    print(f"  ✓ {index_name}: {count:,} documenti")
                else:
                    print(f"  ✗ {index_name}: 0 documenti")

            if total_docs > 0:
                print(f"\n✅ Totale: {total_docs:,} documenti inseriti")
                return True, soc_indices
            else:
                print(f"\n❌ Nessun documento trovato")
                return False, {}

        except Exception as e:
            print(f"✗ Errore: {e}")
            return False, {}

    def run_dashboard_creator(self) -> bool:
        """Esegue creator dashboard"""
        self.print_header("Creazione Visualizzazioni e Dashboard")

        self.print_section("Setup dashboard creator...")
        try:
            import requests
            print("✓ requests disponibile")
        except ImportError:
            print("✗ requests non installato")
            print("  Installa con: pip install requests")
            return False

        self.print_section("Generazione visualizzazioni...")
        try:
            # Import locale dello script
            import importlib.util
            spec = importlib.util.spec_from_file_location("soc_dashboard_creator",
                                                          "../../OpenSearch/SOC/soc_dashboard_creator.py")
            if spec is None:
                print("✗ Impossibile trovare soc_dashboard_creator.py")
                return False

            creator_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(creator_module)

            # Esegui
            print("▶ Avvio creazione dashboard...")
            creator_module.main()
            return True

        except FileNotFoundError:
            print("✗ File 'soc_dashboard_creator.py' non trovato")
            print("  Assicurati di avere lo script nella stessa cartella")
            return False
        except Exception as e:
            print(f"✗ Errore durante creazione dashboard: {e}")
            return False

    def print_completion_summary(self, indices_data: dict):
        """Stampa riassunto completamento"""
        self.print_header("Setup Completato! ✅")

        print("📊 DATI INSERITI:")
        total = sum(indices_data.values())
        for idx, count in indices_data.items():
            pct = (count / total * 100) if total > 0 else 0
            print(f"  • {idx}")
            print(f"    {count:,} log ({pct:.1f}%)")

        print("\n" + "=" * 70)
        print("🎯 ACCEDI ALLE VISUALIZZAZIONI:")
        print("=" * 70)

        print(f"\n🌐 OpenSearch Dashboards:")
        print(f"   👉 http://localhost:5601")
        print(f"\n   o direttamente al dashboard SOC:")
        print(f"   👉 http://localhost:5601/app/dashboards?title=SOC")

        print("\n" + "=" * 70)
        print("📚 VISUALIZZAZIONI DISPONIBILI:")
        print("=" * 70)

        visualizations = {
            "DDoS Detection": [
                "Top 10 IP Attaccanti",
                "Timeline Connessioni DENY",
                "Porte Bersagliate"
            ],
            "Data Exfiltration": [
                "Categorie Bloccate (C2/Malware)",
                "IP Interni con Accessi Bloccati",
                "Trend Accessi Bloccati",
                "Top Domini Bloccati"
            ],
            "Web Attack": [
                "Timeline Attacchi Rilevati",
                "Status Code Distribution",
                "Percorsi Attaccati",
                "User Agent Attacker",
                "Response Time Trend"
            ],
            "Insider Threat": [
                "Timeline IP Compromesso (10.0.1.50)",
                "Percorsi Acceduti (Admin/Config)",
                "IP Interni Sospetti"
            ],
            "Router Anomaly": [
                "CPU/Memory Trend",
                "Tipi di Alert",
                "Warning Timeline"
            ],
            "Monitoraggio SOC": [
                "Totale Incidenti (Ultimi 60m)",
                "Incidenti per Fonte",
                "Timeline Attività Complessiva",
                "Volume Log per Fonte"
            ]
        }

        for category, vizzes in visualizations.items():
            print(f"\n🎯 {category}:")
            for viz in vizzes:
                print(f"   ✓ {viz}")

        print("\n" + "=" * 70)
        print("💡 PROSSIMI STEP:")
        print("=" * 70)

        steps = [
            "Apri il dashboard SOC in OpenSearch Dashboards",
            "Osserva i 5 case study nel dettaglio",
            "Filtra per timeframe diversi (1h, 24h, 7d)",
            "Clicca sulle visualizzazioni per drill-down",
            "Usa Discover per analisi approfondite",
            "Crea alert rules per i KPI critici"
        ]

        for i, step in enumerate(steps, 1):
            print(f"  {i}. {step}")

        print("\n" + "=" * 70)
        print("🔍 QUERY VELOCI NEL DEV TOOLS:")
        print("=" * 70)

        queries = {
            "Tutti gli incidenti": "GET soc-*/_search\n{ \"query\": { \"term\": { \"is_suspicious\": true } } }",
            "IP compromesso": "GET soc-*/_search\n{ \"query\": { \"term\": { \"client_ip\": \"10.0.1.50\" } } }",
            "Accessi bloccati": "GET soc-proxy-logs/_search\n{ \"query\": { \"term\": { \"is_blocked\": true } } }",
            "Firewall DENY": "GET soc-firewall-logs/_search\n{ \"query\": { \"term\": { \"action\": \"DENY\" } } }"
        }

        for title, query in queries.items():
            print(f"\n📝 {title}:")
            print(f"   {query}")

        print("\n" + "=" * 70)
        print("⚠️  TROUBLESHOOTING:")
        print("=" * 70)

        troubleshooting = {
            "Dashboard vuota": [
                "Verifica che i dati siano in OpenSearch: GET _cat/indices | grep soc",
                "Ricrea gli index pattern in Management",
                "Controlla che timestamp sia in formato ISO"
            ],
            "Visualizzazioni non appaiono": [
                "Attendi 10-15 secondi per il caricamento",
                "Refresha la pagina (F5)",
                "Verifica la console del browser (F12)"
            ],
            "Connessione fallita": [
                "Riavvia i container: docker-compose restart",
                "Verifica che porte 9200 e 5601 siano aperte",
                "Controlla i log: docker-compose logs opensearch"
            ]
        }

        for issue, solutions in troubleshooting.items():
            print(f"\n❓ {issue}:")
            for solution in solutions:
                print(f"   • {solution}")

        print("\n" + "=" * 70)
        print("✅ SETUP COMPLETATO CON SUCCESSO!")
        print("=" * 70)
        print("\n🎉 Inizia a investigare i tuoi incidenti di sicurezza!\n")

    def run(self) -> bool:
        """Esegui orchestrazione completa"""
        print("\n" + "🔰" * 35)
        print("SOC ORCHESTRATOR - Setup Completo SOC")
        print("🔰" * 35)

        # Step 1: Verifica ambiente
        if not self.verify_environment():
            return False

        # Step 2: Genera log
        print("\n⏳ Attendi il completamento della generazione log...")
        print("   (questo potrebbe richiedere 1-2 minuti)")
        if not self.run_log_generator():
            print("\n❌ Generazione log fallita!")
            return False

        # Step 3: Verifica dati
        time.sleep(2)
        data_ok, indices_data = self.verify_data_inserted()
        if not data_ok:
            print("\n❌ Dati non inseriti correttamente!")
            return False

        # Step 4: Crea dashboard
        print("\n⏳ Attendi creazione dashboard...")
        print("   (questo potrebbe richiedere 1-2 minuti)")
        if not self.run_dashboard_creator():
            print("\n❌ Creazione dashboard fallita!")
            return False

        # Step 5: Riassunto
        self.print_completion_summary(indices_data)
        return True


def main():
    """Main"""
    orchestrator = SOCOrchestrator()

    try:
        success = orchestrator.run()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrotto dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Errore non gestito: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()