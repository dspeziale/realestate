# core/services/gmail_sender.py
"""
Gmail Sender Service - Invio email con Gmail API
"""

import base64
import json
import os
import pickle
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional, Dict
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.send']


class GmailSender:
    """Service per invio email tramite Gmail API"""

    def __init__(self, credentials_path: str = 'credentials.json',
                 token_path: str = 'data/gmail_token.pickle'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Autentica con Gmail API"""
        creds = None

        # Carica token salvato se esiste
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)

        # Se non ci sono credenziali valide, richiedi login
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    logger.error(f"❌ Credentials file not found: {self.credentials_path}")
                    raise FileNotFoundError(f"Missing {self.credentials_path}")

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            # Salva token per utilizzo futuro
            os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)

        self.service = build('gmail', 'v1', credentials=creds)
        logger.info("✅ Gmail API authenticated")

    def send_email(self,
                   to: List[str],
                   subject: str,
                   body: str,
                   html_body: Optional[str] = None,
                   attachments: Optional[List[Dict]] = None,
                   cc: Optional[List[str]] = None,
                   bcc: Optional[List[str]] = None) -> Dict:
        """
        Invia email tramite Gmail

        Args:
            to: Lista destinatari
            subject: Oggetto email
            body: Corpo testuale
            html_body: Corpo HTML (opzionale)
            attachments: Lista allegati [{path, filename}]
            cc: Lista CC
            bcc: Lista BCC

        Returns:
            Dict con risultato invio
        """
        try:
            message = self._create_message(to, subject, body, html_body, attachments, cc, bcc)
            sent = self.service.users().messages().send(userId='me', body=message).execute()

            logger.info(f"📧 Email sent successfully. ID: {sent['id']}")
            return {
                'success': True,
                'message_id': sent['id'],
                'recipients': to
            }

        except HttpError as error:
            logger.error(f"❌ Gmail API error: {error}")
            return {
                'success': False,
                'error': str(error),
                'recipients': to
            }

        except Exception as e:
            logger.error(f"❌ Error sending email: {e}")
            return {
                'success': False,
                'error': str(e),
                'recipients': to
            }

    def send_report_email(self,
                          to: List[str],
                          report_type: str,
                          report_file_path: str,
                          from_date: str,
                          to_date: str,
                          devices: List[str],
                          summary_data: Optional[Dict] = None) -> Dict:
        """
        Invia email con report allegato

        Args:
            to: Destinatari
            report_type: Tipo report (summary, trips, etc)
            report_file_path: Path file report
            from_date: Data inizio
            to_date: Data fine
            devices: Lista nomi dispositivi
            summary_data: Dati riassuntivi opzionali
        """
        # Crea subject
        subject = f"Fleet Report - {report_type.title()} ({from_date} to {to_date})"

        # Crea corpo email
        body = f"""Fleet Management Report

Report Type: {report_type.title()}
Period: {from_date} to {to_date}
Devices: {', '.join(devices)}

"""

        if summary_data:
            body += "\n=== Summary ===\n"
            for key, value in summary_data.items():
                body += f"{key}: {value}\n"

        body += """
This is an automated report from Fleet Manager.
Please find the detailed report in the attached file.

---
Fleet Manager Pro
"""

        # HTML body
        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif;">
    <h2>Fleet Management Report</h2>
    <table style="border-collapse: collapse; margin: 20px 0;">
        <tr>
            <td style="padding: 8px; font-weight: bold;">Report Type:</td>
            <td style="padding: 8px;">{report_type.title()}</td>
        </tr>
        <tr>
            <td style="padding: 8px; font-weight: bold;">Period:</td>
            <td style="padding: 8px;">{from_date} to {to_date}</td>
        </tr>
        <tr>
            <td style="padding: 8px; font-weight: bold;">Devices:</td>
            <td style="padding: 8px;">{', '.join(devices)}</td>
        </tr>
    </table>
"""

        if summary_data:
            html_body += """
    <h3>Summary</h3>
    <table style="border: 1px solid #ddd; border-collapse: collapse;">
"""
            for key, value in summary_data.items():
                html_body += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">{key}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{value}</td>
        </tr>
"""
            html_body += """
    </table>
"""

        html_body += """
    <p>Please find the detailed report in the attached file.</p>
    <hr>
    <p style="color: #666; font-size: 12px;">Fleet Manager Pro - Automated Report</p>
</body>
</html>
"""

        # Allegato
        attachments = [{
            'path': report_file_path,
            'filename': os.path.basename(report_file_path)
        }]

        return self.send_email(to, subject, body, html_body, attachments)

    def _create_message(self,
                        to: List[str],
                        subject: str,
                        body: str,
                        html_body: Optional[str] = None,
                        attachments: Optional[List[Dict]] = None,
                        cc: Optional[List[str]] = None,
                        bcc: Optional[List[str]] = None) -> Dict:
        """Crea messaggio email per Gmail API"""

        if html_body:
            message = MIMEMultipart('alternative')
        elif attachments:
            message = MIMEMultipart()
        else:
            message = MIMEText(body)
            message['to'] = ', '.join(to)
            message['subject'] = subject
            if cc:
                message['cc'] = ', '.join(cc)
            if bcc:
                message['bcc'] = ', '.join(bcc)

            return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}

        # Multipart message
        message['to'] = ', '.join(to)
        message['subject'] = subject
        if cc:
            message['cc'] = ', '.join(cc)
        if bcc:
            message['bcc'] = ', '.join(bcc)

        # Aggiungi corpo
        text_part = MIMEText(body, 'plain')
        message.attach(text_part)

        if html_body:
            html_part = MIMEText(html_body, 'html')
            message.attach(html_part)

        # Aggiungi allegati
        if attachments:
            for attachment in attachments:
                self._attach_file(message, attachment['path'], attachment.get('filename'))

        return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}

    def _attach_file(self, message: MIMEMultipart, file_path: str, filename: Optional[str] = None):
        """Allega file al messaggio"""
        if not filename:
            filename = os.path.basename(file_path)

        with open(file_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())

        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={filename}')
        message.attach(part)