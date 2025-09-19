"""
Traccar Device Simulator - Sistema di Simulazione Dispositivi con Cache Percorsi
================================================================================

Sistema completo per simulare dispositivi GPS che si muovono lungo percorsi realistici
utilizzando Google Maps Directions API e il framework Traccar.

NOVITA: Sistema di cache intelligente per evitare richieste duplicate a Google Maps
Menu strutturato con 10 opzioni per tutti i tipi di viaggi
"""

import math
import time
import json
import threading
import hashlib
import os
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import requests
import random
from dataclasses import dataclass, field
import logging

# Importa il framework Traccar esistente
from core.traccar_framework import TraccarAPI, TraccarException

logger = logging.getLogger('TraccarSimulator')


@dataclass
class Location:
    """Rappresenta una posizione geografica"""
    latitude: float
    longitude: float
    address: Optional[str] = None
    timestamp: Optional[datetime] = None

    def to_key_string(self) -> str:
        """Genera una stringa chiave per la cache basata su coordinate o nome"""
        # FIX: Priorità all'indirizzo se presente per garantire cache hit
        if self.address:
            # Normalizza l'indirizzo per la cache
            return self.address.lower().strip()
        # Se abbiamo coordinate valide, usale
        elif self.latitude != 0.0 and self.longitude != 0.0:
            return f"{round(self.latitude, 4)},{round(self.longitude, 4)}"
        else:
            return "unknown_location"


@dataclass
class RoutePoint:
    """Punto lungo un percorso con informazioni aggiuntive"""
    location: Location
    speed: float = 50.0  # km/h
    bearing: float = 0.0  # gradi
    distance_from_start: float = 0.0  # metri


@dataclass
class CachedRoute:
    """Percorso cachato con metadati"""
    route_points: List[RoutePoint]
    created_at: datetime
    origin_key: str
    destination_key: str
    waypoints_key: str
    transport_mode: str
    total_distance: float
    estimated_duration: timedelta

    def is_expired(self, max_age_days: int = 30) -> bool:
        """Controlla se il percorso cachato è scaduto"""
        return datetime.now() - self.created_at > timedelta(days=max_age_days)


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


class RouteCache:
    """Gestione cache percorsi per ottimizzare chiamate Google Maps API"""

    def __init__(self, cache_dir: str = "route_cache", max_age_days: int = 30, max_cache_size: int = 1000):
        """
        Inizializza il sistema di cache

        Args:
            cache_dir: Directory per salvare i file di cache
            max_age_days: Giorni dopo cui un percorso scade
            max_cache_size: Numero massimo di percorsi da mantenere in cache
        """
        self.cache_dir = cache_dir
        self.max_age_days = max_age_days
        self.max_cache_size = max_cache_size
        self.memory_cache: Dict[str, CachedRoute] = {}

        # Crea directory cache se non exists
        os.makedirs(cache_dir, exist_ok=True)

        # Carica cache esistente
        self._load_cache_from_disk()

        logger.info(f"🗄️ RouteCache inizializzato: {len(self.memory_cache)} percorsi in cache")

    def _generate_route_key(self, origin: Location, destination: Location,
                            waypoints: List[Location] = None, mode: str = "driving") -> str:
        """Genera chiave univoca per un percorso"""
        waypoints_str = ""
        if waypoints:
            waypoints_str = "|".join([wp.to_key_string() for wp in waypoints])

        # Costruisci la stringa del percorso
        route_string = f"{origin.to_key_string()}->{destination.to_key_string()}|{waypoints_str}|{mode}"

        # DEBUG: Log della chiave generata
        logger.debug(f"🔑 Chiave cache generata: {route_string}")

        return hashlib.md5(route_string.encode()).hexdigest()

    def _get_cache_file_path(self, route_key: str) -> str:
        """Ottiene il percorso del file di cache per una route"""
        return os.path.join(self.cache_dir, f"{route_key}.pkl")

    def _load_cache_from_disk(self):
        """Carica cache esistente dal disco"""
        try:
            cache_files = [f for f in os.listdir(self.cache_dir) if f.endswith('.pkl')]
            loaded_count = 0

            for cache_file in cache_files:
                try:
                    route_key = cache_file[:-4]  # Rimuovi .pkl
                    file_path = os.path.join(self.cache_dir, cache_file)

                    with open(file_path, 'rb') as f:
                        cached_route = pickle.load(f)

                    # Controlla se il percorso è scaduto
                    if cached_route.is_expired(self.max_age_days):
                        os.remove(file_path)
                        logger.debug(f"🗑️ Cache scaduta rimossa: {route_key}")
                        continue

                    self.memory_cache[route_key] = cached_route
                    loaded_count += 1

                except Exception as e:
                    logger.warning(f"⚠️ Errore caricamento cache {cache_file}: {e}")
                    # Rimuovi file corrotto
                    try:
                        os.remove(os.path.join(self.cache_dir, cache_file))
                    except:
                        pass

            logger.info(f"📚 Caricati {loaded_count} percorsi dalla cache su disco")

        except Exception as e:
            logger.warning(f"⚠️ Errore caricamento cache generale: {e}")

    def _save_route_to_disk(self, route_key: str, cached_route: CachedRoute):
        """Salva un percorso su disco"""
        try:
            file_path = self._get_cache_file_path(route_key)
            with open(file_path, 'wb') as f:
                pickle.dump(cached_route, f)
            logger.debug(f"💾 Percorso salvato in cache: {route_key}")
        except Exception as e:
            logger.error(f"❌ Errore salvataggio cache {route_key}: {e}")

    def get_cached_route(self, origin: Location, destination: Location,
                        waypoints: List[Location] = None, mode: str = "driving") -> Optional[CachedRoute]:
        """
        Cerca un percorso nella cache

        Returns:
            CachedRoute se trovato e valido, None altrimenti
        """
        route_key = self._generate_route_key(origin, destination, waypoints, mode)

        # Controlla prima la memoria cache
        if route_key in self.memory_cache:
            cached_route = self.memory_cache[route_key]

            # Controlla se scaduto
            if cached_route.is_expired(self.max_age_days):
                logger.debug(f"⏰ Cache scaduta per {route_key}")
                del self.memory_cache[route_key]
                # Rimuovi anche dal disco
                try:
                    os.remove(self._get_cache_file_path(route_key))
                except:
                    pass
                return None

            logger.info(f"🎯 CACHE HIT: Percorso trovato in cache ({len(cached_route.route_points)} punti)")
            return cached_route

        logger.debug(f"🔍 Cache miss per {route_key}")
        return None

    def store_route(self, origin: Location, destination: Location, waypoints: List[Location],
                   mode: str, route_points: List[RoutePoint], total_distance: float) -> str:
        """
        Memorizza un percorso nella cache

        Returns:
            Chiave del percorso memorizzato
        """
        route_key = self._generate_route_key(origin, destination, waypoints, mode)

        # Calcola durata stimata
        avg_speed = sum(rp.speed for rp in route_points) / len(route_points) if route_points else 50
        estimated_duration = timedelta(hours=total_distance / 1000 / avg_speed)

        waypoints_key = ""
        if waypoints:
            waypoints_key = "|".join([wp.to_key_string() for wp in waypoints])

        cached_route = CachedRoute(
            route_points=route_points,
            created_at=datetime.now(),
            origin_key=origin.to_key_string(),
            destination_key=destination.to_key_string(),
            waypoints_key=waypoints_key,
            transport_mode=mode,
            total_distance=total_distance,
            estimated_duration=estimated_duration
        )

        # Gestione dimensioni cache
        if len(self.memory_cache) >= self.max_cache_size:
            self._cleanup_old_cache_entries()

        # Memorizza in memoria e su disco
        self.memory_cache[route_key] = cached_route
        self._save_route_to_disk(route_key, cached_route)

        logger.info(f"💾 Nuovo percorso memorizzato in cache: {len(route_points)} punti, {total_distance:.0f}m")
        return route_key

    def _cleanup_old_cache_entries(self):
        """Rimuove le entry più vecchie dalla cache"""
        if len(self.memory_cache) < self.max_cache_size:
            return

        # Ordina per data di creazione e rimuovi i più vecchi
        sorted_entries = sorted(
            self.memory_cache.items(),
            key=lambda x: x[1].created_at
        )

        entries_to_remove = len(sorted_entries) - (self.max_cache_size // 2)

        for i in range(entries_to_remove):
            route_key, _ = sorted_entries[i]
            del self.memory_cache[route_key]

            # Rimuovi anche dal disco
            try:
                os.remove(self._get_cache_file_path(route_key))
            except:
                pass

        logger.info(f"🧹 Pulizia cache: {entries_to_remove} entry rimosse")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Ottiene statistiche sulla cache"""
        total_points = sum(len(route.route_points) for route in self.memory_cache.values())
        total_distance = sum(route.total_distance for route in self.memory_cache.values())

        modes = {}
        for route in self.memory_cache.values():
            modes[route.transport_mode] = modes.get(route.transport_mode, 0) + 1

        return {
            "total_routes": len(self.memory_cache),
            "total_points": total_points,
            "total_distance_km": total_distance / 1000,
            "cache_dir": self.cache_dir,
            "max_age_days": self.max_age_days,
            "transport_modes": modes,
            "avg_points_per_route": total_points / len(self.memory_cache) if self.memory_cache else 0
        }

    def clear_cache(self):
        """Pulisce completamente la cache"""
        # Rimuovi da memoria
        self.memory_cache.clear()

        # Rimuovi file dal disco
        try:
            cache_files = [f for f in os.listdir(self.cache_dir) if f.endswith('.pkl')]
            for cache_file in cache_files:
                os.remove(os.path.join(self.cache_dir, cache_file))
            logger.info(f"🗑️ Cache completamente pulita: {len(cache_files)} file rimossi")
        except Exception as e:
            logger.error(f"❌ Errore pulizia cache: {e}")


class GoogleMapsClient:
    """Client per Google Maps Directions API con cache intelligente"""

    def __init__(self, api_key: str, cache_dir: str = "route_cache"):
        self.api_key = api_key
        self.base_url = "https://maps.googleapis.com/maps/api/directions/json"
        self.route_cache = RouteCache(cache_dir)
        self.api_calls_count = 0
        self.cache_hits_count = 0

    def get_route(self, origin: Location, destination: Location,
                  waypoints: List[Location] = None, mode: str = "driving") -> List[RoutePoint]:
        """
        Ottiene un percorso da Google Maps o dalla cache

        Args:
            origin: Punto di partenza
            destination: Punto di arrivo
            waypoints: Punti intermedi opzionali
            mode: Modalità di trasporto (driving, walking, bicycling, transit)

        Returns:
            Lista di RoutePoint che compongono il percorso
        """
        # 🎯 PRIMA CONTROLLA LA CACHE
        cached_route = self.route_cache.get_cached_route(origin, destination, waypoints, mode)

        if cached_route:
            self.cache_hits_count += 1
            logger.info(f"⚡ CACHE HIT! Percorso recuperato dalla cache ({len(cached_route.route_points)} punti)")
            logger.info(f"💰 API call risparmiata! Totale cache hits: {self.cache_hits_count}")

            # Aggiorna timestamps delle location per simulazione corrente
            for route_point in cached_route.route_points:
                route_point.location.timestamp = datetime.now()

            return cached_route.route_points

        # 🌐 NESSUNA CACHE - USA GOOGLE MAPS API
        logger.info(f"🔍 Cache miss - Richiesta a Google Maps API")
        return self._fetch_route_from_google_maps(origin, destination, waypoints, mode)

    def _fetch_route_from_google_maps(self, origin: Location, destination: Location,
                                     waypoints: List[Location] = None, mode: str = "driving") -> List[RoutePoint]:
        """Recupera percorso direttamente da Google Maps API"""

        # Prepara i parametri per Google Maps
        # Se le coordinate sono 0.0,0.0 usa il nome della città (address)
        origin_param = origin.address if (abs(origin.latitude) < 0.001 and abs(origin.longitude) < 0.001) else f"{origin.latitude},{origin.longitude}"
        destination_param = destination.address if (abs(destination.latitude) < 0.001 and abs(destination.longitude) < 0.001) else f"{destination.latitude},{destination.longitude}"

        params = {
            'origin': origin_param,
            'destination': destination_param,
            'key': self.api_key,
            'mode': mode
        }

        if waypoints:
            waypoint_params = []
            for wp in waypoints:
                if abs(wp.latitude) < 0.001 and abs(wp.longitude) < 0.001:
                    waypoint_params.append(wp.address)
                else:
                    waypoint_params.append(f"{wp.latitude},{wp.longitude}")
            params['waypoints'] = "|".join(waypoint_params)

        try:
            self.api_calls_count += 1
            logger.info(f"🗺️ API Call #{self.api_calls_count} - Richiesta percorso da '{origin_param}' a '{destination_param}'")

            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()

            if data['status'] != 'OK':
                error_msg = f"Google Maps API error: {data['status']}"
                if 'error_message' in data:
                    error_msg += f" - {data['error_message']}"

                # Messaggi di errore più informativi
                if data['status'] == 'ZERO_RESULTS':
                    error_msg += f"\nNessun percorso trovato tra '{origin_param}' e '{destination_param}'. Verifica che le località esistano."
                elif data['status'] == 'NOT_FOUND':
                    error_msg += f"\nUna o entrambe le località non sono state trovate: '{origin_param}', '{destination_param}'"
                elif data['status'] == 'INVALID_REQUEST':
                    error_msg += f"\nRichiesta non valida. Verifica i parametri: origine='{origin_param}', destinazione='{destination_param}'"

                logger.error(f"❌ {error_msg}")
                raise Exception(error_msg)

            route_points = []
            total_distance = 0

            # Processa la prima rotta
            route = data['routes'][0]

            # Aggiorna le coordinate reali dalle risposte di Google Maps
            # se erano state inserite come nomi di città
            if abs(origin.latitude) < 0.001 and abs(origin.longitude) < 0.001:
                start_location = route['legs'][0]['start_location']
                origin.latitude = start_location['lat']
                origin.longitude = start_location['lng']
                logger.info(f"📍 Coordinate risolte per {origin.address}: {origin.latitude:.4f}, {origin.longitude:.4f}")

            if abs(destination.latitude) < 0.001 and abs(destination.longitude) < 0.001:
                end_location = route['legs'][-1]['end_location']
                destination.latitude = end_location['lat']
                destination.longitude = end_location['lng']
                logger.info(f"🎯 Coordinate risolte per {destination.address}: {destination.latitude:.4f}, {destination.longitude:.4f}")

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

            # 💾 SALVA NELLA CACHE per usi futuri
            if route_points:
                cache_key = self.route_cache.store_route(
                    origin=origin,
                    destination=destination,
                    waypoints=waypoints or [],
                    mode=mode,
                    route_points=route_points,
                    total_distance=total_distance
                )
                logger.info(f"💾 Percorso salvato in cache con chiave: {cache_key[:8]}...")

            logger.info(f"✅ Percorso ottenuto da Google Maps: {len(route_points)} punti, {total_distance:.0f}m totali")
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

    def get_api_stats(self) -> Dict[str, Any]:
        """Ottiene statistiche sull'utilizzo dell'API"""
        total_requests = self.api_calls_count + self.cache_hits_count
        cache_hit_rate = (self.cache_hits_count / total_requests * 100) if total_requests > 0 else 0

        return {
            "api_calls": self.api_calls_count,
            "cache_hits": self.cache_hits_count,
            "total_requests": total_requests,
            "cache_hit_rate": f"{cache_hit_rate:.1f}%",
            "api_calls_saved": self.cache_hits_count,
            "cache_stats": self.route_cache.get_cache_stats()
        }


class TraccarProtocolClient:
    """
    Client per inviare dati GPS direttamente al server Traccar
    utilizzando il protocollo OsmAnd (HTTP GET)
    """

    def __init__(self, host: str, port: int = 57355, protocol: str = "http"):
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
    """Simulatore principale per dispositivi Traccar con cache intelligente"""

    def __init__(self, traccar_api: TraccarAPI, google_maps_key: str,
                 traccar_protocol_host: str, traccar_protocol_port: int = 57355,
                 cache_dir: str = "route_cache"):
        """
        Inizializza il simulatore con sistema di cache

        Args:
            traccar_api: Istanza del TraccarAPI per gestire dispositivi
            google_maps_key: Chiave API Google Maps
            traccar_protocol_host: Host per invio dati GPS
            traccar_protocol_port: Porta per invio dati GPS (default: 57355 per OsmAnd)
            cache_dir: Directory per cache percorsi
        """
        self.traccar = traccar_api
        self.google_maps = GoogleMapsClient(google_maps_key, cache_dir)
        self.protocol_client = TraccarProtocolClient(traccar_protocol_host, traccar_protocol_port)

        self.devices: Dict[str, SimulatedDevice] = {}
        self.is_running = False

        logger.info(f"🚀 TraccarSimulator inizializzato con cache in: {cache_dir}")

    def find_existing_truck_device(self) -> Optional[SimulatedDevice]:
        """Cerca un dispositivo esistente tipo camion/truck"""
        try:
            logger.info("🔍 Ricerca dispositivi tipo camion esistenti...")

            existing_devices = self.traccar.devices.get_devices()

            truck_keywords = [
                'camion', 'truck', 'tir', 'autocarro', 'furgone',
                'van', 'lorry', 'trailer', 'semi', 'freight'
            ]

            for device_data in existing_devices:
                device_name = device_data.get('name', '').lower()
                device_category = device_data.get('category', '').lower()
                unique_id = device_data.get('uniqueId', '')

                is_truck = any(keyword in device_name for keyword in truck_keywords)
                is_truck = is_truck or any(keyword in device_category for keyword in truck_keywords)
                is_truck = is_truck or 'truck' in device_category or 'camion' in device_category

                if is_truck:
                    logger.info(f"🚛 Trovato dispositivo camion esistente: {device_data['name']} (ID: {device_data['id']})")

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
        """Crea un nuovo dispositivo simulato o usa uno esistente se compatibile"""
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
        """Ottiene un dispositivo camion esistente o ne crea uno nuovo"""
        logger.info("🚛 Ricerca o creazione dispositivo camion...")

        existing_truck = self.find_existing_truck_device()

        if existing_truck:
            logger.info(f"♻️ Utilizzo camion esistente: {existing_truck.name} (ID: {existing_truck.id})")
            return existing_truck

        logger.info("🔨 Creazione nuovo dispositivo camion...")
        return self.create_device(preferred_name, force_new=True)

    def set_route(self, device_unique_id: str, origin: Location, destination: Location,
                  waypoints: List[Location] = None, transport_mode: str = "driving") -> bool:
        """
        Imposta un percorso per un dispositivo (con cache automatica)
        """
        if device_unique_id not in self.devices:
            logger.error(f"❌ Dispositivo {device_unique_id} non trovato")
            return False

        device = self.devices[device_unique_id]

        try:
            logger.info(f"🗺️ Calcolo percorso per {device.name} (verifica cache prima...)...")

            route = self.google_maps.get_route(origin, destination, waypoints, transport_mode)

            if not route:
                logger.error(f"❌ Nessun percorso trovato per {device.name}")
                return False

            device.route = route
            device.route_index = 0
            device.current_location = origin

            speeds = {
                'driving': random.uniform(40, 70),
                'walking': random.uniform(4, 6),
                'bicycling': random.uniform(15, 25),
                'transit': random.uniform(30, 50)
            }
            device.speed = speeds.get(transport_mode, 50.0)

            api_stats = self.google_maps.get_api_stats()
            logger.info(f"📊 Statistiche API: {api_stats['api_calls']} calls, {api_stats['cache_hits']} cache hits ({api_stats['cache_hit_rate']} hit rate)")

            logger.info(f"✅ Percorso impostato per {device.name}: {len(route)} punti, velocità {device.speed:.1f} km/h")
            return True

        except Exception as e:
            logger.error(f"❌ Errore impostazione percorso per {device.name}: {e}")
            return False

    def start_device(self, device_unique_id: str, update_interval: float = 5.0) -> bool:
        """Avvia la simulazione per un dispositivo"""
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

        device.thread = threading.Thread(
            target=self._move_device,
            args=(device,),
            daemon=True
        )
        device.thread.start()

        logger.info(f"🚀 Simulazione avviata per {device.name} (intervallo: {update_interval}s)")
        return True

    def stop_device(self, device_unique_id: str) -> bool:
        """Ferma la simulazione per un dispositivo"""
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

    def stop_all_devices(self) -> int:
        """Ferma la simulazione per tutti i dispositivi"""
        stopped = 0
        for device_id in self.devices:
            if self.stop_device(device_id):
                stopped += 1
        logger.info(f"🛑 {stopped}/{len(self.devices)} dispositivi fermati")
        return stopped

    def get_device_status(self, device_unique_id: str = None) -> Dict[str, Any]:
        """Ottiene lo stato dei dispositivi"""
        if device_unique_id:
            if device_unique_id not in self.devices:
                return {}
            device = self.devices[device_unique_id]
            return self._get_single_device_status(device)

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
                if device.route_index >= len(device.route):
                    end_time = datetime.now()
                    duration = end_time - start_time

                    logger.info(f"🏁 {device.name} HA COMPLETATO L'INTERO PERCORSO!")
                    logger.info(f"📊 Statistiche viaggio:")
                    logger.info(f"   ⏱️ Durata totale: {duration}")
                    logger.info(f"   📍 Punti attraversati: {device.route_index}")
                    logger.info(f"   ✅ Aggiornamenti riusciti: {successful_updates}")
                    logger.info(f"   ❌ Aggiornamenti falliti: {failed_updates}")
                    if successful_updates + failed_updates > 0:
                        success_rate = (successful_updates/(successful_updates+failed_updates)*100)
                        logger.info(f"   📡 Successo rate: {success_rate:.1f}%")

                    device.is_moving = False
                    break

                route_point = device.route[device.route_index]
                device.current_location = route_point.location
                device.current_location.timestamp = datetime.now()

                progress = (device.route_index / len(device.route)) * 100

                success = self.protocol_client.send_position(
                    device_id=device.unique_id,
                    location=device.current_location,
                    speed=route_point.speed,
                    bearing=route_point.bearing,
                    altitude=random.uniform(50, 200),
                    accuracy=random.uniform(2, 8)
                )

                if success:
                    successful_updates += 1
                    device.last_update = datetime.now()

                    if device.route_index % 50 == 0 or device.route_index < 10 or device.route_index > len(device.route) - 10:
                        logger.info(f"📍 {device.name} - Punto {device.route_index+1}/{len(device.route)} ({progress:.1f}%): "
                                   f"{device.current_location.latitude:.6f}, {device.current_location.longitude:.6f}, "
                                   f"Velocità: {route_point.speed:.1f} km/h")
                    else:
                        logger.debug(f"📍 {device.name} - {progress:.1f}% - "
                                    f"Lat: {device.current_location.latitude:.6f}, "
                                    f"Lon: {device.current_location.longitude:.6f}")
                else:
                    failed_updates += 1
                    logger.warning(f"⚠️ {device.name} - Errore invio punto {device.route_index+1}/{len(device.route)}")

                device.route_index += 1

                if int(progress) % 10 == 0 and device.route_index > 1:
                    new_progress = (device.route_index / len(device.route)) * 100
                    if int(new_progress) != int(progress):
                        elapsed = datetime.now() - start_time
                        remaining_points = len(device.route) - device.route_index
                        estimated_remaining = (elapsed / device.route_index) * remaining_points if device.route_index > 0 else timedelta(0)

                        logger.info(f"🚗 {device.name} - PROGRESSO {new_progress:.0f}% - "
                                   f"Elapsed: {str(elapsed).split('.')[0]}, "
                                   f"ETA: {str(estimated_remaining).split('.')[0]}")

                dynamic_interval = min(device.update_interval, max(1.0, device.update_interval * (route_point.speed / 50.0)))

                if device.stop_event.wait(dynamic_interval):
                    logger.info(f"🛑 {device.name} - Fermato manualmente al {progress:.1f}%")
                    break

            except Exception as e:
                failed_updates += 1
                logger.error(f"❌ Errore movimento {device.name} al punto {device.route_index}: {e}")
                time.sleep(1)

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

    def get_cache_statistics(self) -> Dict[str, Any]:
        """Ottiene statistiche complete su cache e API usage"""
        return self.google_maps.get_api_stats()

    def clear_route_cache(self):
        """Pulisce completamente la cache dei percorsi"""
        self.google_maps.route_cache.clear_cache()
        logger.info("🗑️ Cache percorsi completamente pulita")

    # METODI MENU PRINCIPALE

    def personal_setup(self):
        """Setup personalizzato dove l'utente inserisce le sue città"""
        print("\n🎯 SETUP PERSONALIZZATO - INSERISCI LE TUE CITTÀ")
        print("="*60)

        try:
            if not self.traccar.test_connection():
                print("❌ Connessione Traccar fallita")
                return False

            print("✅ Connesso a Traccar")

            selected_trips = []

            while len(selected_trips) < 15:
                print(f"\n📋 VIAGGIO #{len(selected_trips) + 1}")
                print("-" * 30)

                # Input città
                origin_input = input("📍 Partenza: ").strip()
                if not origin_input:
                    break

                dest_input = input("🎯 Destinazione: ").strip()
                if not dest_input:
                    break

                origin = Location(0.0, 0.0, origin_input)
                destination = Location(0.0, 0.0, dest_input)

                # Waypoints opzionali
                waypoints = []
                wp_input = input("🔗 Waypoint (opzionale): ").strip()
                if wp_input:
                    waypoints.append(Location(0.0, 0.0, wp_input))

                # Nome dispositivo
                device_name = input(f"🚛 Nome dispositivo [Auto #{len(selected_trips)+1}]: ").strip()
                if not device_name:
                    device_name = f"🚛 Auto #{len(selected_trips)+1}"

                device = self.create_device(device_name, force_new=True)

                selected_trips.append({
                    'device': device,
                    'route_config': {
                        'origin': origin,
                        'destination': destination,
                        'waypoints': waypoints,
                        'transport_mode': 'driving',
                        'name': f"{origin_input} → {dest_input}"
                    },
                    'sim_params': {
                        'update_interval': 5.0,
                        'show_progress': True
                    }
                })

                print(f"✅ Viaggio aggiunto: {origin_input} → {dest_input}")

                if input("\nAggiungi altro viaggio? [s/n]: ").lower() != 's':
                    break

            if not selected_trips:
                return False

            return self._execute_all_trips(selected_trips)

        except Exception as e:
            print(f"❌ Errore setup personalizzato: {e}")
            return False

    def italy_travels(self):
        """Menu viaggi Italia"""
        italy_routes = {
            '1': ('Roma → Milano', 'Roma', 'Milano', []),
            '2': ('Milano → Napoli', 'Milano', 'Napoli', ['Bologna', 'Roma']),
            '3': ('Torino → Bari', 'Torino', 'Bari', ['Milano', 'Bologna', 'Napoli']),
            '4': ('Venezia → Palermo', 'Venezia', 'Palermo', ['Bologna', 'Roma', 'Napoli']),
            '5': ('Genova → Lecce', 'Genova', 'Lecce', ['Roma', 'Napoli', 'Bari']),
            '6': ('Tour Nord Italia', 'Milano', 'Torino', ['Bergamo', 'Brescia']),
            '7': ('Tour Sud Italia', 'Napoli', 'Reggio Calabria', ['Salerno', 'Cosenza']),
            '8': ('Costa a Costa', 'Genova', 'Venezia', ['Milano', 'Verona'])
        }
        return self._category_selection("🇮🇹 VIAGGI ITALIA", italy_routes)

    def europe_travels(self):
        """Menu viaggi Europa"""
        europe_routes = {
            '1': ('Roma → Parigi', 'Roma', 'Parigi', ['Milano', 'Lyon']),
            '2': ('Milano → Berlino', 'Milano', 'Berlino', ['Zurigo', 'Monaco', 'Francoforte']),
            '3': ('Madrid → Amsterdam', 'Madrid', 'Amsterdam', ['Parigi', 'Bruxelles']),
            '4': ('Londra → Roma', 'Londra', 'Roma', ['Parigi', 'Lyon', 'Milano']),
            '5': ('Barcellona → Vienna', 'Barcellona', 'Vienna', ['Lyon', 'Zurigo', 'Monaco']),
            '6': ('Tour Capitali', 'Parigi', 'Berlino', ['Bruxelles', 'Amsterdam']),
            '7': ('Scandinavia Express', 'Copenaghen', 'Stoccolma', ['Oslo']),
            '8': ('Mediterraneo Tour', 'Barcellona', 'Atene', ['Nizza', 'Roma'])
        }
        return self._category_selection("🇪🇺 VIAGGI EUROPA", europe_routes)

    def intercontinental_travels(self):
        """Menu viaggi intercontinentali"""
        intercontinental_routes = {
            '1': ('New York → Los Angeles', 'New York', 'Los Angeles', ['Chicago']),
            '2': ('Mosca → Vladivostok', 'Mosca', 'Vladivostok', []),
            '3': ('Tokyo → Seoul', 'Tokyo', 'Seoul', []),
            '4': ('Sydney → Melbourne', 'Sydney', 'Melbourne', []),
            '5': ('Toronto → Vancouver', 'Toronto', 'Vancouver', []),
            '6': ('Istanbul → Mumbai', 'Istanbul', 'Mumbai', []),
            '7': ('San Paolo → Buenos Aires', 'San Paolo', 'Buenos Aires', []),
            '8': ('Mexico City → New York', 'Mexico City', 'New York', ['Chicago'])
        }
        return self._category_selection("🌍 VIAGGI INTERCONTINENTALI", intercontinental_routes)

    def commercial_travels(self):
        """Menu viaggi commerciali"""
        commercial_routes = {
            '1': ('Logistica Nord-Sud', 'Milano', 'Napoli', ['Bologna']),
            '2': ('Distribuzione Centri', 'Roma', 'Firenze', []),
            '3': ('Express Delivery', 'Torino', 'Roma', ['Milano']),
            '4': ('Trasporto Merci EU', 'Milano', 'Francoforte', ['Zurigo']),
            '5': ('Supply Chain', 'Genova', 'Milano', []),
            '6': ('Cross-Docking', 'Bologna', 'Verona', []),
            '7': ('Last Mile', 'Roma', 'Napoli', []),
            '8': ('International Freight', 'Amsterdam', 'Milano', ['Zurigo'])
        }
        return self._category_selection("🚛 VIAGGI COMMERCIALI", commercial_routes)

    def special_travels(self):
        """Menu viaggi speciali"""
        special_routes = {
            '1': ('Arctic Challenge', 'Oslo', 'Reykjavik', []),
            '2': ('Desert Crossing', 'Marrakech', 'Cairo', []),
            '3': ('Silk Road Mini', 'Istanbul', 'Beijing', ['Moscow']),
            '4': ('Pan-American', 'Anchorage', 'Ushuaia', ['Vancouver', 'Los Angeles', 'Mexico City', 'San Paolo']),
            '5': ('Euro Capitals Tour', 'Lisbon', 'Helsinki', ['Madrid', 'Paris', 'Berlin', 'Warsaw']),
            '6': ('Mediterranean Circle', 'Barcelona', 'Barcelona', ['Nice', 'Rome', 'Athens', 'Istanbul']),
            '7': ('Tech Cities Tour', 'San Francisco', 'Shenzhen', ['Seattle', 'Tokyo']),
            '8': ('Epic Adventure', 'Capo Nord', 'Cape Town', ['Moscow', 'Istanbul', 'Cairo'])
        }
        return self._category_selection("🎯 VIAGGI SPECIALI", special_routes)

    def quick_travels(self):
        """Menu viaggi rapidi"""
        quick_routes = {
            '1': ('Roma → Milano', 'Roma', 'Milano'),
            '2': ('Milano → Napoli', 'Milano', 'Napoli'),
            '3': ('Napoli → Roma', 'Napoli', 'Roma'),
            '4': ('Roma → Parigi', 'Roma', 'Parigi'),
            '5': ('Milano → Berlino', 'Milano', 'Berlino'),
            '6': ('New York → Los Angeles', 'New York', 'Los Angeles'),
            '7': ('Tokyo → Seoul', 'Tokyo', 'Seoul'),
            '8': ('Sydney → Melbourne', 'Sydney', 'Melbourne')
        }

        print("\n⚡ VIAGGI RAPIDI - SELEZIONE MULTIPLA")
        print("="*50)

        try:
            if not self.traccar.test_connection():
                print("❌ Connessione fallita")
                return False

            print("VIAGGI DISPONIBILI:")
            for key, (name, _, _) in quick_routes.items():
                print(f"  {key}. {name}")

            choices = input("\nSeleziona viaggi [es: 1,4,7]: ").strip()
            if not choices:
                return False

            selected_keys = [k.strip() for k in choices.split(',')]
            selected_trips = []

            for choice in selected_keys:
                if choice in quick_routes:
                    route_name, origin_city, dest_city = quick_routes[choice]

                    origin = Location(0.0, 0.0, origin_city)
                    destination = Location(0.0, 0.0, dest_city)

                    device_name = f"⚡ {origin_city} #{len(selected_trips) + 1}"
                    device = self.create_device(device_name, force_new=True)

                    selected_trips.append({
                        'device': device,
                        'route_config': {
                            'origin': origin,
                            'destination': destination,
                            'waypoints': [],
                            'transport_mode': 'driving',
                            'name': route_name
                        },
                        'sim_params': {
                            'update_interval': 3.0,  # Più veloce
                            'show_progress': True
                        }
                    })

                    print(f"✅ Aggiunto: {route_name}")

            if not selected_trips:
                return False

            return self._execute_all_trips(selected_trips)

        except Exception as e:
            print(f"❌ Errore viaggi rapidi: {e}")
            return False

    def _category_selection(self, category_name, routes):
        """Metodo generico per selezione categorie"""
        print(f"\n{category_name}")
        print("="*50)

        try:
            if not self.traccar.test_connection():
                return False

            selected_trips = []

            while len(selected_trips) < 8:
                print(f"\nVIAGGI {category_name}:")

                available_routes = {k: v for k, v in routes.items()
                                  if not any(trip['route_config']['name'] == v[0] for trip in selected_trips)}

                if not available_routes:
                    break

                for key, (name, origin, dest, waypoints) in available_routes.items():
                    waypoint_str = f" (via {', '.join(waypoints)})" if waypoints else ""
                    print(f"  {key}. {name}{waypoint_str}")

                choices = input(f"\nSeleziona viaggi [es: 1,3,5]: ").strip()
                if not choices:
                    break

                selected_keys = [k.strip() for k in choices.split(',')]

                for choice in selected_keys:
                    if choice in available_routes:
                        route_name, origin_city, dest_city, waypoint_cities = available_routes[choice]

                        origin = Location(0.0, 0.0, origin_city)
                        destination = Location(0.0, 0.0, dest_city)
                        waypoints = [Location(0.0, 0.0, city) for city in waypoint_cities]

                        device_name = f"🚛 {route_name.split(' → ')[0]} #{len(selected_trips) + 1}"
                        device = self.create_device(device_name, force_new=True)

                        selected_trips.append({
                            'device': device,
                            'route_config': {
                                'origin': origin,
                                'destination': destination,
                                'waypoints': waypoints,
                                'transport_mode': 'driving',
                                'name': route_name
                            },
                            'sim_params': {
                                'update_interval': 5.0,
                                'show_progress': True
                            }
                        })

                        print(f"✅ Aggiunto: {route_name}")

                print(f"\n📊 VIAGGI SELEZIONATI ({len(selected_trips)}):")
                for trip in selected_trips:
                    print(f"  • {trip['route_config']['name']}")

                if input("\nContinua selezione? [s/n]: ").lower() != 's':
                    break

            if not selected_trips:
                return False

            return self._execute_all_trips(selected_trips)

        except Exception as e:
            print(f"❌ Errore {category_name}: {e}")
            return False

    def _execute_all_trips(self, trips):
        """Esegue tutti i viaggi configurati"""
        print(f"\n🚀 AVVIO {len(trips)} VIAGGI SIMULTANEI")
        print("="*50)

        # Statistiche pre-avvio
        cache_hits = 0
        api_calls_needed = 0

        for trip in trips:
            cached_route = self.google_maps.route_cache.get_cached_route(
                trip['route_config']['origin'],
                trip['route_config']['destination'],
                trip['route_config']['waypoints'],
                trip['route_config']['transport_mode']
            )
            if cached_route:
                cache_hits += 1
            else:
                api_calls_needed += 1

        print(f"📊 Statistiche:")
        print(f"   🚛 Viaggi totali: {len(trips)}")
        print(f"   ⚡ Cache hits: {cache_hits}")
        print(f"   🌐 API calls: {api_calls_needed}")

        # Configurazione percorsi
        print(f"\n🗺️ Configurazione percorsi...")
        configured_trips = []

        for i, trip in enumerate(trips, 1):
            device = trip['device']
            route_config = trip['route_config']

            print(f"   {i}/{len(trips)} Configurando {device.name}...")

            success = self.set_route(
                device.unique_id,
                route_config['origin'],
                route_config['destination'],
                route_config['waypoints'],
                route_config['transport_mode']
            )

            if success:
                configured_trips.append(trip)
            else:
                print(f"   ❌ Errore {device.name}")

        if not configured_trips:
            print("❌ Nessun viaggio configurato correttamente")
            return False

        print(f"✅ {len(configured_trips)}/{len(trips)} viaggi configurati")

        # Avvio simultaneo
        print(f"\n🏁 Avvio simultaneo...")
        started_count = 0

        for trip in configured_trips:
            device = trip['device']
            sim_params = trip['sim_params']

            if self.start_device(device.unique_id, sim_params['update_interval']):
                started_count += 1
                print(f"   ✅ {device.name}")
            else:
                print(f"   ❌ {device.name}")

        if started_count == 0:
            print("❌ Nessun viaggio avviato")
            return False

        print(f"\n📱 {started_count} VIAGGI IN CORSO")
        print(f"⏱️ Avviati alle: {datetime.now().strftime('%H:%M:%S')}")
        print("🛑 CTRL+C per fermare tutti\n")

        # Monitoraggio semplificato
        return self._monitor_progress(configured_trips)

    def _monitor_progress(self, trips):
        """Monitoraggio progresso viaggi"""
        start_time = datetime.now()
        completed_vehicles = set()

        try:
            while len(completed_vehicles) < len(trips):
                time.sleep(20)  # Check ogni 20 secondi

                print(f"\n📊 AGGIORNAMENTO - {datetime.now().strftime('%H:%M:%S')}")
                print("-" * 50)

                active_count = 0

                for trip in trips:
                    device = trip['device']
                    status = self.get_device_status(device.unique_id)

                    if not status:
                        continue

                    if status['is_moving']:
                        active_count += 1
                        progress = float(status['route_progress'].replace('%', ''))
                        print(f"🚛 {device.name[:20]:.<20} {status['route_progress']:>6}")

                    elif device.unique_id not in completed_vehicles:
                        completed_vehicles.add(device.unique_id)
                        print(f"🏁 {device.name} - COMPLETATO!")

                if active_count == 0:
                    break

                print(f"📈 Attivi: {active_count}, Completati: {len(completed_vehicles)}")

        except KeyboardInterrupt:
            print(f"\n⏹️ Simulazione interrotta!")

            stop_all = input("Fermare tutti i veicoli? [s/n]: ").strip().lower()
            if stop_all in ['s', 'si', 'y', 'yes', '']:
                print("🛑 Fermata di tutti i veicoli...")
                stopped = 0
                for trip in trips:
                    if self.stop_device(trip['device'].unique_id):
                        stopped += 1
                print(f"✅ {stopped} veicoli fermati")
            else:
                print("📱 I veicoli continuano in background")

        # Statistiche finali
        end_time = datetime.now()
        total_duration = end_time - start_time

        print(f"\n📊 STATISTICHE FINALI")
        print("="*40)
        print(f"⏱️ Durata simulazione: {str(total_duration).split('.')[0]}")
        print(f"🚛 Veicoli totali: {len(trips)}")
        print(f"🏁 Veicoli completati: {len(completed_vehicles)}")

        # Mostra stato finale di ogni veicolo
        for trip in trips:
            device = trip['device']
            status = self.get_device_status(device.unique_id)
            if status:
                final_progress = status['route_progress']
                print(f"   {device.name}: {final_progress}")

        # Statistiche cache
        cache_stats = self.get_cache_statistics()
        print(f"\n📊 Statistiche API/Cache:")
        print(f"   🌐 API calls: {cache_stats['api_calls']}")
        print(f"   ⚡ Cache hits: {cache_stats['cache_hits']}")
        print(f"   📈 Hit rate: {cache_stats['cache_hit_rate']}")

        return True

    def multi_vehicle_setup(self):
        """
        Setup multi-veicolo completo con configurazione avanzata
        Permette di configurare più veicoli con percorsi diversi
        """
        print("\n🚛 SETUP MULTI-VEICOLO COMPLETO")
        print("="*60)

        try:
            if not self.traccar.test_connection():
                print("❌ Connessione Traccar fallita")
                return False

            print("✅ Connesso a Traccar")
            selected_trips = []

            while len(selected_trips) < 10:  # Limite 10 veicoli
                print(f"\n🚛 CONFIGURAZIONE VEICOLO #{len(selected_trips) + 1}")
                print("-" * 40)

                # Selezione dispositivo esistente o nuovo
                device = self._select_or_create_device_advanced()
                if not device:
                    if len(selected_trips) == 0:
                        print("⚠️ Devi configurare almeno un veicolo")
                        continue
                    else:
                        break

                # Percorso
                origin_input = input("📍 Partenza: ").strip()
                if not origin_input:
                    if len(selected_trips) == 0:
                        print("⚠️ Devi configurare almeno un veicolo")
                        continue
                    else:
                        break

                dest_input = input("🎯 Destinazione: ").strip()
                if not dest_input:
                    if len(selected_trips) == 0:
                        print("⚠️ Devi configurare almeno un veicolo")
                        continue
                    else:
                        break

                origin = Location(0.0, 0.0, origin_input)
                destination = Location(0.0, 0.0, dest_input)

                # Waypoints opzionali
                waypoints = []
                wp_input = input("🔗 Waypoint (opzionale): ").strip()
                if wp_input:
                    waypoints.append(Location(0.0, 0.0, wp_input))

                # Modalità trasporto
                print("\nModalità di trasporto:")
                print("1. 🚗 Auto/Camion (default)")
                print("2. 🚲 Bicicletta")
                print("3. 🚶 A piedi")
                mode_choice = input("Scelta [1-3]: ").strip()

                transport_modes = {'1': 'driving', '2': 'bicycling', '3': 'walking'}
                transport_mode = transport_modes.get(mode_choice, 'driving')

                # Intervallo aggiornamento
                print("\nIntervallo aggiornamento:")
                print("1. Veloce (2s)")
                print("2. Normale (5s)")
                print("3. Lento (10s)")
                interval_choice = input("Scelta [1-3]: ").strip()

                intervals = {'1': 2.0, '2': 5.0, '3': 10.0}
                update_interval = intervals.get(interval_choice, 5.0)

                # Controllo cache
                cached_route = self.google_maps.route_cache.get_cached_route(
                    origin, destination, waypoints, transport_mode
                )

                cache_status = "⚡ CACHE HIT" if cached_route else "🌐 CACHE MISS"

                selected_trips.append({
                    'device': device,
                    'route_config': {
                        'origin': origin,
                        'destination': destination,
                        'waypoints': waypoints,
                        'transport_mode': transport_mode,
                        'name': f"{origin_input} → {dest_input}"
                    },
                    'sim_params': {
                        'update_interval': update_interval,
                        'show_progress': True
                    }
                })

                print(f"✅ Veicolo {len(selected_trips)} configurato: {device.name}")
                print(f"   📍 {origin_input} → {dest_input} ({cache_status})")
                print(f"   ⏱️ Intervallo: {update_interval}s")

                if len(selected_trips) >= 10:
                    print("⚠️ Limite massimo 10 veicoli raggiunto")
                    break

                print(f"\nOpzioni:")
                print(f"1. Aggiungi altro veicolo")
                print(f"2. AVVIA tutti i {len(selected_trips)} veicoli")
                print(f"3. Annulla")

                action = input("Scelta [1/2/3]: ").strip()

                if action == '2':
                    break
                elif action == '3':
                    print("🚫 Setup multi-veicolo annullato")
                    return False

            if not selected_trips:
                print("❌ Nessun veicolo configurato")
                return False

            print(f"\n🚀 Procedo con l'avvio di {len(selected_trips)} veicoli...")
            return self._execute_all_trips(selected_trips)

        except KeyboardInterrupt:
            print("\n⏹️ Setup multi-veicolo interrotto dall'utente")
            return False
        except Exception as e:
            print(f"❌ Errore setup multi-veicolo: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _select_or_create_device_advanced(self) -> Optional[SimulatedDevice]:
        """Selezione avanzata di dispositivi esistenti o creazione nuovo"""
        print("\n📱 SELEZIONE DISPOSITIVO")
        print("-" * 30)

        try:
            # Ottieni tutti i dispositivi esistenti
            existing_devices = self.traccar.devices.get_devices()

            if existing_devices:
                print("Dispositivi esistenti trovati:")
                device_options = {}

                for i, device_data in enumerate(existing_devices[:20], 1):  # Limite primi 20
                    device_name = device_data.get('name', 'Senza nome')
                    device_id = device_data.get('id')
                    unique_id = device_data.get('uniqueId', '')
                    last_update = device_data.get('lastUpdate', 'Mai')

                    # Controlla se già in uso in questa sessione
                    in_use = unique_id in self.devices and self.devices[unique_id].is_moving
                    status_str = " (🔴 IN USO)" if in_use else " (🟢 Libero)"

                    print(f"  {i}. {device_name} (ID: {device_id}){status_str}")
                    device_options[str(i)] = device_data

                print(f"  {len(existing_devices) + 1}. 🆕 Crea nuovo dispositivo")

                choice = input(f"\nScegli dispositivo [1-{len(existing_devices) + 1}]: ").strip()

                if choice in device_options:
                    # Dispositivo esistente selezionato
                    selected_data = device_options[choice]
                    unique_id = selected_data.get('uniqueId', '')

                    # Controlla se già in movimento
                    if unique_id in self.devices and self.devices[unique_id].is_moving:
                        print(f"⚠️ Il dispositivo {selected_data['name']} è già in movimento!")
                        stop_current = input("Vuoi fermarlo per riutilizzarlo? [s/n]: ").lower().strip()
                        if stop_current in ['s', 'si', 'y', 'yes']:
                            self.stop_device(unique_id)
                            print("🛑 Dispositivo fermato e disponibile per riutilizzo")
                        else:
                            print("❌ Dispositivo non disponibile")
                            return None

                    # Crea oggetto SimulatedDevice da dispositivo esistente
                    device = SimulatedDevice(
                        id=selected_data['id'],
                        name=selected_data['name'],
                        unique_id=unique_id,
                        stop_event=threading.Event()
                    )

                    self.devices[unique_id] = device
                    print(f"✅ Selezionato dispositivo esistente: {device.name}")
                    return device

                elif choice == str(len(existing_devices) + 1):
                    # Crea nuovo dispositivo
                    return self._create_new_device_interactive()
                else:
                    print("❌ Scelta non valida")
                    return None
            else:
                print("📱 Nessun dispositivo esistente trovato")
                print("Procedo con la creazione di un nuovo dispositivo...")
                return self._create_new_device_interactive()

        except Exception as e:
            print(f"⚠️ Errore durante la ricerca dispositivi: {e}")
            print("Procedo con la creazione di un nuovo dispositivo...")
            return self._create_new_device_interactive()

    def _create_new_device_interactive(self) -> Optional[SimulatedDevice]:
        """Creazione interattiva di un nuovo dispositivo"""
        print("\n🆕 CREAZIONE NUOVO DISPOSITIVO")
        print("-" * 30)

        # Nome dispositivo
        device_name = input("Nome del nuovo dispositivo: ").strip()
        if not device_name:
            current_time = datetime.now().strftime('%H:%M')
            device_name = f"🚛 Dispositivo {current_time}"
            print(f"Utilizzo nome automatico: {device_name}")

        # Categoria opzionale
        print("\nCategorie disponibili:")
        print("1. 🚛 Camion/Autocarro")
        print("2. 🚐 Furgone")
        print("3. 🚗 Auto")
        print("4. 🚌 Autobus")
        print("5. 🏍️ Motocicletta")
        print("6. 📦 Altro")

        cat_choice = input("Categoria [1-6, default=1]: ").strip()
        categories = {
            '1': 'truck', '2': 'van', '3': 'car',
            '4': 'bus', '5': 'motorcycle', '6': 'other'
        }
        category = categories.get(cat_choice, 'truck')

        try:
            device = self.create_device(
                name=device_name,
                force_new=True
            )

            # Aggiorna categoria se necessario
            if category != 'truck':
                try:
                    # Aggiorna categoria del dispositivo su Traccar
                    update_data = {
                        'id': device.id,
                        'name': device.name,
                        'uniqueId': device.unique_id,
                        'category': category
                    }
                    self.traccar.devices.update_device(device.id, update_data)
                    print(f"📋 Categoria impostata su: {category}")
                except Exception as e:
                    print(f"⚠️ Impossibile aggiornare categoria: {e}")

            print(f"✅ Nuovo dispositivo creato: {device.name} (ID: {device.id})")
            return device

        except Exception as e:
            print(f"❌ Errore creazione dispositivo: {e}")
            return None
        """Pulizia risorse e dispositivi simulati"""
        logger.info("🧹 Pulizia simulatore in corso...")
        self.stop_all_devices()
        self.devices.clear()
        logger.info("✅ Pulizia completata")


# Esempi e test
def example_with_cache():
    """Esempio che mostra l'efficacia della cache"""
    print("\n" + "="*80)
    print("🗄️ ESEMPIO CON SISTEMA DI CACHE INTELLIGENTE")
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
        traccar_protocol_port=57355,
        cache_dir="../demo_route_cache"
    )

    try:
        if not traccar.test_connection():
            print("❌ Impossibile connettersi a Traccar")
            return

        print("✅ Connesso a Traccar")

        device = simulator.get_or_create_truck_device("🚛 Test Cache System")

        origin = Location(41.9028, 12.4964, "Roma")
        destination = Location(45.4642, 9.1900, "Milano")

        print(f"\n📊 PRIMO CALCOLO PERCORSO (dovrebbe usare Google Maps API)")
        print("-" * 60)

        start_time = time.time()
        success1 = simulator.set_route(device.unique_id, origin, destination, transport_mode="driving")
        time1 = time.time() - start_time

        if success1:
            stats1 = simulator.get_cache_statistics()
            print(f"⏱️ Tempo primo calcolo: {time1:.2f} secondi")
            print(f"🌐 API calls: {stats1['api_calls']}")
            print(f"⚡ Cache hits: {stats1['cache_hits']}")
            print(f"📈 Cache hit rate: {stats1['cache_hit_rate']}")

        print(f"\n📊 SECONDO CALCOLO STESSO PERCORSO (dovrebbe usare cache!)")
        print("-" * 60)

        start_time = time.time()
        success2 = simulator.set_route(device.unique_id, origin, destination, transport_mode="driving")
        time2 = time.time() - start_time

        if success2:
            stats2 = simulator.get_cache_statistics()
            print(f"⏱️ Tempo secondo calcolo: {time2:.2f} secondi")
            print(f"🌐 API calls: {stats2['api_calls']}")
            print(f"⚡ Cache hits: {stats2['cache_hits']}")
            print(f"📈 Cache hit rate: {stats2['cache_hit_rate']}")

            speedup = time1 / time2 if time2 > 0 else float('inf')
            print(f"🚀 Speedup con cache: {speedup:.1f}x più veloce!")

            if stats2['cache_hits'] > stats1['cache_hits']:
                print("✅ CACHE FUNZIONA PERFETTAMENTE!")
            else:
                print("⚠️ Cache non utilizzata - verifica configurazione")

    except Exception as e:
        print(f"❌ Errore durante il test cache: {e}")
    finally:
        print("\n🧹 Pulizia risorse...")
        simulator.stop_all_devices()
        print("✅ Test cache completato!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("🚀 TRACCAR DEVICE SIMULATOR - SISTEMA MULTI-VIAGGIO")
    print("="*80)
    print("🗄️ Cache automatico per risparmiare API calls")
    print("🚛 Ogni opzione permette VIAGGI MULTIPLI simultanei!")
    print("⚡ Selezione multipla e avvio coordinato")
    print("📊 Monitoraggio unificato di tutti i veicoli")
    print("="*80)

    print("\n🎯 OPZIONI DISPONIBILI:")
    print("\n--- SETUP E TEST ---")
    print("1. 🗄️ Test sistema cache")
    print("2. 🎯 Setup PERSONALIZZATO (inserisci tue città)")
    print("3. 🚛 Setup MULTI-VEICOLO (configurazione completa)")

    print("\n--- VIAGGI PREDEFINITI ---")
    print("4. 🇮🇹 VIAGGI ITALIA (Roma→Milano, Milano→Napoli, etc.)")
    print("5. 🇪🇺 VIAGGI EUROPA (Roma→Parigi, Milano→Berlino, etc.)")
    print("6. 🌍 VIAGGI INTERCONTINENTALI (NY→LA, Tokyo→Seoul, etc.)")
    print("7. 🚛 VIAGGI COMMERCIALI (Logistica, Express, Freight, etc.)")
    print("8. 🎯 VIAGGI SPECIALI (Arctic, Desert, Silk Road, etc.)")

    print("\n--- RAPIDI ---")
    print("9. ⚡ VIAGGI RAPIDI (8 rotte popolari)")
    print("10. 🚗 Viaggio completo con cache")

    choice = input("\nInserisci il numero (1-10): ").strip()

    # Setup comune per tutte le opzioni
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

    try:
        success = False

        if choice == "1":
            example_with_cache()
            success = True
        elif choice == "2":
            print("🎯 Setup PERSONALIZZATO con supporto multi-viaggio...")
            success = simulator.personal_setup()
        elif choice == "3":
            print("🚛 Setup MULTI-VEICOLO completo...")
            success = simulator.multi_vehicle_setup()
        elif choice == "4":
            print("🇮🇹 Avvio VIAGGI ITALIA...")
            success = simulator.italy_travels()
        elif choice == "5":
            print("🇪🇺 Avvio VIAGGI EUROPA...")
            success = simulator.europe_travels()
        elif choice == "6":
            print("🌍 Avvio VIAGGI INTERCONTINENTALI...")
            success = simulator.intercontinental_travels()
        elif choice == "7":
            print("🚛 Avvio VIAGGI COMMERCIALI...")
            success = simulator.commercial_travels()
        elif choice == "8":
            print("🎯 Avvio VIAGGI SPECIALI...")
            success = simulator.special_travels()
        elif choice == "9":
            print("⚡ VIAGGI RAPIDI con selezione multipla...")
            success = simulator.quick_travels()
        elif choice == "10":
            print("🚗 Viaggio completo...")
            example_with_cache()
            success = True
        else:
            print("❌ Scelta non valida")

        if choice not in ["1", "10"] and choice in ["2", "3", "4", "5", "6", "7", "8", "9"]:
            if success:
                print(f"\n✅ Opzione {choice} completata con successo!")
            else:
                print(f"\n❌ Errore durante opzione {choice}")

    except Exception as e:
        print(f"\n❌ Errore durante l'esecuzione: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n🧹 Pulizia risorse...")
        simulator.stop_all_devices()
        print("✅ Tutte le risorse pulite!")