# config.py
import os
import json
import uuid

# ==================== CONFIGURAZIONE ====================
DB_FILE = "instance/network_probe.db"
LOG_DIR = "logs"
OUI_FILE = "oui/oui.txt"
OUI_URL = "https://standards-oui.ieee.org/oui.txt"
CONFIG_FILE = "config.json"

# Packet Sniffing
SNIFFING_ENABLED = True
SNIFFING_INTERFACE = 'Wi-Fi'
SNIFFING_FILTER = "tcp port 80"
SNIFFING_MAX_PACKETS_PER_BATCH = 100
SNIFFING_BATCH_INTERVAL = 30

# Variabile globale per configurazione sonda
PROBE_CONFIG = None


def create_default_config():
    """Crea un file di configurazione JSON di default se non esiste"""
    config = {
        "probe": {
            "id": str(uuid.uuid4()).upper(),
            "nome": "Sonda-" + str(uuid.uuid4())[:8].upper(),
            "posizione_geografica": "Milano, Italia",
            "latitudine": 45.4642,
            "longitudine": 9.1900,
            "referente_nome": "Mario Rossi",
            "referente_email": "mario.rossi@example.com",
            "referente_telefono": "+39 123 456 7890"
        },
        "scan": {
            "target_network": "192.168.1.0/24",
            "scan_interval": 600,
            "oui_update_days": 7
        },
        "sniffing": {
            "enabled": True,
            "interface": "Wi-Fi",
            "filter": "tcp port 80",
            "max_packets_per_batch": 100,
            "batch_interval": 30
        }
    }

    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

    log(f"File di configurazione creato: {CONFIG_FILE}")
    log(f"ID Sonda generato: {config['probe']['id']}")
    log(f"Nome Sonda generato: {config['probe']['nome']}")
    log("ATTENZIONE: Modifica il file con le informazioni corrette della sonda!")


def load_probe_config():
    """Carica la configurazione della sonda dal file JSON"""
    global PROBE_CONFIG

    if not os.path.exists(CONFIG_FILE):
        create_default_config()

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        if 'probe' not in config:
            log("ERRORE: Sezione 'probe' non trovata nel file di configurazione")
            raise ValueError("Configurazione sonda non valida")

        probe = config['probe']

        # Validazione campi obbligatori
        required_fields = ['id', 'nome', 'posizione_geografica', 'latitudine',
                           'longitudine', 'referente_nome', 'referente_email',
                           'referente_telefono']

        for field in required_fields:
            if field not in probe:
                log(f"ERRORE: Campo '{field}' mancante nella configurazione")
                raise ValueError(f"Campo '{field}' mancante")

        # Configurazioni di scan con valori di default
        scan_config = config.get('scan', {})
        target_network = scan_config.get('target_network', '192.168.1.0/24')
        scan_interval = scan_config.get('scan_interval', 600)
        oui_update_days = scan_config.get('oui_update_days', 7)

        # Configurazioni di sniffing con valori di default
        sniffing_config = config.get('sniffing', {})
        sniffing_enabled = sniffing_config.get('enabled', True)
        sniffing_interface = sniffing_config.get('interface', 'Wi-Fi')
        sniffing_filter = sniffing_config.get('filter', 'tcp port 80')
        sniffing_max_packets = sniffing_config.get('max_packets_per_batch', 100)
        sniffing_batch_interval = sniffing_config.get('batch_interval', 30)

        PROBE_CONFIG = {
            # Informazioni sonda
            'id': probe['id'],
            'nome': probe['nome'],
            'posizione_geografica': probe['posizione_geografica'],
            'latitudine': probe['latitudine'],
            'longitudine': probe['longitudine'],
            'referente_nome': probe['referente_nome'],
            'referente_email': probe['referente_email'],
            'referente_telefono': probe['referente_telefono'],

            # Configurazioni scan
            'target_network': target_network,
            'scan_interval': scan_interval,
            'oui_update_days': oui_update_days,

            # Configurazioni sniffing
            'sniffing_enabled': sniffing_enabled,
            'sniffing_interface': sniffing_interface,
            'sniffing_filter': sniffing_filter,
            'sniffing_max_packets_per_batch': sniffing_max_packets,
            'sniffing_batch_interval': sniffing_batch_interval
        }

        log(f"Configurazione caricata - Sonda ID: {PROBE_CONFIG['id']}")
        log(f"Nome: {PROBE_CONFIG['nome']}")
        log(f"Posizione: {PROBE_CONFIG['posizione_geografica']} ({PROBE_CONFIG['latitudine']}, {PROBE_CONFIG['longitudine']})")
        log(f"Referente: {PROBE_CONFIG['referente_nome']} ({PROBE_CONFIG['referente_email']})")
        log(f"Rete target: {PROBE_CONFIG['target_network']}")
        log(f"Intervallo scan: {PROBE_CONFIG['scan_interval']} secondi")
        log(f"Aggiornamento OUI ogni: {PROBE_CONFIG['oui_update_days']} giorni")

        return PROBE_CONFIG

    except json.JSONDecodeError as e:
        log(f"ERRORE: File di configurazione JSON non valido: {e}")
        raise
    except Exception as e:
        log(f"ERRORE durante il caricamento della configurazione: {e}")
        raise


def get_probe_config():
    """Restituisce la configurazione della sonda (per uso in altri thread)"""
    if PROBE_CONFIG is None:
        raise ValueError("Configurazione sonda non caricata. Chiamare load_probe_config() prima.")
    return PROBE_CONFIG.copy()


def get_scan_config():
    """Restituisce solo le configurazioni di scan"""
    probe_config = get_probe_config()
    return {
        'target_network': probe_config['target_network'],
        'scan_interval': probe_config['scan_interval'],
        'oui_update_days': probe_config['oui_update_days']
    }


def get_sniffing_config():
    """Restituisce solo le configurazioni di sniffing"""
    probe_config = get_probe_config()
    return {
        'enabled': probe_config['sniffing_enabled'],
        'interface': probe_config['sniffing_interface'],
        'filter': probe_config['sniffing_filter'],
        'max_packets_per_batch': probe_config['sniffing_max_packets_per_batch'],
        'batch_interval': probe_config['sniffing_batch_interval']
    }


def log(message):
    """Scrive log su file e console"""
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_path = os.path.join(LOG_DIR, "probe.log")
    with open(log_path, "a") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"[{timestamp}] {message}")