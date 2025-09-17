"""
Traccar Device Simulator - Sistema di Simulazione Dispositivi
===========================================================

Sistema completo per simulare dispositivi GPS che si muovono lungo percorsi realistici
utilizzando Google Maps Directions API e il framework Traccar.
"""

import math
import time
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import requests
import random
from dataclasses import dataclass, field
import logging

# Importa il framework Traccar esistente
from traccar_framework import TraccarAPI, TraccarException

logger = logging.getLogger('TraccarSimulator')


@dataclass
class Location:
    """Rappresenta una posizione geografica"""
    latitude: float
    longitude: float
    address: Optional[str] = None
    timestamp: Optional[datetime] = None


@dataclass
class RoutePoint:
    """Punto lungo un percorso con informazioni aggiuntive"""
    location: Location
    speed: float = 50.0  # km/h
    bearing: float = 0.0  # gradi
    distance_from_start: float = 0.0  # metri


@dataclass
class SimulatedDevice:
    """Dispositivo simulato"""
    id: Optional[int] = None
    name: str = ""
    unique_id: str = ""
    current_location: Optional[Location] = None
    route: List[RoutePoint] = field(default_factory=list)
    route_index: int = 0
    is_moving: bool = False
    speed: float = 50.0  # km/h
    update_interval: float = 5.0  # secondi
    last_update: Optional[datetime] = None
    thread: Optional[threading.Thread] = None
    stop_event: Optional[threading.Event] = None


class GoogleMapsClient:
    """Client per Google Maps Directions API"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api/directions/json"

    def get_route(self, origin: Location, destination: Location,
                  waypoints: List[Location] = None, mode: str = "driving") -> List[RoutePoint]:
        """
        Ottiene un percorso da Google Maps

        Args:
            origin: Punto di partenza
            destination: Punto di arrivo
            waypoints: Punti intermedi opzionali
            mode: Modalità di trasporto (driving, walking, bicycling, transit)

        Returns:
            Lista di RoutePoint che compongono il percorso
        """
        params = {
            'origin': f"{origin.latitude},{origin.longitude}",
            'destination': f"{destination.latitude},{destination.longitude}",
            'key': self.api_key,
            'mode': mode
        }

        if waypoints:
            waypoints_str = "|".join([f"{wp.latitude},{wp.longitude}" for wp in waypoints])
            params['waypoints'] = waypoints_str

        try:
            logger.info(f"🗺️ Richiesta percorso da {params['origin']} a {params['destination']}")

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data['status'] != 'OK':
                raise Exception(f"Google Maps API error: {data['status']}")

            route_points = []
            total_distance = 0

            # Processa la prima rotta
            route = data['routes'][0]

            for leg in route['legs']:
                for step in leg['steps']:
                    # Decodifica i punti del polyline
                    points = self._decode_polyline(step['polyline']['points'])

                    for i, point in enumerate(points):
                        # Calcola bearing (direzione)
                        if i < len(points) - 1:
                            bearing = self._calculate_bearing(point, points[i + 1])
                        else:
                            bearing = route_points[-1].bearing if route_points else 0

                        route_point = RoutePoint(
                            location=Location(
                                latitude=point[0],
                                longitude=point[1],
                                timestamp=datetime.now()
                            ),
                            speed=self._estimate_speed(mode),
                            bearing=bearing,
                            distance_from_start=total_distance
                        )

                        route_points.append(route_point)

                        # Aggiorna distanza totale
                        if len(route_points) > 1:
                            total_distance += self._calculate_distance(
                                route_points[-2].location,
                                route_points[-1].location
                            )
                            route_points[-1].distance_from_start = total_distance

            logger.info(f"✅ Percorso ottenuto: {len(route_points)} punti, {total_distance:.0f}m totali")
            return route_points

        except requests.RequestException as e:
            logger.error(f"❌ Errore richiesta Google Maps: {e}")
            raise Exception(f"Errore connessione Google Maps: {e}")
        except Exception as e:
            logger.error(f"❌ Errore elaborazione percorso: {e}")
            raise Exception(f"Errore elaborazione percorso: {e}")

    def _decode_polyline(self, polyline_str: str) -> List[Tuple[float, float]]:
        """Decodifica una stringa polyline di Google Maps"""
        points = []
        index = lat = lng = 0

        while index < len(polyline_str):
            b = shift = result = 0

            while True:
                b = ord(polyline_str[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break

            dlat = ~(result >> 1) if result & 1 else result >> 1
            lat += dlat

            shift = result = 0
            while True:
                b = ord(polyline_str[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break

            dlng = ~(result >> 1) if result & 1 else result >> 1
            lng += dlng

            points.append((lat * 1e-5, lng * 1e-5))

        return points

    def _calculate_bearing(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
        """Calcola il bearing (direzione) tra due punti"""
        lat1, lng1 = math.radians(point1[0]), math.radians(point1[1])
        lat2, lng2 = math.radians(point2[0]), math.radians(point2[1])

        dLng = lng2 - lng1

        y = math.sin(dLng) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dLng)

        bearing = math.atan2(y, x)
        return (math.degrees(bearing) + 360) % 360

    def _calculate_distance(self, loc1: Location, loc2: Location) -> float:
        """Calcola la distanza tra due punti in metri"""
        lat1, lng1 = math.radians(loc1.latitude), math.radians(loc1.longitude)
        lat2, lng2 = math.radians(loc2.latitude), math.radians(loc2.longitude)

        dlat = lat2 - lat1
        dlng = lng2 - lng1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        c = 2 * math.asin(math.sqrt(a))

        return 6371000 * c  # Raggio della Terra in metri

    def _estimate_speed(self, mode: str) -> float:
        """Stima la velocità basata sul tipo di trasporto"""
        speeds = {
            'driving': random.uniform(30, 80),
            'walking': random.uniform(3, 6),
            'bicycling': random.uniform(15, 25),
            'transit': random.uniform(20, 50)
        }
        return speeds.get(mode, 50.0)


class TraccarProtocolClient:
    """
    Client per inviare dati GPS direttamente al server Traccar
    utilizzando il protocollo OsmAnd (HTTP GET)
    """

    def __init__(self, host: str, port: int = 5055, protocol: str = "http"):
        self.base_url = f"{protocol}://{host}:{port}"

    def send_position(self, device_id: str, location: Location, speed: float = 0,
                     bearing: float = 0, altitude: float = 0, accuracy: float = 10) -> bool:
        """
        Invia una posizione al server Traccar usando il protocollo OsmAnd

        Args:
            device_id: ID univoco del dispositivo
            location: Posizione GPS
            speed: Velocità in km/h
            bearing: Direzione in gradi
            altitude: Altitudine in metri
            accuracy: Accuratezza GPS in metri
        """
        timestamp = location.timestamp or datetime.now()

        params = {
            'id': device_id,
            'lat': location.latitude,
            'lon': location.longitude,
            'speed': speed,
            'bearing': bearing,
            'altitude': altitude,
            'accuracy': accuracy,
            'timestamp': int(timestamp.timestamp())
        }

        url = f"{self.base_url}/"

        try:
            response = requests.get(url, params=params, timeout=5)

            if response.status_code == 200:
                logger.debug(f"📡 Posizione inviata per {device_id}: {location.latitude:.6f}, {location.longitude:.6f}")
                return True
            else:
                logger.warning(f"⚠️ Errore invio posizione per {device_id}: HTTP {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"❌ Errore connessione per {device_id}: {e}")
            return False


class TraccarSimulator:
    """Simulatore principale per dispositivi Traccar"""

    def __init__(self, traccar_api: TraccarAPI, google_maps_key: str,
                 traccar_protocol_host: str, traccar_protocol_port: int = 5055):
        """
        Inizializza il simulatore

        Args:
            traccar_api: Istanza del TraccarAPI per gestire dispositivi
            google_maps_key: Chiave API Google Maps
            traccar_protocol_host: Host per invio dati GPS
            traccar_protocol_port: Porta per invio dati GPS (default: 5055 per OsmAnd)
        """
        self.traccar = traccar_api
        self.google_maps = GoogleMapsClient(google_maps_key)
        self.protocol_client = TraccarProtocolClient(traccar_protocol_host, traccar_protocol_port)

        self.devices: Dict[str, SimulatedDevice] = {}
        self.is_running = False

        logger.info("🚀 TraccarSimulator inizializzato")

    def find_existing_truck_device(self) -> Optional[SimulatedDevice]:
        """
        Cerca un dispositivo esistente tipo camion/truck

        Returns:
            SimulatedDevice se trovato, None altrimenti
        """
        try:
            logger.info("🔍 Ricerca dispositivi tipo camion esistenti...")

            # Ottieni tutti i dispositivi dal server Traccar
            existing_devices = self.traccar.devices.get_devices()

            truck_keywords = [
                'camion', 'truck', 'tir', 'autocarro', 'furgone',
                'van', 'lorry', 'trailer', 'semi', 'freight'
            ]

            for device_data in existing_devices:
                device_name = device_data.get('name', '').lower()
                device_category = device_data.get('category', '').lower()
                unique_id = device_data.get('uniqueId', '')

                # Controlla se è un camion dal nome o categoria
                is_truck = any(keyword in device_name for keyword in truck_keywords)
                is_truck = is_truck or any(keyword in device_category for keyword in truck_keywords)
                is_truck = is_truck or 'truck' in device_category or 'camion' in device_category

                if is_truck:
                    logger.info(f"🚛 Trovato dispositivo camion esistente: {device_data['name']} (ID: {device_data['id']})")

                    # Crea oggetto SimulatedDevice per dispositivo esistente
                    device = SimulatedDevice(
                        id=device_data['id'],
                        name=device_data['name'],
                        unique_id=unique_id,
                        stop_event=threading.Event()
                    )

                    self.devices[unique_id] = device
                    return device

            logger.info("🚛 Nessun dispositivo camion trovato")
            return None

        except Exception as e:
            logger.warning(f"⚠️ Errore ricerca dispositivi esistenti: {e}")
            return None

    def create_device(self, name: str, unique_id: str = None, force_new: bool = False) -> SimulatedDevice:
        """
        Crea un nuovo dispositivo simulato o usa uno esistente se compatibile

        Args:
            name: Nome del dispositivo
            unique_id: ID univoco (se None, ne genera uno automatico)
            force_new: Se True, crea sempre un nuovo dispositivo

        Returns:
            SimulatedDevice creato o trovato
        """
        # Se non forza la creazione e il nome contiene "camion/truck", cerca prima esistenti
        if not force_new:
            truck_keywords = ['camion', 'truck', 'tir', 'autocarro', 'furgone']
            if any(keyword in name.lower() for keyword in truck_keywords):
                existing_truck = self.find_existing_truck_device()
                if existing_truck:
                    logger.info(f"♻️ Riutilizzo dispositivo esistente: {existing_truck.name}")
                    return existing_truck

        if unique_id is None:
            unique_id = f"sim_{int(time.time())}_{random.randint(1000, 9999)}"

        try:
            # Crea il dispositivo su Traccar
            device_data = self.traccar.devices.create_device(
                name=name,
                unique_id=unique_id,
                category="simulation"
            )

            device = SimulatedDevice(
                id=device_data['id'],
                name=name,
                unique_id=unique_id,
                stop_event=threading.Event()
            )

            self.devices[unique_id] = device

            logger.info(f"✅ Nuovo dispositivo creato: {name} (ID: {device.id}, UniqueID: {unique_id})")
            return device

        except TraccarException as e:
            logger.error(f"❌ Errore creazione dispositivo {name}: {e}")
            raise

    def get_or_create_truck_device(self, preferred_name: str = "🚛 Camion Simulato") -> SimulatedDevice:
        """
        Ottiene un dispositivo camion esistente o ne crea uno nuovo

        Args:
            preferred_name: Nome preferito per il nuovo dispositivo

        Returns:
            SimulatedDevice pronto per l'uso
        """
        logger.info("🚛 Ricerca o creazione dispositivo camion...")

        # Prima cerca dispositivi esistenti tipo camion
        existing_truck = self.find_existing_truck_device()

        if existing_truck:
            logger.info(f"♻️ Utilizzo camion esistente: {existing_truck.name} (ID: {existing_truck.id})")
            return existing_truck

        # Se non trovato, crea nuovo
        logger.info("🔨 Creazione nuovo dispositivo camion...")
        return self.create_device(preferred_name, force_new=True)

    def set_route(self, device_unique_id: str, origin: Location, destination: Location,
                  waypoints: List[Location] = None, transport_mode: str = "driving") -> bool:
        """
        Imposta un percorso per un dispositivo

        Args:
            device_unique_id: ID univoco del dispositivo
            origin: Punto di partenza
            destination: Punto di arrivo
            waypoints: Punti intermedi opzionali
            transport_mode: Modalità di trasporto

        Returns:
            True se il percorso è stato impostato con successo
        """
        if device_unique_id not in self.devices:
            logger.error(f"❌ Dispositivo {device_unique_id} non trovato")
            return False

        device = self.devices[device_unique_id]

        try:
            logger.info(f"🗺️ Calcolo percorso per {device.name}...")

            route = self.google_maps.get_route(origin, destination, waypoints, transport_mode)

            if not route:
                logger.error(f"❌ Nessun percorso trovato per {device.name}")
                return False

            device.route = route
            device.route_index = 0
            device.current_location = origin

            # Calcola velocità media basata sul tipo di trasporto
            speeds = {
                'driving': random.uniform(40, 70),
                'walking': random.uniform(4, 6),
                'bicycling': random.uniform(15, 25),
                'transit': random.uniform(30, 50)
            }
            device.speed = speeds.get(transport_mode, 50.0)

            logger.info(f"✅ Percorso impostato per {device.name}: {len(route)} punti, velocità {device.speed:.1f} km/h")
            return True

        except Exception as e:
            logger.error(f"❌ Errore impostazione percorso per {device.name}: {e}")
            return False

    def start_device(self, device_unique_id: str, update_interval: float = 5.0) -> bool:
        """
        Avvia la simulazione per un dispositivo

        Args:
            device_unique_id: ID univoco del dispositivo
            update_interval: Intervallo di aggiornamento in secondi

        Returns:
            True se avviato con successo
        """
        if device_unique_id not in self.devices:
            logger.error(f"❌ Dispositivo {device_unique_id} non trovato")
            return False

        device = self.devices[device_unique_id]

        if device.is_moving:
            logger.warning(f"⚠️ Dispositivo {device.name} già in movimento")
            return True

        if not device.route:
            logger.error(f"❌ Nessun percorso impostato per {device.name}")
            return False

        device.update_interval = update_interval
        device.is_moving = True
        device.stop_event.clear()

        # Avvia thread di movimento
        device.thread = threading.Thread(
            target=self._move_device,
            args=(device,),
            daemon=True
        )
        device.thread.start()

        logger.info(f"🚀 Simulazione avviata per {device.name} (intervallo: {update_interval}s)")
        return True

    def stop_device(self, device_unique_id: str) -> bool:
        """
        Ferma la simulazione per un dispositivo

        Args:
            device_unique_id: ID univoco del dispositivo

        Returns:
            True se fermato con successo
        """
        if device_unique_id not in self.devices:
            logger.error(f"❌ Dispositivo {device_unique_id} non trovato")
            return False

        device = self.devices[device_unique_id]

        if not device.is_moving:
            logger.info(f"ℹ️ Dispositivo {device.name} già fermo")
            return True

        device.is_moving = False
        device.stop_event.set()

        if device.thread and device.thread.is_alive():
            device.thread.join(timeout=2)

        logger.info(f"🛑 Simulazione fermata per {device.name}")
        return True

    def start_all_devices(self, update_interval: float = 5.0) -> int:
        """
        Avvia la simulazione per tutti i dispositivi

        Args:
            update_interval: Intervallo di aggiornamento in secondi

        Returns:
            Numero di dispositivi avviati
        """
        started = 0

        for device_id in self.devices:
            if self.start_device(device_id, update_interval):
                started += 1

        logger.info(f"🚀 {started}/{len(self.devices)} dispositivi avviati")
        return started

    def stop_all_devices(self) -> int:
        """
        Ferma la simulazione per tutti i dispositivi

        Returns:
            Numero di dispositivi fermati
        """
        stopped = 0

        for device_id in self.devices:
            if self.stop_device(device_id):
                stopped += 1

        logger.info(f"🛑 {stopped}/{len(self.devices)} dispositivi fermati")
        return stopped

    def get_device_status(self, device_unique_id: str = None) -> Dict[str, Any]:
        """
        Ottiene lo stato dei dispositivi

        Args:
            device_unique_id: ID specifico (se None, ritorna tutti)

        Returns:
            Dizionario con informazioni sui dispositivi
        """
        if device_unique_id:
            if device_unique_id not in self.devices:
                return {}

            device = self.devices[device_unique_id]
            return self._get_single_device_status(device)

        # Ritorna stato di tutti i dispositivi
        status = {}
        for unique_id, device in self.devices.items():
            status[unique_id] = self._get_single_device_status(device)

        return status

    def _get_single_device_status(self, device: SimulatedDevice) -> Dict[str, Any]:
        """Ottiene lo stato di un singolo dispositivo"""
        progress = 0
        if device.route:
            progress = (device.route_index / len(device.route)) * 100

        return {
            'name': device.name,
            'id': device.id,
            'unique_id': device.unique_id,
            'is_moving': device.is_moving,
            'current_location': {
                'latitude': device.current_location.latitude if device.current_location else None,
                'longitude': device.current_location.longitude if device.current_location else None
            } if device.current_location else None,
            'speed': device.speed,
            'route_progress': f"{progress:.1f}%",
            'route_points': len(device.route),
            'route_index': device.route_index,
            'last_update': device.last_update.isoformat() if device.last_update else None,
            'update_interval': device.update_interval
        }

    def _move_device(self, device: SimulatedDevice):
        """Thread di movimento per un dispositivo - COMPLETA TUTTO IL VIAGGIO"""
        logger.info(f"🏃 Thread movimento avviato per {device.name}")
        logger.info(f"🛣️ Percorso: {len(device.route)} punti totali da attraversare")

        start_time = datetime.now()
        successful_updates = 0
        failed_updates = 0

        while device.is_moving and not device.stop_event.is_set():
            try:
                # Controlla se abbiamo completato il percorso
                if device.route_index >= len(device.route):
                    end_time = datetime.now()
                    duration = end_time - start_time

                    logger.info(f"🏁 {device.name} HA COMPLETATO L'INTERO PERCORSO!")
                    logger.info(f"📊 Statistiche viaggio:")
                    logger.info(f"   ⏱️ Durata totale: {duration}")
                    logger.info(f"   📍 Punti attraversati: {device.route_index}")
                    logger.info(f"   ✅ Aggiornamenti riusciti: {successful_updates}")
                    logger.info(f"   ❌ Aggiornamenti falliti: {failed_updates}")
                    logger.info(f"   📡 Successo rate: {(successful_updates/(successful_updates+failed_updates)*100):.1f}%")

                    device.is_moving = False
                    break

                # Ottieni prossimo punto del percorso
                route_point = device.route[device.route_index]
                device.current_location = route_point.location
                device.current_location.timestamp = datetime.now()

                # Calcola progresso
                progress = (device.route_index / len(device.route)) * 100

                # Invia posizione al server Traccar
                success = self.protocol_client.send_position(
                    device_id=device.unique_id,
                    location=device.current_location,
                    speed=route_point.speed,  # Usa velocità del punto specifico
                    bearing=route_point.bearing,
                    altitude=random.uniform(50, 200),  # Altitudine più realistica
                    accuracy=random.uniform(2, 8)      # GPS di buona qualità
                )

                if success:
                    successful_updates += 1
                    device.last_update = datetime.now()

                    # Log dettagliato ogni 50 punti o agli step importanti
                    if device.route_index % 50 == 0 or device.route_index < 10 or device.route_index > len(device.route) - 10:
                        logger.info(f"📍 {device.name} - Punto {device.route_index+1}/{len(device.route)} ({progress:.1f}%): "
                                   f"{device.current_location.latitude:.6f}, {device.current_location.longitude:.6f}, "
                                   f"Velocità: {route_point.speed:.1f} km/h")
                    else:
                        # Log debug per tutti gli altri punti
                        logger.debug(f"📍 {device.name} - {progress:.1f}% - "
                                    f"Lat: {device.current_location.latitude:.6f}, "
                                    f"Lon: {device.current_location.longitude:.6f}")
                else:
                    failed_updates += 1
                    logger.warning(f"⚠️ {device.name} - Errore invio punto {device.route_index+1}/{len(device.route)}")

                device.route_index += 1

                # Log di progresso ogni 10%
                new_progress = (device.route_index / len(device.route)) * 100
                if int(new_progress) % 10 == 0 and int(progress) != int(new_progress):
                    elapsed = datetime.now() - start_time
                    remaining_points = len(device.route) - device.route_index
                    estimated_remaining = (elapsed / device.route_index) * remaining_points if device.route_index > 0 else timedelta(0)

                    logger.info(f"🚗 {device.name} - PROGRESSO {new_progress:.0f}% - "
                               f"Elapsed: {str(elapsed).split('.')[0]}, "
                               f"ETA: {str(estimated_remaining).split('.')[0]}")

                # Calcola intervallo dinamico basato sulla velocità
                # Più veloce = aggiornamenti meno frequenti per simulare movimento realistico
                dynamic_interval = min(device.update_interval, max(1.0, device.update_interval * (route_point.speed / 50.0)))

                # Aspetta prima del prossimo aggiornamento
                if device.stop_event.wait(dynamic_interval):
                    logger.info(f"🛑 {device.name} - Fermato manualmente al {progress:.1f}%")
                    break

            except Exception as e:
                failed_updates += 1
                logger.error(f"❌ Errore movimento {device.name} al punto {device.route_index}: {e}")
                time.sleep(1)  # Pausa breve prima di riprovare

        final_time = datetime.now()
        total_duration = final_time - start_time

        if device.route_index >= len(device.route):
            logger.info(f"🎉 {device.name} - VIAGGIO COMPLETATO CON SUCCESSO!")
        else:
            logger.info(f"🛑 {device.name} - Viaggio interrotto al {((device.route_index/len(device.route))*100):.1f}%")

        logger.info(f"📊 {device.name} - STATISTICHE FINALI:")
        logger.info(f"   ⏱️ Durata: {str(total_duration).split('.')[0]}")
        logger.info(f"   🎯 Punti completati: {device.route_index}/{len(device.route)}")
        logger.info(f"   ✅ Successi: {successful_updates}, ❌ Fallimenti: {failed_updates}")

        logger.info(f"🏁 Thread movimento terminato per {device.name}")

    def cleanup(self):
        """Pulizia risorse e dispositivi simulati"""
        logger.info("🧹 Pulizia simulatore in corso...")

        # Ferma tutti i dispositivi
        self.stop_all_devices()

        # Opzionalmente elimina i dispositivi da Traccar
        # (commentato per sicurezza - decommentare se necessario)
        # for device in self.devices.values():
        #     try:
        #         if device.id:
        #             self.traccar.devices.delete_device(device.id)
        #             logger.info(f"🗑️ Dispositivo {device.name} eliminato da Traccar")
        #     except Exception as e:
        #         logger.error(f"❌ Errore eliminazione {device.name}: {e}")

        self.devices.clear()
        logger.info("✅ Pulizia completata")


# Esempi e test
def example_complete_journey():
    """Esempio con viaggio completo - FINO ALLA FINE!"""
    print("\n" + "="*60)
    print("🛣️ ESEMPIO VIAGGIO COMPLETO - FINO ALLA DESTINAZIONE!")
    print("="*60)

    # Configura il simulatore
    traccar = TraccarAPI(
        host="torraccia.iliadboxos.it",
        port=58082,
        username="dspeziale@gmail.com",
        password="Elisa2025!",
        debug=False
    )

    # INSERIRE QUI LA TUA GOOGLE MAPS API KEY
    GOOGLE_MAPS_KEY = "AIzaSyAZLNmrmri-HUzex5s4FaJZPk8xVeAyFVk"

    # Host per invio dati GPS (stesso del server Traccar ma porta diversa)
    TRACCAR_GPS_HOST = "torraccia.iliadboxos.it"
    TRACCAR_GPS_PORT = 5055  # Porta standard OsmAnd

    simulator = TraccarSimulator(
        traccar_api=traccar,
        google_maps_key=GOOGLE_MAPS_KEY,
        traccar_protocol_host=TRACCAR_GPS_HOST,
        traccar_protocol_port=TRACCAR_GPS_PORT
    )

    try:
        # Test connessione Traccar
        if not traccar.test_connection():
            print("❌ Impossibile connettersi a Traccar")
            return

        print("✅ Connesso a Traccar")

        # 🚛 NOVITÀ: Cerca dispositivo camion esistente o crea nuovo
        print("\n🔍 Ricerca dispositivi camion esistenti...")
        device = simulator.get_or_create_truck_device("🚛 Viaggio Completo Roma-Milano")

        print(f"📱 Dispositivo selezionato: {device.name}")
        print(f"🆔 ID Traccar: {device.id}")
        print(f"🔑 Unique ID: {device.unique_id}")

        # Definisci percorso lungo: Roma -> Milano (circa 570km)
        origin = Location(
            latitude=41.9028,
            longitude=12.4964,
            address="Roma, Italia"
        )

        destination = Location(
            latitude=45.4642,
            longitude=9.1900,
            address="Milano, Italia"
        )

        # Aggiungi waypoints per rendere il viaggio più interessante
        waypoints = [
            Location(43.3188, 11.3307, "Siena"),  # Toscana
            Location(43.7711, 11.2486, "Firenze"), # Firenze
            Location(44.4056, 8.9463, "Genova")    # Liguria
        ]

        print(f"🗺️ Impostazione percorso COMPLETO:")
        print(f"   🏁 Partenza: Roma")
        print(f"   📍 Tappe: Siena → Firenze → Genova")
        print(f"   🎯 Arrivo: Milano")
        print(f"   🚛 Veicolo: {device.name}")

        # Imposta percorso
        if not simulator.set_route(device.unique_id, origin, destination, waypoints, transport_mode="driving"):
            print("❌ Errore impostazione percorso")
            return

        print("✅ Percorso impostato con successo")

        # Ottieni info sul percorso
        device_obj = simulator.devices[device.unique_id]
        total_points = len(device_obj.route)
        estimated_duration_hours = (total_points * 2.0) / 3600  # Stima grossolana

        print(f"📊 Informazioni percorso:")
        print(f"   📍 Punti totali da attraversare: {total_points}")
        print(f"   ⏱️ Durata stimata: {estimated_duration_hours:.1f} ore")
        print(f"   🚄 Velocità media: {device_obj.speed:.1f} km/h")
        print(f"   📡 Aggiornamento ogni: 2 secondi")

        # Controlla se il dispositivo sta già muovendosi
        if device.unique_id in simulator.devices:
            existing_device = simulator.devices[device.unique_id]
            if hasattr(existing_device, 'is_moving') and existing_device.is_moving:
                print(f"\n⚠️ ATTENZIONE: {device.name} è già in movimento!")
                stop_current = input("🛑 Vuoi fermarlo e iniziare nuovo viaggio? (s/n): ").lower()
                if stop_current == 's':
                    simulator.stop_device(device.unique_id)
                    print("🛑 Dispositivo fermato")
                else:
                    print("ℹ️ Mantengo il viaggio corrente")
                    return

        # Conferma dall'utente
        print("\n" + "⚠️"*20)
        print("ATTENZIONE: Il viaggio completo può richiedere diverse ore!")
        print("Il simulatore continuerà fino alla destinazione finale.")
        print("Premi CTRL+C per interrompere in qualsiasi momento.")
        print("⚠️"*20)

        input("\n👍 Premi INVIO per iniziare il viaggio completo...")

        # Avvia simulazione con aggiornamenti frequenti
        print(f"\n🚀 INIZIO VIAGGIO COMPLETO!")
        print(f"🕐 {datetime.now().strftime('%H:%M:%S')} - Partenza da Roma")
        print("="*60)

        simulator.start_device(device.unique_id, update_interval=2.0)  # Aggiorna ogni 2 secondi

        # Monitora il viaggio fino alla fine
        print("📊 Monitoraggio viaggio in corso...")
        print("💡 Verrà mostrato lo stato ogni 30 secondi")
        print("🛑 Usa CTRL+C per interrompere\n")

        last_progress = -1
        start_time = datetime.now()

        while True:
            try:
                time.sleep(30)  # Controlla ogni 30 secondi

                status = simulator.get_device_status(device.unique_id)

                if not status['is_moving']:
                    print(f"\n🎉 VIAGGIO COMPLETATO!")
                    print(f"🕐 {datetime.now().strftime('%H:%M:%S')} - Arrivo a Milano")
                    duration = datetime.now() - start_time
                    print(f"⏱️ Durata totale: {str(duration).split('.')[0]}")
                    break

                # Estrai progresso numerico
                progress_str = status['route_progress'].replace('%', '')
                current_progress = float(progress_str)

                # Mostra aggiornamento solo se c'è stato progresso significativo
                if current_progress != last_progress:
                    elapsed = datetime.now() - start_time

                    # Stima tempo rimanente
                    if current_progress > 0:
                        total_estimated = elapsed / (current_progress / 100)
                        remaining = total_estimated - elapsed
                        eta_str = str(remaining).split('.')[0]
                    else:
                        eta_str = "Calcolando..."

                    print(f"🚛 {status['name']}")
                    print(f"   📍 Progresso: {status['route_progress']}")
                    print(f"   🚄 Velocità: {status['speed']:.1f} km/h")
                    print(f"   ⏱️ Trascorso: {str(elapsed).split('.')[0]}")
                    print(f"   🎯 ETA: {eta_str}")
                    print(f"   🕐 {datetime.now().strftime('%H:%M:%S')}")
                    print("-" * 40)

                    last_progress = current_progress

            except KeyboardInterrupt:
                print(f"\n⏹️ Viaggio interrotto dall'utente!")
                status = simulator.get_device_status(device.unique_id)
                print(f"📍 Progresso al momento dell'interruzione: {status['route_progress']}")
                break

        print("\n🛑 Fermata simulazione...")
        simulator.stop_device(device.unique_id)

        # Statistiche finali
        final_status = simulator.get_device_status(device.unique_id)
        final_duration = datetime.now() - start_time

        print(f"\n📊 STATISTICHE FINALI:")
        print(f"   🚛 Veicolo: {final_status['name']}")
        print(f"   📍 Progresso finale: {final_status['route_progress']}")
        print(f"   ⏱️ Durata totale: {str(final_duration).split('.')[0]}")
        print(f"   🎯 Punti attraversati: {final_status['route_index']}/{final_status['route_points']}")

        if final_status['route_progress'] == '100.0%':
            print(f"   🎉 VIAGGIO COMPLETATO CON SUCCESSO! 🎉")
        else:
            print(f"   ⏹️ Viaggio interrotto prematuramente")

        print("✅ Esempio viaggio completo terminato!")

    except KeyboardInterrupt:
        print(f"\n⏹️ Simulazione interrotta dall'utente")
        if 'device' in locals():
            simulator.stop_device(device.unique_id)
    except Exception as e:
        print(f"❌ Errore durante il viaggio completo: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Pulizia (ma mantieni i dispositivi esistenti)
        print("\n🧹 Pulizia risorse...")
        simulator.stop_all_devices()
        print("✅ Pulizia completata (dispositivi mantenuti su Traccar)")


def example_epic_journey():
    """Esempio con viaggio epico attraverso l'Europa!"""
    print("\n" + "="*80)
    print("🌍 VIAGGIO EPICO: ROMA → PARIGI → BERLINO → AMSTERDAM! 🌍")
    print("="*80)

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
        traccar_protocol_port=57355
    )

    try:
        if not traccar.test_connection():
            print("❌ Impossibile connettersi a Traccar")
            return

        # 🚛 NOVITÀ: Cerca dispositivo camion esistente per il grand tour
        print("\n🔍 Ricerca del migliore camion per il Grand Tour europeo...")
        device = simulator.get_or_create_truck_device("🚛 EURO TRUCK GRAND TOUR")

        print(f"🚛 Camion selezionato per l'Europa: {device.name}")
        print(f"🆔 ID Traccar: {device.id}")

        # Grand tour europeo!
        origin = Location(41.9028, 12.4964, "Roma, Italia")
        destination = Location(52.3702, 4.8951, "Amsterdam, Paesi Bassi")

        waypoints = [
            Location(45.4642, 9.1900, "Milano, Italia"),
            Location(45.7640, 4.8357, "Lyon, Francia"),
            Location(48.8566, 2.3522, "Paris, Francia"),
            Location(50.1109, 8.6821, "Frankfurt, Germania"),
            Location(52.5200, 13.4050, "Berlin, Germania"),
        ]

        print(f"🗺️ PERCORSO EPICO:")
        print(f"   🇮🇹 Roma (partenza)")
        print(f"   🇮🇹 → Milano")
        print(f"   🇫🇷 → Lyon")
        print(f"   🇫🇷 → Paris")
        print(f"   🇩🇪 → Frankfurt")
        print(f"   🇩🇪 → Berlin")
        print(f"   🇳🇱 → Amsterdam (arrivo)")
        print(f"   📏 Distanza stimata: ~1800 km")

        # Controlla se il camion sta già viaggiando
        if device.unique_id in simulator.devices:
            existing_device = simulator.devices[device.unique_id]
            if hasattr(existing_device, 'is_moving') and existing_device.is_moving:
                print(f"\n⚠️ ATTENZIONE: {device.name} è già in viaggio!")
                current_status = simulator.get_device_status(device.unique_id)
                print(f"📍 Attualmente al {current_status.get('route_progress', '0%')} del percorso")

                action = input("🤔 Cosa vuoi fare? (f=ferma e riparte, c=continua, a=annulla): ").lower()
                if action == 'f':
                    simulator.stop_device(device.unique_id)
                    print("🛑 Camion fermato")
                elif action == 'c':
                    print("📍 Continuo il viaggio corrente")
                    return
                elif action == 'a':
                    print("❌ Operazione annullata")
                    return

        if not simulator.set_route(device.unique_id, origin, destination, waypoints):
            print("❌ Errore impostazione percorso")
            return

        device_obj = simulator.devices[device.unique_id]
        total_points = len(device_obj.route)

        print(f"\n📊 DETTAGLI GRAND TOUR:")
        print(f"   🚛 Veicolo: {device.name}")
        print(f"   📍 Punti GPS totali: {total_points:,}")
        print(f"   🚄 Velocità media: {device_obj.speed:.1f} km/h")
        print(f"   ⏱️ Durata stimata: {(total_points * 1.5 / 3600):.1f} ore")

        print("\n" + "🚨"*25)
        print("QUESTO È UN VIAGGIO MOLTO LUNGO!")
        print("Il simulatore attraverserà TUTTA L'EUROPA!")
        print("Può richiedere MOLTE ORE per completarsi!")
        print("🚨"*25)

        confirm = input("\n🤔 Sei SICURO di voler iniziare questo viaggio epico? (scrivi 'SI'): ")
        if confirm.upper() != 'SI':
            print("👋 Viaggio annullato. Scelta saggia!")
            return

        print(f"\n🚀 INIZIAMO IL GRAND TOUR EUROPEO!")
        print(f"🕐 {datetime.now().strftime('%H:%M:%S')} - Partenza da Roma")
        print("="*80)

        simulator.start_device(device.unique_id, update_interval=1.5)

        print("🗺️ Tracciamento viaggio in corso...")
        print("📍 Aggiornamenti ogni 60 secondi")
        print("🛑 CTRL+C per interrompere\n")

        start_time = datetime.now()
        update_counter = 0
        milestones = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99]
        milestone_index = 0

        while True:
            try:
                time.sleep(60)  # Check ogni minuto
                update_counter += 1

                status = simulator.get_device_status(device.unique_id)

                if not status['is_moving']:
                    print(f"\n🎉🎉🎉 GRAND TOUR COMPLETATO! 🎉🎉🎉")
                    print(f"🏁 {datetime.now().strftime('%H:%M:%S')} - Arrivo ad Amsterdam")
                    duration = datetime.now() - start_time
                    print(f"⏱️ Durata epica: {str(duration).split('.')[0]}")
                    print(f"🌍 Hai attraversato tutta l'Europa!")
                    break

                progress = float(status['route_progress'].replace('%', ''))
                elapsed = datetime.now() - start_time

                # Mostra milestone speciali
                if milestone_index < len(milestones) and progress >= milestones[milestone_index]:
                    milestone = milestones[milestone_index]

                    # Città stimate basate sul progresso
                    city_estimates = {
                        10: "🇮🇹 Uscendo da Roma...",
                        20: "🇮🇹 Attraversando la Toscana...",
                        30: "🇮🇹 Arrivando a Milano...",
                        40: "🇫🇷 Entrando in Francia...",
                        50: "🇫🇷 Passando per Lyon...",
                        60: "🇫🇷 Avvicinandosi a Parigi...",
                        70: "🇩🇪 Entrando in Germania...",
                        80: "🇩🇪 Attraversando Frankfurt...",
                        90: "🇩🇪 Raggiungendo Berlino...",
                        95: "🇳🇱 Entrando nei Paesi Bassi...",
                        99: "🇳🇱 Quasi ad Amsterdam!"
                    }

                    print(f"\n🌟 MILESTONE {milestone}% RAGGIUNTO! 🌟")
                    print(f"📍 {city_estimates.get(milestone, 'Continuando il viaggio...')}")
                    print(f"⏱️ Tempo trascorso: {str(elapsed).split('.')[0]}")
                    milestone_index += 1

                # Aggiornamento regolare
                if update_counter % 5 == 0:  # Ogni 5 minuti mostra dettagli completi
                    if progress > 0:
                        eta = elapsed / (progress / 100) - elapsed
                        eta_str = str(eta).split('.')[0]
                    else:
                        eta_str = "Calcolando..."

                    print(f"\n🚛 GRAND TOUR UPDATE #{update_counter}")
                    print(f"   📍 Progresso: {status['route_progress']}")
                    print(f"   🚄 Velocità: {status['speed']:.1f} km/h")
                    print(f"   ⏱️ Trascorso: {str(elapsed).split('.')[0]}")
                    print(f"   🎯 ETA finale: {eta_str}")
                    print(f"   🕐 {datetime.now().strftime('%H:%M:%S')}")

            except KeyboardInterrupt:
                print(f"\n⏹️ Grand Tour interrotto!")
                status = simulator.get_device_status(device.unique_id)
                print(f"📍 Eri al {status['route_progress']} del viaggio")
                break

        simulator.stop_device(device.unique_id)

        # Statistiche epiche finali
        final_status = simulator.get_device_status(device.unique_id)
        total_time = datetime.now() - start_time

        print(f"\n🏆 STATISTICHE GRAND TOUR:")
        print(f"   🚛 {final_status['name']}")
        print(f"   📍 Progresso: {final_status['route_progress']}")
        print(f"   ⏱️ Durata: {str(total_time).split('.')[0]}")
        print(f"   🗺️ Punti attraversati: {final_status['route_index']:,}/{final_status['route_points']:,}")

        if final_status['route_progress'] == '100.0%':
            print(f"\n🎉 CONGRATULAZIONI! HAI COMPLETATO IL GRAND TOUR EUROPEO! 🎉")
            print(f"🌍 Sei andato da Roma ad Amsterdam attraversando 6 paesi!")

    except Exception as e:
        print(f"❌ Errore nel Grand Tour: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Mantieni il dispositivo per usi futuri
        print("\n🧹 Pulizia risorse...")
        simulator.stop_all_devices()
        print("✅ Pulizia completata (camion mantenuto su Traccar)")


if __name__ == "__main__":
    # Configura logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("🚀 TRACCAR DEVICE SIMULATOR - VIAGGI COMPLETI!")
    print("="*80)
    print("⚠️  IMPORTANTE: Inserire la Google Maps API Key nel codice!")
    print("📍 Assicurarsi che la porta 5055 sia aperta sul server Traccar")
    print("🛣️  NUOVO: I viaggi ora vengono completati FINO ALLA FINE!")
    print("="*80)

    try:
        print("\n🎯 Scegli il tipo di simulazione:")
        print("1. 🚗 Viaggio completo Roma-Milano (con tappe)")
        print("2. 🌍 GRAND TOUR EUROPEO (Roma→Amsterdam)")
        print("3. 🚛 Test veloce (solo per verificare che funzioni)")

        choice = input("\n👉 Inserisci il numero (1-3): ").strip()

        if choice == "1":
            example_complete_journey()
        elif choice == "2":
            example_epic_journey()
        elif choice == "3":
            # Versione breve per test
            print("\n🧪 TEST VELOCE - Solo per verificare il funzionamento")

            traccar = TraccarAPI(
                host="torraccia.iliadboxos.it",
                port=58082,
                username="dspeziale@gmail.com",
                password="Elisa2025!",
                debug=False
            )

            GOOGLE_MAPS_KEY = "YOUR_GOOGLE_MAPS_API_KEY_HERE"

            simulator = TraccarSimulator(
                traccar_api=traccar,
                google_maps_key=GOOGLE_MAPS_KEY,
                traccar_protocol_host="torraccia.iliadboxos.it",
                traccar_protocol_port=5055
            )

            try:
                if not traccar.test_connection():
                    print("❌ Test connessione fallito")
                    exit(1)

                # 🚛 Usa logica di ricerca dispositivo anche per il test
                print("🔍 Ricerca dispositivo per test veloce...")
                device = simulator.get_or_create_truck_device("🧪 Test Veloce")

                print(f"📱 Dispositivo test: {device.name} (ID: {device.id})")

                # Percorso breve Roma centro
                origin = Location(41.9028, 12.4964, "Roma Termini")
                destination = Location(41.8986, 12.4768, "Roma Colosseo")

                # Controlla se già in movimento
                if device.unique_id in simulator.devices:
                    existing_device = simulator.devices[device.unique_id]
                    if hasattr(existing_device, 'is_moving') and existing_device.is_moving:
                        print("⚠️ Dispositivo già in movimento - lo fermo per il test")
                        simulator.stop_device(device.unique_id)

                simulator.set_route(device.unique_id, origin, destination)
                simulator.start_device(device.unique_id, update_interval=2.0)

                print("🚀 Test avviato per 30 secondi...")
                for i in range(15):
                    time.sleep(2)
                    status = simulator.get_device_status(device.unique_id)
                    print(f"📍 {i+1}/15 - Progresso: {status['route_progress']}")

                    if not status['is_moving']:
                        print("✅ Test completato!")
                        break

                simulator.stop_device(device.unique_id)

            finally:
                # Non fare cleanup completo per il test
                print("🧹 Fine test (dispositivo mantenuto)")
                simulator.stop_all_devices()

        else:
            print("❌ Scelta non valida")

    except KeyboardInterrupt:
        print("\n⏹️ Simulazione interrotta dall'utente")
    except Exception as e:
        print(f"\n💥 ERRORE CRITICO: {e}")
        import traceback
        traceback.print_exc()