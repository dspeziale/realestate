#!/usr/bin/env python3
"""
Traccar Fleet Management Web Application
========================================

Applicazione Flask per gestione completa flotta Traccar
"""

import os
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
from flask_session import Session
import requests

# Import blueprint
from blueprints.devices import devices_bp
from blueprints.positions import positions_bp
from blueprints.reports import reports_bp
from blueprints.api import api_bp

# Import framework esistente
from emulator.traccar_framework import TraccarAPI, TraccarException

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TraccarFleetApp')


def create_app():
    """Factory per creare l'applicazione Flask"""
    app = Flask(__name__)

    # Configurazione base
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'change-this-in-production'),
        SESSION_TYPE='filesystem',
        SESSION_PERMANENT=False,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=24)
    )

    # Configurazione Traccar
    app.config.update(
        TRACCAR_HOST=os.environ.get('TRACCAR_HOST', 'torraccia.iliadboxos.it'),
        TRACCAR_PORT=int(os.environ.get('TRACCAR_PORT', 58082)),
        TRACCAR_USERNAME=os.environ.get('TRACCAR_USERNAME', 'dspeziale@gmail.com'),
        TRACCAR_PASSWORD=os.environ.get('TRACCAR_PASSWORD', 'Elisa2025!')
    )

    # Inizializza sessioni
    Session(app)

    # Registra blueprint
    app.register_blueprint(devices_bp, url_prefix='/devices')
    app.register_blueprint(positions_bp, url_prefix='/positions')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(api_bp, url_prefix='/api')

    return app


# Crea l'app
app = create_app()


def get_traccar_api():
    """Ottiene istanza TraccarAPI configurata"""
    return TraccarAPI(
        host=app.config['TRACCAR_HOST'],
        port=app.config['TRACCAR_PORT'],
        username=app.config['TRACCAR_USERNAME'],
        password=app.config['TRACCAR_PASSWORD'],
        debug=False
    )


@app.before_request
def before_request():
    """Middleware per autenticazione"""
    public_endpoints = ['login', 'static']

    if request.endpoint not in public_endpoints and 'user_id' not in session:
        if request.is_json:
            return jsonify({'error': 'Authentication required'}), 401
        return redirect(url_for('login'))


@app.context_processor
def inject_template_vars():
    """Inietta variabili globali nei template"""
    return {
        'app_name': 'Traccar Fleet Manager',
        'app_version': '1.0.0',
        'current_user': session.get('user_name', 'Guest'),
        'user_email': session.get('user_email', ''),
        'is_admin': session.get('is_admin', False),
        'current_year': datetime.now().year
    }


@app.route('/')
@app.route('/dashboard')
def dashboard():
    """Dashboard principale"""
    try:
        traccar = get_traccar_api()
        devices = traccar.devices.get_devices()

        # Statistiche dispositivi
        online_devices = sum(1 for d in devices if d.get('status') == 'online')
        offline_devices = len(devices) - online_devices

        # Ultime posizioni per dispositivi online
        recent_positions = []
        for device in devices[:10]:
            try:
                if device.get('status') == 'online':
                    positions = traccar.positions.get_positions(device_id=device['id'], limit=1)
                    if positions:
                        recent_positions.append({
                            'device': device,
                            'position': positions[0]
                        })
            except Exception as e:
                logger.warning(f"Errore posizioni device {device.get('id')}: {e}")

        dashboard_stats = {
            'total_devices': len(devices),
            'online_devices': online_devices,
            'offline_devices': offline_devices,
            'recent_alerts': 0
        }

        return render_template('dashboard.html',
                               stats=dashboard_stats,
                               devices=devices[:10],
                               recent_positions=recent_positions[:10])

    except TraccarException as e:
        logger.error(f"Errore Traccar dashboard: {e}")
        flash(f'Errore connessione Traccar: {e}', 'danger')
        return render_template('dashboard.html',
                               stats={'total_devices': 0, 'online_devices': 0, 'offline_devices': 0,
                                      'recent_alerts': 0},
                               devices=[], recent_positions=[])


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Gestione login"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Username e password sono richiesti', 'danger')
            return render_template('auth/login.html')

        try:
            # Test connessione con credenziali
            traccar = TraccarAPI(
                host=app.config['TRACCAR_HOST'],
                port=app.config['TRACCAR_PORT'],
                username=username,
                password=password,
                debug=False
            )

            if traccar.test_connection():
                # Ottieni info utente
                user_info = traccar.session.get_session()

                # Salva in sessione
                session.permanent = True
                session['user_id'] = user_info.get('id')
                session['user_name'] = user_info.get('name', username)
                session['user_email'] = user_info.get('email', username)
                session['is_admin'] = user_info.get('administrator', False)

                # ✅ SALVA LE CREDENZIALI TRACCAR PER RIUTILIZZO
                session['traccar_host'] = app.config['TRACCAR_HOST']
                session['traccar_port'] = app.config['TRACCAR_PORT']
                session['traccar_username'] = username
                session['traccar_password'] = password

                flash(f'Benvenuto, {session["user_name"]}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Credenziali non valide', 'danger')

        except TraccarException as e:
            flash(f'Errore autenticazione: {e}', 'danger')
        except Exception as e:
            logger.error(f'Errore login: {e}')
            flash('Errore durante il login', 'danger')

    return render_template('auth/login.html')


@app.route('/logout')
def logout():
    """Logout utente"""
    user_name = session.get('user_name', 'Utente')
    session.clear()
    flash(f'Arrivederci, {user_name}!', 'info')
    return redirect(url_for('login'))


# ✅ AGGIUNTA ROUTE PROFILE MANCANTE
@app.route('/profile')
def profile():
    """Pagina profilo utente"""
    try:
        traccar = get_traccar_api()

        # Ottieni informazioni aggiornate dell'utente
        user_info = traccar.session.get_session()

        # Statistiche utente
        user_stats = {
            'devices_count': 0,
            'last_login': session.get('login_time', datetime.now()),
            'session_duration': 'N/A'
        }

        try:
            devices = traccar.devices.get_devices()
            user_stats['devices_count'] = len(devices)
        except:
            pass

        return render_template('auth/profile.html',
                               user_info=user_info,
                               user_stats=user_stats)

    except TraccarException as e:
        logger.error(f"Errore caricamento profilo: {e}")
        flash(f'Errore caricamento profilo: {e}', 'danger')
        return redirect(url_for('dashboard'))


# ✅ ROUTE PER AGGIORNAMENTO PROFILO
@app.route('/profile/update', methods=['POST'])
def update_profile():
    """Aggiornamento informazioni profilo"""
    try:
        traccar = get_traccar_api()

        # Dati dal form
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()

        if not name or not email:
            flash('Nome e email sono richiesti', 'danger')
            return redirect(url_for('profile'))

        # Ottieni ID utente corrente
        user_id = session.get('user_id')
        if not user_id:
            flash('Errore: utente non identificato', 'danger')
            return redirect(url_for('login'))

        # Aggiorna dati utente (se supportato dall'API)
        update_data = {
            'id': user_id,
            'name': name,
            'email': email
        }

        # Nota: Questo dipende dall'API Traccar disponibile
        # Alcuni server potrebbero non permettere l'aggiornamento del profilo
        try:
            # Tentativo di aggiornamento (potrebbe non essere supportato)
            result = traccar.session.update_user(user_id, update_data)

            # Aggiorna sessione locale
            session['user_name'] = name
            session['user_email'] = email

            flash('Profilo aggiornato con successo', 'success')

        except Exception as api_error:
            logger.warning(f"API update non supportata: {api_error}")
            # Aggiorna solo la sessione locale
            session['user_name'] = name
            session['user_email'] = email
            flash('Profilo aggiornato localmente (alcune modifiche potrebbero non essere permanenti)', 'warning')

        return redirect(url_for('profile'))

    except Exception as e:
        logger.error(f"Errore aggiornamento profilo: {e}")
        flash('Errore durante l\'aggiornamento', 'danger')
        return redirect(url_for('profile'))


# ✅ ROUTE DASHBOARD ALIAS
@app.route('/index')
def index():
    """Alias per dashboard"""
    return redirect(url_for('dashboard'))


@app.template_filter('speed_format')
def speed_format(speed_knots):
    """Converte velocità da nodi a km/h e formatta"""
    if speed_knots is None or speed_knots == 0:
        return "0 km/h"

    try:
        speed_kmh = float(speed_knots) * 1.852
        return f"{speed_kmh:.1f} km/h"
    except (ValueError, TypeError):
        return "0 km/h"


@app.template_filter('format_datetime')
def format_datetime_filter(value, format='%d/%m/%Y %H:%M'):
    """Alias per datetime_format per compatibilità"""
    return datetime_format(value, format)


@app.template_filter('datetime_format')
def datetime_format(value, format='%d/%m/%Y %H:%M'):
    """Formatta datetime"""
    if isinstance(value, str):
        try:
            # Gestione ISO format con timezone
            if 'T' in value:
                value = value.replace('Z', '+00:00')
                value = datetime.fromisoformat(value)
            else:
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except:
            return str(value)  # Ritorna stringa originale se non parsabile

    if isinstance(value, datetime):
        return value.strftime(format)
    return str(value)


@app.template_filter('status_badge')
def status_badge(status):
    """Converte status in badge Bootstrap"""
    status_map = {
        'online': 'success',
        'offline': 'secondary',
        'unknown': 'warning',
        'moving': 'primary',
        'stopped': 'info'
    }
    badge_class = status_map.get(str(status).lower(), 'secondary')
    status_text = str(status).title()
    return f'<span class="badge badge-{badge_class}">{status_text}</span>'


# ✅ ERROR HANDLERS
@app.errorhandler(404)
def not_found_error(error):
    """Gestione errori 404"""
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Gestione errori 500"""
    logger.error(f"Errore interno: {error}")
    return render_template('errors/500.html'), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)