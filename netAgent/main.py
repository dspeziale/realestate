# main.py
import time
import threading
import sqlite3
import signal
import sys
from core.config import load_probe_config, get_scan_config, get_sniffing_config, DB_FILE, log
from core.database import init_db, update_probe_info
from core.oui import check_oui_update
from core.lan_scan import scan_lan_network
from core.wifi_scan import scan_wifi, store_wifi_scan
from core.bluetooth_scan import scan_bluetooth, store_bluetooth_scan
from core.packet_sniffing import start_packet_capture, stop_packet_capture, get_sniffing_stats

# Variabile globale per gestire l'arresto pulito
running = True


def signal_handler(sig, frame):
    """Gestisce l'arresto tramite Ctrl+C"""
    global running
    log("\nRicevuto segnale di interruzione...")
    running = False
    sys.exit(0)


def main():
    """Funzione principale con loop di scansione"""
    global running

    # Registra il gestore di segnale
    signal.signal(signal.SIGINT, signal_handler)

    log("========================================")
    log("AVVIO NETWORK SCANNER")
    log("========================================")

    # Carica la configurazione della sonda
    probe_config = load_probe_config()

    # Inizializza database
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    init_db()
    update_probe_info(conn)

    # Aggiorna OUI se necessario
    check_oui_update()

    # Ottieni configurazioni
    scan_config = get_scan_config()
    sniffing_config = get_sniffing_config()  # CORRETTO: definito qui
    scan_interval = scan_config['scan_interval']

    # Avvia packet capture se abilitato
    if sniffing_config['enabled']:
        start_packet_capture(conn)
    else:
        log("Packet capture disabilitato nella configurazione")

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

    def sniffing_stats_job():
        """Job per loggare le statistiche del packet capture"""
        if sniffing_config['enabled']:  # CORRETTO: ora sniffing_config è definito
            c = sqlite3.connect(DB_FILE, check_same_thread=False)
            stats = get_sniffing_stats(c)
            if stats:
                log(f"Packet Capture - Sessione: {stats['session_id']}, "
                    f"Pacchetti: {stats['packet_count']}, "
                    f"IP sorgenti unici: {stats['unique_src_ips']}, "
                    f"Payload ASCII: {stats['ascii_packets']} ({stats['ascii_percentage']}%)")
            c.close()

    cycle_count = 0
    while running:
        try:
            log(f"\n{'=' * 50}")
            log(f"CICLO SCANSIONE #{cycle_count} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
            log(f"{'=' * 50}")

            # Esegue scansioni in thread paralleli
            t1 = threading.Thread(target=lan_job)
            t2 = threading.Thread(target=wifi_job)
            t3 = threading.Thread(target=bt_job)

            t1.start();
            t2.start();
            t3.start()
            t1.join();
            t2.join();
            t3.join()

            # Logga statistiche packet capture ogni 5 cicli
            if cycle_count % 5 == 0:
                sniffing_stats_job()

            log(f"\n{'=' * 50}")
            log(f"Attendo {scan_interval} secondi prima del prossimo scan")
            log(f"{'=' * 50}\n")

            # Attesa con controllo periodico per permettere l'arresto pulito
            for _ in range(scan_interval):
                if not running:
                    break
                time.sleep(1)

            cycle_count += 1

        except KeyboardInterrupt:
            log("\nInterruzione tramite Ctrl+C...")
            running = False
            break
        except Exception as e:
            log(f"Errore nel ciclo principale: {e}")
            time.sleep(10)  # Attesa prima di riprovare in caso di errore

    # Pulizia finale
    log("\n========================================")
    log("ARRESTO NETWORK SCANNER")
    log("========================================")

    # Ferma packet capture
    if sniffing_config['enabled']:  # CORRETTO: ora sniffing_config è definito
        stop_packet_capture(conn)

    conn.close()
    log("Database chiuso. Arrivederci!")


if __name__ == "__main__":
    main()