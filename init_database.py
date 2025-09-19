# init_database.py
"""
Database Initialization Script
Crea tutte le directory e database necessari per l'applicazione
"""

import os
import json
import sqlite3
from datetime import datetime


def create_directories():
    """Crea tutte le directory necessarie"""
    directories = [
        'data',
        'data/route_cache',
        'templates',
        'templates/errors',
        'templates/dashboard',
        'templates/vehicles',
        'templates/reports',
        'templates/alerts',
        'static',
        'static/css',
        'static/js',
        'static/img',
        'blueprints',
        'core',
        'core/services',
        'core/emulator',
        'models'
    ]

    print("📁 Creating directories...")
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"   ✅ Created: {directory}")
        else:
            print(f"   ℹ️  Exists: {directory}")

    print()


def init_fleet_database(db_path):
    """Inizializza database fleet.db"""
    print(f"💾 Initializing fleet database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Tabella alerts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            severity TEXT DEFAULT 'info',
            acknowledged INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            acknowledged_at TIMESTAMP,
            acknowledged_by TEXT
        )
    ''')

    # Tabella trips (opzionale per storico)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            start_address TEXT,
            end_address TEXT,
            distance REAL,
            duration INTEGER,
            max_speed REAL,
            avg_speed REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Tabella maintenance (manutenzioni)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS maintenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            maintenance_type TEXT NOT NULL,
            description TEXT,
            scheduled_date DATE,
            completed_date DATE,
            cost REAL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Indici per performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_vehicle ON alerts(vehicle_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trips_device ON trips(device_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trips_start ON trips(start_time)')

    conn.commit()
    conn.close()

    print(f"   ✅ Fleet database initialized")


def init_geocoding_database(db_path):
    """Inizializza database geocoding_cache.db"""
    print(f"🌍 Initializing geocoding database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

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

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_coord_hash ON geocoding_cache(coord_hash)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON geocoding_cache(created_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_city ON geocoding_cache(city)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_country ON geocoding_cache(country)')

    conn.commit()
    conn.close()

    print(f"   ✅ Geocoding database initialized")


def create_config_if_missing():
    """Crea config.json se mancante"""
    if os.path.exists('config.json'):
        print("ℹ️  config.json already exists")
        return

    print("📝 Creating default config.json...")

    default_config = {
        "flask": {
            "host": "0.0.0.0",
            "port": 59000,
            "debug": True
        },
        "traccar": {
            "host": "torraccia.iliadboxos.it",
            "port": 58082,
            "protocol": "http",
            "username": "dspeziale@gmail.com",
            "password": "Elisa2025!",
            "debug": False
        },
        "google_maps": {
            "api_key": "AIzaSyAZLNmrmri-HUzex5s4FaJZPk8xVeAyFVk",
            "cache_max_age_days": 90,
            "default_language": "it"
        },
        "geocoding": {
            "cache_db_path": "data/geocoding_cache.db",
            "max_age_days": 90,
            "precision": 5
        },
        "database": {
            "type": "sqlite",
            "path": "data/fleet.db"
        },
        "cache": {
            "route_cache_dir": "data/route_cache",
            "max_cache_size": 1000,
            "cleanup_interval_hours": 24
        },
        "app": {
            "name": "myTracker",
            "company": "DS Consulting",
            "items_per_page": 20
        }
    }

    with open('config.json', 'w') as f:
        json.dump(default_config, f, indent=2)

    print("   ✅ Default config.json created")


def main():
    """Inizializzazione completa"""
    print("=" * 60)
    print("🚀 Fleet Manager - Database Initialization")
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
        print(f"❌ Error loading config: {e}")
        return

    print()

    # Inizializza database fleet
    fleet_db = config['database']['path']
    init_fleet_database(fleet_db)

    print()

    # Inizializza database geocoding
    geo_db = config['geocoding']['cache_db_path']
    init_geocoding_database(geo_db)

    print()
    print("=" * 60)
    print("✅ Initialization complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Review config.json settings")
    print("2. Run: python app.py")
    print()


if __name__ == "__main__":
    main()