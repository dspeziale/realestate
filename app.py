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

@app.template_filter('datetime_to_timestamp')
def datetime_to_timestamp(datetime_str):
    """Converte datetime ISO string in timestamp Unix"""
    if not datetime_str:
        return 0
    try:
        if isinstance(datetime_str, str):
            dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        else:
            dt = datetime_str
        return dt.timestamp()
    except:
        return 0

@app.template_filter('tojson')
def to_json_filter(obj):
    """Converte oggetto in JSON per JavaScript"""
    import json
    return json.dumps(obj, default=str)


@app.template_filter('datetime_format')
def datetime_format(value, format='%d/%m/%Y %H:%M'):
    """Formatta datetime con gestione migliorata"""
    if not value:
        return 'N/A'

    if isinstance(value, str):
        try:
            # Gestisci diversi formati ISO
            if 'T' in value:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except:
            return value

    if isinstance(value, datetime):
        return value.strftime(format)
    return str(value)

@app.route('/')
def dashboard():
    """Dashboard principale"""
    try:
        traccar = get_traccar_api()

        # Statistiche generali
        devices = traccar.devices.get_devices()

        online_devices = sum(1 for d in devices if d.get('status') == 'online')
        offline_devices = len(devices) - online_devices

        # Ultime posizioni
        recent_positions = []
        try:
            for device in devices[:5]:  # Prime 5 devices
                positions = traccar.positions.get_positions(device_id=device['id'], limit=1)
                if positions:
                    recent_positions.extend(positions)
        except:
            pass

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

                flash(f'Benvenuto, {session["user_name"]}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Credenziali non valide', 'danger')

        except TraccarException as e:
            flash(f'Errore autenticazione: {e}', 'danger')
        except Exception as e:
            flash('Errore durante il login', 'danger')

    return render_template('auth/login.html')


@app.route('/logout')
def logout():
    """Logout utente"""
    user_name = session.get('user_name', 'Utente')
    session.clear()
    flash(f'Arrivederci, {user_name}!', 'info')
    return redirect(url_for('login'))


@app.template_filter('datetime_format')
def datetime_format(value, format='%d/%m/%Y %H:%M'):
    """Formatta datetime"""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value

    if isinstance(value, datetime):
        return value.strftime(format)
    return value


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
    badge_class = status_map.get(status, 'secondary')
    return f'<span class="badge badge-{badge_class}">{status.title()}</span>'


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)