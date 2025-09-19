# core/services/geocoding_service.py
"""
Geocoding Service - Sistema di reverse geocoding con cache SQLite
Ottiene indirizzi da coordinate con sistema di cache persistente
"""

import sqlite3
import hashlib
import requests
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import json
import os

logger = logging.getLogger('GeocodingService')


@dataclass
class Address:
    """Rappresenta un indirizzo geocodificato"""
    formatted_address: str
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: float = 0.0
    longitude: float = 0.0


class GeocodingCache:
    """Cache SQLite per risultati di geocoding"""

    def __init__(self, db_path: str = "geocoding_cache.db", max_age_days: int = 90):
        self.db_path = db_path
        self.max_age_days = max_age_days
        self.conn = None
        self._init_database()

    def _init_database(self):
        """Inizializza il database SQLite"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS geocoding_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coord_hash TEXT UNIQUE NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                formatted_address TEXT NOT NULL,
                street TEXT,
                city TEXT,
                state TEXT,
                country TEXT,
                postal_code TEXT,
                raw_response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 1
            )
        ''')

        # Indici per performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_coord_hash 
            ON geocoding_cache(coord_hash)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_created_at 
            ON geocoding_cache(created_at)
        ''')

        self.conn.commit()
        logger.info(f"📊 Database geocoding cache inizializzato: {self.db_path}")

    def _generate_coord_hash(self, latitude: float, longitude: float, precision: int = 5) -> str:
        """Genera hash univoco per coordinate (con precisione configurabile)"""
        lat_rounded = round(latitude, precision)
        lon_rounded = round(longitude, precision)
        coord_string = f"{lat_rounded},{lon_rounded}"
        return hashlib.md5(coord_string.encode()).hexdigest()

    def get_cached_address(self, latitude: float, longitude: float) -> Optional[Address]:
        """Recupera indirizzo dalla cache"""
        coord_hash = self._generate_coord_hash(latitude, longitude)

        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM geocoding_cache 
            WHERE coord_hash = ? 
            AND datetime(created_at) > datetime('now', '-' || ? || ' days')
        ''', (coord_hash, self.max_age_days))

        row = cursor.fetchone()

        if row:
            # Aggiorna statistiche accesso
            cursor.execute('''
                UPDATE geocoding_cache 
                SET last_accessed = CURRENT_TIMESTAMP,
                    access_count = access_count + 1
                WHERE id = ?
            ''', (row['id'],))
            self.conn.commit()

            logger.info(f"✅ Cache hit per ({latitude:.5f}, {longitude:.5f})")

            return Address(
                formatted_address=row['formatted_address'],
                street=row['street'],
                city=row['city'],
                state=row['state'],
                country=row['country'],
                postal_code=row['postal_code'],
                latitude=row['latitude'],
                longitude=row['longitude']
            )

        logger.debug(f"❌ Cache miss per ({latitude:.5f}, {longitude:.5f})")
        return None

    def store_address(self, latitude: float, longitude: float, address: Address,
                      raw_response: Dict[str, Any] = None):
        """Memorizza indirizzo nella cache"""
        coord_hash = self._generate_coord_hash(latitude, longitude)

        cursor = self.conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO geocoding_cache 
                (coord_hash, latitude, longitude, formatted_address, street, city, 
                 state, country, postal_code, raw_response)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                coord_hash,
                latitude,
                longitude,
                address.formatted_address,
                address.street,
                address.city,
                address.state,
                address.country,
                address.postal_code,
                json.dumps(raw_response) if raw_response else None
            ))

            self.conn.commit()
            logger.info(f"💾 Indirizzo salvato in cache: {address.city or address.formatted_address}")

        except sqlite3.IntegrityError as e:
            logger.warning(f"⚠️ Errore salvataggio cache: {e}")

    def cleanup_old_entries(self):
        """Rimuove entry scadute dalla cache"""
        cursor = self.conn.cursor()

        cursor.execute('''
            DELETE FROM geocoding_cache 
            WHERE datetime(created_at) < datetime('now', '-' || ? || ' days')
        ''', (self.max_age_days,))

        deleted_count = cursor.rowcount
        self.conn.commit()

        if deleted_count > 0:
            logger.info(f"🗑️ Rimossi {deleted_count} indirizzi scaduti dalla cache")

        return deleted_count

    def get_statistics(self) -> Dict[str, Any]:
        """Ottieni statistiche sulla cache"""
        cursor = self.conn.cursor()

        cursor.execute('SELECT COUNT(*) as total FROM geocoding_cache')
        total = cursor.fetchone()['total']

        cursor.execute('''
            SELECT SUM(access_count) as total_accesses 
            FROM geocoding_cache
        ''')
        total_accesses = cursor.fetchone()['total_accesses'] or 0

        cursor.execute('''
            SELECT country, COUNT(*) as count 
            FROM geocoding_cache 
            GROUP BY country 
            ORDER BY count DESC 
            LIMIT 5
        ''')
        top_countries = [dict(row) for row in cursor.fetchall()]

        return {
            'total_addresses': total,
            'total_accesses': total_accesses,
            'top_countries': top_countries,
            'db_size_kb': os.path.getsize(self.db_path) / 1024 if os.path.exists(self.db_path) else 0
        }

    def close(self):
        """Chiudi connessione database"""
        if self.conn:
            self.conn.close()


class GeocodingService:
    """Servizio di geocoding con cache SQLite"""

    def __init__(self, api_key: str, cache_db_path: str = "geocoding_cache.db"):
        self.api_key = api_key
        self.cache = GeocodingCache(cache_db_path)
        self.api_calls_count = 0
        self.cache_hits_count = 0

    def get_address_from_coords(self, latitude: float, longitude: float,
                                language: str = 'it') -> Optional[Address]:
        """
        Ottiene indirizzo da coordinate (reverse geocoding)

        Args:
            latitude: Latitudine
            longitude: Longitudine
            language: Lingua per risultati (default: italiano)

        Returns:
            Address object o None se non trovato
        """
        # Verifica cache
        cached_address = self.cache.get_cached_address(latitude, longitude)

        if cached_address:
            self.cache_hits_count += 1
            return cached_address

        # Chiamata API Google
        self.api_calls_count += 1

        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            'latlng': f"{latitude},{longitude}",
            'key': self.api_key,
            'language': language
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data['status'] == 'OK' and data['results']:
                result = data['results'][0]

                # Estrai componenti indirizzo
                address_components = {}
                for component in result.get('address_components', []):
                    types = component['types']
                    if 'street_number' in types or 'route' in types:
                        address_components['street'] = component['long_name']
                    elif 'locality' in types:
                        address_components['city'] = component['long_name']
                    elif 'administrative_area_level_1' in types:
                        address_components['state'] = component['long_name']
                    elif 'country' in types:
                        address_components['country'] = component['long_name']
                    elif 'postal_code' in types:
                        address_components['postal_code'] = component['long_name']

                address = Address(
                    formatted_address=result['formatted_address'],
                    street=address_components.get('street'),
                    city=address_components.get('city'),
                    state=address_components.get('state'),
                    country=address_components.get('country'),
                    postal_code=address_components.get('postal_code'),
                    latitude=latitude,
                    longitude=longitude
                )

                # Salva in cache
                self.cache.store_address(latitude, longitude, address, data)

                logger.info(f"🌍 Geocoding API: {address.formatted_address}")
                return address

            else:
                logger.warning(f"⚠️ Geocoding fallito: {data.get('status')}")
                return None

        except requests.RequestException as e:
            logger.error(f"❌ Errore API geocoding: {e}")
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """Statistiche complete del servizio"""
        cache_stats = self.cache.get_statistics()

        hit_rate = 0
        total_requests = self.api_calls_count + self.cache_hits_count
        if total_requests > 0:
            hit_rate = (self.cache_hits_count / total_requests) * 100

        return {
            'api_calls': self.api_calls_count,
            'cache_hits': self.cache_hits_count,
            'hit_rate': round(hit_rate, 2),
            'cache_stats': cache_stats
        }

    def cleanup_cache(self):
        """Pulisci cache scaduta"""
        return self.cache.cleanup_old_entries()

    def close(self):
        """Chiudi servizio"""
        self.cache.close()


# Utility per testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Esempio di utilizzo
    service = GeocodingService("AIzaSyAZLNmrmri-HUzex5s4FaJZPk8xVeAyFVk")

    # Test coordinate Roma
    coords = [
        (41.9028, 12.4964),  # Roma
        (45.4642, 9.1900),  # Milano
        (40.8518, 14.2681),  # Napoli
    ]

    print("\n🧪 TEST GEOCODING SERVICE")
    print("=" * 50)

    for lat, lon in coords:
        print(f"\n📍 Coordinate: {lat}, {lon}")

        # Prima chiamata (API)
        address = service.get_address_from_coords(lat, lon)
        if address:
            print(f"   Indirizzo: {address.formatted_address}")
            print(f"   Città: {address.city}")
            print(f"   Paese: {address.country}")

        # Seconda chiamata (cache)
        address = service.get_address_from_coords(lat, lon)
        print(f"   Cache utilizzata: {'✅' if address else '❌'}")

    # Statistiche
    stats = service.get_statistics()
    print(f"\n📊 STATISTICHE")
    print(f"   API calls: {stats['api_calls']}")
    print(f"   Cache hits: {stats['cache_hits']}")
    print(f"   Hit rate: {stats['hit_rate']}%")
    print(f"   Indirizzi in cache: {stats['cache_stats']['total_addresses']}")

    service.close()