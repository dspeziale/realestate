"""
Blueprint per report e analytics
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from emulator.traccar_framework import TraccarAPI, TraccarException

logger = logging.getLogger('reports_blueprint')

reports_bp = Blueprint('reports', __name__)

def get_traccar_api():
    """Ottiene istanza TraccarAPI dalla sessione"""
    from app import get_traccar_api
    return get_traccar_api()

@reports_bp.route('/')
def reports_index():
    """Pagina principale report"""
    try:
        traccar = get_traccar_api()
        devices = traccar.devices.get_devices()

        return render_template('reports/index.html', devices=devices)

    except TraccarException as e:
        logger.error(f"Errore report index: {e}")
        flash(f'Errore caricamento report: {e}', 'danger')
        return render_template('reports/index.html', devices=[])

@reports_bp.route('/trips')
def trips():
    """Report viaggi"""
    try:
        traccar = get_traccar_api()
        devices = traccar.devices.get_devices()

        trips_data = []

        if request.args.get('generate'):
            device_ids = request.args.getlist('deviceId', type=int)
            from_date = request.args.get('from')
            to_date = request.args.get('to')

            if not device_ids:
                flash('Seleziona almeno un dispositivo', 'warning')
                return render_template('reports/trips.html', devices=devices, trips=[])

            try:
                from_time = datetime.fromisoformat(from_date) if from_date else datetime.now() - timedelta(days=1)
                to_time = datetime.fromisoformat(to_date) if to_date else datetime.now()
            except:
                flash('Formato date non valido', 'danger')
                return render_template('reports/trips.html', devices=devices, trips=[])

            trips_data = traccar.reports.get_trips(
                device_ids=device_ids,
                from_time=from_time,
                to_time=to_time
            )

            # Arricchisci con nomi dispositivi
            device_names = {d['id']: d['name'] for d in devices}
            for trip in trips_data:
                trip['device_name'] = device_names.get(trip.get('deviceId'), f"ID {trip.get('deviceId')}")

                if 'distance' in trip:
                    trip['distance_km'] = trip['distance'] / 1000
                if 'maxSpeed' in trip:
                    trip['maxSpeed_kmh'] = trip['maxSpeed'] * 1.852
                if 'averageSpeed' in trip:
                    trip['averageSpeed_kmh'] = trip['averageSpeed'] * 1.852

            return render_template('reports/trips.html',
                                 devices=devices,
                                 trips=trips_data,
                                 selected_devices=device_ids,
                                 from_date=from_date,
                                 to_date=to_date)

        return render_template('reports/trips.html', devices=devices, trips=[])

    except TraccarException as e:
        logger.error(f"Errore report viaggi: {e}")
        flash(f'Errore generazione report: {e}', 'danger')
        return render_template('reports/trips.html', devices=[], trips=[])

@reports_bp.route('/summary')
def summary():
    """Report riepilogativo"""
    try:
        traccar = get_traccar_api()
        devices = traccar.devices.get_devices()

        summary_data = []

        if request.args.get('generate'):
            device_ids = request.args.getlist('deviceId', type=int)
            from_date = request.args.get('from')
            to_date = request.args.get('to')

            if not device_ids:
                flash('Seleziona almeno un dispositivo', 'warning')
                return render_template('reports/summary.html', devices=devices, summary=[])

            try:
                from_time = datetime.fromisoformat(from_date) if from_date else datetime.now() - timedelta(days=1)
                to_time = datetime.fromisoformat(to_date) if to_date else datetime.now()
            except:
                flash('Formato date non valido', 'danger')
                return render_template('reports/summary.html', devices=devices, summary=[])

            summary_data = traccar.reports.get_summary(
                device_ids=device_ids,
                from_time=from_time,
                to_time=to_time
            )

            # Arricchisci dati
            device_names = {d['id']: d['name'] for d in devices}
            for item in summary_data:
                item['device_name'] = device_names.get(item.get('deviceId'), f"ID {item.get('deviceId')}")

                if 'distance' in item:
                    item['distance_km'] = item['distance'] / 1000
                if 'maxSpeed' in item:
                    item['maxSpeed_kmh'] = item['maxSpeed'] * 1.852
                if 'averageSpeed' in item:
                    item['averageSpeed_kmh'] = item['averageSpeed'] * 1.852

            return render_template('reports/summary.html',
                                 devices=devices,
                                 summary=summary_data,
                                 selected_devices=device_ids,
                                 from_date=from_date,
                                 to_date=to_date)

        return render_template('reports/summary.html', devices=devices, summary=[])

    except TraccarException as e:
        logger.error(f"Errore report riepilogativo: {e}")
        flash(f'Errore generazione report: {e}', 'danger')
        return render_template('reports/summary.html', devices=[], summary=[])