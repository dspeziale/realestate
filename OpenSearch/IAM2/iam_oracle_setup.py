"""
IAM Oracle Setup - Gestione Thin Mode vs Thick Mode
======================================================

Script per configurare automaticamente oracledb in modalità Thin (default)
o Thick Mode se Oracle Client è disponibile.

Thin Mode: ✅ No dipendenze esterne, più semplice
Thick Mode: ⚡ Più performante, richiede Oracle Client

Python 3.13+
"""

import oracledb
import platform
import subprocess
import sys
import os
import json
from pathlib import Path
from typing import Dict, Tuple


class OracleSetupManager:
    """Gestisce setup Oracle oracledb - Thin vs Thick Mode"""

    def __init__(self):
        self.os_type = platform.system()
        self.python_version = sys.version
        self.oracledb_version = oracledb.__version__

    def verifica_oracle_client(self) -> Tuple[bool, str]:
        """
        Verifica se Oracle Client è installato

        Returns:
            (installato: bool, percorso: str)
        """
        if self.os_type == "Linux":
            return self._verifica_linux()
        elif self.os_type == "Darwin":
            return self._verifica_macos()
        elif self.os_type == "Windows":
            return self._verifica_windows()
        else:
            return False, f"OS non supportato: {self.os_type}"

    def _verifica_linux(self) -> Tuple[bool, str]:
        """Verifica Oracle Client su Linux"""
        try:
            # Controlla variabile ambiente
            oracle_home = os.environ.get('ORACLE_HOME', '')
            if oracle_home:
                client_path = Path(oracle_home) / 'lib'
                if client_path.exists():
                    return True, str(oracle_home)

            # Cerca in locazioni comuni
            common_paths = [
                '/opt/oracle/instantclient_21_12',
                '/opt/oracle/instantclient',
                '/usr/lib/oracle',
                f'/home/{os.getenv("USER")}/oracle/instantclient'
            ]

            for path in common_paths:
                if Path(path).exists():
                    return True, path

            # Prova con comando
            result = subprocess.run(['which', 'sqlplus'], capture_output=True)
            if result.returncode == 0:
                return True, result.stdout.decode().strip()

            return False, "Oracle Client non trovato"

        except Exception as e:
            return False, f"Errore verifica Linux: {e}"

    def _verifica_macos(self) -> Tuple[bool, str]:
        """Verifica Oracle Client su macOS"""
        try:
            oracle_home = os.environ.get('ORACLE_HOME', '')
            if oracle_home:
                client_path = Path(oracle_home) / 'lib'
                if client_path.exists():
                    return True, str(oracle_home)

            # Controlla Homebrew
            result = subprocess.run(['brew', '--prefix', 'instantclient'],
                                   capture_output=True)
            if result.returncode == 0:
                return True, result.stdout.decode().strip()

            return False, "Oracle Client non trovato"

        except Exception as e:
            return False, f"Errore verifica macOS: {e}"

    def _verifica_windows(self) -> Tuple[bool, str]:
        """Verifica Oracle Client su Windows"""
        try:
            # Controlla variabile ambiente
            oracle_home = os.environ.get('ORACLE_HOME', '')
            if oracle_home:
                client_path = Path(oracle_home) / 'bin'
                if client_path.exists():
                    return True, str(oracle_home)

            # Cerca in locazioni comuni
            common_paths = [
                'C:\\oracle\\instantclient_21_12',
                'C:\\oracle\\instantclient',
                'C:\\app\\oracle\\instantclient_21_12',
                'C:\\Program Files\\Oracle\\instantclient'
            ]

            for path in common_paths:
                if Path(path).exists():
                    return True, path

            # Controlla Registry (Windows)
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                    r'SOFTWARE\Oracle')
                value, _ = winreg.QueryValueEx(key, 'ORACLE_HOME')
                return True, value
            except:
                pass

            return False, "Oracle Client non trovato"

        except Exception as e:
            return False, f"Errore verifica Windows: {e}"

    def configura_thin_mode(self) -> bool:
        """
        Configura oracledb in THIN MODE (default, no dipendenze)

        ✅ Vantaggi:
        - Nessuna dipendenza esterna
        - Setup semplice
        - Funziona ovunque Python è installato
        - Adatto per container/cloud

        ❌ Svantaggi:
        - Leggermente più lento
        - Meno feature avanzate

        Returns:
            True se successo
        """
        try:
            # Thin mode è il default di oracledb 2.0+
            # Non serve configurare nulla, funziona così:

            print("\n" + "=" * 70)
            print("ORACLE - CONFIGURAZIONE THIN MODE")
            print("=" * 70)

            print("\n✅ Thin Mode Attivo (Default)")
            print("\nCaratteristiche:")
            print("  • Nessuna dipendenza esterna")
            print("  • Nessuna Oracle Client library necessaria")
            print("  • Funziona in container Docker")
            print("  • Funziona in ambienti cloud (AWS, Azure, GCP)")
            print("  • Setup semplice e veloce")

            print("\n🔧 Configurazione Python:")
            print("  import oracledb")
            print("  # Automaticamente in thin mode!")

            print("\n📝 Connessione:")
            print("  connection = oracledb.connect(")
            print("      user='username',")
            print("      password='password',")
            print("      dsn='hostname:1521/service_name'")
            print("  )")

            return True

        except Exception as e:
            print(f"✗ Errore configurazione thin mode: {e}")
            return False

    def configura_thick_mode(self, oracle_home: str) -> bool:
        """
        Configura oracledb in THICK MODE (con Oracle Client)

        ✅ Vantaggi:
        - Più performante
        - Accesso a feature avanzate
        - Supporto per Advanced Queuing
        - Migliore per alte performance

        ❌ Svantaggi:
        - Richiede Oracle Client installato
        - Setup più complesso
        - Non funziona in container senza Oracle Client
        - Più pesante

        Args:
            oracle_home: Percorso ORACLE_HOME

        Returns:
            True se successo
        """
        try:
            print("\n" + "=" * 70)
            print("ORACLE - CONFIGURAZIONE THICK MODE")
            print("=" * 70)

            print(f"\n✅ Oracle Client Trovato: {oracle_home}")

            # Configura thick mode
            oracledb.init_oracle_client(lib_dir=oracle_home)

            print("\n✅ Thick Mode Configurato")
            print("\nCaratteristiche:")
            print("  • Utilizza Oracle Client libraries")
            print("  • Più performante")
            print("  • Accesso a feature avanzate")
            print("  • Supporto completo Oracle")

            print(f"\n📍 Oracle Home: {oracle_home}")
            print(f"🐍 Python: {sys.version.split()[0]}")
            print(f"📦 oracledb: {oracledb.__version__}")

            return True

        except Exception as e:
            print(f"\n✗ Errore configurazione thick mode: {e}")
            print("  → Ricaduta in THIN MODE (default)")
            return False

    def crea_config_file(self, output_path: str = 'oracle_setup_config.json'):
        """Genera file di configurazione per riutilizzo"""
        config = {
            'os': self.os_type,
            'python_version': self.python_version.split()[0],
            'oracledb_version': self.oracledb_version,
            'oracle_client_installed': False,
            'oracle_client_path': '',
            'mode': 'thin',
            'note': 'Generato automaticamente'
        }

        client_installed, client_path = self.verifica_oracle_client()
        config['oracle_client_installed'] = client_installed
        config['oracle_client_path'] = client_path
        config['mode'] = 'thick' if client_installed else 'thin'

        with open(output_path, 'w') as f:
            json.dump(config, f, indent=2)

        return config

    def stampa_info_sistema(self):
        """Stampa informazioni sistema"""
        print("\n" + "=" * 70)
        print("INFORMAZIONI SISTEMA")
        print("=" * 70)

        print(f"\n🖥️  OS: {self.os_type}")
        print(f"🐍 Python: {sys.version.split()[0]}")
        print(f"📦 oracledb: {self.oracledb_version}")

        client_installed, client_path = self.verifica_oracle_client()
        print(f"\n🔍 Oracle Client:")
        if client_installed:
            print(f"  ✅ Installato")
            print(f"  📍 Percorso: {client_path}")
            print(f"  💾 Modalità: THICK MODE (consigliato)")
        else:
            print(f"  ❌ Non installato")
            print(f"  💾 Modalità: THIN MODE (default)")

    def test_connessione(self, config: Dict) -> bool:
        """
        Testa connessione a Oracle

        Args:
            config: Dizionario con host, port, service, user, password

        Returns:
            True se connessione riuscita
        """
        try:
            print("\n🔗 Test Connessione...")

            dsn = oracledb.makedsn(
                config['host'],
                config['port'],
                service_name=config['service_name']
            )

            connection = oracledb.connect(
                user=config['user'],
                password=config['password'],
                dsn=dsn
            )

            cursor = connection.cursor()
            cursor.execute('SELECT 1 FROM DUAL')
            result = cursor.fetchone()

            connection.close()

            if result:
                print("✅ Connessione OK")
                return True
            else:
                print("✗ Connessione fallita")
                return False

        except Exception as e:
            print(f"✗ Errore connessione: {e}")
            return False


# ============================================================================
# FUNZIONI DI SETUP
# ============================================================================

def setup_automatico():
    """Setup automatico con rilevamento modalità"""
    manager = OracleSetupManager()

    # 1. Info sistema
    manager.stampa_info_sistema()

    # 2. Verifica Oracle Client
    client_installed, client_path = manager.verifica_oracle_client()

    # 3. Configura modalità
    if client_installed:
        print("\n" + "=" * 70)
        print("🔄 Configurazione Thick Mode...")
        print("=" * 70)
        manager.configura_thick_mode(client_path)
    else:
        print("\n" + "=" * 70)
        print("🔄 Configurazione Thin Mode (default)...")
        print("=" * 70)
        manager.configura_thin_mode()

    # 4. Genera config file
    config = manager.crea_config_file()

    print("\n" + "=" * 70)
    print("✅ SETUP COMPLETATO")
    print("=" * 70)
    print(f"\n📋 Configurazione salvata: oracle_setup_config.json")
    print(json.dumps(config, indent=2))

    return manager


def setup_modalita_specifica(modalita: str):
    """Setup per modalità specifica"""
    manager = OracleSetupManager()

    if modalita.lower() == 'thin':
        manager.configura_thin_mode()
    elif modalita.lower() == 'thick':
        client_installed, client_path = manager.verifica_oracle_client()
        if client_installed:
            manager.configura_thick_mode(client_path)
        else:
            print("❌ Oracle Client non trovato")
            print("Ricaduta in THIN MODE")
            manager.configura_thin_mode()
    else:
        print(f"❌ Modalità non riconosciuta: {modalita}")
        print("Opzioni: 'thin' o 'thick'")


# ============================================================================
# ISTRUZIONI DI INTEGRAZIONE
# ============================================================================

def get_setup_code() -> str:
    """Ritorna codice da aggiungere a iam_opensearch_dashboard.py"""
    return '''
# ==== AGGIUNGERE ALL'INIZIO DI iam_opensearch_dashboard.py ====

import oracledb

# Configurazione automatica Oracle - Thin/Thick Mode
try:
    # Prova thick mode (con Oracle Client)
    oracledb.init_oracle_client()
    print("✓ Oracle: THICK MODE (con Oracle Client)")
except Exception:
    # Ricaduta a thin mode (no dipendenze)
    print("✓ Oracle: THIN MODE (no dipendenze esterne)")

# ================================================================
    '''


# ============================================================================
# ESECUZIONE
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Oracle Setup Manager')
    parser.add_argument('--mode', choices=['auto', 'thin', 'thick'],
                       default='auto',
                       help='Setup automatico (auto), Thin (thin), o Thick (thick)')
    parser.add_argument('--test', action='store_true',
                       help='Test connessione Oracle')
    parser.add_argument('--info', action='store_true',
                       help='Mostra informazioni sistema')

    args = parser.parse_args()

    if args.info:
        manager = OracleSetupManager()
        manager.stampa_info_sistema()
    elif args.mode == 'auto':
        manager = setup_automatico()
    else:
        setup_modalita_specifica(args.mode)

    if args.test:
        print("\n🔍 TEST CONNESSIONE")
        print("Inserisci credenziali Oracle:")
        host = input("Host: ")
        port = input("Port (default 1521): ") or "1521"
        service = input("Service Name: ")
        user = input("Username: ")
        password = input("Password: ")

        manager = OracleSetupManager()
        config = {
            'host': host,
            'port': int(port),
            'service_name': service,
            'user': user,
            'password': password
        }
        manager.test_connessione(config)

    print("\n💡 INTEGRAZIONE IN iam_opensearch_dashboard.py:")
    print(get_setup_code())