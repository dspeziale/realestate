# core/services/geocoding_service.py
"""
Servizio di Geocoding con cache SQLite ottimizzata
Implementa reverse geocoding con sistema di cache persistente e intelligente
"""

import sqlite3
import hashlib
import requests
import logging
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from threading import Lock

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
    """Cache SQLite avanzata per risultati di geocoding con statistiche e pulizia automatica"""

    def __init__(self, db_path: str = "geocoding_cache.db", max_age_days: int = 90, precision: int = 5):
        self.db_path = db_path
        self.max_age_days = max_age_days
        self.precision = precision
        self.conn = None
        self._lock = Lock()
        self._init_database()

    def _init_database(self):
        """Inizializza il database SQLite con ottimizzazioni"""
        # Crea directory se non esiste
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # Ottimizzazioni SQLite
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA temp_store = MEMORY")
        self.conn.execute("PRAGMA mmap_size = 268435456")  # 256MB

        cursor = self.conn.cursor()

        # Tabella principale cache
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
                source TEXT DEFAULT 'google',
                confidence_score REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 1,
                is_verified BOOLEAN DEFAULT 0
            )
        ''')

        # Tabella statistiche cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                api_calls INTEGER DEFAULT 0,
                cache_hits INTEGER DEFAULT 0,
                cache_misses INTEGER DEFAULT 0,
                new_addresses INTEGER DEFAULT 0
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

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_city_country 
            ON geocoding_cache(city, country)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_access_count 
            ON geocoding_cache(access_count DESC)
        ''')

        self.conn.commit()
        logger.info(f"📊 Geocoding cache database inizializzato: {self.db_path}")

    def _generate_coord_hash(self, latitude: float, longitude: float) -> str:
        """Genera hash univoco per coordinate con precisione configurabile"""
        lat_rounded = round(latitude, self.precision)
        lon_rounded = round(longitude, self.precision)
        coord_string = f"{lat_rounded},{lon_rounded}"
        return hashlib.md5(coord_string.encode()).hexdigest()

    def get_cached_address(self, latitude: float, longitude: float) -> Optional[Address]:
        """Recupera indirizzo dalla cache con aggiornamento statistiche"""
        with self._lock:
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

                # Aggiorna statistiche giornaliere
                self._update_daily_stats('cache_hits')
                self.conn.commit()

                logger.debug(f"✅ Cache hit per ({latitude:.5f}, {longitude:.5f}) - {row['city']}")

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

            # Cache miss
            self._update_daily_stats('cache_misses')
            self.conn.commit()
            logger.debug(f"❌ Cache miss per ({latitude:.5f}, {longitude:.5f})")
            return None

    def store_address(self, latitude: float, longitude: float, address: Address,
                      raw_response: Dict[str, Any] = None, source: str = 'google',
                      confidence_score: float = 1.0):
        """Memorizza indirizzo nella cache con metadati avanzati"""
        with self._lock:
            coord_hash = self._generate_coord_hash(latitude, longitude)
            cursor = self.conn.cursor()

            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO geocoding_cache 
                    (coord_hash, latitude, longitude, formatted_address, street, city, 
                     state, country, postal_code, raw_response, source, confidence_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    json.dumps(raw_response) if raw_response else None,
                    source,
                    confidence_score
                ))

                # Aggiorna statistiche
                self._update_daily_stats('new_addresses')
                self.conn.commit()

                logger.info(f"💾 Indirizzo salvato in cache: {address.city or address.formatted_address}")

            except sqlite3.IntegrityError as e:
                logger.warning(f"⚠️ Errore salvataggio cache: {e}")

    def _update_daily_stats(self, stat_type: str):
        """Aggiorna statistiche giornaliere"""
        today = datetime.now().strftime('%Y-%m-%d')
        cursor = self.conn.cursor()

        cursor.execute('''
            INSERT OR IGNORE INTO cache_stats (date) VALUES (?)
        ''', (today,))

        cursor.execute(f'''
            UPDATE cache_stats 
            SET {stat_type} = {stat_type} + 1 
            WHERE date = ?
        ''', (today,))

    def cleanup_old_entries(self) -> int:
        """Rimuove entry scadute e poco utilizzate dalla cache"""
        with self._lock:
            cursor = self.conn.cursor()

            # Rimuove entry scadute
            cursor.execute('''
                DELETE FROM geocoding_cache 
                WHERE datetime(created_at) < datetime('now', '-' || ? || ' days')
            ''', (self.max_age_days,))
            expired_count = cursor.rowcount

            # Rimuove entry con basso utilizzo (meno di 2 accessi in 30 giorni)
            cursor.execute('''
                DELETE FROM geocoding_cache 
                WHERE access_count < 2 
                AND datetime(last_accessed) < datetime('now', '-30 days')
            ''')
            unused_count = cursor.rowcount

            # Pulisci statistiche vecchie (oltre 1 anno)
            cursor.execute('''
                DELETE FROM cache_stats 
                WHERE date < date('now', '-1 year')
            ''')

            self.conn.commit()
            total_deleted = expired_count + unused_count

            if total_deleted > 0:
                logger.info(f"🗑️ Cache cleanup: {expired_count} scaduti, {unused_count} inutilizzati")

            return total_deleted

    def get_statistics(self) -> Dict[str, Any]:
        """Ottieni statistiche dettagliate sulla cache"""
        with self._lock:
            cursor = self.conn.cursor()

            # Statistiche generali cache
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_addresses,
                    AVG(access_count) as avg_access_count,
                    MAX(access_count) as max_access_count,
                    COUNT(CASE WHEN access_count > 5 THEN 1 END) as popular_addresses
                FROM geocoding_cache
            ''')
            cache_stats = dict(cursor.fetchone())

            # Top paesi
            cursor.execute('''
                SELECT country, COUNT(*) as count 
                FROM geocoding_cache 
                WHERE country IS NOT NULL
                GROUP BY country 
                ORDER BY count DESC 
                LIMIT 10
            ''')
            top_countries = [dict(row) for row in cursor.fetchall()]

            # Top città
            cursor.execute('''
                SELECT city, country, COUNT(*) as count 
                FROM geocoding_cache 
                WHERE city IS NOT NULL
                GROUP BY city, country 
                ORDER BY count DESC 
                LIMIT 10
            ''')
            top_cities = [dict(row) for row in cursor.fetchall()]

            # Statistiche giornaliere recenti
            cursor.execute('''
                SELECT * FROM cache_stats 
                ORDER BY date DESC 
                LIMIT 30
            ''')
            daily_stats = [dict(row) for row in cursor.fetchall()]

            # Calcola hit rate
            total_hits = sum(stat.get('cache_hits', 0) for stat in daily_stats)
            total_misses = sum(stat.get('cache_misses', 0) for stat in daily_stats)
            hit_rate = (total_hits / (total_hits + total_misses)) * 100 if (total_hits + total_misses) > 0 else 0

            # Dimensione file database
            db_size_bytes = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0

            return {
                'cache_stats': {
                    **cache_stats,
                    'db_size_kb': db_size_bytes / 1024,
                    'db_size_mb': db_size_bytes / (1024 * 1024),
                    'hit_rate_percent': round(hit_rate, 2)
                },
                'geographic_distribution': {
                    'top_countries': top_countries,
                    'top_cities': top_cities
                },
                'daily_stats': daily_stats[:7],  # Ultimi 7 giorni
                'performance_metrics': {
                    'total_hits_30d': total_hits,
                    'total_misses_30d': total_misses,
                    'avg_daily_usage': (total_hits + total_misses) / max(len(daily_stats), 1)
                }
            }

    def get_addresses_by_region(self, country: str = None, state: str = None,
                                city: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Ricerca indirizzi per regione geografica"""
        with self._lock:
            cursor = self.conn.cursor()

            conditions = []
            params = []

            if country:
                conditions.append("country LIKE ?")
                params.append(f"%{country}%")

            if state:
                conditions.append("state LIKE ?")
                params.append(f"%{state}%")

            if city:
                conditions.append("city LIKE ?")
                params.append(f"%{city}%")

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            params.append(limit)

            cursor.execute(f'''
                SELECT formatted_address, city, state, country, access_count, last_accessed
                FROM geocoding_cache 
                {where_clause}
                ORDER BY access_count DESC, last_accessed DESC
                LIMIT ?
            ''', params)

            return [dict(row) for row in cursor.fetchall()]

    def optimize_database(self):
        """Ottimizza il database SQLite"""
        with self._lock:
            cursor = self.conn.cursor()

            logger.info("🔧 Ottimizzazione database cache in corso...")

            # Analizza e ottimizza
            cursor.execute("ANALYZE")
            cursor.execute("VACUUM")
            cursor.execute("PRAGMA optimize")

            self.conn.commit()
            logger.info("✅ Ottimizzazione database completata")

    def close(self):
        """Chiudi connessione database"""
        if self.conn:
            self.conn.close()
            logger.info("📊 Geocoding cache database chiuso")


class GeocodingService:
    """Servizio di geocoding con cache SQLite intelligente e multiple API"""

    def __init__(self, api_key: str, cache_db_path: str = "geocoding_cache.db",
                 max_age_days: int = 90, precision: int = 5):
        self.api_key = api_key
        self.cache = GeocodingCache(cache_db_path, max_age_days, precision)
        self.api_calls_count = 0
        self.cache_hits_count = 0
        self.api_errors_count = 0
        self.session = requests.Session()

        # Configura session con timeout e retry
        self.session.headers.update({
            'User-Agent': 'Fleet-Manager-Geocoding/1.0'
        })

    def get_address_from_coordinates(self, latitude: float, longitude: float,
                                     force_refresh: bool = False) -> Optional[Address]:
        """
        Ottieni indirizzo da coordinate con cache intelligente
        """
        # Verifica cache (se non force refresh)
        if not force_refresh:
            cached_address = self.cache.get_cached_address(latitude, longitude)
            if cached_address:
                self.cache_hits_count += 1
                return cached_address

        # Chiamata API Google Maps
        try:
            address = self._geocode_google_maps(latitude, longitude)
            if address:
                # Salva in cache con confidence score
                confidence = self._calculate_confidence_score(address)
                self.cache.store_address(
                    latitude, longitude, address,
                    source='google_maps',
                    confidence_score=confidence
                )
                self.api_calls_count += 1
                return address

        except Exception as e:
            self.api_errors_count += 1
            logger.error(f"❌ Errore geocoding per ({latitude:.5f}, {longitude:.5f}): {e}")

            # Fallback su cache anche se scaduta
            return self.cache.get_cached_address(latitude, longitude)

        return None

    def _geocode_google_maps(self, latitude: float, longitude: float) -> Optional[Address]:
        """Geocoding tramite Google Maps API"""
        url = "https://maps.googleapis.com/maps/api/geocode/json"

        params = {
            'latlng': f"{latitude},{longitude}",
            'key': self.api_key,
            'language': 'it',
            'result_type': 'street_address|route|neighborhood|locality'
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            if data['status'] == 'OK' and data.get('results'):
                result = data['results'][0]

                # Parsing componenti indirizzo
                components = {comp['types'][0]: comp['long_name']
                              for comp in result.get('address_components', [])}

                return Address(
                    formatted_address=result.get('formatted_address', ''),
                    street=self._get_street_from_components(components),
                    city=components.get('locality') or components.get('administrative_area_level_3'),
                    state=components.get('administrative_area_level_1'),
                    country=components.get('country'),
                    postal_code=components.get('postal_code'),
                    latitude=latitude,
                    longitude=longitude
                )

            elif data['status'] == 'OVER_QUERY_LIMIT':
                logger.warning("⚠️ Google Maps API: Quota exceeded")
            elif data['status'] == 'REQUEST_DENIED':
                logger.error("❌ Google Maps API: Request denied - check API key")

        except requests.exceptions.Timeout:
            logger.warning("⏰ Google Maps API timeout")
        except requests.exceptions.RequestException as e:
            logger.error(f"🌐 Google Maps API network error: {e}")
        except Exception as e:
            logger.error(f"❌ Google Maps API unexpected error: {e}")

        return None

    def _get_street_from_components(self, components: Dict[str, str]) -> Optional[str]:
        """Estrae via/strada dai componenti indirizzo"""
        street_parts = []

        if 'street_number' in components:
            street_parts.append(components['street_number'])
        if 'route' in components:
            street_parts.append(components['route'])
        elif 'street_address' in components:
            street_parts.append(components['street_address'])

        return ' '.join(street_parts) if street_parts else None

    def _calculate_confidence_score(self, address: Address) -> float:
        """Calcola punteggio di confidenza per l'indirizzo"""
        score = 1.0

        if not address.street:
            score -= 0.2
        if not address.city:
            score -= 0.3
        if not address.country:
            score -= 0.1
        if len(address.formatted_address) < 20:
            score -= 0.1

        return max(0.0, score)

    def batch_geocode(self, coordinates_list: List[Tuple[float, float]]) -> Dict[Tuple[float, float], Address]:
        """Geocoding batch per multiple coordinate"""
        results = {}

        logger.info(f"🔄 Avvio batch geocoding per {len(coordinates_list)} coordinate")

        for lat, lon in coordinates_list:
            address = self.get_address_from_coordinates(lat, lon)
            if address:
                results[(lat, lon)] = address

        logger.info(f"✅ Batch geocoding completato: {len(results)}/{len(coordinates_list)} successi")
        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Statistiche complete del servizio"""
        cache_stats = self.cache.get_statistics()

        return {
            **cache_stats,
            'service_stats': {
                'api_calls_session': self.api_calls_count,
                'cache_hits_session': self.cache_hits_count,
                'api_errors_session': self.api_errors_count,
                'session_hit_rate': (self.cache_hits_count / max(self.cache_hits_count + self.api_calls_count, 1)) * 100
            }
        }

    def cleanup_cache(self) -> int:
        """Pulizia cache con statistiche"""
        return self.cache.cleanup_old_entries()

    def optimize_cache(self):
        """Ottimizza cache database"""
        self.cache.optimize_database()

    def search_addresses(self, query: str, country: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Ricerca indirizzi nella cache per query testuale"""
        return self.cache.get_addresses_by_region(country=country, limit=limit)

    def close(self):
        """Chiude tutte le connessioni"""
        self.session.close()
        self.cache.close()
        logger.info("🔌 Geocoding service chiuso")