# core/services/report_scheduler.py
"""
Report Scheduler - Gestione schedulazione e generazione automatica report
"""

import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import os
import json

from core.traccar_framework import TraccarAPI
from core.services.report_repository import ReportRepository
from core.services.gmail_sender import GmailSender
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
import io

logger = logging.getLogger(__name__)


class ReportScheduler:
    """Scheduler per generazione e invio automatico report"""

    def __init__(self,
                 traccar_api: TraccarAPI,
                 repository: ReportRepository,
                 gmail_sender: GmailSender,
                 output_dir: str = 'data/reports'):
        self.traccar = traccar_api
        self.repository = repository
        self.gmail = gmail_sender
        self.output_dir = output_dir
        self.running = False
        self.scheduler_thread = None

        os.makedirs(output_dir, exist_ok=True)

    def start(self):
        """Avvia scheduler in background thread"""
        if self.running:
            logger.warning("Scheduler già in esecuzione")
            return

        self.running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        logger.info("📅 Report Scheduler started")

    def stop(self):
        """Ferma scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("⏹️ Report Scheduler stopped")

    def _run_scheduler(self):
        """Loop principale scheduler"""
        # Carica schedulazioni esistenti
        self._load_schedules()

        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Check ogni minuto

    def _load_schedules(self):
        """Carica schedulazioni dal repository"""
        scheduled_reports = self.repository.get_scheduled_reports(active_only=True)

        for sched in scheduled_reports:
            self._add_schedule(sched)

        logger.info(f"📋 Loaded {len(scheduled_reports)} scheduled reports")

    def _add_schedule(self, scheduled_report: Dict):
        """Aggiunge schedulazione a schedule"""
        schedule_type = scheduled_report['schedule_type']
        config = json.loads(scheduled_report['schedule_config']) if scheduled_report['schedule_config'] else {}

        job = lambda: self._execute_scheduled_report(scheduled_report['id'])

        if schedule_type == 'daily':
            hour = config.get('hour', 9)
            schedule.every().day.at(f"{hour:02d}:00").do(job)

        elif schedule_type == 'weekly':
            weekday = config.get('weekday', 0)  # 0=Monday
            hour = config.get('hour', 9)
            days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            getattr(schedule.every(), days[weekday]).at(f"{hour:02d}:00").do(job)

        elif schedule_type == 'monthly':
            # Schedule non supporta monthly direttamente, usiamo daily e controlliamo il giorno
            day = config.get('day', 1)
            hour = config.get('hour', 9)

            def monthly_check():
                if datetime.now().day == day:
                    self._execute_scheduled_report(scheduled_report['id'])

            schedule.every().day.at(f"{hour:02d}:00").do(monthly_check)

        logger.debug(f"Added schedule: {scheduled_report['name']} ({schedule_type})")

    def _execute_scheduled_report(self, scheduled_id: int):
        """Esegue report schedulato"""
        logger.info(f"🔄 Executing scheduled report ID: {scheduled_id}")

        try:
            # Recupera configurazione
            conn = self.repository._get_connection() if hasattr(self.repository, '_get_connection') else None
            if not conn:
                import sqlite3
                conn = sqlite3.connect(self.repository.db_path)
                conn.row_factory = sqlite3.Row

            cursor = conn.cursor()
            cursor.execute('SELECT * FROM scheduled_reports WHERE id = ?', (scheduled_id,))
            sched = dict(cursor.fetchone())
            conn.close()

            # Prepara parametri
            device_ids = json.loads(sched['device_ids'])
            to_date = datetime.now()

            # Calcola from_date in base al tipo
            if sched['schedule_type'] == 'daily':
                from_date = to_date - timedelta(days=1)
            elif sched['schedule_type'] == 'weekly':
                from_date = to_date - timedelta(days=7)
            elif sched['schedule_type'] == 'monthly':
                from_date = to_date - timedelta(days=30)
            else:
                from_date = to_date - timedelta(days=1)

            # Genera report
            report_data = self._generate_report(
                sched['report_type'],
                device_ids,
                from_date,
                to_date
            )

            if not report_data:
                logger.warning(f"No data for scheduled report {scheduled_id}")
                return

            # Salva file
            filename = f"{sched['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            file_path = os.path.join(self.output_dir, filename)

            self._create_pdf_report(
                report_data,
                sched['report_type'],
                file_path,
                from_date,
                to_date
            )

            # Salva in repository
            report_uuid = self.repository.save_report(
                report_type=sched['report_type'],
                report_format='pdf',
                device_ids=device_ids,
                from_date=from_date,
                to_date=to_date,
                data=report_data,
                file_path=file_path,
                generated_by='scheduler'
            )

            # Invia email
            recipients = json.loads(sched['email_recipients'])
            devices = self.traccar.devices.get_devices()
            device_names = [d['name'] for d in devices if d['id'] in device_ids]

            result = self.gmail.send_report_email(
                to=recipients,
                report_type=sched['report_type'],
                report_file_path=file_path,
                from_date=from_date.strftime('%Y-%m-%d'),
                to_date=to_date.strftime('%Y-%m-%d'),
                devices=device_names
            )

            # Log risultato
            if result['success']:
                self.repository.mark_report_sent(report_uuid, recipients)
                logger.info(f"✅ Scheduled report sent: {filename}")
            else:
                logger.error(f"❌ Failed to send report: {result.get('error')}")

            self.repository.log_email_sent(
                report_id=None,
                scheduled_report_id=scheduled_id,
                recipients=recipients,
                subject=f"Fleet Report - {sched['report_type']}",
                status='sent' if result['success'] else 'failed',
                error_message=result.get('error')
            )

            # Aggiorna last_run
            import sqlite3
            conn = sqlite3.connect(self.repository.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE scheduled_reports 
                SET last_run_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (scheduled_id,))
            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"❌ Error executing scheduled report: {e}", exc_info=True)

    def _generate_report(self, report_type: str, device_ids: List[int],
                         from_date: datetime, to_date: datetime) -> List[Dict]:
        """Genera dati report da Traccar"""
        try:
            if report_type == 'summary':
                return self.traccar.reports.get_summary_report(
                    device_ids=device_ids,
                    from_time=from_date,
                    to_time=to_date
                )
            elif report_type == 'trips':
                return self.traccar.reports.get_trips_report(
                    device_ids=device_ids,
                    from_time=from_date,
                    to_time=to_date
                )
            elif report_type == 'stops':
                return self.traccar.reports.get_stops_report(
                    device_ids=device_ids,
                    from_time=from_date,
                    to_time=to_date
                )
            else:
                logger.error(f"Unknown report type: {report_type}")
                return []

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return []

    def _create_pdf_report(self, data: List[Dict], report_type: str,
                           output_path: str, from_date: datetime, to_date: datetime):
        """Crea PDF report"""
        doc = SimpleDocTemplate(output_path, pagesize=landscape(A4) if len(data) > 0 else A4)
        elements = []
        styles = getSampleStyleSheet()

        # Title
        title = Paragraph(f"<b>{report_type.upper()} REPORT</b>", styles['Title'])
        elements.append(title)
        elements.append(Spacer(1, 12))

        # Period
        period = Paragraph(
            f"Period: {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}",
            styles['Normal']
        )
        elements.append(period)
        elements.append(Spacer(1, 20))

        # Data table
        if data:
            # Headers based on report type
            if report_type == 'summary':
                headers = ['Device', 'Distance (km)', 'Max Speed', 'Avg Speed', 'Engine Hours']
                rows = [[
                    item.get('deviceName', 'N/A'),
                    f"{item.get('distance', 0) / 1000:.2f}",
                    f"{item.get('maxSpeed', 0):.1f}",
                    f"{item.get('averageSpeed', 0):.1f}",
                    f"{item.get('engineHours', 0):.1f}"
                ] for item in data]

            elif report_type == 'trips':
                headers = ['Device', 'Start', 'End', 'Distance (km)', 'Duration (min)', 'Avg Speed']
                rows = [[
                    item.get('deviceName', 'N/A'),
                    item.get('startTime', 'N/A')[:16],
                    item.get('endTime', 'N/A')[:16],
                    f"{item.get('distance', 0) / 1000:.2f}",
                    f"{item.get('duration', 0) / 60000:.0f}",
                    f"{item.get('averageSpeed', 0):.1f}"
                ] for item in data[:50]]  # Max 50 rows

            else:  # stops
                headers = ['Device', 'Start', 'End', 'Duration (min)', 'Position']
                rows = [[
                    item.get('deviceName', 'N/A'),
                    item.get('startTime', 'N/A')[:16],
                    item.get('endTime', 'N/A')[:16],
                    f"{item.get('duration', 0) / 60000:.0f}",
                    item.get('address', 'N/A')[:30]
                ] for item in data[:50]]

            table_data = [headers] + rows
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(table)
        else:
            no_data = Paragraph("<i>No data available for this period</i>", styles['Normal'])
            elements.append(no_data)

        doc.build(elements)
        logger.debug(f"PDF created: {output_path}")

    def add_daily_report(self, name: str, report_type: str, device_ids: List[int],
                         email_recipients: List[str], hour: int = 9) -> int:
        """Aggiungi report giornaliero"""
        return self.repository.create_scheduled_report(
            name=name,
            report_type=report_type,
            report_format='pdf',
            device_ids=device_ids,
            schedule_type='daily',
            email_recipients=email_recipients,
            schedule_config={'hour': hour}
        )

    def add_weekly_report(self, name: str, report_type: str, device_ids: List[int],
                          email_recipients: List[str], weekday: int = 0, hour: int = 9) -> int:
        """Aggiungi report settimanale (0=Lunedì, 6=Domenica)"""
        return self.repository.create_scheduled_report(
            name=name,
            report_type=report_type,
            report_format='pdf',
            device_ids=device_ids,
            schedule_type='weekly',
            email_recipients=email_recipients,
            schedule_config={'weekday': weekday, 'hour': hour}
        )

    def add_monthly_report(self, name: str, report_type: str, device_ids: List[int],
                           email_recipients: List[str], day: int = 1, hour: int = 9) -> int:
        """Aggiungi report mensile"""
        return self.repository.create_scheduled_report(
            name=name,
            report_type=report_type,
            report_format='pdf',
            device_ids=device_ids,
            schedule_type='monthly',
            email_recipients=email_recipients,
            schedule_config={'day': day, 'hour': hour}
        )
