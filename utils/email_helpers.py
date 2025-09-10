# Filename: utils/email_helpers.py
# Copyright 2025 SILICONDEV SPA
# Description: Helper functions for email operations

from datetime import datetime
from flask import url_for, current_app
from services.email_service import send_email, send_template_email
import logging

logger = logging.getLogger(__name__)


def send_welcome_email(user):
    """Send welcome email to new user"""
    try:
        context = {
            'user_name': user.full_name,
            'user_email': user.email,
            'registration_date': user.created_at.strftime('%d/%m/%Y'),
            'login_url': url_for('auth.login', _external=True),
            'current_year': datetime.now().year
        }

        success = send_template_email(
            to_emails=user.email,
            template_name='emails/welcome.html',
            context=context,
            subject='Benvenuto nel Sistema Aste Immobiliari',
            from_name='Sistema Aste Immobiliari'
        )

        if success:
            logger.info(f"Welcome email sent to {user.email}")
        else:
            logger.error(f"Failed to send welcome email to {user.email}")

        return success

    except Exception as e:
        logger.error(f"Error sending welcome email to {user.email}: {str(e)}")
        return False


def send_auction_notification(user, auction, notification_type, **kwargs):
    """
    Send auction notification email

    Args:
        user: User object
        auction: Auction object
        notification_type: 'auction_starting', 'auction_ending', 'outbid', 'won_auction'
        **kwargs: Additional context variables
    """
    try:
        # Base context
        context = {
            'user_name': user.full_name,
            'notification_type': notification_type,
            'property_address': auction.property.full_address,
            'property_type': auction.property.property_type,
            'property_size': auction.property.surface_area,
            'auction_url': url_for('auctions.detail', id=auction.id, _external=True),
            'current_year': datetime.now().year
        }

        # Add specific context based on notification type
        if auction.current_bid:
            context['current_bid'] = f"{auction.current_bid:,.2f}"

        if auction.end_date:
            context['auction_end_time'] = auction.end_date.strftime('%d/%m/%Y alle %H:%M')

        # Add any additional context
        context.update(kwargs)

        # Subject mapping
        subjects = {
            'auction_starting': f'Asta in avvio - {auction.property.city}',
            'auction_ending': f'Asta in scadenza - {auction.property.city}',
            'outbid': f'Sei stato superato - {auction.property.city}',
            'won_auction': f'Hai vinto l\'asta - {auction.property.city}!'
        }

        success = send_template_email(
            to_emails=user.email,
            template_name='emails/auction_notification.html',
            context=context,
            subject=subjects.get(notification_type, 'Notifica Asta'),
            from_name='Sistema Aste Immobiliari'
        )

        if success:
            logger.info(f"Auction notification ({notification_type}) sent to {user.email}")
        else:
            logger.error(f"Failed to send auction notification to {user.email}")

        return success

    except Exception as e:
        logger.error(f"Error sending auction notification to {user.email}: {str(e)}")
        return False


def send_password_reset_email(user, reset_token):
    """Send password reset email"""
    try:
        context = {
            'user_name': user.full_name,
            'reset_url': url_for('auth.reset_password', token=reset_token, _external=True),
            'current_year': datetime.now().year
        }

        success = send_template_email(
            to_emails=user.email,
            template_name='emails/reset_password.html',
            context=context,
            subject='Reset Password - Sistema Aste Immobiliari',
            from_name='Sistema Aste Immobiliari'
        )

        if success:
            logger.info(f"Password reset email sent to {user.email}")
        else:
            logger.error(f"Failed to send password reset email to {user.email}")

        return success

    except Exception as e:
        logger.error(f"Error sending password reset email to {user.email}: {str(e)}")
        return False


def send_bid_confirmation_email(user, bid):
    """Send bid confirmation email"""
    try:
        auction = bid.auction
        property_obj = auction.property

        # Simple email without template
        subject = f'Conferma Offerta - {property_obj.city}'

        body = f"""
Ciao {user.full_name},

La tua offerta è stata registrata con successo!

Dettagli offerta:
- Proprietà: {property_obj.full_address}
- Tipo: {property_obj.property_type}
- Superficie: {property_obj.surface_area} mq
- Tua offerta: €{bid.amount:,.2f}
- Data offerta: {bid.created_at.strftime('%d/%m/%Y alle %H:%M')}

Puoi seguire lo stato dell'asta al seguente link:
{url_for('auctions.detail', id=auction.id, _external=True)}

Buona fortuna!

Sistema Aste Immobiliari
        """

        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <h2>Conferma Offerta</h2>
    <p>Ciao {user.full_name},</p>
    <p>La tua offerta è stata registrata con successo!</p>

    <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;">
        <h3>Dettagli offerta:</h3>
        <ul>
            <li><strong>Proprietà:</strong> {property_obj.full_address}</li>
            <li><strong>Tipo:</strong> {property_obj.property_type}</li>
            <li><strong>Superficie:</strong> {property_obj.surface_area} mq</li>
            <li><strong>Tua offerta:</strong> €{bid.amount:,.2f}</li>
            <li><strong>Data offerta:</strong> {bid.created_at.strftime('%d/%m/%Y alle %H:%M')}</li>
        </ul>
    </div>

    <p>
        <a href="{url_for('auctions.detail', id=auction.id, _external=True)}" 
           style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
            Visualizza Asta
        </a>
    </p>

    <p>Buona fortuna!</p>
    <hr>
    <p style="font-size: 12px; color: #666;">Sistema Aste Immobiliari</p>
</body>
</html>
        """

        success = send_email(
            to_emails=user.email,
            subject=subject,
            body=body,
            html_body=html_body,
            from_name='Sistema Aste Immobiliari'
        )

        if success:
            logger.info(f"Bid confirmation email sent to {user.email}")
        else:
            logger.error(f"Failed to send bid confirmation email to {user.email}")

        return success

    except Exception as e:
        logger.error(f"Error sending bid confirmation email to {user.email}: {str(e)}")
        return False


def send_bulk_newsletter(users, subject, content, html_content=None):
    """Send newsletter to multiple users"""
    try:
        successful_sends = 0
        failed_sends = 0

        for user in users:
            if not user.email or not user.is_active:
                continue

            try:
                context = {
                    'user_name': user.full_name,
                    'month_year': datetime.now().strftime('%B %Y'),
                    'current_year': datetime.now().year,
                    'website_url': url_for('index', _external=True)
                }

                if html_content:
                    # Use template
                    success = send_template_email(
                        to_emails=user.email,
                        template_name='emails/newsletter.html',
                        context=context,
                        subject=subject,
                        from_name='Sistema Aste Immobiliari'
                    )
                else:
                    # Simple email
                    success = send_email(
                        to_emails=user.email,
                        subject=subject,
                        body=content,
                        html_body=html_content,
                        from_name='Sistema Aste Immobiliari'
                    )

                if success:
                    successful_sends += 1
                else:
                    failed_sends += 1

            except Exception as e:
                logger.error(f"Error sending newsletter to {user.email}: {str(e)}")
                failed_sends += 1

        logger.info(f"Newsletter sent: {successful_sends} successful, {failed_sends} failed")
        return successful_sends, failed_sends

    except Exception as e:
        logger.error(f"Error in bulk newsletter send: {str(e)}")
        return 0, len(users)


def send_system_notification_email(admins, subject, message, priority='normal'):
    """Send system notification to administrators"""
    try:
        if not admins:
            return False

        admin_emails = [admin.email for admin in admins if admin.email and admin.is_active]

        if not admin_emails:
            return False

        # Priority styling
        priority_colors = {
            'low': '#17a2b8',  # info
            'normal': '#007bff',  # primary
            'high': '#ffc107',  # warning
            'critical': '#dc3545'  # danger
        }

        priority_icons = {
            'low': 'ℹ️',
            'normal': '📧',
            'high': '⚠️',
            'critical': '🚨'
        }

        color = priority_colors.get(priority, '#007bff')
        icon = priority_icons.get(priority, '📧')

        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: {color}; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0;">
            <h1>{icon} Notifica Sistema</h1>
        </div>
        <div style="background: #f8f9fa; padding: 20px; border-radius: 0 0 5px 5px;">
            <p><strong>Priorità:</strong> {priority.upper()}</p>
            <p><strong>Timestamp:</strong> {datetime.now().strftime('%d/%m/%Y alle %H:%M:%S')}</p>
            <hr>
            <div style="background: white; padding: 15px; border-radius: 5px;">
                {message.replace('\n', '<br>')}
            </div>
            <hr>
            <p style="font-size: 12px; color: #666; text-align: center;">
                Sistema Aste Immobiliari - Notifica Automatica
            </p>
        </div>
    </div>
</body>
</html>
        """

        text_body = f"""
{icon} NOTIFICA SISTEMA

Priorità: {priority.upper()}
Timestamp: {datetime.now().strftime('%d/%m/%Y alle %H:%M:%S')}

{message}

---
Sistema Aste Immobiliari - Notifica Automatica
        """

        success = send_email(
            to_emails=admin_emails,
            subject=f"[SISTEMA] {subject}",
            body=text_body,
            html_body=html_body,
            from_name='Sistema Aste Immobiliari'
        )

        if success:
            logger.info(f"System notification sent to {len(admin_emails)} admins")
        else:
            logger.error("Failed to send system notification")

        return success

    except Exception as e:
        logger.error(f"Error sending system notification: {str(e)}")
        return False


def validate_email_config():
    """Validate email configuration"""
    try:
        gmail_user = current_app.config.get('GMAIL_USER')
        gmail_password = current_app.config.get('GMAIL_APP_PASSWORD')

        if not gmail_user or not gmail_password:
            return False, "GMAIL_USER or GMAIL_APP_PASSWORD not configured"

        # Basic email format validation
        import re
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+', gmail_user):
            return False, "GMAIL_USER is not a valid email format"

        if len(gmail_password) != 16:
            return False, "GMAIL_APP_PASSWORD should be 16 characters (without spaces)"

        return True, "Configuration valid"

    except Exception as e:
        return False, f"Configuration check error: {str(e)}"


def format_email_address(email, name=None):
    """Format email address with optional display name"""
    if name:
        return f"{name} <{email}>"
    return email


def extract_email_addresses(email_string):
    """Extract and validate email addresses from comma-separated string"""
    import re

    emails = []
    email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+'

    for email in email_string.split(','):
        email = email.strip()
        if email and re.match(email_pattern, email):
            emails.append(email)

    return emails


def get_email_statistics():
    """Get email sending statistics (would require database logging)"""
    # This would typically query a database table for email logs
    # For now, returning mock data
    return {
        'total_sent': 0,
        'successful': 0,
        'failed': 0,
        'last_send': None
    }