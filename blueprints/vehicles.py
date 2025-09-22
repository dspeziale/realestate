# blueprints/vehicles.py - VERSIONE COMPLETA CON TUTTE LE ROUTE

from flask import Blueprint, render_template, current_app, redirect, url_for, flash, jsonify, request, Response
from core.traccar_framework import TraccarException
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

vehicles_bp = Blueprint('vehicles', __name__, template_folder='../templates')


def login_required(f):
    """Decorator to check if user is logged in"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import session
        if 'user' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated_function


@vehicles_bp.route('/')
@login_required
def list():
    """Lista veicoli con dettagli live"""
    traccar = current_app.config['TRACCAR_API']

    try:
        devices = traccar.devices.get_devices()

        # Arricchisci ogni veicolo con dati live
        for device in devices:
            try:
                # Ultima posizione
                positions = traccar.positions.get_positions(device_id=device['id'])
                device['latest_position'] = positions[-1] if positions else None

                # Calcola tempo dall'ultimo aggiornamento
                if device.get('lastUpdate'):
                    last_update = datetime.fromisoformat(device['lastUpdate'].replace('Z', '+00:00'))
                    now = datetime.now(last_update.tzinfo)
                    diff_minutes = int((now - last_update).total_seconds() / 60)
                    device['minutes_ago'] = diff_minutes
                else:
                    device['minutes_ago'] = None

            except Exception as e:
                logger.warning(f"Error loading data for device {device['id']}: {e}")
                device['latest_position'] = None
                device['minutes_ago'] = None

        # Ordina per stato (online prima) e poi per nome
        devices.sort(key=lambda x: (x['status'] != 'online', x['name']))

        return render_template('vehicles/list.html', vehicles=devices)

    except TraccarException as e:
        flash(f'Error loading vehicles: {str(e)}', 'error')
        return render_template('vehicles/list.html', vehicles=[])


@vehicles_bp.route('/<int:vehicle_id>')
@login_required
def detail(vehicle_id):
    """Dettagli completi del veicolo"""
    traccar = current_app.config['TRACCAR_API']

    try:
        # Carica il veicolo
        devices = traccar.devices.get_devices()
        vehicle = next((d for d in devices if d['id'] == vehicle_id), None)

        if not vehicle:
            flash('Vehicle not found', 'error')
            return redirect(url_for('vehicles.list'))

        # Posizioni ultime 24h
        from_time = datetime.now() - timedelta(days=1)
        to_time = datetime.now()

        positions = traccar.positions.get_positions(
            device_id=vehicle_id,
            from_time=from_time,
            to_time=to_time
        )

        # Summary report
        try:
            summary = traccar.reports.get_summary_report(
                device_ids=[vehicle_id],
                from_time=from_time,
                to_time=to_time
            )
            vehicle['summary_24h'] = summary[0] if summary else None
        except Exception as e:
            logger.warning(f"Error loading summary for vehicle {vehicle_id}: {e}")
            vehicle['summary_24h'] = None

        # Trip report
        try:
            trips = traccar.reports.get_trips_report(
                device_ids=[vehicle_id],
                from_time=from_time,
                to_time=to_time
            )
            vehicle['trips'] = trips[:10]  # Ultimi 10 viaggi
        except Exception as e:
            logger.warning(f"Error loading trips for vehicle {vehicle_id}: {e}")
            vehicle['trips'] = []

        return render_template('vehicles/detail.html',
                               vehicle=vehicle,
                               positions=positions)

    except TraccarException as e:
        flash(f'Error loading vehicle details: {str(e)}', 'error')
        return redirect(url_for('vehicles.list'))


@vehicles_bp.route('/<int:vehicle_id>/live')
@login_required
def live_tracking(vehicle_id):
    """Tracking live del veicolo"""
    traccar = current_app.config['TRACCAR_API']

    try:
        devices = traccar.devices.get_devices()
        vehicle = next((d for d in devices if d['id'] == vehicle_id), None)

        if not vehicle:
            flash('Vehicle not found', 'error')
            return redirect(url_for('vehicles.list'))

        # Posizioni ultime 6 ore
        from_time = datetime.now() - timedelta(hours=6)
        to_time = datetime.now()

        positions = traccar.positions.get_positions(
            device_id=vehicle_id,
            from_time=from_time,
            to_time=to_time
        )

        return render_template('vehicles/live_tracking.html',
                               vehicle=vehicle,
                               positions=positions)

    except TraccarException as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('vehicles.detail', vehicle_id=vehicle_id))


@vehicles_bp.route('/<int:vehicle_id>/history')
@login_required
def history(vehicle_id):
    """Storico posizioni e viaggi del veicolo"""
    traccar = current_app.config['TRACCAR_API']

    try:
        # Carica il veicolo
        devices = traccar.devices.get_devices()
        vehicle = next((d for d in devices if d['id'] == vehicle_id), None)

        if not vehicle:
            flash('Vehicle not found', 'error')
            return redirect(url_for('vehicles.list'))

        # Parametri dalla query string
        days = request.args.get('days', default=7, type=int)
        if days > 30:
            days = 30  # Limite massimo

        from_time = datetime.now() - timedelta(days=days)
        to_time = datetime.now()

        # Carica posizioni
        positions = traccar.positions.get_positions(
            device_id=vehicle_id,
            from_time=from_time,
            to_time=to_time
        )

        # Carica report viaggi
        trips = []
        try:
            trips_data = traccar.reports.get_trips_report(
                device_ids=[vehicle_id],
                from_time=from_time,
                to_time=to_time
            )
            trips = trips_data[:50]  # Limita a 50 viaggi
        except Exception as e:
            logger.warning(f"Error loading trips: {e}")

        # Carica report soste
        stops = []
        try:
            stops_data = traccar.reports.get_stops_report(
                device_ids=[vehicle_id],
                from_time=from_time,
                to_time=to_time
            )
            stops = stops_data[:20]  # Limita a 20 soste
        except Exception as e:
            logger.warning(f"Error loading stops: {e}")

        # Summary report
        summary = {}
        try:
            summary_data = traccar.reports.get_summary_report(
                device_ids=[vehicle_id],
                from_time=from_time,
                to_time=to_time
            )
            summary = summary_data[0] if summary_data else {}
        except Exception as e:
            logger.warning(f"Error loading summary: {e}")

        return render_template('vehicles/history.html',
                               vehicle=vehicle,
                               positions=positions,
                               trips=trips,
                               stops=stops,
                               summary=summary,
                               days=days,
                               from_date=from_time.strftime('%Y-%m-%d'),
                               to_date=to_time.strftime('%Y-%m-%d'))

    except TraccarException as e:
        flash(f'Error loading vehicle history: {str(e)}', 'error')
        return redirect(url_for('vehicles.detail', vehicle_id=vehicle_id))