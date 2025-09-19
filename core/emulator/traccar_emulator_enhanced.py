# core/emulator/traccar_emulator_enhanced.py
"""
Traccar Emulator Enhanced - Con sistema di geocoding integrato
Estende TraccarSimulator con funzionalità di reverse geocoding
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass

# Import del simulatore base
from core.emulator.traccar_emulator import (
    TraccarSimulator, Location, RoutePoint, SimulatedDevice,
    TraccarAPI, GoogleMapsClient
)

# Import servizio geocoding
from core.services.geocoding_service import GeocodingService, Address

logger = logging.getLogger('TraccarEmulatorEnhanced')


class EnhancedTraccarSimulator(TraccarSimulator):
    """Simulatore Traccar con geocoding integrato"""

    def __init__(self, traccar_api: TraccarAPI, google_maps_key: str,
                 traccar_protocol_host: str, traccar_protocol_port: int = 57355,
                 cache_dir: str = "route_cache",
                 geocoding_cache_db: str = "data/geocoding_cache.db"):

        # Inizializza simulatore base
        super().__init__(
            traccar_api=traccar_api,
            google_maps_key=google_maps_key,
            traccar_protocol_host=traccar_protocol_host,
            traccar_protocol_port=traccar_protocol_port,
            cache_dir=cache_dir
        )

        # Inizializza servizio geocoding
        try:
            self.geocoding = GeocodingService(
                api_key=google_maps_key,
                cache_db_path=geocoding_cache_db
            )
            self.geocoding_enabled = True
            logger.info(f"🌍 Geocoding service integrato: {geocoding_cache_db}")
        except Exception as e:
            logger.warning(f"⚠️ Geocoding service non disponibile: {e}")
            self.geocoding = None
            self.geocoding_enabled = False

    def get_address_for_location(self, latitude: float, longitude: float) -> Optional[Address]:
        """Ottiene indirizzo per una posizione GPS"""
        if not self.geocoding_enabled:
            return None

        try:
            return self.geocoding.get_address_from_coords(latitude, longitude)
        except Exception as e:
            logger.error(f"Errore geocoding: {e}")
            return None

    def enrich_route_with_addresses(self, route_points: List[RoutePoint],
                                    sample_interval: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Arricchisce i punti del percorso con indirizzi geocodificati

        Args:
            route_points: Lista di RoutePoint
            sample_interval: Intervallo campionamento (default: calcolo automatico)

        Returns:
            Lista di dizionari con coordinate e indirizzi
        """
        if not self.geocoding_enabled:
            logger.warning("Geocoding non disponibile")
            return []

        enriched_points = []

        # Calcola intervallo campionamento
        if sample_interval is None:
            sample_interval = max(1, len(route_points) // 20)  # Max 20 indirizzi

        for i, point in enumerate(route_points):
            enriched_point = {
                'index': i,
                'latitude': point.location.latitude,
                'longitude': point.location.longitude,
                'speed': point.speed,
                'bearing': point.bearing,
                'distance_from_start': point.distance_from_start
            }

            # Aggiungi timestamp se disponibile
            if point.location.timestamp:
                enriched_point['timestamp'] = point.location.timestamp.isoformat()

            # Geocodifica punti strategici
            if i == 0 or i == len(route_points) - 1 or i % sample_interval == 0:
                address = self.get_address_for_location(
                    point.location.latitude,
                    point.location.longitude
                )

                if address:
                    enriched_point['address'] = {
                        'formatted': address.formatted_address,
                        'city': address.city,
                        'state': address.state,
                        'country': address.country
                    }

                    # Flag punto speciale
                    if i == 0:
                        enriched_point['point_type'] = 'start'
                    elif i == len(route_points) - 1:
                        enriched_point['point_type'] = 'end'
                    else:
                        enriched_point['point_type'] = 'waypoint'

            enriched_points.append(enriched_point)

        return enriched_points

    def get_device_current_address(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Ottiene l'indirizzo corrente di un dispositivo"""
        if not self.geocoding_enabled:
            return None

        device = self.devices.get(device_id)

        if not device or not device.current_location:
            return None

        address = self.get_address_for_location(
            device.current_location.latitude,
            device.current_location.longitude
        )

        if address:
            return {
                'device_id': device_id,
                'device_name': device.name,
                'latitude': device.current_location.latitude,
                'longitude': device.current_location.longitude,
                'address': {
                    'formatted': address.formatted_address,
                    'city': address.city,
                    'state': address.state,
                    'country': address.country,
                    'postal_code': address.postal_code
                },
                'timestamp': datetime.now().isoformat()
            }

        return None

    def get_trip_summary_with_addresses(self, device_id: str) -> Dict[str, Any]:
        """Genera sommario viaggio con indirizzi di partenza e arrivo"""
        device = self.devices.get(device_id)

        if not device or not device.route:
            return {'error': 'Device or route not found'}

        # Primo e ultimo punto
        start_point = device.route[0]
        end_point = device.route[-1]
        current_index = min(device.route_index, len(device.route) - 1)

        # Inizializza summary base
        summary = {
            'device_id': device_id,
            'device_name': device.name,
            'status': 'moving' if device.is_moving else 'stopped',
            'origin': {
                'latitude': start_point.location.latitude,
                'longitude': start_point.location.longitude,
                'address': 'Unknown'
            },
            'destination': {
                'latitude': end_point.location.latitude,
                'longitude': end_point.location.longitude,
                'address': 'Unknown'
            },
            'current_position': current_index,
            'total_points': len(device.route)
        }

        # Geocodifica se disponibile
        if self.geocoding_enabled:
            start_address = self.get_address_for_location(
                start_point.location.latitude,
                start_point.location.longitude
            )

            end_address = self.get_address_for_location(
                end_point.location.latitude,
                end_point.location.longitude
            )

            if start_address:
                summary['origin']['address'] = start_address.formatted_address
                summary['origin']['city'] = start_address.city

            if end_address:
                summary['destination']['address'] = end_address.formatted_address
                summary['destination']['city'] = end_address.city

        # Calcola progressione
        total_distance = end_point.distance_from_start
        current_distance = device.route[current_index].distance_from_start if current_index < len(device.route) else 0
        progress_percent = (current_distance / total_distance * 100) if total_distance > 0 else 0

        summary['progress'] = {
            'percent': round(progress_percent, 1),
            'current_km': round(current_distance / 1000, 2),
            'total_km': round(total_distance / 1000, 2),
            'remaining_km': round((total_distance - current_distance) / 1000, 2)
        }

        return summary

    def get_all_devices_with_addresses(self) -> List[Dict[str, Any]]:
        """Ottiene tutti i dispositivi con indirizzi correnti"""
        devices_info = []

        for device_id in self.devices:
            device_info = self.get_device_current_address(device_id)
            if device_info:
                # Aggiungi info movimento
                device = self.devices[device_id]
                device_info['is_moving'] = device.is_moving
                device_info['speed'] = device.speed

                # Aggiungi progresso se in viaggio
                if device.route:
                    progress = (device.route_index / len(device.route) * 100) if device.route else 0
                    device_info['route_progress'] = round(progress, 1)

                devices_info.append(device_info)

        return devices_info

    def get_geocoding_statistics(self) -> Dict[str, Any]:
        """Statistiche complete del sistema"""
        route_stats = self.get_cache_statistics()

        stats = {
            'routes': route_stats,
            'devices': len(self.devices),
            'active_devices': sum(1 for d in self.devices.values() if d.is_moving)
        }

        if self.geocoding_enabled and self.geocoding:
            geo_stats = self.geocoding.get_statistics()
            stats['geocoding'] = geo_stats
            stats['total_api_calls'] = route_stats['api_calls'] + geo_stats['api_calls']
            stats['total_cache_hits'] = route_stats['cache_hits'] + geo_stats['cache_hits']
        else:
            stats['geocoding'] = {'enabled': False}
            stats['total_api_calls'] = route_stats['api_calls']
            stats['total_cache_hits'] = route_stats['cache_hits']

        return stats

    def cleanup_all_caches(self):
        """Pulisce tutte le cache del sistema"""
        # Cache percorsi
        self.clear_route_cache()

        # Cache geocoding
        if self.geocoding_enabled and self.geocoding:
            deleted = self.geocoding.cleanup_cache()
            logger.info(f"🧹 Cache geocoding pulita: {deleted} indirizzi rimossi")

        logger.info("✅ Pulizia cache completata")

    def close(self):
        """Chiudi tutte le risorse"""
        self.stop_all_devices()

        if self.geocoding_enabled and self.geocoding:
            self.geocoding.close()

        logger.info("🔒 Simulator enhanced chiuso correttamente")


# Utility function per creare simulator da config
def create_enhanced_simulator_from_config(config_file: str = "config.json") -> EnhancedTraccarSimulator:
    """Crea simulator enhanced dalla configurazione"""
    import json
    import os

    with open(config_file, 'r') as f:
        config = json.load(f)

    # Crea directory per cache se necessario
    cache_dir = config.get('cache', {}).get('route_cache_dir', 'data/route_cache')
    os.makedirs(cache_dir, exist_ok=True)

    geo_db_path = config.get('geocoding', {}).get('cache_db_path', 'data/geocoding_cache.db')
    os.makedirs(os.path.dirname(geo_db_path), exist_ok=True)

    traccar = TraccarAPI(
        host=config['traccar']['host'],
        port=config['traccar']['port'],
        username=config['traccar']['username'],
        password=config['traccar']['password'],
        debug=config['traccar'].get('debug', False)
    )

    simulator = EnhancedTraccarSimulator(
        traccar_api=traccar,
        google_maps_key=config['google_maps']['api_key'],
        traccar_protocol_host=config['traccar']['host'],
        traccar_protocol_port=57355,  # OsmAnd protocol
        cache_dir=cache_dir,
        geocoding_cache_db=geo_db_path
    )

    return simulator


# Test del sistema
if __name__ == "__main__":
    import logging
    import time

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    print("🧪 TEST ENHANCED SIMULATOR CON GEOCODING")
    print("=" * 60)

    try:
        simulator = create_enhanced_simulator_from_config()

        print("\n✅ Simulator enhanced inizializzato")
        print(f"   Geocoding: {'Attivo' if simulator.geocoding_enabled else 'Non disponibile'}")

        # Test creazione device
        device = simulator.create_device("🚗 Test Geocoding Enhanced")
        print(f"\n📱 Device creato: {device.name}")

        # Imposta route Roma -> Milano
        origin = Location(41.9028, 12.4964, "Roma")
        destination = Location(45.4642, 9.1900, "Milano")

        print("\n📍 Impostazione route Roma -> Milano...")
        success = simulator.set_route(device.unique_id, origin, destination)

        if success:
            print("✅ Route impostata correttamente")

            # Ottieni sommario con indirizzi
            print("\n📊 Sommario viaggio con indirizzi:")
            summary = simulator.get_trip_summary_with_addresses(device.unique_id)

            print(f"   Da: {summary['origin'].get('city', 'N/A')} - {summary['origin']['address']}")
            print(f"   A: {summary['destination'].get('city', 'N/A')} - {summary['destination']['address']}")
            print(f"   Distanza: {summary['progress']['total_km']} km")

            # Arricchisci route con indirizzi (sample)
            print("\n🌍 Geocoding punti route (sample)...")
            enriched = simulator.enrich_route_with_addresses(device.route[:5])

            for point in enriched:
                addr = point.get('address', {})
                city = addr.get('city', 'N/A')
                print(f"   Punto {point['index']}: {city}")

        # Statistiche finali
        print("\n📈 STATISTICHE COMPLETE:")
        stats = simulator.get_geocoding_statistics()

        print(f"   Route API calls: {stats['routes']['api_calls']}")
        print(f"   Route cache hits: {stats['routes']['cache_hits']}")

        if stats['geocoding'].get('enabled'):
            print(f"   Geocoding API calls: {stats['geocoding']['api_calls']}")
            print(f"   Geocoding cache hits: {stats['geocoding']['cache_hits']}")
            print(f"   Geocoding hit rate: {stats['geocoding']['hit_rate']}%")

        print(f"   Total API calls: {stats['total_api_calls']}")
        print(f"   Active devices: {stats['active_devices']}")

    except Exception as e:
        print(f"\n❌ Errore durante il test: {e}")
        import traceback

        traceback.print_exc()

    finally:
        if 'simulator' in locals():
            simulator.close()
        print("\n✅ Test completato!")