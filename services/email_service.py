# Filename: services/email_service.py
# Copyright 2025 SILICONDEV SPA
# Description: Gmail Email Service for sending emails

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from typing import List, Optional, Union
from flask import current_app
import logging

logger = logging.getLogger(__name__)


class GmailService:
    """Service for sending emails through Gmail SMTP"""

    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

    def _get_credentials(self):
        """Get Gmail credentials from app config"""
        gmail_user = current_app.config.get('GMAIL_USER')
        gmail_password = current_app.config.get('GMAIL_APP_PASSWORD')

        if not gmail_user or not gmail_password:
            raise ValueError("GMAIL_USER and GMAIL_APP_PASSWORD must be set in configuration")

        return gmail_user, gmail_password

    def send_email(
            self,
            to_emails: Union[str, List[str]],
            subject: str,
            body: str,
            html_body: Optional[str] = None,
            cc_emails: Optional[Union[str, List[str]]] = None,
            bcc_emails: Optional[Union[str, List[str]]] = None,
            attachments: Optional[List[str]] = None,
            from_name: Optional[str] = None
    ) -> bool:
        """
        Send email via Gmail SMTP

        Args:
            to_emails: Recipient email(s)
            subject: Email subject
            body: Plain text body
            html_body: HTML body (optional)
            cc_emails: CC recipients (optional)
            bcc_emails: BCC recipients (optional)
            attachments: List of file paths to attach (optional)
            from_name: Display name for sender (optional)

        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            gmail_user, gmail_password = self._get_credentials()

            # Create message
            message = MIMEMultipart("alternative")
            message["From"] = f"{from_name} <{gmail_user}>" if from_name else gmail_user
            message["Subject"] = subject

            # Handle recipients
            if isinstance(to_emails, str):
                to_emails = [to_emails]
            message["To"] = ", ".join(to_emails)

            if cc_emails:
                if isinstance(cc_emails, str):
                    cc_emails = [cc_emails]
                message["Cc"] = ", ".join(cc_emails)
                to_emails.extend(cc_emails)

            if bcc_emails:
                if isinstance(bcc_emails, str):
                    bcc_emails = [bcc_emails]
                to_emails.extend(bcc_emails)

            # Add text body
            text_part = MIMEText(body, "plain", "utf-8")
            message.attach(text_part)

            # Add HTML body if provided
            if html_body:
                html_part = MIMEText(html_body, "html", "utf-8")
                message.attach(html_part)

            # Add attachments if provided
            if attachments:
                for file_path in attachments:
                    if os.path.isfile(file_path):
                        self._add_attachment(message, file_path)
                    else:
                        logger.warning(f"Attachment file not found: {file_path}")

            # Create SMTP session
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(gmail_user, gmail_password)

                # Send email
                text = message.as_string()
                server.sendmail(gmail_user, to_emails, text)

            logger.info(f"Email sent successfully to: {', '.join(to_emails)}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False

    def _add_attachment(self, message: MIMEMultipart, file_path: str):
        """Add file attachment to email message"""
        try:
            with open(file_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())

            encoders.encode_base64(part)

            filename = os.path.basename(file_path)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}'
            )

            message.attach(part)

        except Exception as e:
            logger.error(f"Failed to add attachment {file_path}: {str(e)}")

    def send_template_email(
            self,
            to_emails: Union[str, List[str]],
            template_name: str,
            context: dict,
            subject: str,
            **kwargs
    ) -> bool:
        """
        Send email using Flask template

        Args:
            to_emails: Recipient email(s)
            template_name: Template file name (e.g., 'emails/welcome.html')
            context: Template context variables
            subject: Email subject
            **kwargs: Additional arguments for send_email method

        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            from flask import render_template

            # Render HTML template
            html_body = render_template(template_name, **context)

            # Generate plain text version (simple HTML stripping)
            import re
            text_body = re.sub('<[^<]+?>', '', html_body)
            text_body = re.sub(r'\n\s*\n', '\n\n', text_body.strip())

            return self.send_email(
                to_emails=to_emails,
                subject=subject,
                body=text_body,
                html_body=html_body,
                **kwargs
            )

        except Exception as e:
            logger.error(f"Failed to send template email: {str(e)}")
            return False


# Convenience functions
def send_email(*args, **kwargs) -> bool:
    """Convenience function to send email"""
    service = GmailService()
    return service.send_email(*args, **kwargs)


def send_template_email(*args, **kwargs) -> bool:
    """Convenience function to send template email"""
    service = GmailService()
    return service.send_template_email(*args, **kwargs)