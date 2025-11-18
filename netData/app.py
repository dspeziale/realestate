# python
import os
import sqlite3
import subprocess
import time
import datetime
import urllib.request
import xml.etree.ElementTree as ET

DB_FILE = "network_probe.db"
LOG_DIR = "logs"
OUI_FILE = "oui.txt"
OUI_URL = "https://standards-oui.ieee.org/oui.txt"

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


def log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_path = os.path.join(LOG_DIR, "probe.log")
    with open(log_path, "a") as f:
        f.write(f"[{timestamp}] {message}\n")
    print(f"[{timestamp}] {message}")


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip TEXT,
        mac TEXT,
        first_seen TEXT,
        last_seen TEXT,
        hostname TEXT,
        ports_open TEXT,
        os_info TEXT
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS oui (
        prefix TEXT PRIMARY KEY,
        vendor TEXT
    )""")
    conn.commit()
    return conn


def update_oui():
    try:
        log("Aggiornamento OUI avviato")
        urllib.request.urlretrieve(OUI_URL, OUI_FILE)
        with open(OUI_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM oui")
        for line in lines:
            if "(hex)" in line:
                parts = line.split()
                prefix = parts[0].strip()
                vendor = " ".join(parts[2:]).strip()
                cursor.execute("INSERT OR IGNORE INTO oui (prefix, vendor) VALUES (?, ?)", (prefix, vendor))
        conn.commit()
        conn.close()
        log("Aggiornamento OUI completato")
    except Exception as e:
        log(f"Errore aggiornamento OUI: {e}")


def nmap_ping_scan(target="10.97.90.0/24"):
    try:
        log(f"Esecuzione Nmap ping scan su {target}")
        result = subprocess.run(["nmap", "-sn", target, "-oX", "-"], capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        log(f"Errore Nmap scan ping: {e}")
        return None


def nmap_port_os_scan(target_ip):
    try:
        log(f"Esecuzione Nmap port/OS scan su {target_ip}")
        # -sS stealth scan, -sV service/version, -O OS detection
        result = subprocess.run(["nmap", "-sS", "-sV", "-O", "-oX", "-", target_ip], capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        log(f"Errore Nmap port/os scan: {e}")
        return None


def parse_ping_xml(xml_text):
    hosts = []
    try:
        root = ET.fromstring(xml_text)
        for host in root.findall("host"):
            info = {"ip": None, "mac": None, "hostname": None}
            addr_elems = host.findall("address")
            for addr in addr_elems:
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
    ports = []
    os_info = None
    try:
        root = ET.fromstring(xml_text)
        host = root.find("host")
        if host is None:
            return "", None
        # ports
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
        # os
        os_elem = host.find("os")
        if os_elem is not None:
            match = os_elem.find("osmatch")
            if match is not None:
                os_info = match.get("name")
    except Exception as e:
        log(f"Errore parsing port/os XML: {e}")
    return ",".join(ports), os_info


def normalize_oui_prefix(mac):
    if not mac:
        return None
    # mac examples: 00:11:22:33:44:55 or 00-11-22-33-44-55
    m = mac.upper().replace(":", "-")
    parts = m.split("-")
    if len(parts) >= 3:
        return "-".join(parts[:3])
    return None


def get_vendor_from_mac(mac, cursor):
    prefix = normalize_oui_prefix(mac)
    if not prefix:
        return None
    cursor.execute("SELECT vendor FROM oui WHERE prefix = ?", (prefix,))
    row = cursor.fetchone()
    return row[0] if row else None


def upsert_device(conn, ip, mac, hostname, ports_open, os_info):
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Try to find existing by mac first, then ip
    existing = None
    if mac:
        cursor.execute("SELECT id, first_seen FROM devices WHERE mac = ?", (mac,))
        existing = cursor.fetchone()
    if not existing:
        cursor.execute("SELECT id, first_seen FROM devices WHERE ip = ?", (ip,))
        existing = cursor.fetchone()
    if existing:
        device_id, first_seen = existing
        cursor.execute("""
            UPDATE devices SET ip = ?, mac = ?, last_seen = ?, hostname = ?, ports_open = ?, os_info = ?
            WHERE id = ?
        """, (ip, mac, now, hostname, ports_open, os_info, device_id))
    else:
        first_seen = now
        cursor.execute("""
            INSERT INTO devices (ip, mac, first_seen, last_seen, hostname, ports_open, os_info)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ip, mac, first_seen, now, hostname, ports_open, os_info))
    conn.commit()


def main():
    conn = init_db()
    ensure_extra_tables(conn)

    #WiFi scan
    wifi_nets = scan_wifi()
    log(f"Reti WiFi trovate: {len(wifi_nets)}")
    store_wifi_scan(conn, wifi_nets)

    # Bluetooth scan
    bt_devs = scan_bluetooth()
    log(f"Dispositivi Bluetooth trovati: {len(bt_devs)}")
    store_bt_scan(conn, bt_devs)

    # Aggiorna OUI ogni 7 giorni (esempio)
    last_oui_update_path = "last_oui_update.txt"
    need_update = True
    if os.path.exists(last_oui_update_path):
        with open(last_oui_update_path) as f:
            last = f.read().strip()
        try:
            last_date = datetime.datetime.strptime(last, "%Y-%m-%d")
            if (datetime.datetime.now() - last_date).days < 7:
                need_update = False
        except Exception:
            need_update = True
    if need_update:
        update_oui()
        with open(last_oui_update_path, "w") as f:
            f.write(datetime.datetime.now().strftime("%Y-%m-%d"))

    if 1==2:
        scan_interval = 600  # secondi tra uno scan e il successivo
        target_network = "10.97.90.0/24"

        try:
            while True:
                scan_xml = nmap_ping_scan(target_network)
                if scan_xml:
                    hosts = parse_ping_xml(scan_xml)
                    log(f"Trovati {len(hosts)} host attivi")
                    cursor = conn.cursor()
                    for h in hosts:
                        ip = h.get("ip")
                        mac = h.get("mac")
                        hostname = h.get("hostname")
                        # Port & OS scan per host
                        port_os_xml = nmap_port_os_scan(ip)
                        ports_open = ""
                        os_info = None
                        if port_os_xml:
                            ports_open, os_info = parse_port_os_xml(port_os_xml)
                        # Combine hostname if not found in ping
                        # Update DB
                        upsert_device(conn, ip, mac, hostname, ports_open, os_info)
                        # Log vendor if mac available
                        if mac:
                            vendor = get_vendor_from_mac(mac, cursor)
                            if vendor:
                                log(f"{ip} {mac} {hostname or ''} vendor={vendor} ports={ports_open} os={os_info}")
                            else:
                                log(f"{ip} {mac} {hostname or ''} vendor=unknown ports={ports_open} os={os_info}")
                        else:
                            log(f"{ip} {hostname or ''} ports={ports_open} os={os_info}")
                else:
                    log("Nessun risultato dallo scan ping")
                log(f"Attendo {scan_interval} secondi prima del prossimo scan")
                time.sleep(scan_interval)
        except KeyboardInterrupt:
            log("Interrotto dall'utente")
        finally:
            conn.close()


# python
import json
import shlex

def ensure_extra_tables(conn):
    """
    Crea le tabelle per wifi e bluetooth se non esistono.
    Chiamare subito dopo `conn = init_db()`.
    """
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wifi_networks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ssid TEXT,
        bssid TEXT UNIQUE,
        signal TEXT,
        auth TEXT,
        channel TEXT,
        seen_at TEXT
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bluetooth_devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        instance_id TEXT UNIQUE,
        status TEXT,
        seen_at TEXT
    )""")
    conn.commit()

# python
import re
import subprocess

def check_wifi_adapter():
    """
    Verifica se esiste un'interfaccia WiFi visibile a netsh.
    Ritorna (bool, raw_output)
    """
    try:
        res = subprocess.run(["netsh", "wlan", "show", "interfaces"],
                             capture_output=True, text=True, shell=False)
        out = res.stdout.strip()
        if not out:
            return False, out
        # Se l'output contiene frasi note di assenza interfaccia, consideriamo assente
        lower = out.lower()
        if "there is no wireless interface" in lower or "no wireless interface" in lower \
           or "nessuna interfaccia wireless" in lower or "non è presente alcuna" in lower:
            return False, out
        return True, out
    except Exception as e:
        log(f"Errore controllo adattatore WiFi: {e}")
        return False, ""

# python
import importlib

def scan_lan_devices(target="10.97.90.0/24"):
    """
    Scan della rete LAN usando nmap (usare la funzione nmap_ping_scan() già definita).
    Ritorna lista di dict simili: [{ssid: None, bssid: mac, signal: None, auth: None, channel: None, ip, hostname}, ...]
    """
    try:
        xml = nmap_ping_scan(target)
        if not xml:
            log("scan_lan_devices: nmap non ha restituito output")
            return []
        hosts = parse_ping_xml(xml)
        nets = []
        for h in hosts:
            nets.append({
                "ssid": None,
                "bssid": h.get("mac"),
                "signal": None,
                "auth": None,
                "channel": None,
                "ip": h.get("ip"),
                "hostname": h.get("hostname")
            })
        log(f"scan_lan_devices: trovati {len(nets)} host in LAN")
        return nets
    except Exception as e:
        log(f"Errore scan_lan_devices: {e}")
        return []

def scan_wifi():
    """
    Prova in ordine: winwifi -> pywifi -> netsh.
    Se rileva il blocco per 'Posizione' (richiesta di autorizzazione) logga e ritorna [].
    Non richiede prompt di elevazione: se impossibile, usare scan_lan_devices() come fallback.
    """
    # 1) winwifi
    try:
        if importlib.util.find_spec("winwifi") is not None:
            try:
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
                    return nets
            except Exception as e:
                log(f"winwifi presente ma errore: {e}")
    except Exception:
        pass

    # 2) pywifi
    try:
        if importlib.util.find_spec("pywifi") is not None:
            try:
                import pywifi
                wifi = pywifi.PyWiFi()
                ifaces = wifi.interfaces()
                if not ifaces:
                    log("pywifi: nessuna interfaccia trovata")
                else:
                    iface = ifaces[0]
                    try:
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
                            return nets
                    except Exception as e:
                        log(f"pywifi errore scan: {e}")
            except Exception as e:
                log(f"pywifi non utilizzabile: {e}")
    except Exception:
        pass

    # 3) fallback netsh con rilevamento blocco Posizione
    try:
        res = subprocess.run(["netsh", "wlan", "show", "networks", "mode=bssid"],
                             capture_output=True, text=True, shell=False)
        stdout = (res.stdout or "").strip()
        stderr = (res.stderr or "").strip()
        combined = (stdout + "\n" + stderr).lower()

        # rileva messaggio standard di blocco Posizione in italiano / inglese
        if ("richiedono l'autorizzazione di posizione" in combined
            or "requiring location authorization" in combined
            or "commands require location permission" in combined
            or "access to location" in combined
            or "location" in combined and "privacy" in combined):
            log("Accesso WiFi bloccato dalle impostazioni Posizione. Solo un amministratore può abilitare i servizi di posizione.")
            log("Chiedi all'amministratore di attivare: Impostazioni > Privacy e sicurezza > Posizione > 'Consenti alle app desktop di accedere alla posizione'.")
            # Non forzare elevazione: ritorniamo vuoto e suggeriamo fallback
            return []
        # se netsh ha fallito per altro motivo, loggare e restituire []
        if res.returncode != 0 and not stdout:
            log(f"netsh errore returncode={res.returncode} stderr={stderr[:500]}")
            return []

        # parsing semplice dell'output netsh (come fallback robusto)
        out_lines = stdout.splitlines()
        nets = []
        ssid = None
        for raw in out_lines:
            line = raw.strip()
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
                nets.append({"ssid": ssid, "bssid": bssid, "signal": None, "auth": None, "channel": None})
                continue
            if nets and (line.lower().startswith("signal") or line.lower().startswith("segnale")):
                parts = line.split(":", 1)
                nets[-1]["signal"] = parts[1].strip() if len(parts) == 2 else nets[-1]["signal"]
                continue
            if nets and (line.lower().startswith("authentication") or line.lower().startswith("autenticazione")):
                parts = line.split(":", 1)
                nets[-1]["auth"] = parts[1].strip() if len(parts) == 2 else nets[-1]["auth"]
                continue
            if nets and (line.lower().startswith("channel") or line.lower().startswith("canale")):
                parts = line.split(":", 1)
                nets[-1]["channel"] = parts[1].strip() if len(parts) == 2 else nets[-1]["channel"]
                continue

        if nets:
            return nets
        else:
            log(f"scan_wifi: netsh non ha restituito reti (output troncato): {stdout[:500]}")
            return []
    except Exception as e:
        log(f"scan_wifi fallback netsh errore: {e}")
        return []


def scan_bluetooth():
    """
    Usa PowerShell per ottenere dispositivi Bluetooth (name, instance id, status).
    Ritorna lista di dict: [{name, instance_id, status}, ...]
    """
    try:
        # comando PowerShell che converte l'output in JSON
        ps_cmd = 'Get-PnpDevice -Class Bluetooth | Select-Object -Property FriendlyName,InstanceId,Status | ConvertTo-Json'
        # evitiamo shell=True con lista, ma PowerShell richiede stringa
        result = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd],
                                capture_output=True, text=True, shell=False)
        out = result.stdout.strip()
        if not out:
            return []
        # PowerShell può restituire un singolo oggetto o una lista; json.loads gestisce entrambi
        data = json.loads(out)
        devices = []
        if isinstance(data, dict):
            # singolo dispositivo
            name = data.get("FriendlyName") or data.get("friendlyname") or data.get("Name")
            devices.append({"name": name, "instance_id": data.get("InstanceId"), "status": data.get("Status")})
        elif isinstance(data, list):
            for d in data:
                name = d.get("FriendlyName") or d.get("friendlyname") or d.get("Name")
                devices.append({"name": name, "instance_id": d.get("InstanceId"), "status": d.get("Status")})
        return devices
    except Exception as e:
        log(f"Errore scan Bluetooth: {e}")
        return []


def store_wifi_scan(conn, networks):
    """
    Inserisce o aggiorna le reti wifi rilevate nel DB.
    """
    if not networks:
        return
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for n in networks:
        try:
            cursor.execute("""
            INSERT OR REPLACE INTO wifi_networks (id, ssid, bssid, signal, auth, channel, seen_at)
            VALUES (
                COALESCE((SELECT id FROM wifi_networks WHERE bssid = ?), NULL),
                ?, ?, ?, ?, ?, ?
            )
            """, (n.get("bssid"), n.get("ssid"), n.get("bssid"), n.get("signal"), n.get("auth"), n.get("channel"), now))
        except Exception as e:
            log(f"Errore salvataggio wifi {n}: {e}")
    conn.commit()


def store_bt_scan(conn, devices):
    """
    Inserisce o aggiorna i dispositivi bluetooth rilevati nel DB.
    """
    if not devices:
        return
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for d in devices:
        try:
            cursor.execute("""
            INSERT OR REPLACE INTO bluetooth_devices (id, name, instance_id, status, seen_at)
            VALUES (
                COALESCE((SELECT id FROM bluetooth_devices WHERE instance_id = ?), NULL),
                ?, ?, ?, ?
            )
            """, (d.get("instance_id"), d.get("name"), d.get("instance_id"), d.get("status"), now))
        except Exception as e:
            log(f"Errore salvataggio bluetooth {d}: {e}")
    conn.commit()


# --- INTEGRAZIONE NELLA MAIN LOOP ---
# 1) Dopo `conn = init_db()` aggiungere:
#       ensure_extra_tables(conn)
#
# 2) All'interno del loop principale, dopo gli scan host (ad es. dopo il for h in hosts: ...),
#    aggiungere queste righe per eseguire e salvare le scansioni WiFi e Bluetooth:
#
#       # WiFi scan
#       wifi_nets = scan_wifi()
#       log(f"Reti WiFi trovate: {len(wifi_nets)}")
#       store_wifi_scan(conn, wifi_nets)
#
#       # Bluetooth scan
#       bt_devs = scan_bluetooth()
#       log(f"Dispositivi Bluetooth trovati: {len(bt_devs)}")
#       store_bt_scan(conn, bt_devs)
#
# Nota: questi comandi usano `netsh` e PowerShell e richiedono che l'utente abbia i permessi necessari.


if __name__ == "__main__":
    main()