# core/emulator/trip_config_loader.py
"""
Sistema di caricamento configurazioni viaggi da file JSON
"""

import json
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger('TripConfigLoader')


@dataclass
class TripConfig:
    """Configurazione singolo viaggio"""
    name: str
    origin: str
    destination: str
    waypoints: List[str]
    transport_mode: str
    device_name: str
    update_interval: float
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TripConfig':
        """Crea TripConfig da dizionario"""
        return cls(
            name=data.get('name', ''),
            origin=data.get('origin', ''),
            destination=data.get('destination', ''),
            waypoints=data.get('waypoints', []),
            transport_mode=data.get('transport_mode', 'driving'),
            device_name=data.get('device_name', ''),
            update_interval=data.get('update_interval', 5.0),
            enabled=data.get('enabled', True)
        )


class TripConfigLoader:
    """Caricatore configurazioni viaggi da JSON"""

    def __init__(self, config_dir: str = "trip_configs"):
        self.config_dir = config_dir
        os.makedirs(config_dir, exist_ok=True)

    def load_config_file(self, filename: str) -> Dict[str, Any]:
        """Carica file configurazione JSON"""
        filepath = os.path.join(self.config_dir, filename)

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File configurazione non trovato: {filepath}")

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)

            logger.info(f"✅ Configurazione caricata: {filename}")
            return config

        except json.JSONDecodeError as e:
            logger.error(f"❌ Errore parsing JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Errore caricamento file: {e}")
            raise

    def load_trips(self, filename: str) -> List[TripConfig]:
        """Carica lista viaggi da file JSON"""
        config = self.load_config_file(filename)

        trips = []
        trip_list = config.get('trips', [])

        for i, trip_data in enumerate(trip_list):
            try:
                trip = TripConfig.from_dict(trip_data)

                # Validazione base
                if not trip.origin or not trip.destination:
                    logger.warning(f"⚠️ Viaggio {i + 1} incompleto - saltato")
                    continue

                if trip.enabled:
                    trips.append(trip)
                    logger.info(f"📍 Viaggio {i + 1}: {trip.origin} → {trip.destination}")
                else:
                    logger.info(f"⏸️ Viaggio {i + 1} disabilitato - saltato")

            except Exception as e:
                logger.error(f"❌ Errore viaggio {i + 1}: {e}")
                continue

        logger.info(f"📊 Totale viaggi caricati: {len(trips)}")
        return trips

    def get_config_stats(self, filename: str) -> Dict[str, Any]:
        """Ottieni statistiche configurazione"""
        config = self.load_config_file(filename)

        total_trips = len(config.get('trips', []))
        enabled_trips = sum(1 for t in config.get('trips', []) if t.get('enabled', True))

        transport_modes = {}
        for trip in config.get('trips', []):
            mode = trip.get('transport_mode', 'driving')
            transport_modes[mode] = transport_modes.get(mode, 0) + 1

        return {
            'filename': filename,
            'total_trips': total_trips,
            'enabled_trips': enabled_trips,
            'disabled_trips': total_trips - enabled_trips,
            'transport_modes': transport_modes,
            'metadata': config.get('metadata', {})
        }

    def list_available_configs(self) -> List[str]:
        """Lista tutti i file di configurazione disponibili"""
        configs = []

        for filename in os.listdir(self.config_dir):
            if filename.endswith('.json'):
                configs.append(filename)

        return sorted(configs)

    def create_template(self, filename: str = "template.json"):
        """Crea file template di esempio"""
        template = {
            "metadata": {
                "name": "Template Configurazione Viaggi",
                "description": "Template per configurare viaggi multipli",
                "created_at": datetime.now().isoformat(),
                "version": "1.0"
            },
            "global_settings": {
                "default_transport_mode": "driving",
                "default_update_interval": 5.0,
                "cache_enabled": True
            },
            "trips": [
                {
                    "name": "Roma → Milano",
                    "origin": "Roma",
                    "destination": "Milano",
                    "waypoints": ["Firenze"],
                    "transport_mode": "driving",
                    "device_name": "🚛 Camion 1",
                    "update_interval": 5.0,
                    "enabled": True
                },
                {
                    "name": "Napoli → Torino",
                    "origin": "Napoli",
                    "destination": "Torino",
                    "waypoints": ["Roma", "Firenze"],
                    "transport_mode": "driving",
                    "device_name": "🚛 Camion 2",
                    "update_interval": 5.0,
                    "enabled": True
                }
            ]
        }

        filepath = os.path.join(self.config_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Template creato: {filepath}")
        return filepath


class ConfigurableSimulator:
    """Simulatore con supporto configurazioni JSON"""

    def __init__(self, simulator, config_loader: TripConfigLoader):
        self.simulator = simulator
        self.config_loader = config_loader
        self.current_config = None

    def load_and_execute_config(self, config_filename: str) -> bool:
        """Carica ed esegue configurazione da file JSON"""
        print(f"\n📁 CARICAMENTO CONFIGURAZIONE: {config_filename}")
        print("=" * 60)

        try:
            # Statistiche configurazione
            stats = self.config_loader.get_config_stats(config_filename)

            print(f"📊 Statistiche configurazione:")
            print(f"   📝 Nome: {stats['metadata'].get('name', 'N/A')}")
            print(f"   🚛 Viaggi totali: {stats['total_trips']}")
            print(f"   ✅ Viaggi abilitati: {stats['enabled_trips']}")
            print(f"   ❌ Viaggi disabilitati: {stats['disabled_trips']}")
            print(f"   🚗 Modalità: {stats['transport_modes']}")

            # Carica viaggi
            trips = self.config_loader.load_trips(config_filename)

            if not trips:
                print("❌ Nessun viaggio valido trovato nella configurazione")
                return False

            # Carica dispositivi esistenti da Traccar
            print("\n🔍 Verifica dispositivi esistenti...")
            existing_devices = {}
            try:
                traccar_devices = self.simulator.traccar.devices.get_devices()
                for dev in traccar_devices:
                    existing_devices[dev['name']] = dev
                print(f"   📱 Trovati {len(existing_devices)} dispositivi su Traccar")
            except Exception as e:
                print(f"   ⚠️ Impossibile caricare dispositivi: {e}")

            # Converti in formato simulator
            simulator_trips = []

            for trip_config in trips:
                from core.emulator.traccar_emulator import Location, SimulatedDevice
                import threading

                # Verifica se device già esiste
                device = None

                if trip_config.device_name in existing_devices:
                    # Device esiste già su Traccar - riutilizzalo
                    existing = existing_devices[trip_config.device_name]

                    print(f"♻️ Riutilizzo dispositivo esistente: {trip_config.device_name} (ID: {existing['id']})")

                    # Crea SimulatedDevice da esistente
                    device = SimulatedDevice(
                        id=existing['id'],
                        name=existing['name'],
                        unique_id=existing['uniqueId'],
                        stop_event=threading.Event()
                    )

                    # Registra nel simulator
                    self.simulator.devices[existing['uniqueId']] = device

                else:
                    # Device non esiste - crealo
                    print(f"🆕 Creazione nuovo dispositivo: {trip_config.device_name}")
                    device = self.simulator.create_device(
                        trip_config.device_name,
                        force_new=False
                    )

                # Prepara route config
                origin = Location(0.0, 0.0, trip_config.origin)
                destination = Location(0.0, 0.0, trip_config.destination)
                waypoints = [Location(0.0, 0.0, wp) for wp in trip_config.waypoints]

                simulator_trips.append({
                    'device': device,
                    'route_config': {
                        'origin': origin,
                        'destination': destination,
                        'waypoints': waypoints,
                        'transport_mode': trip_config.transport_mode,
                        'name': trip_config.name
                    },
                    'sim_params': {
                        'update_interval': trip_config.update_interval,
                        'show_progress': True
                    }
                })

                print(f"✅ {trip_config.device_name}: {trip_config.name}")

            # Esegui tutti i viaggi
            print(f"\n🚀 Avvio {len(simulator_trips)} viaggi dalla configurazione...")
            return self.simulator._execute_all_trips(simulator_trips)

        except FileNotFoundError as e:
            print(f"❌ File non trovato: {e}")
            return False
        except Exception as e:
            print(f"❌ Errore caricamento configurazione: {e}")
            import traceback
            traceback.print_exc()
            return False

    def interactive_config_selection(self) -> Optional[str]:
        """Selezione interattiva file configurazione"""
        print("\n📂 FILE CONFIGURAZIONE DISPONIBILI")
        print("=" * 50)

        configs = self.config_loader.list_available_configs()

        if not configs:
            print("❌ Nessuna configurazione trovata")
            print(f"📁 Directory: {self.config_loader.config_dir}")

            create = input("\nCreare template di esempio? [s/n]: ").strip().lower()
            if create in ['s', 'si', 'y', 'yes']:
                template_path = self.config_loader.create_template()
                print(f"✅ Template creato: {template_path}")
                print("Modifica il file e riavvia il programma")

            return None

        print("File disponibili:")
        for i, config in enumerate(configs, 1):
            print(f"  {i}. {config}")

        choice = input(f"\nSeleziona configurazione [1-{len(configs)}]: ").strip()

        try:
            index = int(choice) - 1
            if 0 <= index < len(configs):
                return configs[index]
        except ValueError:
            pass

        print("❌ Selezione non valida")
        return None


def add_config_menu_to_simulator(simulator):
    """Aggiunge opzione configurazione JSON al menu principale"""
    config_loader = TripConfigLoader()
    configurable_sim = ConfigurableSimulator(simulator, config_loader)

    print("\n" + "=" * 80)
    print("📁 OPZIONE AGGIUNTIVA: CONFIGURAZIONE DA FILE JSON")
    print("=" * 80)

    # Crea template se non esistono config
    configs = config_loader.list_available_configs()
    if not configs:
        print("🔧 Nessuna configurazione trovata - creo template...")
        config_loader.create_template("example_trips.json")
        config_loader.create_template("italy_routes.json")

        # Crea configurazione esempio Italia
        italy_config = {
            "metadata": {
                "name": "Viaggi Italia - Configurazione Completa",
                "description": "Configurazione viaggi principali Italia",
                "created_at": datetime.now().isoformat(),
                "version": "1.0"
            },
            "global_settings": {
                "default_transport_mode": "driving",
                "default_update_interval": 5.0
            },
            "trips": [
                {
                    "name": "Roma → Milano Express",
                    "origin": "Roma",
                    "destination": "Milano",
                    "waypoints": ["Firenze", "Bologna"],
                    "transport_mode": "driving",
                    "device_name": "🚛 TIR Nord 1",
                    "update_interval": 3.0,
                    "enabled": True
                },
                {
                    "name": "Milano → Napoli Merci",
                    "origin": "Milano",
                    "destination": "Napoli",
                    "waypoints": ["Bologna", "Roma"],
                    "transport_mode": "driving",
                    "device_name": "🚛 TIR Sud 1",
                    "update_interval": 5.0,
                    "enabled": True
                },
                {
                    "name": "Torino → Bari",
                    "origin": "Torino",
                    "destination": "Bari",
                    "waypoints": ["Milano", "Bologna", "Napoli"],
                    "transport_mode": "driving",
                    "device_name": "🚛 Camion Adriatico",
                    "update_interval": 5.0,
                    "enabled": True
                },
                {
                    "name": "Venezia → Palermo",
                    "origin": "Venezia",
                    "destination": "Palermo",
                    "waypoints": ["Bologna", "Roma", "Napoli"],
                    "transport_mode": "driving",
                    "device_name": "🚛 Furgone Sicilia",
                    "update_interval": 7.0,
                    "enabled": True
                }
            ]
        }

        with open("trip_configs/italy_routes.json", 'w', encoding='utf-8') as f:
            json.dump(italy_config, f, indent=2, ensure_ascii=False)

        print("✅ Configurazioni esempio create!")
        print("📁 Directory: trip_configs/")
        print("   - template.json")
        print("   - example_trips.json")
        print("   - italy_routes.json")

    # Menu selezione
    print("\n11. 📁 CARICA DA FILE JSON (configurazione multipla)")

    choice = input("\nVuoi usare configurazione JSON? [11 per sì, altro per no]: ").strip()

    if choice == "11":
        selected_config = configurable_sim.interactive_config_selection()

        if selected_config:
            return configurable_sim.load_and_execute_config(selected_config)

    return False