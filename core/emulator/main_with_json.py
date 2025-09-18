# core/emulator/main_with_json.py
"""
Traccar Emulator - Versione con supporto configurazione JSON
"""

import sys
import os

# Aggiungi il path del progetto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.traccar_framework import TraccarAPI
from core.emulator.traccar_emulator import TraccarSimulator, example_with_cache
from core.emulator.trip_config_loader import TripConfigLoader, ConfigurableSimulator
import logging

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("🚀 TRACCAR DEVICE SIMULATOR - VERSIONE JSON CONFIG")
    print("=" * 80)
    print("📁 Supporto configurazioni JSON per viaggi multipli")
    print("🗄️ Cache automatico per risparmiare API calls")
    print("🚛 Configurazioni predefinite e personalizzabili")
    print("=" * 80)

    print("\n🎯 OPZIONI DISPONIBILI:")
    print("\n--- CONFIGURAZIONI JSON ---")

    print("\n--- SETUP MANUALE ---")
    print("1. 🗄️ Test sistema cache")
    print("2. 🎯 Setup PERSONALIZZATO")
    print("3. 🚛 Setup MULTI-VEICOLO")

    print("\n--- VIAGGI PREDEFINITI ---")
    print("4. 🇮🇹 VIAGGI ITALIA")
    print("5. 🇪🇺 VIAGGI EUROPA")
    print("6. 🌍 VIAGGI INTERCONTINENTALI")
    print("7. 🚛 VIAGGI COMMERCIALI")
    print("8. 🎯 VIAGGI SPECIALI")
    print("9. ⚡ VIAGGI RAPIDI")
    print("10. 🚗 Viaggio completo cache")
    print("11. 📁 CARICA DA FILE JSON")
    print("12. 📝 CREA NUOVA CONFIGURAZIONE")
    print("13. 📊 MOSTRA CONFIGURAZIONI DISPONIBILI")

    choice = input("\nInserisci il numero (1-13): ").strip()

    # Setup Traccar
    traccar = TraccarAPI(
        host="torraccia.iliadboxos.it",
        port=58082,
        username="dspeziale@gmail.com",
        password="Elisa2025!",
        debug=False
    )

    GOOGLE_MAPS_KEY = "AIzaSyAZLNmrmri-HUzex5s4FaJZPk8xVeAyFVk"

    simulator = TraccarSimulator(
        traccar_api=traccar,
        google_maps_key=GOOGLE_MAPS_KEY,
        traccar_protocol_host="torraccia.iliadboxos.it",
        traccar_protocol_port=57355,
        cache_dir=f"option_{choice}_cache"
    )

    # Setup config loader
    config_loader = TripConfigLoader()
    configurable_sim = ConfigurableSimulator(simulator, config_loader)

    try:
        success = False

        # NUOVE OPZIONI JSON
        if choice == "11":
            print("\n📁 CARICA CONFIGURAZIONE JSON")
            print("=" * 50)

            selected_config = configurable_sim.interactive_config_selection()
            if selected_config:
                success = configurable_sim.load_and_execute_config(selected_config)

        elif choice == "12":
            print("\n📝 CREAZIONE NUOVA CONFIGURAZIONE")
            print("=" * 50)

            config_name = input("Nome file configurazione (es: my_trips.json): ").strip()
            if not config_name.endswith('.json'):
                config_name += '.json'

            template_path = config_loader.create_template(config_name)
            print(f"\n✅ Template creato: {template_path}")
            print("Modifica il file con i tuoi viaggi e riavvia con opzione 11")
            success = True

        elif choice == "13":
            print("\n📊 CONFIGURAZIONI DISPONIBILI")
            print("=" * 50)

            configs = config_loader.list_available_configs()

            if not configs:
                print("❌ Nessuna configurazione trovata")
                print(f"📁 Directory: {config_loader.config_dir}")
            else:
                print(f"📁 Directory: {config_loader.config_dir}\n")

                for config_file in configs:
                    try:
                        stats = config_loader.get_config_stats(config_file)
                        print(f"📄 {config_file}")
                        print(f"   📝 Nome: {stats['metadata'].get('name', 'N/A')}")
                        print(f"   🚛 Viaggi: {stats['total_trips']} (✅ {stats['enabled_trips']} abilitati)")
                        print(f"   🚗 Modalità: {stats['transport_modes']}")
                        print()
                    except Exception as e:
                        print(f"⚠️ {config_file}: errore lettura - {e}\n")

            success = True

        # OPZIONI ORIGINALI
        elif choice == "1":
            example_with_cache()
            success = True
        elif choice == "2":
            success = simulator.personal_setup()
        elif choice == "3":
            success = simulator.multi_vehicle_setup()
        elif choice == "4":
            success = simulator.italy_travels()
        elif choice == "5":
            success = simulator.europe_travels()
        elif choice == "6":
            success = simulator.intercontinental_travels()
        elif choice == "7":
            success = simulator.commercial_travels()
        elif choice == "8":
            success = simulator.special_travels()
        elif choice == "9":
            success = simulator.quick_travels()
        elif choice == "10":
            example_with_cache()
            success = True
        else:
            print("❌ Scelta non valida")

        if success and choice not in ["1", "10", "12", "13"]:
            print(f"\n✅ Opzione {choice} completata!")

    except KeyboardInterrupt:
        print("\n⏹️ Programma interrotto dall'utente")
    except Exception as e:
        print(f"\n❌ Errore: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print("\n🧹 Pulizia risorse...")
        simulator.stop_all_devices()
        print("✅ Completato!")


def quick_start_from_json():
    """Quick start diretto da file JSON"""
    print("\n⚡ QUICK START - CONFIGURAZIONE JSON")
    print("=" * 50)

    config_file = input("Nome file configurazione: ").strip()
    if not config_file:
        config_file = "italy_routes.json"

    if not config_file.endswith('.json'):
        config_file += '.json'

    traccar = TraccarAPI(
        host="torraccia.iliadboxos.it",
        port=58082,
        username="dspeziale@gmail.com",
        password="Elisa2025!",
        debug=False
    )

    simulator = TraccarSimulator(
        traccar_api=traccar,
        google_maps_key="AIzaSyAZLNmrmri-HUzex5s4FaJZPk8xVeAyFVk",
        traccar_protocol_host="torraccia.iliadboxos.it",
        traccar_protocol_port=57355
    )

    config_loader = TripConfigLoader()
    configurable_sim = ConfigurableSimulator(simulator, config_loader)

    try:
        success = configurable_sim.load_and_execute_config(config_file)

        if success:
            print("\n✅ Simulazione completata!")
        else:
            print("\n❌ Simulazione fallita")

    except Exception as e:
        print(f"\n❌ Errore: {e}")
    finally:
        simulator.stop_all_devices()