# database.py
import sqlite3
import datetime
from .config import PROBE_CONFIG, DB_FILE, log, load_probe_config


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

    # Tabella dispositivi LAN - AGGIUNTA device_type e vendor
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
            device_type TEXT,  -- NUOVO CAMPO
            vendor TEXT,       -- NUOVO CAMPO
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
            payload_hex TEXT,      -- NUOVA COLONNA: payload in esadecimale completo
            payload_ascii TEXT,    -- NUOVA COLONNA: payload in ASCII (se possibile)
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
    PROBE_CONFIG = load_probe_config()
    print(PROBE_CONFIG)
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