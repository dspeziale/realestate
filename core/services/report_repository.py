# core/services/report_repository.py
"""
Report Repository Service - Gestione e archiviazione report generati
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import hashlib
import logging

logger = logging.getLogger(__name__)


class ReportRepository:
    """Repository per salvare e recuperare report generati"""

    def __init__(self, db_path: str = 'data/reports_repository.db'):
        self.db_path = db_path
        self._ensure_directory()
        self._init_database()

    def _ensure_directory(self):
        """Crea directory se non esiste"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def _init_database(self):
        """Inizializza database repository"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Tabella report generati
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS generated_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_uuid TEXT UNIQUE NOT NULL,
                report_type TEXT NOT NULL,
                report_format TEXT NOT NULL,
                device_ids TEXT NOT NULL,
                from_date TEXT NOT NULL,
                to_date TEXT NOT NULL,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                generated_by TEXT,
                file_path TEXT,
                file_size INTEGER,
                data_json TEXT,
                metadata TEXT,
                sent_via_email INTEGER DEFAULT 0,
                email_sent_at TIMESTAMP,
                email_recipients TEXT
            )
        ''')

        # Tabella schedulazione report
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                report_type TEXT NOT NULL,
                report_format TEXT NOT NULL,
                device_ids TEXT NOT NULL,
                schedule_type TEXT NOT NULL,
                schedule_config TEXT,
                email_recipients TEXT NOT NULL,
                email_subject TEXT,
                email_body TEXT,
                active INTEGER DEFAULT 1,
                last_run_at TIMESTAMP,
                next_run_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT
            )
        ''')

        # Tabella log invii email
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER,
                scheduled_report_id INTEGER,
                recipients TEXT NOT NULL,
                subject TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                error_message TEXT,
                FOREIGN KEY (report_id) REFERENCES generated_reports(id),
                FOREIGN KEY (scheduled_report_id) REFERENCES scheduled_reports(id)
            )
        ''')

        conn.commit()
        conn.close()
        logger.info(f"📊 Report repository initialized: {self.db_path}")

    def save_report(self,
                    report_type: str,
                    report_format: str,
                    device_ids: List[int],
                    from_date: datetime,
                    to_date: datetime,
                    data: Any,
                    file_path: Optional[str] = None,
                    generated_by: Optional[str] = None,
                    metadata: Optional[Dict] = None) -> str:
        """
        Salva report generato nel repository

        Returns:
            report_uuid: UUID del report salvato
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Genera UUID univoco
        report_uuid = self._generate_uuid(report_type, device_ids, from_date, to_date)

        # Calcola dimensione file se specificato
        file_size = None
        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)

        cursor.execute('''
            INSERT INTO generated_reports 
            (report_uuid, report_type, report_format, device_ids, from_date, to_date,
             generated_by, file_path, file_size, data_json, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            report_uuid,
            report_type,
            report_format,
            json.dumps(device_ids),
            from_date.isoformat(),
            to_date.isoformat(),
            generated_by,
            file_path,
            file_size,
            json.dumps(data) if isinstance(data, (dict, list)) else str(data),
            json.dumps(metadata) if metadata else None
        ))

        conn.commit()
        conn.close()

        logger.info(f"💾 Report saved: {report_uuid} ({report_type}, {report_format})")
        return report_uuid

    def get_report(self, report_uuid: str) -> Optional[Dict]:
        """Recupera report dal repository"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM generated_reports WHERE report_uuid = ?
        ''', (report_uuid,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def list_reports(self,
                     report_type: Optional[str] = None,
                     from_date: Optional[datetime] = None,
                     to_date: Optional[datetime] = None,
                     limit: int = 50) -> List[Dict]:
        """Lista report con filtri opzionali"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = 'SELECT * FROM generated_reports WHERE 1=1'
        params = []

        if report_type:
            query += ' AND report_type = ?'
            params.append(report_type)

        if from_date:
            query += ' AND generated_at >= ?'
            params.append(from_date.isoformat())

        if to_date:
            query += ' AND generated_at <= ?'
            params.append(to_date.isoformat())

        query += ' ORDER BY generated_at DESC LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def create_scheduled_report(self,
                                name: str,
                                report_type: str,
                                report_format: str,
                                device_ids: List[int],
                                schedule_type: str,
                                email_recipients: List[str],
                                schedule_config: Optional[Dict] = None,
                                email_subject: Optional[str] = None,
                                email_body: Optional[str] = None,
                                created_by: Optional[str] = None) -> int:
        """
        Crea schedulazione report periodico

        schedule_type: daily, weekly, monthly, custom
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Calcola prossima esecuzione
        next_run = self._calculate_next_run(schedule_type, schedule_config)

        cursor.execute('''
            INSERT INTO scheduled_reports
            (name, report_type, report_format, device_ids, schedule_type, 
             schedule_config, email_recipients, email_subject, email_body,
             created_by, next_run_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            name,
            report_type,
            report_format,
            json.dumps(device_ids),
            schedule_type,
            json.dumps(schedule_config) if schedule_config else None,
            json.dumps(email_recipients),
            email_subject,
            email_body,
            created_by,
            next_run.isoformat() if next_run else None
        ))

        scheduled_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"📅 Scheduled report created: {name} (ID: {scheduled_id})")
        return scheduled_id

    def get_scheduled_reports(self, active_only: bool = True) -> List[Dict]:
        """Recupera report schedulati"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = 'SELECT * FROM scheduled_reports'
        if active_only:
            query += ' WHERE active = 1'
        query += ' ORDER BY next_run_at ASC'

        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def mark_report_sent(self, report_uuid: str, recipients: List[str]):
        """Marca report come inviato via email"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE generated_reports 
            SET sent_via_email = 1,
                email_sent_at = CURRENT_TIMESTAMP,
                email_recipients = ?
            WHERE report_uuid = ?
        ''', (json.dumps(recipients), report_uuid))

        conn.commit()
        conn.close()

    def log_email_sent(self,
                       report_id: Optional[int],
                       scheduled_report_id: Optional[int],
                       recipients: List[str],
                       subject: str,
                       status: str,
                       error_message: Optional[str] = None):
        """Log invio email"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO email_log
            (report_id, scheduled_report_id, recipients, subject, status, error_message)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            report_id,
            scheduled_report_id,
            json.dumps(recipients),
            subject,
            status,
            error_message
        ))

        conn.commit()
        conn.close()

    def _generate_uuid(self, report_type: str, device_ids: List[int],
                       from_date: datetime, to_date: datetime) -> str:
        """Genera UUID univoco per report"""
        content = f"{report_type}_{sorted(device_ids)}_{from_date.isoformat()}_{to_date.isoformat()}_{datetime.now().isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _calculate_next_run(self, schedule_type: str, config: Optional[Dict]) -> Optional[datetime]:
        """Calcola prossima esecuzione schedulata"""
        from datetime import timedelta

        now = datetime.now()

        if schedule_type == 'daily':
            # Prossimo giorno alle ore specificate
            hour = config.get('hour', 9) if config else 9
            next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run

        elif schedule_type == 'weekly':
            # Prossima settimana, giorno specifico
            weekday = config.get('weekday', 0) if config else 0  # 0 = Lunedì
            hour = config.get('hour', 9) if config else 9

            days_ahead = weekday - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7

            next_run = now + timedelta(days=days_ahead)
            next_run = next_run.replace(hour=hour, minute=0, second=0, microsecond=0)
            return next_run

        elif schedule_type == 'monthly':
            # Prossimo mese, giorno specifico
            day = config.get('day', 1) if config else 1
            hour = config.get('hour', 9) if config else 9

            next_run = now.replace(day=day, hour=hour, minute=0, second=0, microsecond=0)
            if next_run <= now:
                # Prossimo mese
                if now.month == 12:
                    next_run = next_run.replace(year=now.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=now.month + 1)

            return next_run

        return None