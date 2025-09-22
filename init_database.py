# init_database.py
"""
Inizializzazione completa del database per Fleet Manager
Supporta SQLite con ottimizzazioni WAL e cache geocoding avanzata
"""

import sqlite3
import json
import os
import logging
from datetime import datetime

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DatabaseInit')


def create_directories():
    """Crea le directory necessarie per l'applicazione"""
    directories = [
        'data',
        'logs',
        'backups',
        'data/route_cache'
    ]

    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            logger.info(f"📁 Directory creata: {directory}")


def init_fleet_database(db_path):
    """Inizializza database principale fleet manager con ottimizzazioni"""
    logger.info(f"🚗 Inizializzazione database fleet: {db_path}")

    conn = sqlite3.connect(db_path)

    # Abilita ottimizzazioni SQLite
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA mmap_size = 268435456")  # 256MB
    conn.execute("PRAGMA cache_size = -64000")  # 64MB cache

    cursor = conn.cursor()

    # Tabella vehicles (enhanced)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            traccar_id INTEGER UNIQUE,
            name TEXT NOT NULL,
            plate TEXT,
            brand TEXT,
            model TEXT,
            year INTEGER,
            fuel_type TEXT DEFAULT 'gasoline',
            fuel_capacity REAL,
            insurance_expiry DATE,
            maintenance_km INTEGER DEFAULT 0,
            next_maintenance_km INTEGER,
            driver_name TEXT,
            driver_phone TEXT,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tabella alerts (enhanced)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            traccar_device_id INTEGER,
            alert_type TEXT NOT NULL,
            severity TEXT DEFAULT 'medium',
            title TEXT NOT NULL,
            message TEXT,
            location TEXT,
            latitude REAL,
            longitude REAL,
            speed REAL,
            fuel_level REAL,
            is_read BOOLEAN DEFAULT 0,
            is_resolved BOOLEAN DEFAULT 0,
            resolved_by TEXT,
            resolved_at TIMESTAMP,
            metadata TEXT,  -- JSON per dati aggiuntivi
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
        )
    ''')

    # Tabella trips (enhanced)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            traccar_device_id INTEGER,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            start_latitude REAL,
            start_longitude REAL,
            end_latitude REAL,
            end_longitude REAL,
            start_address TEXT,
            end_address TEXT,
            distance REAL DEFAULT 0,
            duration INTEGER DEFAULT 0,
            max_speed REAL DEFAULT 0,
            avg_speed REAL DEFAULT 0,
            fuel_consumed REAL,
            driver_name TEXT,
            trip_type TEXT DEFAULT 'business',
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
        )
    ''')

    # Tabella maintenance (enhanced)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS maintenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            maintenance_type TEXT NOT NULL,
            category TEXT DEFAULT 'routine',
            description TEXT,
            scheduled_date DATE,
            completed_date DATE,
            scheduled_km INTEGER,
            completed_km INTEGER,
            cost REAL DEFAULT 0,
            supplier TEXT,
            invoice_number TEXT,
            warranty_months INTEGER DEFAULT 0,
            next_maintenance_km INTEGER,
            status TEXT DEFAULT 'scheduled',
            priority TEXT DEFAULT 'medium',
            notes TEXT,
            attachments TEXT,  -- JSON per file allegati
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
        )
    ''')

    # Tabella fuel_logs (nuova)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fuel_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            date DATE NOT NULL,
            km_reading INTEGER,
            liters REAL NOT NULL,
            cost_per_liter REAL,
            total_cost REAL,
            fuel_type TEXT DEFAULT 'gasoline',
            station_name TEXT,
            full_tank BOOLEAN DEFAULT 1,
            trip_km REAL,
            consumption REAL,  -- km/litro o l/100km
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
        )
    ''')

    # Tabella geofences (nuova)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS geofences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            type TEXT DEFAULT 'circle',  -- circle, polygon
            center_latitude REAL,
            center_longitude REAL,
            radius REAL,  -- per cerchi in metri
            polygon_points TEXT,  -- JSON per poligoni
            color TEXT DEFAULT '#FF0000',
            is_active BOOLEAN DEFAULT 1,
            alert_on_enter BOOLEAN DEFAULT 0,
            alert_on_exit BOOLEAN DEFAULT 0,
            allowed_vehicles TEXT,  -- JSON array di vehicle_ids
            schedule_json TEXT,  -- JSON per orari attivazione
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tabella geofence_events (nuova)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS geofence_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            geofence_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,  -- enter, exit
            timestamp TIMESTAMP NOT NULL,
            latitude REAL,
            longitude REAL,
            speed REAL,
            address TEXT,
            duration_minutes INTEGER,  -- per exit events
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id),
            FOREIGN KEY (geofence_id) REFERENCES geofences(id)
        )
    ''')

    # Indici per performance ottimizzate
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_vehicles_traccar ON vehicles(traccar_id)",
        "CREATE INDEX IF NOT EXISTS idx_vehicles_status ON vehicles(status)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_vehicle ON alerts(vehicle_id)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type)",
        "CREATE INDEX IF NOT EXISTS idx_alerts_unread ON alerts(is_read)",
        "CREATE INDEX IF NOT EXISTS idx_trips_vehicle ON trips(vehicle_id)",
        "CREATE INDEX IF NOT EXISTS idx_trips_start ON trips(start_time)",
        "CREATE INDEX IF NOT EXISTS idx_trips_status ON trips(status)",
        "CREATE INDEX IF NOT EXISTS idx_maintenance_vehicle ON maintenance(vehicle_id)",
        "CREATE INDEX IF NOT EXISTS idx_maintenance_status ON maintenance(status)",
        "CREATE INDEX IF NOT EXISTS idx_maintenance_scheduled ON maintenance(scheduled_date)",
        "CREATE INDEX IF NOT EXISTS idx_fuel_vehicle ON fuel_logs(vehicle_id)",
        "CREATE INDEX IF NOT EXISTS idx_fuel_date ON fuel_logs(date)",
        "CREATE INDEX IF NOT EXISTS idx_geofence_active ON geofences(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_geofence_events_vehicle ON geofence_events(vehicle_id)",
        "CREATE INDEX IF NOT EXISTS idx_geofence_events_timestamp ON geofence_events(timestamp)"
    ]

    for index_sql in indices:
        cursor.execute(index_sql)

    # Trigger per updated_at automatico
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS update_vehicles_timestamp 
        AFTER UPDATE ON vehicles
        BEGIN
            UPDATE vehicles SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    ''')

    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS update_maintenance_timestamp 
        AFTER UPDATE ON maintenance
        BEGIN
            UPDATE maintenance SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    ''')

    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS update_geofences_timestamp 
        AFTER UPDATE ON geofences
        BEGIN
            UPDATE geofences SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    ''')

    conn.commit()
    conn.close()

    logger.info("✅ Database fleet inizializzato con successo")


def init_geocoding_database(db_path):
    """Inizializza database geocoding_cache.db ottimizzato"""
    logger.info(f"🌍 Inizializzazione database geocoding: {db_path}")

    conn = sqlite3.connect(db_path)

    # Ottimizzazioni SQLite specifiche per cache
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA mmap_size = 268435456")  # 256MB
    conn.execute("PRAGMA cache_size = -32000")  # 32MB cache
    conn.execute("PRAGMA auto_vacuum = INCREMENTAL")

    cursor = conn.cursor()

    # Tabella principale cache geocoding
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
            new_addresses INTEGER DEFAULT 0,
            cleanup_runs INTEGER DEFAULT 0,
            deleted_entries INTEGER DEFAULT 0
        )
    ''')

    # Tabella performance metrics
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS performance_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            operation_type TEXT NOT NULL,
            duration_ms REAL NOT NULL,
            coordinates_processed INTEGER DEFAULT 1,
            success BOOLEAN DEFAULT 1,
            error_message TEXT
        )
    ''')

    # Indici ottimizzati per cache
    indices_geocoding = [
        "CREATE INDEX IF NOT EXISTS idx_coord_hash ON geocoding_cache(coord_hash)",
        "CREATE INDEX IF NOT EXISTS idx_created_at ON geocoding_cache(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_last_accessed ON geocoding_cache(last_accessed)",
        "CREATE INDEX IF NOT EXISTS idx_access_count ON geocoding_cache(access_count DESC)",
        "CREATE INDEX IF NOT EXISTS idx_city_country ON geocoding_cache(city, country)",
        "CREATE INDEX IF NOT EXISTS idx_country ON geocoding_cache(country)",
        "CREATE INDEX IF NOT EXISTS idx_confidence ON geocoding_cache(confidence_score)",
        "CREATE INDEX IF NOT EXISTS idx_source ON geocoding_cache(source)",
        "CREATE INDEX IF NOT EXISTS idx_stats_date ON cache_stats(date)",
        "CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON performance_metrics(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_metrics_operation ON performance_metrics(operation_type)"
    ]

    for index_sql in indices_geocoding:
        cursor.execute(index_sql)

    # View per statistiche aggregate
    cursor.execute('''
        CREATE VIEW IF NOT EXISTS v_cache_summary AS
        SELECT 
            COUNT(*) as total_addresses,
            COUNT(DISTINCT country) as countries_count,
            COUNT(DISTINCT city) as cities_count,
            AVG(access_count) as avg_access_count,
            MAX(access_count) as max_access_count,
            SUM(access_count) as total_accesses,
            AVG(confidence_score) as avg_confidence,
            COUNT(CASE WHEN access_count > 5 THEN 1 END) as popular_addresses,
            MIN(created_at) as oldest_entry,
            MAX(last_accessed) as last_access
        FROM geocoding_cache
    ''')

    conn.commit()
    conn.close()

    logger.info("✅ Database geocoding inizializzato con successo")


def create_config_if_missing():
    """Crea config.json predefinita se mancante"""
    if os.path.exists('config.json'):
        return

    logger.info("📋 Creazione config.json predefinita")

    default_config = {
        "traccar": {
            "host": "localhost",
            "port": 8082,
            "username": "admin",
            "password": "admin",
            "protocol": "http",
            "debug": False,
            "timeout": 30,
            "max_retries": 3
        },
        "google_maps": {
            "api_key": "",
            "cache_max_age_days": 90,
            "default_language": "it",
            "region": "IT",
            "result_types": ["street_address", "route", "neighborhood", "locality"]
        },
        "geocoding": {
            "cache_db_path": "data/geocoding_cache.db",
            "max_age_days": 90,
            "precision": 5,
            "batch_limit": 100,
            "enable_auto_cleanup": True,
            "cleanup_interval_hours": 24,
            "confidence_threshold": 0.7,
            "enable_statistics": True
        },
        "database": {
            "type": "sqlite",
            "path": "data/fleet.db",
            "enable_wal": True,
            "timeout": 30,
            "pool_size": 10
        },
        "cache": {
            "route_cache_dir": "data/route_cache",
            "max_cache_size": 1000,
            "cleanup_interval_hours": 24,
            "enable_compression": True
        },
        "logging": {
            "level": "INFO",
            "file": "logs/fleet_manager.log",
            "max_size_mb": 10,
            "backup_count": 5,
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        },
        "performance": {
            "enable_profiling": False,
            "slow_query_threshold": 1.0,
            "max_concurrent_geocoding": 10,
            "cache_warmup_enabled": True
        },
        "security": {
            "enable_rate_limiting": True,
            "rate_limit_per_minute": 60,
            "enable_cors": True,
            "allowed_origins": ["*"],
            "session_timeout_minutes": 120
        },
        "app": {
            "name": "Fleet Manager Pro",
            "company": "DS Consulting",
            "version": "2.0.0",
            "items_per_page": 20,
            "timezone": "Europe/Rome",
            "default_language": "it"
        },
        "features": {
            "geocoding_enabled": True,
            "alerts_enabled": True,
            "reports_enabled": True,
            "maintenance_enabled": True,
            "real_time_tracking": True,
            "geofencing_enabled": True
        },
        "backup": {
            "enabled": True,
            "interval_hours": 6,
            "retention_days": 30,
            "backup_path": "backups/",
            "compress_backups": True
        }
    }

    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(default_config, f, indent=2, ensure_ascii=False)

    logger.info("✅ Config.json predefinita creata")


def verify_databases():
    """Verifica integrità dei database"""
    logger.info("🔍 Verifica integrità database...")

    try:
        # Verifica database fleet
        with open('config.json', 'r') as f:
            config = json.load(f)

        fleet_db = config['database']['path']
        if os.path.exists(fleet_db):
            conn = sqlite3.connect(fleet_db)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            conn.close()

            if result[0] == 'ok':
                logger.info("✅ Database fleet integro")
            else:
                logger.warning(f"⚠️ Problema integrità database fleet: {result[0]}")

        # Verifica database geocoding
        geo_db = config['geocoding']['cache_db_path']
        if os.path.exists(geo_db):
            conn = sqlite3.connect(geo_db)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            conn.close()

            if result[0] == 'ok':
                logger.info("✅ Database geocoding integro")
            else:
                logger.warning(f"⚠️ Problema integrità database geocoding: {result[0]}")

    except Exception as e:
        logger.error(f"❌ Errore verifica database: {e}")


def print_summary():
    """Stampa riepilogo inizializzazione"""
    logger.info("\n" + "=" * 60)
    logger.info("✅ INIZIALIZZAZIONE COMPLETATA")
    logger.info("=" * 60)

    try:
        with open('config.json', 'r') as f:
            config = json.load(f)

        logger.info(f"📊 Database fleet: {config['database']['path']}")
        logger.info(f"🌍 Database geocoding: {config['geocoding']['cache_db_path']}")
        logger.info(f"📁 Directory cache: {config['cache']['route_cache_dir']}")
        logger.info(f"📝 Logs directory: logs/")
        logger.info(f"💾 Backup directory: {config['backup']['backup_path']}")

        logger.info("\n🚀 PROSSIMI PASSI:")
        logger.info("1. Configura API key Google Maps in config.json")
        logger.info("2. Verifica impostazioni Traccar in config.json")
        logger.info("3. Avvia l'applicazione: python app.py")
        logger.info("")

    except Exception as e:
        logger.error(f"Errore stampa riepilogo: {e}")


def main():
    """Inizializzazione completa del sistema"""
    print("🚀 Fleet Manager Pro - Database Initialization v2.0")
    print("=" * 60)
    print()

    # Crea directory
    create_directories()

    # Crea config se mancante
    create_config_if_missing()

    # Carica config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except Exception as e:
        logger.error(f"❌ Errore caricamento config: {e}")
        return

    # Inizializza database fleet
    fleet_db = config['database']['path']
    init_fleet_database(fleet_db)

    # Inizializza database geocoding
    geo_db = config['geocoding']['cache_db_path']
    init_geocoding_database(geo_db)

    # Verifica database
    verify_databases()

    # Riepilogo finale
    print_summary()


if __name__ == "__main__":
    main()