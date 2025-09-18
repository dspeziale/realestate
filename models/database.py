"""
models/database.py - Database models for Fleet Manager
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any


class Database:
    def __init__(self, db_path: str = 'fleet.db'):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')

        # Vehicle preferences
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vehicle_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                vehicle_id INTEGER NOT NULL,
                color TEXT,
                icon TEXT,
                notes TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # Alerts
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_id INTEGER NOT NULL,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT DEFAULT 'info',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                acknowledged BOOLEAN DEFAULT 0
            )
        ''')

        # Scheduled reports
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                report_type TEXT NOT NULL,
                frequency TEXT NOT NULL,
                vehicle_ids TEXT,
                email_to TEXT,
                last_sent TIMESTAMP,
                active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        conn.commit()
        conn.close()

    # Alert methods
    def create_alert(self, vehicle_id: int, alert_type: str, message: str, severity: str = 'info'):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO alerts (vehicle_id, alert_type, message, severity)
            VALUES (?, ?, ?, ?)
        ''', (vehicle_id, alert_type, message, severity))
        conn.commit()
        conn.close()

    def get_alerts(self, limit: int = 50, acknowledged: bool = False) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM alerts 
            WHERE acknowledged = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (acknowledged, limit))
        alerts = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return alerts

    def acknowledge_alert(self, alert_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE alerts SET acknowledged = 1 WHERE id = ?', (alert_id,))
        conn.commit()
        conn.close()

    # Vehicle preferences
    def save_vehicle_preference(self, user_id: int, vehicle_id: int, **kwargs):
        conn = self.get_connection()
        cursor = conn.cursor()

        # Check if exists
        cursor.execute('''
            SELECT id FROM vehicle_preferences 
            WHERE user_id = ? AND vehicle_id = ?
        ''', (user_id, vehicle_id))

        existing = cursor.fetchone()

        if existing:
            # Update
            updates = ', '.join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values()) + [existing['id']]
            cursor.execute(f'''
                UPDATE vehicle_preferences 
                SET {updates}
                WHERE id = ?
            ''', values)
        else:
            # Insert
            fields = ', '.join(['user_id', 'vehicle_id'] + list(kwargs.keys()))
            placeholders = ', '.join(['?'] * (len(kwargs) + 2))
            values = [user_id, vehicle_id] + list(kwargs.values())
            cursor.execute(f'''
                INSERT INTO vehicle_preferences ({fields})
                VALUES ({placeholders})
            ''', values)

        conn.commit()
        conn.close()

    def get_vehicle_preferences(self, user_id: int, vehicle_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM vehicle_preferences
            WHERE user_id = ? AND vehicle_id = ?
        ''', (user_id, vehicle_id))
        pref = cursor.fetchone()
        conn.close()
        return dict(pref) if pref else None