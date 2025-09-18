# core/emulator/devices_loader.py
"""
Device Bulk Loader - Caricamento massivo dispositivi da JSON
Sistema per creare, aggiornare ed eliminare dispositivi Traccar in batch
"""

import json
import os
import sys
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Aggiungi path per importare TraccarAPI
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from core.traccar_framework import TraccarAPI, TraccarException

logger = logging.getLogger('DevicesLoader')


@dataclass
class DeviceConfig:
    """Configurazione singolo dispositivo"""
    name: str
    unique_id: str
    category: str = "default"
    model: str = None
    contact: str = None
    phone: str = None
    disabled: bool = False
    group_id: int = None
    attributes: dict = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceConfig':
        """Crea DeviceConfig da dizionario"""
        return cls(
            name=data.get('name'),
            unique_id=data.get('unique_id'),
            category=data.get('category', 'default'),
            model=data.get('model'),
            contact=data.get('contact'),
            phone=data.get('phone'),
            disabled=data.get('disabled', False),
            group_id=data.get('group_id'),
            attributes=data.get('attributes', {})
        )


class DevicesBulkLoader:
    """Caricatore massivo dispositivi"""

    def __init__(self, traccar_api: TraccarAPI, config_dir: str = "device_configs"):
        self.traccar = traccar_api
        self.config_dir = config_dir
        os.makedirs(config_dir, exist_ok=True)

        self.stats = {
            'created': 0,
            'updated': 0,
            'deleted': 0,
            'errors': 0,
            'skipped': 0
        }

    def load_config_file(self, filename: str) -> Dict[str, Any]:
        """Carica file configurazione JSON"""
        filepath = os.path.join(self.config_dir, filename)

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File non trovato: {filepath}")

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)

            logger.info(f"✅ Configurazione caricata: {filename}")
            return config

        except json.JSONDecodeError as e:
            logger.error(f"❌ Errore parsing JSON: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Errore caricamento: {e}")
            raise

    def get_existing_devices(self) -> Dict[str, Dict]:
        """Ottiene dispositivi esistenti da Traccar"""
        try:
            devices = self.traccar.devices.get_devices()
            return {d['uniqueId']: d for d in devices}
        except TraccarException as e:
            logger.error(f"❌ Errore caricamento dispositivi: {e}")
            return {}

    def create_device(self, device_config: DeviceConfig) -> bool:
        """Crea nuovo dispositivo"""
        try:
            # Crea dispositivo con parametri posizionali richiesti
            result = self.traccar.devices.create_device(
                name=device_config.name,
                unique_id=device_config.unique_id,
                category=device_config.category,
                model=device_config.model,
                contact=device_config.contact,
                phone=device_config.phone,
                disabled=device_config.disabled,
                groupId=device_config.group_id,
                attributes=device_config.attributes or {}
            )

            logger.info(f"✅ Creato: {device_config.name} (ID: {result['id']})")
            self.stats['created'] += 1
            return True

        except TraccarException as e:
            logger.error(f"❌ Errore creazione {device_config.name}: {e}")
            self.stats['errors'] += 1
            return False

    def update_device(self, device_id: int, device_config: DeviceConfig) -> bool:
        """Aggiorna dispositivo esistente"""
        try:
            # Prepara dati per update - tutti i campi devono essere presenti
            update_data = {
                'id': device_id,
                'name': device_config.name,
                'uniqueId': device_config.unique_id,
                'category': device_config.category,
                'disabled': device_config.disabled,
                'model': device_config.model or '',
                'contact': device_config.contact or '',
                'phone': device_config.phone or '',
                'groupId': device_config.group_id,
                'attributes': device_config.attributes or {}
            }

            result = self.traccar.devices.update_device(device_id, update_data)

            logger.info(f"🔄 Aggiornato: {device_config.name} (ID: {device_id})")
            self.stats['updated'] += 1
            return True

        except TraccarException as e:
            logger.error(f"❌ Errore aggiornamento {device_config.name}: {e}")
            self.stats['errors'] += 1
            return False

    def delete_device(self, device_id: int, device_name: str) -> bool:
        """Elimina dispositivo"""
        try:
            self.traccar.devices.delete_device(device_id)

            logger.info(f"🗑️ Eliminato: {device_name} (ID: {device_id})")
            self.stats['deleted'] += 1
            return True

        except TraccarException as e:
            logger.error(f"❌ Errore eliminazione {device_name}: {e}")
            self.stats['errors'] += 1
            return False

    def load_devices_from_json(self, filename: str, mode: str = 'create_or_update') -> Dict[str, Any]:
        """
        Carica dispositivi da file JSON

        Modes:
        - create_only: Crea solo nuovi dispositivi
        - update_only: Aggiorna solo esistenti
        - create_or_update: Crea nuovi o aggiorna esistenti (default)
        - delete: Elimina dispositivi nel file
        """
        print(f"\n📁 CARICAMENTO DISPOSITIVI: {filename}")
        print(f"⚙️ Modalità: {mode}")
        print("=" * 60)

        try:
            # Carica configurazione
            config = self.load_config_file(filename)
            devices_config = config.get('devices', [])

            if not devices_config:
                print("❌ Nessun dispositivo trovato nel file")
                return self.stats

            # Ottieni dispositivi esistenti
            existing_devices = self.get_existing_devices()
            print(f"📱 Dispositivi esistenti su Traccar: {len(existing_devices)}")
            print(f"📝 Dispositivi da processare: {len(devices_config)}\n")

            # Processa ogni dispositivo
            for i, device_data in enumerate(devices_config, 1):
                try:
                    device_config = DeviceConfig.from_dict(device_data)

                    if not device_config.name or not device_config.unique_id:
                        logger.warning(f"⚠️ Dispositivo {i} incompleto - saltato")
                        self.stats['skipped'] += 1
                        continue

                    exists = device_config.unique_id in existing_devices

                    print(f"[{i}/{len(devices_config)}] {device_config.name} ({device_config.unique_id})")

                    if mode == 'delete':
                        if exists:
                            existing = existing_devices[device_config.unique_id]
                            self.delete_device(existing['id'], device_config.name)
                        else:
                            logger.info(f"⏭️ Non esiste - saltato")
                            self.stats['skipped'] += 1

                    elif mode == 'create_only':
                        if not exists:
                            self.create_device(device_config)
                        else:
                            logger.info(f"⏭️ Già esistente - saltato")
                            self.stats['skipped'] += 1

                    elif mode == 'update_only':
                        if exists:
                            existing = existing_devices[device_config.unique_id]
                            self.update_device(existing['id'], device_config)
                        else:
                            logger.info(f"⏭️ Non esiste - saltato")
                            self.stats['skipped'] += 1

                    elif mode == 'create_or_update':
                        if exists:
                            existing = existing_devices[device_config.unique_id]
                            self.update_device(existing['id'], device_config)
                        else:
                            self.create_device(device_config)

                except Exception as e:
                    logger.error(f"❌ Errore dispositivo {i}: {e}")
                    self.stats['errors'] += 1
                    continue

            # Statistiche finali
            print("\n" + "=" * 60)
            print("📊 STATISTICHE OPERAZIONE:")
            print(f"   ✅ Creati: {self.stats['created']}")
            print(f"   🔄 Aggiornati: {self.stats['updated']}")
            print(f"   🗑️ Eliminati: {self.stats['deleted']}")
            print(f"   ⏭️ Saltati: {self.stats['skipped']}")
            print(f"   ❌ Errori: {self.stats['errors']}")
            print("=" * 60)

            return self.stats

        except Exception as e:
            logger.error(f"❌ Errore generale: {e}")
            import traceback
            traceback.print_exc()
            return self.stats

    def create_template(self, filename: str = "devices_template.json", num_devices: int = 5):
        """Crea file template di esempio"""
        template = {
            "metadata": {
                "name": "Template Dispositivi Traccar",
                "description": "Template per caricamento massivo dispositivi",
                "created_at": datetime.now().isoformat(),
                "version": "1.0"
            },
            "global_settings": {
                "default_category": "truck",
                "auto_generate_ids": False
            },
            "devices": []
        }

        # Genera dispositivi di esempio
        categories = ['truck', 'car', 'van', 'motorcycle', 'bus']

        for i in range(1, num_devices + 1):
            device = {
                "name": f"Veicolo {i:03d}",
                "unique_id": f"DEVICE{i:05d}",
                "category": categories[i % len(categories)],
                "model": f"Model {i}",
                "contact": f"contact{i}@example.com",
                "phone": f"+39 123 456 {i:04d}",
                "disabled": False,
                "group_id": None,
                "attributes": {
                    "fuel_type": "diesel" if i % 2 == 0 else "gasoline",
                    "max_speed": 120,
                    "license_plate": f"AB{i:03d}CD"
                }
            }
            template['devices'].append(device)

        filepath = os.path.join(self.config_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=2, ensure_ascii=False)

        logger.info(f"✅ Template creato: {filepath}")
        print(f"📝 Template creato con {num_devices} dispositivi di esempio")
        return filepath

    def export_existing_devices(self, filename: str = "existing_devices.json"):
        """Esporta dispositivi esistenti in formato JSON"""
        try:
            devices = self.traccar.devices.get_devices()

            config = {
                "metadata": {
                    "name": "Export Dispositivi Esistenti",
                    "description": f"Export da Traccar del {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    "exported_at": datetime.now().isoformat(),
                    "total_devices": len(devices)
                },
                "devices": []
            }

            for device in devices:
                device_config = {
                    "name": device.get('name'),
                    "unique_id": device.get('uniqueId'),
                    "category": device.get('category', 'default'),
                    "model": device.get('model'),
                    "contact": device.get('contact'),
                    "phone": device.get('phone'),
                    "disabled": device.get('disabled', False),
                    "group_id": device.get('groupId'),
                    "attributes": device.get('attributes', {})
                }
                config['devices'].append(device_config)

            filepath = os.path.join(self.config_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            print(f"✅ Esportati {len(devices)} dispositivi in: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"❌ Errore export: {e}")
            return None

    def list_config_files(self):
        """Lista file configurazione disponibili"""
        files = []
        for filename in os.listdir(self.config_dir):
            if filename.endswith('.json'):
                files.append(filename)
        return sorted(files)


def interactive_menu():
    """Menu interattivo per caricamento dispositivi"""
    print("\n" + "=" * 80)
    print("📱 DEVICE BULK LOADER - Caricamento Massivo Dispositivi Traccar")
    print("=" * 80)

    # Setup Traccar
    traccar = TraccarAPI(
        host="torraccia.iliadboxos.it",
        port=58082,
        username="dspeziale@gmail.com",
        password="Elisa2025!",
        debug=False
    )

    loader = DevicesBulkLoader(traccar)

    while True:
        print("\n📋 MENU PRINCIPALE:")
        print("1. 📁 Carica dispositivi da JSON")
        print("2. 📝 Crea template esempio")
        print("3. 💾 Esporta dispositivi esistenti")
        print("4. 📊 Lista file configurazione")
        print("5. 🔧 Test connessione Traccar")
        print("0. ❌ Esci")

        choice = input("\nScelta [0-5]: ").strip()

        if choice == '0':
            print("👋 Arrivederci!")
            break

        elif choice == '1':
            # Carica dispositivi
            files = loader.list_config_files()

            if not files:
                print("❌ Nessun file configurazione trovato")
                create = input("Creare template? [s/n]: ").strip().lower()
                if create in ['s', 'si', 'y', 'yes']:
                    loader.create_template()
                continue

            print("\nFile disponibili:")
            for i, f in enumerate(files, 1):
                print(f"  {i}. {f}")

            file_choice = input(f"\nSeleziona file [1-{len(files)}]: ").strip()

            try:
                file_index = int(file_choice) - 1
                if 0 <= file_index < len(files):
                    selected_file = files[file_index]

                    print("\nModalità operazione:")
                    print("1. Crea o Aggiorna (default)")
                    print("2. Solo Crea nuovi")
                    print("3. Solo Aggiorna esistenti")
                    print("4. Elimina dispositivi")

                    mode_choice = input("\nScelta [1-4]: ").strip()

                    modes = {
                        '1': 'create_or_update',
                        '2': 'create_only',
                        '3': 'update_only',
                        '4': 'delete'
                    }

                    mode = modes.get(mode_choice, 'create_or_update')

                    if mode == 'delete':
                        confirm = input(
                            "\n⚠️ ATTENZIONE: Stai per ELIMINARE dispositivi! Confermi? [si/no]: ").strip().lower()
                        if confirm != 'si':
                            print("Operazione annullata")
                            continue

                    loader.load_devices_from_json(selected_file, mode)

            except (ValueError, IndexError):
                print("❌ Selezione non valida")

        elif choice == '2':
            # Crea template
            filename = input("\nNome file [devices_template.json]: ").strip()
            if not filename:
                filename = "devices_template.json"

            num_devices = input("Numero dispositivi esempio [5]: ").strip()
            try:
                num_devices = int(num_devices) if num_devices else 5
            except ValueError:
                num_devices = 5

            loader.create_template(filename, num_devices)

        elif choice == '3':
            # Esporta esistenti
            filename = input("\nNome file export [existing_devices.json]: ").strip()
            if not filename:
                filename = "existing_devices.json"

            loader.export_existing_devices(filename)

        elif choice == '4':
            # Lista file
            files = loader.list_config_files()
            print(f"\n📁 File in {loader.config_dir}:")
            if files:
                for f in files:
                    filepath = os.path.join(loader.config_dir, f)
                    size = os.path.getsize(filepath)
                    print(f"  📄 {f} ({size} bytes)")
            else:
                print("  (nessun file)")

        elif choice == '5':
            # Test connessione
            print("\n🔌 Test connessione Traccar...")
            if traccar.test_connection():
                print("✅ Connessione OK!")
            else:
                print("❌ Connessione fallita")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    interactive_menu()