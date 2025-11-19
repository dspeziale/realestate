import os
import sqlite3
import subprocess
import time
import datetime
import urllib.request
import xml.etree.ElementTree as ET
import json
import importlib.util
import uuid
import threading
import base64

import whois

# ==================== CONFIGURAZIONE ====================
DB_FILE = "instance/network_probe.db"
LOG_DIR = "logs"
OUI_FILE = "oui/oui.txt"
OUI_URL = "https://standards-oui.ieee.org/oui.txt"
TARGET_NETWORK = "192.168.1.0/24"
SCAN_INTERVAL = 600  # secondi tra scansioni
OUI_UPDATE_DAYS = 7  # aggiorna OUI ogni N giorni
CONFIG_FILE = "probe_config.json"
SNIFFING_ENABLED = True  # Abilita/disabilita packet capture
SNIFFING_INTERFACE = 'Wi-Fi'  # None = auto-detect, oppure nome specifico (es: "eth0", "Wi-Fi")
SNIFFING_FILTER = "tcp port 80"  # Filtro BPF (es: "tcp port 80" o "host 192.168.1.1")
SNIFFING_MAX_PACKETS_PER_BATCH = 100  # Massimo pacchetti da salvare per batch
SNIFFING_BATCH_INTERVAL = 30  # Secondi tra salvataggi batch

# ==================== INIZIALIZZAZIONE ====================
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Variabile globale per configurazione sonda
PROBE_CONFIG = {}

# Variabili globali per packet sniffing
SNIFFING_SESSION_ID = None
SNIFFING_THREAD = None
SNIFFING_STOP_FLAG = threading.Event()
PACKET_BUFFER = []
PACKET_BUFFER_LOCK = threading.Lock()


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

        PROBE_CONFIG = {
            'id': probe['id'],
            'nome': probe['nome'],
            'posizione_geografica': probe['posizione_geografica'],
            'latitudine': probe['latitudine'],
            'longitudine': probe['longitudine'],
            'referente_nome': probe['referente_nome'],
            'referente_email': probe['referente_email'],
            'referente_telefono': probe['referente_telefono']
        }

        log(f"Configurazione caricata - Sonda ID: {PROBE_CONFIG['id']}")
        log(f"Nome: {PROBE_CONFIG['nome']}")
        log(f"Posizione: {PROBE_CONFIG['posizione_geografica']} ({PROBE_CONFIG['latitudine']}, {PROBE_CONFIG['longitudine']})")
        log(f"Referente: {PROBE_CONFIG['referente_nome']} ({PROBE_CONFIG['referente_email']})")

        return PROBE_CONFIG

    except json.JSONDecodeError as e:
        log(f"ERRORE: File di configurazione JSON non valido: {e}")
        raise
    except Exception as e:
        log(f"ERRORE durante il caricamento della configurazione: {e}")
        raise

def log(message):
    """Scrive log su file e console"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_path = os.path.join(LOG_DIR, "probe.log")
    with open(log_path, "a") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"[{timestamp}] {message}")

def init_db():
    """Inizializza il database e crea tutte le tabelle necessarie"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Tabella informazioni sonda
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS probe_info (
        probe_id TEXT PRIMARY KEY,
        nome TEXT,
        posizione_geografica TEXT,
        latitudine REAL,
        longitudine REAL,
        referente_nome TEXT,
        referente_email TEXT,
        referente_telefono TEXT,
        created_at TEXT,
        updated_at TEXT
    )""")

    # Tabella dispositivi LAN
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        probe_id TEXT NOT NULL,
        ip TEXT,
        mac TEXT,
        first_seen TEXT,
        last_seen TEXT,
        hostname TEXT,
        ports_open TEXT,
        os_info TEXT,
        FOREIGN KEY(probe_id) REFERENCES probe_info(probe_id)
    )""")

    # Tabella OUI (vendor lookup)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS oui (
        prefix TEXT PRIMARY KEY,
        vendor TEXT
    )""")

    # Tabella reti WiFi
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wifi_networks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        probe_id TEXT NOT NULL,
        ssid TEXT,
        bssid TEXT,
        signal TEXT,
        auth TEXT,
        channel TEXT,
        seen_at TEXT,
        FOREIGN KEY(probe_id) REFERENCES probe_info(probe_id)
    )""")

    # Tabella dispositivi Bluetooth (stato corrente)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bluetooth_devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        probe_id TEXT NOT NULL,
        name TEXT,
        instance_id TEXT,
        status TEXT,
        manufacturer TEXT,
        properties TEXT,
        abstract TEXT,
        seen_at TEXT,
        FOREIGN KEY(probe_id) REFERENCES probe_info(probe_id)
    )""")

    # Tabella scansioni Bluetooth (storico)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bluetooth_scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        probe_id TEXT NOT NULL,
        scanned_at TEXT,
        FOREIGN KEY(probe_id) REFERENCES probe_info(probe_id)
    )""")

    # Tabella storico dispositivi Bluetooth
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bluetooth_devices_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        probe_id TEXT NOT NULL,
        scan_id INTEGER,
        name TEXT,
        instance_id TEXT,
        status TEXT,
        manufacturer TEXT,
        properties TEXT,
        abstract TEXT,
        seen_at TEXT,
        FOREIGN KEY(probe_id) REFERENCES probe_info(probe_id),
        FOREIGN KEY(scan_id) REFERENCES bluetooth_scans(id)
    )""")

    # Tabella sessioni di sniffing
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sniffing_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        probe_id TEXT NOT NULL,
        started_at TEXT,
        stopped_at TEXT,
        interface TEXT,
        filter TEXT,
        packets_captured INTEGER DEFAULT 0,
        status TEXT DEFAULT 'running',
        FOREIGN KEY(probe_id) REFERENCES probe_info(probe_id)
    )""")

    # Tabella pacchetti catturati
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS captured_packets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        probe_id TEXT NOT NULL,
        session_id INTEGER,
        timestamp TEXT,
        src_ip TEXT,
        dst_ip TEXT,
        src_port INTEGER,
        dst_port INTEGER,
        protocol TEXT,
        length INTEGER,
        src_mac TEXT,
        dst_mac TEXT,
        flags TEXT,
        payload_preview TEXT,
        raw_packet BLOB,
        FOREIGN KEY(probe_id) REFERENCES probe_info(probe_id),
        FOREIGN KEY(session_id) REFERENCES sniffing_sessions(id)
    )""")

    # Tabella statistiche traffico (aggregazioni per analisi rapide)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS traffic_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        probe_id TEXT NOT NULL,
        session_id INTEGER,
        timestamp TEXT,
        src_ip TEXT,
        dst_ip TEXT,
        protocol TEXT,
        packet_count INTEGER DEFAULT 0,
        total_bytes INTEGER DEFAULT 0,
        FOREIGN KEY(probe_id) REFERENCES probe_info(probe_id),
        FOREIGN KEY(session_id) REFERENCES sniffing_sessions(id)
    )""")

    # Indici per migliorare performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_devices_probe ON devices(probe_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_wifi_probe ON wifi_networks(probe_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bt_probe ON bluetooth_devices(probe_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bt_scans_probe ON bluetooth_scans(probe_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bt_history_probe ON bluetooth_devices_history(probe_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sniff_session ON sniffing_sessions(probe_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_packets_session ON captured_packets(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_packets_timestamp ON captured_packets(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_packets_src_ip ON captured_packets(src_ip)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_packets_dst_ip ON captured_packets(dst_ip)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_traffic_stats ON traffic_stats(probe_id, session_id)")

    conn.commit()
    log("Database inizializzato con successo")
    return conn

def update_probe_info(conn):
    """Aggiorna o inserisce le informazioni della sonda nel database"""
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Verifica se la sonda esiste già
    cursor.execute("SELECT probe_id FROM probe_info WHERE probe_id = ?", (PROBE_CONFIG['id'],))
    exists = cursor.fetchone()

    if exists:
        cursor.execute("""
            UPDATE probe_info 
            SET nome = ?, posizione_geografica = ?, latitudine = ?, longitudine = ?,
                referente_nome = ?, referente_email = ?, referente_telefono = ?, updated_at = ?
            WHERE probe_id = ?
        """, (
            PROBE_CONFIG['nome'],
            PROBE_CONFIG['posizione_geografica'],
            PROBE_CONFIG['latitudine'],
            PROBE_CONFIG['longitudine'],
            PROBE_CONFIG['referente_nome'],
            PROBE_CONFIG['referente_email'],
            PROBE_CONFIG['referente_telefono'],
            now,
            PROBE_CONFIG['id']
        ))
        log(f"Informazioni sonda aggiornate: {PROBE_CONFIG['id']}")
    else:
        cursor.execute("""
            INSERT INTO probe_info 
            (probe_id, nome, posizione_geografica, latitudine, longitudine, 
             referente_nome, referente_email, referente_telefono, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            PROBE_CONFIG['id'],
            PROBE_CONFIG['nome'],
            PROBE_CONFIG['posizione_geografica'],
            PROBE_CONFIG['latitudine'],
            PROBE_CONFIG['longitudine'],
            PROBE_CONFIG['referente_nome'],
            PROBE_CONFIG['referente_email'],
            PROBE_CONFIG['referente_telefono'],
            now,
            now
        ))
        log(f"Sonda registrata nel database: {PROBE_CONFIG['id']}")

    conn.commit()


# ==================== OUI / VENDOR LOOKUP ====================
def update_oui():
    """Scarica e aggiorna il database OUI per il vendor lookup"""
    try:
        log("Aggiornamento OUI avviato")

        # Aggiungi User-Agent per evitare errore 418
        req = urllib.request.Request(
            OUI_URL,
            headers={'User-Agent': 'Mozilla/5.0 (Network-Probe/1.0)'}
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            with open(OUI_FILE, 'wb') as f:
                f.write(response.read())

        with open(OUI_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM oui")

        count = 0
        for line in lines:
            if "(hex)" in line:
                parts = line.split()
                prefix = parts[0].strip()
                vendor = " ".join(parts[2:]).strip()
                cursor.execute("INSERT OR IGNORE INTO oui (prefix, vendor) VALUES (?, ?)", (prefix, vendor))
                count += 1

        conn.commit()
        conn.close()
        log(f"Aggiornamento OUI completato: {count} vendor caricati")
    except Exception as e:
        log(f"Errore aggiornamento OUI: {e}")


def normalize_oui_prefix(mac):
    """Normalizza il MAC address per lookup OUI"""
    if not mac:
        return None
    m = mac.upper().replace(":", "-")
    parts = m.split("-")
    if len(parts) >= 3:
        return "-".join(parts[:3])
    return None

def get_vendor_from_mac(mac, cursor):
    """Ottiene il vendor dal MAC address"""
    prefix = normalize_oui_prefix(mac)
    if not prefix:
        return None
    cursor.execute("SELECT vendor FROM oui WHERE prefix = ?", (prefix,))
    row = cursor.fetchone()
    return row[0] if row else None

def check_oui_update():
    """Verifica se è necessario aggiornare il database OUI"""
    last_update_file = "oui/last_oui_update.txt"
    need_update = True

    if os.path.exists(last_update_file):
        with open(last_update_file) as f:
            last = f.read().strip()
        try:
            last_date = datetime.datetime.strptime(last, "%Y-%m-%d")
            if (datetime.datetime.now() - last_date).days < OUI_UPDATE_DAYS:
                need_update = False
        except Exception:
            need_update = True

    if need_update:
        update_oui()
        with open(last_update_file, "w") as f:
            f.write(datetime.datetime.now().strftime("%Y-%m-%d"))


# ==================== SCANSIONE LAN (NMAP) ====================
def nmap_ping_scan(target=TARGET_NETWORK):
    """Esegue un ping scan sulla rete con nmap"""
    try:
        log(f"Esecuzione Nmap ping scan su {target}")
        result = subprocess.run(
            ["nmap", "-sn", target, "-oX", "-"],
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.stdout
    except Exception as e:
        log(f"Errore Nmap scan ping: {e}")
        return None


def nmap_port_os_scan(target_ip):
    """Esegue scan porte e OS detection su un IP specifico"""
    try:
        log(f"Esecuzione Nmap port/OS scan su {target_ip}")
        result = subprocess.run(
            ["nmap", "-sS", "-sV", "-O", "-oX", "-", target_ip],
            capture_output=True,
            text=True,
            timeout=300
        )
        return result.stdout
    except Exception as e:
        log(f"Errore Nmap port/os scan: {e}")
        return None


def parse_ping_xml(xml_text):
    """Parsifica l'output XML del ping scan"""
    hosts = []
    try:
        root = ET.fromstring(xml_text)
        for host in root.findall("host"):
            info = {"ip": None, "mac": None, "hostname": None}

            for addr in host.findall("address"):
                atype = addr.get("addrtype")
                addrval = addr.get("addr")
                if atype == "ipv4":
                    info["ip"] = addrval
                elif atype == "mac":
                    info["mac"] = addrval

            hostnames = host.find("hostnames")
            if hostnames is not None:
                hn = hostnames.find("hostname")
                if hn is not None:
                    info["hostname"] = hn.get("name")

            hosts.append(info)
    except Exception as e:
        log(f"Errore parsing ping XML: {e}")
    return hosts


def parse_port_os_xml(xml_text):
    """Parsifica l'output XML dello scan porte/OS"""
    ports = []
    os_info = None
    try:
        root = ET.fromstring(xml_text)
        host = root.find("host")
        if host is None:
            return "", None

        # Porte aperte
        ports_elem = host.find("ports")
        if ports_elem is not None:
            for p in ports_elem.findall("port"):
                portid = p.get("portid")
                proto = p.get("protocol")
                state = ""
                service = ""

                st = p.find("state")
                if st is not None:
                    state = st.get("state")

                sv = p.find("service")
                if sv is not None:
                    service = sv.get("name", "")

                ports.append(f"{portid}/{proto}({state},{service})")

        # OS detection
        os_elem = host.find("os")
        if os_elem is not None:
            match = os_elem.find("osmatch")
            if match is not None:
                os_info = match.get("name")
    except Exception as e:
        log(f"Errore parsing port/os XML: {e}")
    return ",".join(ports), os_info


def upsert_device(conn, ip, mac, hostname, ports_open, os_info):
    """Inserisce o aggiorna un dispositivo nel database"""
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    probe_id = PROBE_CONFIG['id']

    # Cerca dispositivo esistente per MAC o IP (nella stessa sonda)
    existing = None
    if mac:
        cursor.execute("SELECT id, first_seen FROM devices WHERE mac = ? AND probe_id = ?", (mac, probe_id))
        existing = cursor.fetchone()
    if not existing and ip:
        cursor.execute("SELECT id, first_seen FROM devices WHERE ip = ? AND probe_id = ?", (ip, probe_id))
        existing = cursor.fetchone()

    if existing:
        device_id, first_seen = existing
        cursor.execute("""
            UPDATE devices SET ip = ?, mac = ?, last_seen = ?, hostname = ?, ports_open = ?, os_info = ?
            WHERE id = ?
        """, (ip, mac, now, hostname, ports_open, os_info, device_id))
    else:
        cursor.execute("""
            INSERT INTO devices (probe_id, ip, mac, first_seen, last_seen, hostname, ports_open, os_info)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (probe_id, ip, mac, now, now, hostname, ports_open, os_info))

    conn.commit()


def scan_lan_network(conn):
    """Esegue la scansione completa della rete LAN"""
    log("=== INIZIO SCANSIONE LAN ===")

    scan_xml = nmap_ping_scan(TARGET_NETWORK)
    if not scan_xml:
        log("Nessun risultato dallo scan ping")
        return

    hosts = parse_ping_xml(scan_xml)
    log(f"Trovati {len(hosts)} host attivi")

    cursor = conn.cursor()
    for h in hosts:
        ip = h.get("ip")
        mac = h.get("mac")
        hostname = h.get("hostname")

        if not ip:
            continue

        # Scan porte e OS
        port_os_xml = nmap_port_os_scan(ip)
        ports_open = ""
        os_info = None
        if port_os_xml:
            ports_open, os_info = parse_port_os_xml(port_os_xml)

        # Salva nel database
        upsert_device(conn, ip, mac, hostname, ports_open, os_info)

        # Log con vendor se disponibile
        vendor_info = ""
        if mac:
            vendor = get_vendor_from_mac(mac, cursor)
            vendor_info = f" vendor={vendor or 'unknown'}"

        log(f"  {ip} {mac or 'N/A'} {hostname or 'N/A'}{vendor_info} ports={ports_open or 'none'} os={os_info or 'N/A'}")

    log("=== FINE SCANSIONE LAN ===")


# ==================== SCANSIONE WIFI ====================
def scan_wifi():
    """Scansione reti WiFi con fallback multipli"""
    log("=== INIZIO SCANSIONE WIFI ===")

    # Prova 1: winwifi
    try:
        if importlib.util.find_spec("winwifi") is not None:
            from winwifi import WinWiFi
            nets = []
            for n in WinWiFi.scan():
                nets.append({
                    "ssid": getattr(n, "ssid", "") or str(n),
                    "bssid": getattr(n, "bssid", "") or None,
                    "signal": getattr(n, "signal", "") or None,
                    "auth": getattr(n, "auth", "") or None,
                    "channel": getattr(n, "channel", "") or None
                })
            if nets:
                log(f"WiFi scan (winwifi): {len(nets)} reti trovate")
                return nets
    except Exception as e:
        log(f"winwifi non disponibile: {e}")

    # Prova 2: pywifi
    try:
        if importlib.util.find_spec("pywifi") is not None:
            import pywifi
            wifi = pywifi.PyWiFi()
            ifaces = wifi.interfaces()
            if ifaces:
                iface = ifaces[0]
                iface.scan()
                time.sleep(2)
                results = iface.scan_results()
                nets = []
                for r in results:
                    nets.append({
                        "ssid": getattr(r, "ssid", "") or "",
                        "bssid": getattr(r, "bssid", "") or "",
                        "signal": str(getattr(r, "signal", "")) or "",
                        "auth": None,
                        "channel": None
                    })
                if nets:
                    log(f"WiFi scan (pywifi): {len(nets)} reti trovate")
                    return nets
    except Exception as e:
        log(f"pywifi non disponibile: {e}")

    # Prova 3: netsh (fallback Windows)
    try:
        res = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True,
            text=True,
            shell=False,
            timeout=30
        )
        stdout = (res.stdout or "").strip()
        stderr = (res.stderr or "").strip()
        combined = (stdout + "\n" + stderr).lower()

        # Rileva blocco permessi Posizione
        if any(x in combined for x in [
            "richiedono l'autorizzazione di posizione",
            "requiring location authorization",
            "commands require location permission"
        ]):
            log("ATTENZIONE: Accesso WiFi bloccato dalle impostazioni Posizione")
            log("Chiedi all'amministratore di attivare: Impostazioni > Privacy e sicurezza > Posizione")
            return []

        if res.returncode != 0:
            log(f"netsh errore: returncode={res.returncode}")
            return []

        # Parsing output netsh
        nets = []
        ssid = None
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.lower().startswith("ssid"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    ssid = parts[1].strip()
                continue

            if line.lower().startswith("bssid") and ssid:
                parts = line.split(":", 1)
                bssid = parts[1].strip() if len(parts) == 2 else None
                nets.append({
                    "ssid": ssid,
                    "bssid": bssid,
                    "signal": None,
                    "auth": None,
                    "channel": None
                })
                continue

            if nets:
                if line.lower().startswith(("signal", "segnale")):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        nets[-1]["signal"] = parts[1].strip()
                elif line.lower().startswith(("authentication", "autenticazione")):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        nets[-1]["auth"] = parts[1].strip()
                elif line.lower().startswith(("channel", "canale")):
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        nets[-1]["channel"] = parts[1].strip()

        if nets:
            log(f"WiFi scan (netsh): {len(nets)} reti trovate")
            return nets
        else:
            log("WiFi scan (netsh): nessuna rete trovata")
            return []

    except Exception as e:
        log(f"Errore scan WiFi: {e}")
        return []


def store_wifi_scan(conn, networks):
    """Salva le reti WiFi nel database"""
    if not networks:
        log("Nessuna rete WiFi da salvare")
        return

    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    probe_id = PROBE_CONFIG['id']
    count = 0

    for n in networks:
        try:
            cursor.execute("""
            INSERT INTO wifi_networks (probe_id, ssid, bssid, signal, auth, channel, seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                probe_id,
                n.get("ssid"),
                n.get("bssid"),
                n.get("signal"),
                n.get("auth"),
                n.get("channel"),
                now
            ))
            count += 1
        except Exception as e:
            log(f"Errore salvataggio WiFi {n.get('ssid')}: {e}")

    conn.commit()
    log(f"WiFi: salvate {count} reti nel database")


# ==================== SCANSIONE BLUETOOTH ====================
def scan_bluetooth():
    """Scansione dispositivi Bluetooth (Windows)"""
    log("=== INIZIO SCANSIONE BLUETOOTH ===")
    devices = []

    try:
        # Comando PowerShell per ottenere dispositivi Bluetooth
        ps_cmd = 'Get-PnpDevice -Class Bluetooth | Select-Object -Property FriendlyName,InstanceId,Status,Manufacturer | ConvertTo-Json -Depth 3'
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            shell=False,
            timeout=60
        )

        out = (res.stdout or "").strip()
        if not out:
            log("Nessun output da Get-PnpDevice")
            return []

        try:
            data = json.loads(out)
            items = data if isinstance(data, list) else [data]

            for it in items:
                inst = it.get("InstanceId") or it.get("DeviceID")
                name = it.get("FriendlyName") or it.get("Name")
                status = it.get("Status")
                manufacturer = it.get("Manufacturer")

                dev = {
                    "name": name,
                    "instance_id": inst,
                    "status": status,
                    "manufacturer": manufacturer,
                    "properties": {},
                    "abstract": None
                }

                # Ottieni proprietà dettagliate
                if inst:
                    inst_escaped = inst.replace("'", "''")
                    ps_props = f"Get-PnpDeviceProperty -InstanceId '{inst_escaped}' -ErrorAction SilentlyContinue | Select-Object KeyName,Data | ConvertTo-Json -Depth 4"
                    pres = subprocess.run(
                        ["powershell", "-NoProfile", "-Command", ps_props],
                        capture_output=True,
                        text=True,
                        shell=False,
                        timeout=30
                    )

                    pout = (pres.stdout or "").strip()
                    if pout:
                        try:
                            pjson = json.loads(pout)
                            pitems = pjson if isinstance(pjson, list) else [pjson]
                            for p in pitems:
                                k = p.get("KeyName") or str(p.get("Key"))
                                v = p.get("Data")
                                if k:
                                    kk = k.replace(":", "_").replace(".", "_").replace(" ", "_")
                                    dev["properties"][kk] = v
                        except Exception:
                            pass

                devices.append(dev)

            log(f"Bluetooth: trovati {len(devices)} dispositivi")

        except json.JSONDecodeError as e:
            log(f"Errore parsing JSON Bluetooth: {e}")

    except Exception as e:
        log(f"Errore scan Bluetooth: {e}")

    return devices


def store_bluetooth_scan(conn, devices):
    """Salva i dispositivi Bluetooth nel database (stato corrente + storico)"""
    if not devices:
        log("Nessun dispositivo Bluetooth da salvare")
        return

    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    probe_id = PROBE_CONFIG['id']

    # Crea record della scansione
    try:
        cursor.execute("INSERT INTO bluetooth_scans (probe_id, scanned_at) VALUES (?, ?)", (probe_id, now))
        scan_id = cursor.lastrowid
    except Exception as e:
        log(f"Errore creazione record scan Bluetooth: {e}")
        return

    count_current = 0
    count_history = 0

    for d in devices:
        try:
            props = d.get("properties") or {}
            props_json = json.dumps(props, ensure_ascii=False)
            instance_id = d.get("instance_id")

            # Aggiorna tabella stato corrente
            cursor.execute("SELECT id FROM bluetooth_devices WHERE instance_id = ? AND probe_id = ?",
                           (instance_id, probe_id))
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                UPDATE bluetooth_devices 
                SET name = ?, status = ?, manufacturer = ?, properties = ?, abstract = ?, seen_at = ?
                WHERE id = ?
                """, (
                    d.get("name"),
                    d.get("status"),
                    d.get("manufacturer"),
                    props_json,
                    d.get("abstract"),
                    now,
                    existing[0]
                ))
            else:
                cursor.execute("""
                INSERT INTO bluetooth_devices 
                (probe_id, name, instance_id, status, manufacturer, properties, abstract, seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    probe_id,
                    d.get("name"),
                    instance_id,
                    d.get("status"),
                    d.get("manufacturer"),
                    props_json,
                    d.get("abstract"),
                    now
                ))
            count_current += 1

            # Inserisci nello storico
            cursor.execute("""
            INSERT INTO bluetooth_devices_history
            (probe_id, scan_id, name, instance_id, status, manufacturer, properties, abstract, seen_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                probe_id,
                scan_id,
                d.get("name"),
                instance_id,
                d.get("status"),
                d.get("manufacturer"),
                props_json,
                d.get("abstract"),
                now
            ))
            count_history += 1

        except Exception as e:
            log(f"Errore salvataggio Bluetooth {d.get('name')}: {e}")

    conn.commit()
    log(f"Bluetooth: salvati {count_current} dispositivi (correnti), {count_history} nello storico")


# ==================== PACKET SNIFFING ====================
def get_network_interface():
    """Rileva l'interfaccia di rete principale"""
    try:
        # Prova con scapy se disponibile
        print('Prova con scapy se disponibile')
        if importlib.util.find_spec("scapy") is not None:
            from scapy.arch import get_if_list, get_working_if
            return get_working_if()

        # Fallback per Windows
        import socket
        print('Fallback per Windows')
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()

        # Su Windows, cerca interfaccia con quell'IP
        result = subprocess.run(
            ["ipconfig"],
            capture_output=True,
            text=True,
            timeout=10
        )

        lines = result.stdout.split('\n')
        current_adapter = None


        for line in lines:
            if 'adapter' in line.lower() or 'scheda' in line.lower():
                current_adapter = line.split(':')[0].strip()
            if local_ip in line and current_adapter:
                log(f"Interfaccia rilevata: {current_adapter}")
                return current_adapter

    except Exception as e:
        log(f"Errore rilevamento interfaccia: {e}")

    return None


def start_sniffing_session(conn, interface=None):
    """Crea una nuova sessione di sniffing nel database"""
    global SNIFFING_SESSION_ID

    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    probe_id = PROBE_CONFIG['id']

    if interface is None:
        interface = SNIFFING_INTERFACE or get_network_interface() or "auto"

    cursor.execute("""
        INSERT INTO sniffing_sessions 
        (probe_id, started_at, interface, filter, status)
        VALUES (?, ?, ?, ?, 'running')
    """, (probe_id, now, interface, SNIFFING_FILTER))

    SNIFFING_SESSION_ID = cursor.lastrowid
    conn.commit()

    log(f"Sessione sniffing avviata: ID={SNIFFING_SESSION_ID}, interface={interface}")
    return SNIFFING_SESSION_ID


def stop_sniffing_session(conn):
    """Termina la sessione di sniffing corrente"""
    global SNIFFING_SESSION_ID

    if SNIFFING_SESSION_ID is None:
        return

    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Conta pacchetti catturati
    cursor.execute(
        "SELECT COUNT(*) FROM captured_packets WHERE session_id = ?",
        (SNIFFING_SESSION_ID,)
    )
    packet_count = cursor.fetchone()[0]

    cursor.execute("""
        UPDATE sniffing_sessions 
        SET stopped_at = ?, packets_captured = ?, status = 'stopped'
        WHERE id = ?
    """, (now, packet_count, SNIFFING_SESSION_ID))

    conn.commit()
    log(f"Sessione sniffing terminata: ID={SNIFFING_SESSION_ID}, pacchetti={packet_count}")
    SNIFFING_SESSION_ID = None


def parse_packet(packet):
    """Estrae informazioni da un pacchetto scapy"""
    try:
        from scapy.layers.inet import IP, TCP, UDP
        from scapy.layers.l2 import Ether

        packet_info = {
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            'src_ip': None,
            'dst_ip': None,
            'src_port': None,
            'dst_port': None,
            'protocol': None,
            'length': len(packet),
            'src_mac': None,
            'dst_mac': None,
            'flags': None,
            'payload_preview': None,
            'raw_packet': base64.b64encode(bytes(packet)).decode('utf-8')
        }

        # Layer Ethernet
        if packet.haslayer(Ether):
            eth = packet[Ether]
            packet_info['src_mac'] = eth.src
            packet_info['dst_mac'] = eth.dst

        # Layer IP
        if packet.haslayer(IP):
            ip = packet[IP]
            packet_info['src_ip'] = ip.src
            packet_info['dst_ip'] = ip.dst
            packet_info['protocol'] = ip.proto

            # TCP
            if packet.haslayer(TCP):
                tcp = packet[TCP]
                packet_info['src_port'] = tcp.sport
                packet_info['dst_port'] = tcp.dport
                packet_info['protocol'] = 'TCP'
                packet_info['flags'] = str(tcp.flags)

                # Payload preview (primi 100 caratteri)
                if tcp.payload:
                    payload_bytes = bytes(tcp.payload)
                    packet_info['payload_preview'] = payload_bytes[:100].hex()

            # UDP
            elif packet.haslayer(UDP):
                udp = packet[UDP]
                packet_info['src_port'] = udp.sport
                packet_info['dst_port'] = udp.dport
                packet_info['protocol'] = 'UDP'

                if udp.payload:
                    payload_bytes = bytes(udp.payload)
                    packet_info['payload_preview'] = payload_bytes[:100].hex()

            # Altri protocolli IP
            else:
                proto_map = {1: 'ICMP', 2: 'IGMP', 6: 'TCP', 17: 'UDP', 41: 'IPv6', 47: 'GRE', 50: 'ESP'}
                packet_info['protocol'] = proto_map.get(ip.proto, f'IP-{ip.proto}')

        return packet_info

    except Exception as e:
        log(f"Errore parsing pacchetto: {e}")
        return None


def save_packets_batch(conn, packets):
    """Salva un batch di pacchetti nel database"""
    if not packets:
        return

    cursor = conn.cursor()
    probe_id = PROBE_CONFIG['id']
    saved_count = 0

    # Dizionario per statistiche aggregate
    stats = {}

    for pkt in packets:
        try:
            # Salva pacchetto completo
            cursor.execute("""
                INSERT INTO captured_packets 
                (probe_id, session_id, timestamp, src_ip, dst_ip, src_port, dst_port,
                 protocol, length, src_mac, dst_mac, flags, payload_preview, raw_packet)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                probe_id,
                SNIFFING_SESSION_ID,
                pkt['timestamp'],
                pkt['src_ip'],
                pkt['dst_ip'],
                pkt['src_port'],
                pkt['dst_port'],
                pkt['protocol'],
                pkt['length'],
                pkt['src_mac'],
                pkt['dst_mac'],
                pkt['flags'],
                pkt['payload_preview'],
                pkt['raw_packet']
            ))
            saved_count += 1

            # Aggiorna statistiche aggregate
            if pkt['src_ip'] and pkt['dst_ip']:
                key = (pkt['src_ip'], pkt['dst_ip'], pkt['protocol'] or 'UNKNOWN')
                if key not in stats:
                    stats[key] = {'count': 0, 'bytes': 0}
                stats[key]['count'] += 1
                stats[key]['bytes'] += pkt['length']

        except Exception as e:
            log(f"Errore salvataggio pacchetto: {e}")

    # Salva statistiche aggregate
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for (src_ip, dst_ip, proto), data in stats.items():
        try:
            cursor.execute("""
                INSERT INTO traffic_stats 
                (probe_id, session_id, timestamp, src_ip, dst_ip, protocol, packet_count, total_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                probe_id,
                SNIFFING_SESSION_ID,
                timestamp,
                src_ip,
                dst_ip,
                proto,
                data['count'],
                data['bytes']
            ))
        except Exception as e:
            log(f"Errore salvataggio statistiche: {e}")

    conn.commit()
    log(f"Batch salvato: {saved_count} pacchetti, {len(stats)} flussi unici")


def packet_callback(packet):
    """Callback per ogni pacchetto catturato"""
    global PACKET_BUFFER

    packet_info = parse_packet(packet)
    if packet_info:
        with PACKET_BUFFER_LOCK:
            PACKET_BUFFER.append(packet_info)

def get_ip_owner(ip):
    try:
        w = whois.whois(ip)
        print("=== Informazioni WHOIS ===")
        print("Organizzazione:", w.get("org"))
        print("ASN:", w.get("asn"))
        print("Paese:", w.get("country"))
        print("NetName:", w.get("netname"))
    except Exception as e:
        print("Errore:", e)

def sniffing_worker(interface, bpf_filter):
    """Thread worker per packet capture"""
    global PACKET_BUFFER

    try:
        from scapy.all import sniff

        log(f"Sniffing avviato su interfaccia: {interface}")
        log(f"Filtro BPF: '{bpf_filter}' (vuoto = tutti i pacchetti)")

        # Sniffing continuo con timeout per controllare stop flag
        while not SNIFFING_STOP_FLAG.is_set():
            try:
                sniff(
                    iface=interface,
                    prn=packet_callback,
                    filter=bpf_filter if bpf_filter else None,
                    timeout=SNIFFING_BATCH_INTERVAL,
                    store=False
                )

                # Salva batch se ci sono pacchetti
                with PACKET_BUFFER_LOCK:
                    if PACKET_BUFFER:
                        packets_to_save = PACKET_BUFFER[:SNIFFING_MAX_PACKETS_PER_BATCH]
                        PACKET_BUFFER = PACKET_BUFFER[SNIFFING_MAX_PACKETS_PER_BATCH:]

                        # Salva su database
                        conn = sqlite3.connect(DB_FILE)
                        save_packets_batch(conn, packets_to_save)
                        conn.close()

            except Exception as e:
                if not SNIFFING_STOP_FLAG.is_set():
                    log(f"Errore durante sniffing: {e}")
                    time.sleep(5)

        log("Sniffing worker terminato")

    except ImportError:
        log("ERRORE: Scapy non installato. Installare con: pip install scapy")
    except Exception as e:
        log(f"Errore fatale sniffing worker: {e}")


def start_packet_capture(conn):
    """Avvia il packet capture in un thread separato"""
    global SNIFFING_THREAD, SNIFFING_STOP_FLAG

    if not SNIFFING_ENABLED:
        log("Packet capture disabilitato nella configurazione")
        return

    try:
        # Verifica disponibilità scapy
        if importlib.util.find_spec("scapy") is None:
            log("ATTENZIONE: Scapy non installato - packet capture disabilitato")
            log("Installare con: pip install scapy")
            return

        # Crea sessione nel database
        interface = SNIFFING_INTERFACE or get_network_interface()
        if not interface:
            log("ERRORE: Impossibile rilevare interfaccia di rete")
            return

        start_sniffing_session(conn, interface)

        # Avvia thread di capture
        SNIFFING_STOP_FLAG.clear()
        SNIFFING_THREAD = threading.Thread(
            target=sniffing_worker,
            args=(interface, SNIFFING_FILTER),
            daemon=True
        )
        SNIFFING_THREAD.start()

        log("=== PACKET CAPTURE AVVIATO ===")

    except Exception as e:
        log(f"Errore avvio packet capture: {e}")


def stop_packet_capture(conn):
    """Ferma il packet capture"""
    global SNIFFING_THREAD, PACKET_BUFFER

    if SNIFFING_THREAD is None:
        return

    log("Arresto packet capture...")
    SNIFFING_STOP_FLAG.set()

    # Attendi termine thread (max 10 secondi)
    SNIFFING_THREAD.join(timeout=10)

    # Salva eventuali pacchetti rimasti nel buffer
    with PACKET_BUFFER_LOCK:
        if PACKET_BUFFER:
            log(f"Salvataggio ultimi {len(PACKET_BUFFER)} pacchetti...")
            save_packets_batch(conn, PACKET_BUFFER)
            PACKET_BUFFER = []

    stop_sniffing_session(conn)
    log("=== PACKET CAPTURE TERMINATO ===")


# ==================== MAIN LOOP ====================
# def main():
#     """Funzione principale con loop di scansione"""
#     log("========================================")
#     log("AVVIO NETWORK SCANNER")
#     log("========================================")
#     get_ip_owner('157.240.231.6')
#
#     # Carica la configurazione della sonda
#     load_probe_config()
#
#     # Inizializza database
#     conn = init_db()
#
#     # Aggiorna le informazioni della sonda nel database
#     update_probe_info(conn)
#
#     # Aggiorna OUI se necessario
#     check_oui_update()
#
#     # Avvia packet capture se abilitato
#     if SNIFFING_ENABLED:
#         start_packet_capture(conn)
#
#     try:
#         while True:
#             log(f"\n{'=' * 50}")
#             log(f"CICLO SCANSIONE - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
#             log(f"{'=' * 50}")
#
#             # 1. Scansione LAN
#             try:
#                 scan_lan_network(conn)
#             except Exception as e:
#                 log(f"ERRORE scansione LAN: {e}")
#
#             # 2. Scansione WiFi
#             try:
#                 wifi_nets = scan_wifi()
#                 store_wifi_scan(conn, wifi_nets)
#             except Exception as e:
#                 log(f"ERRORE scansione WiFi: {e}")
#
#             # 3. Scansione Bluetooth
#             try:
#                 bt_devs = scan_bluetooth()
#                 store_bluetooth_scan(conn, bt_devs)
#             except Exception as e:
#                 log(f"ERRORE scansione Bluetooth: {e}")
#
#             # 4. Statistiche packet capture
#             if SNIFFING_ENABLED and SNIFFING_SESSION_ID:
#                 try:
#                     cursor = conn.cursor()
#                     cursor.execute(
#                         "SELECT COUNT(*) FROM captured_packets WHERE session_id = ?",
#                         (SNIFFING_SESSION_ID,)
#                     )
#                     packet_count = cursor.fetchone()[0]
#                     log(f"Packet capture: {packet_count} pacchetti catturati in questa sessione")
#                 except Exception as e:
#                     log(f"Errore statistiche packet capture: {e}")
#
#             # Attendi prossimo ciclo
#             log(f"\n{'=' * 50}")
#             log(f"Attendo {SCAN_INTERVAL} secondi prima del prossimo scan")
#             log(f"{'=' * 50}\n")
#             time.sleep(SCAN_INTERVAL)
#
#     except KeyboardInterrupt:
#         log("\n========================================")
#         log("SCANNER INTERROTTO DALL'UTENTE")
#         log("========================================")
#
#     finally:
#         # Ferma packet capture
#         if SNIFFING_ENABLED:
#             stop_packet_capture(conn)
#
#         conn.close()
#         log("Database chiuso. Arrivederci!")

def main():
    load_probe_config()

    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    init_db()
    update_probe_info(conn)
    check_oui_update()

    threads = []

    def lan_job():
        c = sqlite3.connect(DB_FILE, check_same_thread=False)
        scan_lan_network(c)
        c.close()

    def wifi_job():
        c = sqlite3.connect(DB_FILE, check_same_thread=False)
        nets = scan_wifi()
        store_wifi_scan(c, nets)
        c.close()

    def bt_job():
        c = sqlite3.connect(DB_FILE, check_same_thread=False)
        devs = scan_bluetooth()
        store_bluetooth_scan(c, devs)
        c.close()

    while True:
        t1 = threading.Thread(target=lan_job)
        t2 = threading.Thread(target=wifi_job)
        t3 = threading.Thread(target=bt_job)

        t1.start(); t2.start(); t3.start()
        t1.join(); t2.join(); t3.join()

        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()