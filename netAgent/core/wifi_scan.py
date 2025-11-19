# wifi_scan.py
import subprocess
import time
import json
import importlib.util
from .config import PROBE_CONFIG, log

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
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    from .config import get_probe_config
    probe_config = get_probe_config()
    probe_id = probe_config['id']
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