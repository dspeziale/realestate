# bluetooth_scan.py
import subprocess
import json
import time
from .config import PROBE_CONFIG, log

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
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    from .config import get_probe_config
    probe_config = get_probe_config()
    probe_id = probe_config['id']

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