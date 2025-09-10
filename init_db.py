#!/usr/bin/env python3
# Copyright 2025 SILICONDEV SPA
# Filename: create_db.py
# Description: Simple database creation script

import os
import sys
import sqlite3
from datetime import datetime


def create_database():
    """Create SQLite database with basic tables"""

    # Database file path
    db_path = 'real_estate_auctions.db'

    # Remove existing database
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"🗑️  Database rimosso: {db_path}")

    # Create new database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create Users table
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email VARCHAR(120) UNIQUE NOT NULL,
            username VARCHAR(80) UNIQUE,
            password_hash VARCHAR(255),
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            google_id VARCHAR(100) UNIQUE,
            profile_picture TEXT,
            is_active BOOLEAN DEFAULT 1 NOT NULL,
            is_verified BOOLEAN DEFAULT 0 NOT NULL,
            is_admin BOOLEAN DEFAULT 0 NOT NULL,
            phone VARCHAR(20),
            address TEXT,
            city VARCHAR(100),
            postal_code VARCHAR(20),
            country VARCHAR(100) DEFAULT 'Italia',
            license_number VARCHAR(50),
            company_name VARCHAR(200),
            vat_number VARCHAR(20),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            last_login DATETIME
        )
    ''')

    # Create Properties table
    cursor.execute('''
        CREATE TABLE properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            property_type VARCHAR(50) NOT NULL,
            condition VARCHAR(50),
            surface_area REAL,
            rooms INTEGER,
            bathrooms INTEGER,
            floor VARCHAR(20),
            year_built INTEGER,
            address VARCHAR(200) NOT NULL,
            city VARCHAR(100) NOT NULL,
            province VARCHAR(50) NOT NULL,
            postal_code VARCHAR(20),
            region VARCHAR(50),
            latitude REAL,
            longitude REAL,
            base_price DECIMAL(12, 2) NOT NULL,
            estimated_value DECIMAL(12, 2),
            minimum_bid DECIMAL(12, 2),
            cadastral_income DECIMAL(10, 2),
            cadastral_data TEXT,
            court VARCHAR(100),
            procedure_number VARCHAR(50),
            judge VARCHAR(100),
            status VARCHAR(20) DEFAULT 'pre_auction' NOT NULL,
            auction_type VARCHAR(50),
            is_occupied BOOLEAN DEFAULT 0 NOT NULL,
            has_debts BOOLEAN DEFAULT 0 NOT NULL,
            debt_amount DECIMAL(12, 2),
            has_garage BOOLEAN DEFAULT 0 NOT NULL,
            has_garden BOOLEAN DEFAULT 0 NOT NULL,
            has_terrace BOOLEAN DEFAULT 0 NOT NULL,
            has_elevator BOOLEAN DEFAULT 0 NOT NULL,
            energy_class VARCHAR(5),
            documents TEXT,
            images TEXT,
            virtual_tour_url VARCHAR(255),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            agent_id INTEGER NOT NULL,
            FOREIGN KEY(agent_id) REFERENCES users(id)
        )
    ''')

    # Create Auctions table
    cursor.execute('''
        CREATE TABLE auctions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            auction_number VARCHAR(50) UNIQUE NOT NULL,
            auction_type VARCHAR(50) DEFAULT 'synchronous' NOT NULL,
            start_date DATETIME NOT NULL,
            end_date DATETIME,
            registration_deadline DATETIME,
            starting_price DECIMAL(12, 2) NOT NULL,
            minimum_bid_increment DECIMAL(10, 2) DEFAULT 1000.00 NOT NULL,
            deposit_amount DECIMAL(12, 2) NOT NULL,
            deposit_percentage REAL DEFAULT 10.0,
            current_price DECIMAL(12, 2),
            highest_bid DECIMAL(12, 2),
            total_bids INTEGER DEFAULT 0 NOT NULL,
            status VARCHAR(20) DEFAULT 'scheduled' NOT NULL,
            court VARCHAR(100),
            procedure_number VARCHAR(50),
            professional_delegate VARCHAR(200),
            requires_registration BOOLEAN DEFAULT 1 NOT NULL,
            allows_remote_bidding BOOLEAN DEFAULT 1 NOT NULL,
            special_conditions TEXT,
            viewing_schedule TEXT,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            property_id INTEGER NOT NULL,
            FOREIGN KEY(property_id) REFERENCES properties(id)
        )
    ''')

    # Create Bids table
    cursor.execute('''
        CREATE TABLE bids (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount DECIMAL(12, 2) NOT NULL,
            is_winning BOOLEAN DEFAULT 0 NOT NULL,
            is_valid BOOLEAN DEFAULT 1 NOT NULL,
            bid_type VARCHAR(20) DEFAULT 'standard' NOT NULL,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            auction_id INTEGER NOT NULL,
            bidder_id INTEGER NOT NULL,
            FOREIGN KEY(auction_id) REFERENCES auctions(id),
            FOREIGN KEY(bidder_id) REFERENCES users(id)
        )
    ''')

    # Create indexes
    cursor.execute('CREATE INDEX idx_users_email ON users(email)')
    cursor.execute('CREATE INDEX idx_properties_status ON properties(status)')
    cursor.execute('CREATE INDEX idx_properties_city ON properties(city)')
    cursor.execute('CREATE INDEX idx_auctions_status ON auctions(status)')
    cursor.execute('CREATE INDEX idx_auctions_start_date ON auctions(start_date)')
    cursor.execute('CREATE INDEX idx_bids_auction_id ON bids(auction_id)')

    # Create admin user (password hash for 'admin123')
    from werkzeug.security import generate_password_hash
    admin_password_hash = generate_password_hash('admin123')

    cursor.execute('''
        INSERT INTO users (email, first_name, last_name, password_hash, is_admin, is_active, is_verified)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', ('admin@example.com', 'Admin', 'User', admin_password_hash, 1, 1, 1))

    # Commit and close
    conn.commit()
    conn.close()

    print(f"✅ Database creato: {db_path}")
    print("👤 Utente admin creato:")
    print("   📧 Email: admin@example.com")
    print("   🔒 Password: admin123")
    print("   ⚠️  CAMBIA LA PASSWORD DOPO IL PRIMO LOGIN!")

    return True


if __name__ == '__main__':
    try:
        print("🚀 Inizializzazione database...")
        create_database()
        print("🎉 Inizializzazione completata!")
        print("\n💡 Prossimi passi:")
        print("   1. python app.py")
        print("   2. Apri http://127.0.0.1:5000")
        print("   3. Login con admin@example.com / admin123")

    except Exception as e:
        print(f"❌ Errore: {str(e)}")
        sys.exit(1)