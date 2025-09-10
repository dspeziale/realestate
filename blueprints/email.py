# Filename: blueprints/email.py
# Copyright 2025 SILICONDEV SPA
# Description: Email Blueprint for sending emails

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from services.email_service import GmailService
import os
from werkzeug.utils import secure_filename

# Initialize Blueprint
email_bp = Blueprint('email', __name__, url_prefix='/email')

# Email service instance
email_service = GmailService()


@email_bp.route('/')
@login_required
def index():
    """Email dashboard"""
    if not current_user.is_admin:
        flash('Accesso negato. Solo gli amministratori possono accedere.', 'error')
        return redirect(url_for('index'))

    return render_template('email/index.html')


@email_bp.route('/compose', methods=['GET', 'POST'])
@login_required
def compose():
    """Compose and send email"""
    if not current_user.is_admin:
        flash('Accesso negato. Solo gli amministratori possono inviare email.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            # Get form data
            to_emails = request.form.get('to_emails', '').strip()
            cc_emails = request.form.get('cc_emails', '').strip()
            bcc_emails = request.form.get('bcc_emails', '').strip()
            subject = request.form.get('subject', '').strip()
            body = request.form.get('body', '').strip()
            html_body = request.form.get('html_body', '').strip()
            from_name = request.form.get('from_name', '').strip()

            # Validation
            if not to_emails:
                flash('Destinatario richiesto.', 'error')
                return render_template('email/compose.html')

            if not subject:
                flash('Oggetto richiesto.', 'error')
                return render_template('email/compose.html')

            if not body and not html_body:
                flash('Contenuto email richiesto.', 'error')
                return render_template('email/compose.html')

            # Process email lists
            to_list = [email.strip() for email in to_emails.split(',') if email.strip()]
            cc_list = [email.strip() for email in cc_emails.split(',') if email.strip()] if cc_emails else None
            bcc_list = [email.strip() for email in bcc_emails.split(',') if email.strip()] if bcc_emails else None

            # Handle file attachments
            attachments = []
            uploaded_files = request.files.getlist('attachments')
            upload_folder = os.path.join(os.getcwd(), 'temp_attachments')

            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)

            for file in uploaded_files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(upload_folder, filename)
                    file.save(file_path)
                    attachments.append(file_path)

            # Send email
            success = email_service.send_email(
                to_emails=to_list,
                subject=subject,
                body=body or "Vedi contenuto HTML",
                html_body=html_body if html_body else None,
                cc_emails=cc_list,
                bcc_emails=bcc_list,
                attachments=attachments if attachments else None,
                from_name=from_name if from_name else None
            )

            # Clean up temporary files
            for file_path in attachments:
                try:
                    os.remove(file_path)
                except:
                    pass

            if success:
                flash('Email inviata con successo!', 'success')
                return redirect(url_for('email.index'))
            else:
                flash('Errore durante l\'invio dell\'email.', 'error')

        except Exception as e:
            flash(f'Errore: {str(e)}', 'error')

    return render_template('email/compose.html')


@email_bp.route('/test', methods=['GET', 'POST'])
@login_required
def test():
    """Test email configuration"""
    if not current_user.is_admin:
        flash('Accesso negato.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            test_email = request.form.get('test_email', current_user.email)

            success = email_service.send_email(
                to_emails=test_email,
                subject="Test Email - Configurazione Gmail",
                body="Questa è una email di test per verificare la configurazione Gmail.\n\nSe ricevi questo messaggio, la configurazione è corretta!",
                html_body="""
                <html>
                <body>
                    <h2>Test Email</h2>
                    <p>Questa è una email di test per verificare la configurazione Gmail.</p>
                    <p><strong>Se ricevi questo messaggio, la configurazione è corretta!</strong></p>
                    <hr>
                    <p><em>Inviato dal sistema di gestione aste immobiliari</em></p>
                </body>
                </html>
                """,
                from_name="Sistema Aste Immobiliari"
            )

            if success:
                flash('Email di test inviata con successo!', 'success')
            else:
                flash('Errore durante l\'invio dell\'email di test.', 'error')

        except Exception as e:
            flash(f'Errore: {str(e)}', 'error')

    return render_template('email/test.html')


@email_bp.route('/templates')
@login_required
def templates():
    """Email templates management"""
    if not current_user.is_admin:
        flash('Accesso negato.', 'error')
        return redirect(url_for('index'))

    # List available email templates
    templates_dir = os.path.join(os.getcwd(), 'templates', 'emails')
    available_templates = []

    if os.path.exists(templates_dir):
        for filename in os.listdir(templates_dir):
            if filename.endswith('.html'):
                available_templates.append({
                    'name': filename,
                    'display_name': filename.replace('.html', '').replace('_', ' ').title()
                })

    return render_template('email/templates.html', templates=available_templates)


@email_bp.route('/send-template', methods=['POST'])
@login_required
def send_template():
    """Send email using template"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accesso negato'}), 403

    try:
        data = request.get_json()

        template_name = data.get('template')
        to_emails = data.get('to_emails', [])
        context = data.get('context', {})
        subject = data.get('subject', '')

        if not template_name or not to_emails or not subject:
            return jsonify({'success': False, 'message': 'Dati richiesti mancanti'}), 400

        success = email_service.send_template_email(
            to_emails=to_emails,
            template_name=f'emails/{template_name}',
            context=context,
            subject=subject,
            from_name="Sistema Aste Immobiliari"
        )

        if success:
            return jsonify({'success': True, 'message': 'Email inviata con successo'})
        else:
            return jsonify({'success': False, 'message': 'Errore durante l\'invio'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@email_bp.route('/config')
@login_required
def config():
    """Display email configuration status"""
    if not current_user.is_admin:
        flash('Accesso negato.', 'error')
        return redirect(url_for('index'))

    from flask import current_app

    config_status = {
        'gmail_user': bool(current_app.config.get('GMAIL_USER')),
        'gmail_password': bool(current_app.config.get('GMAIL_APP_PASSWORD')),
        'gmail_user_value': current_app.config.get('GMAIL_USER', 'Non configurato')
    }

    return render_template('email/config.html', config=config_status)