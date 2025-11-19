import subprocess
import time
import datetime
import xml.etree.ElementTree as ET
import sqlite3
from .config import get_probe_config, get_scan_config, DB_FILE, log
from .oui import get_vendor_from_mac
from .device_classifier import DeviceClassifier


def nmap_ping_scan(target=None):
    """Esegue un ping scan sulla rete con nmap"""
    if target is None:
        scan_config = get_scan_config()
        target = scan_config['target_network']

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


def upsert_device(conn, ip, mac, hostname, ports_open, os_info, device_type, vendor):
    """Inserisce o aggiorna un dispositivo nel database"""
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    probe_config = get_probe_config()  # MODIFICATO: usa get_probe_config()
    probe_id = probe_config['id']

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
            UPDATE devices SET ip = ?, mac = ?, last_seen = ?, hostname = ?, 
            ports_open = ?, os_info = ?, device_type = ?, vendor = ?
            WHERE id = ?
        """, (ip, mac, now, hostname, ports_open, os_info, device_type, vendor, device_id))
    else:
        cursor.execute("""
            INSERT INTO devices (probe_id, ip, mac, first_seen, last_seen, 
            hostname, ports_open, os_info, device_type, vendor)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (probe_id, ip, mac, now, now, hostname, ports_open, os_info, device_type, vendor))

    conn.commit()


def scan_lan_network(conn):
    """Esegue la scansione completa della rete LAN"""
    log("=== INIZIO SCANSIONE LAN ===")

    scan_config = get_scan_config()  # MODIFICATO: ottiene configurazione
    target_network = scan_config['target_network']

    scan_xml = nmap_ping_scan(target_network)  # MODIFICATO: passa target_network
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

        # Ottieni vendor da OUI
        vendor_from_oui = get_vendor_from_mac(mac, cursor) if mac else None

        # Classifica dispositivo
        device_type, vendor = DeviceClassifier.classify_device(
            mac, hostname, ports_open, os_info, vendor_from_oui
        )

        # Salva nel database
        upsert_device(conn, ip, mac, hostname, ports_open, os_info, device_type, vendor)

        # Log con informazioni complete
        vendor_info = f" vendor={vendor}" if vendor != "Unknown" else ""
        device_type_info = f" type={device_type}" if device_type != "Unknown" else ""

        log(f"  {ip} {mac or 'N/A'} {hostname or 'N/A'}{vendor_info}{device_type_info} ports={ports_open or 'none'} os={os_info or 'N/A'}")

    log("=== FINE SCANSIONE LAN ===")