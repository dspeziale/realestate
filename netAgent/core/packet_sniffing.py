# packet_sniffing.py
import threading
import time
import base64
import sqlite3
import importlib.util
import subprocess
from datetime import datetime
from .config import get_probe_config, get_sniffing_config, DB_FILE, log

# Variabili globali per packet sniffing
SNIFFING_SESSION_ID = None
SNIFFING_THREAD = None
SNIFFING_STOP_FLAG = threading.Event()
PACKET_BUFFER = []
PACKET_BUFFER_LOCK = threading.Lock()


def get_network_interface():
    """Rileva l'interfaccia di rete principale"""
    try:
        # Prova con scapy se disponibile
        if importlib.util.find_spec("scapy") is not None:
            from scapy.arch import get_if_list, get_working_if
            return get_working_if()

        # Fallback per Windows
        import socket
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
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        probe_config = get_probe_config()  # MODIFICATO: dentro try/except
        probe_id = probe_config['id']
    except Exception as e:
        log(f"ERRORE: Impossibile ottenere configurazione sonda: {e}")
        return None

    sniffing_config = get_sniffing_config()
    bpf_filter = sniffing_config['filter']

    if interface is None:
        interface = sniffing_config['interface'] or get_network_interface() or "auto"

    try:
        cursor.execute("""
            INSERT INTO sniffing_sessions 
            (probe_id, started_at, interface, filter, status)
            VALUES (?, ?, ?, ?, 'running')
        """, (probe_id, now, interface, bpf_filter))

        SNIFFING_SESSION_ID = cursor.lastrowid
        conn.commit()

        log(f"Sessione sniffing avviata: ID={SNIFFING_SESSION_ID}, interface={interface}")
        return SNIFFING_SESSION_ID
    except Exception as e:
        log(f"Errore creazione sessione sniffing: {e}")
        return None


def stop_sniffing_session(conn):
    """Termina la sessione di sniffing corrente"""
    global SNIFFING_SESSION_ID

    if SNIFFING_SESSION_ID is None:
        return

    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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


def is_printable_ascii(data):
    """Verifica se i dati sono ASCII stampabile"""
    try:
        decoded = data.decode('ascii', errors='ignore')
        # Controlla se almeno il 70% dei caratteri sono stampabili
        if len(decoded) > 0:
            printable_count = sum(1 for c in decoded if 32 <= ord(c) <= 126)
            return (printable_count / len(decoded)) > 0.7
        return False
    except:
        return False


def bytes_to_ascii_preview(data, max_length=100):
    """Converte i bytes in una preview ASCII leggibile"""
    try:
        # Prova a decodificare come ASCII
        decoded = data.decode('ascii', errors='ignore')

        # Filtra solo caratteri stampabili
        printable = ''.join(c for c in decoded if 32 <= ord(c) <= 126)

        # Tronca alla lunghezza massima
        if len(printable) > max_length:
            return printable[:max_length] + "..."
        else:
            return printable

    except Exception:
        # Fallback a hex se non è decodificabile
        hex_repr = data.hex()
        if len(hex_repr) > max_length * 2:
            return f"hex:{hex_repr[:max_length * 2]}..."
        else:
            return f"hex:{hex_repr}"


def parse_packet(packet):
    """Estrae informazioni da un pacchetto scapy"""
    try:
        from scapy.layers.inet import IP, TCP, UDP
        from scapy.layers.l2 import Ether

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

        packet_info = {
            'timestamp': timestamp,
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
            'payload_hex': None,
            'payload_ascii': None,
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

                # Estrai e analizza il payload
                if tcp.payload:
                    payload_bytes = bytes(tcp.payload)
                    packet_info['payload_hex'] = payload_bytes.hex()

                    # Prova conversione ASCII
                    if is_printable_ascii(payload_bytes):
                        packet_info['payload_ascii'] = bytes_to_ascii_preview(payload_bytes)
                        packet_info['payload_preview'] = f"ASCII: {packet_info['payload_ascii']}"
                    else:
                        packet_info['payload_preview'] = f"HEX: {payload_bytes[:50].hex()}..."

            # UDP
            elif packet.haslayer(UDP):
                udp = packet[UDP]
                packet_info['src_port'] = udp.sport
                packet_info['dst_port'] = udp.dport
                packet_info['protocol'] = 'UDP'

                if udp.payload:
                    payload_bytes = bytes(udp.payload)
                    packet_info['payload_hex'] = payload_bytes.hex()

                    # Prova conversione ASCII
                    if is_printable_ascii(payload_bytes):
                        packet_info['payload_ascii'] = bytes_to_ascii_preview(payload_bytes)
                        packet_info['payload_preview'] = f"ASCII: {packet_info['payload_ascii']}"
                    else:
                        packet_info['payload_preview'] = f"HEX: {payload_bytes[:50].hex()}..."

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
    try:
        probe_config = get_probe_config()  # MODIFICATO: dentro try/except
        probe_id = probe_config['id']
    except Exception as e:
        log(f"ERRORE: Impossibile ottenere configurazione sonda: {e}")
        return

    saved_count = 0

    # Dizionario per statistiche aggregate
    stats = {}

    for pkt in packets:
        try:
            # Salva pacchetto completo
            cursor.execute("""
                INSERT INTO captured_packets 
                (probe_id, session_id, timestamp, src_ip, dst_ip, src_port, dst_port,
                 protocol, length, src_mac, dst_mac, flags, payload_preview, payload_hex, payload_ascii, raw_packet)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                pkt.get('payload_hex'),
                pkt.get('payload_ascii'),
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
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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


def sniffing_worker(interface, bpf_filter):
    """Thread worker per packet capture"""
    global PACKET_BUFFER

    try:
        from scapy.all import sniff

        sniffing_config = get_sniffing_config()
        batch_interval = sniffing_config['batch_interval']
        max_packets = sniffing_config['max_packets_per_batch']

        log(f"Sniffing avviato su interfaccia: {interface}")
        log(f"Filtro BPF: '{bpf_filter}' (vuoto = tutti i pacchetti)")

        # Sniffing continuo con timeout per controllare stop flag
        while not SNIFFING_STOP_FLAG.is_set():
            try:
                sniff(
                    iface=interface,
                    prn=packet_callback,
                    filter=bpf_filter if bpf_filter else None,
                    timeout=batch_interval,
                    store=False
                )

                # Salva batch se ci sono pacchetti
                with PACKET_BUFFER_LOCK:
                    if PACKET_BUFFER:
                        packets_to_save = PACKET_BUFFER[:max_packets]
                        PACKET_BUFFER = PACKET_BUFFER[max_packets:]

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

    sniffing_config = get_sniffing_config()

    if not sniffing_config['enabled']:
        log("Packet capture disabilitato nella configurazione")
        return

    try:
        # Verifica disponibilità scapy
        if importlib.util.find_spec("scapy") is None:
            log("ATTENZIONE: Scapy non installato - packet capture disabilitato")
            log("Installare con: pip install scapy")
            return

        # Crea sessione nel database
        interface = sniffing_config['interface'] or get_network_interface()
        if not interface:
            log("ERRORE: Impossibile rilevare interfaccia di rete")
            return

        session_id = start_sniffing_session(conn, interface)
        if session_id is None:
            log("ERRORE: Impossibile avviare sessione di sniffing")
            return

        # Avvia thread di capture
        SNIFFING_STOP_FLAG.clear()
        SNIFFING_THREAD = threading.Thread(
            target=sniffing_worker,
            args=(interface, sniffing_config['filter']),
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


def get_sniffing_stats(conn):
    """Restituisce statistiche del packet capture corrente"""
    if SNIFFING_SESSION_ID is None:
        return None

    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM captured_packets WHERE session_id = ?",
            (SNIFFING_SESSION_ID,)
        )
        packet_count = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(DISTINCT src_ip) FROM captured_packets WHERE session_id = ?",
            (SNIFFING_SESSION_ID,)
        )
        unique_src_ips = cursor.fetchone()[0]

        # Statistiche sui payload
        cursor.execute(
            "SELECT COUNT(*) FROM captured_packets WHERE session_id = ? AND payload_ascii IS NOT NULL",
            (SNIFFING_SESSION_ID,)
        )
        ascii_packets = cursor.fetchone()[0]

        return {
            'session_id': SNIFFING_SESSION_ID,
            'packet_count': packet_count,
            'unique_src_ips': unique_src_ips,
            'ascii_packets': ascii_packets,
            'ascii_percentage': round((ascii_packets / packet_count * 100), 2) if packet_count > 0 else 0
        }
    except Exception as e:
        log(f"Errore statistiche packet capture: {e}")
        return None