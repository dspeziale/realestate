# oui.py
import os
import sqlite3
import datetime
import urllib.request
from .config import OUI_FILE, OUI_URL, get_scan_config, DB_FILE, log


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

    scan_config = get_scan_config()  # MODIFICATO: ottiene configurazione
    oui_update_days = scan_config['oui_update_days']

    need_update = True

    if os.path.exists(last_update_file):
        with open(last_update_file) as f:
            last = f.read().strip()
        try:
            last_date = datetime.datetime.strptime(last, "%Y-%m-%d")
            if (datetime.datetime.now() - last_date).days < oui_update_days:  # MODIFICATO
                need_update = False
        except Exception:
            need_update = True

    if need_update:
        update_oui()
        with open(last_update_file, "w") as f:
            f.write(datetime.datetime.now().strftime("%Y-%m-%d"))