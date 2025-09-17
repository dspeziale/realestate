"""
Blueprint per gestione posizioni e tracking
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from emulator.traccar_framework import TraccarAPI, TraccarException

logger = logging.getLogger('positions_blueprint')

positions_bp = Blueprint('positions', __name__)


def get_traccar_api():
    """Ottiene istanza TraccarAPI dalla sessione"""
    from app import get_traccar_api
    return get_traccar_api()


@positions_bp.route('/live')
def live_tracking():
    """Tracking live di tutti i dispositivi su mappa"""
    try:
        traccar = get_traccar_api()
        devices = traccar.devices.get_devices()

        device_positions = []

        for device in devices:
            try:
                positions = traccar.positions.get_positions(device_id=device['id'], limit=1)
                last_position = positions[0] if positions else None

                if last_position:
                    speed_knots = last_position.get('speed', 0)
                    speed_kmh = float(speed_knots) * 1.852

                    status = 'moving' if speed_kmh > 5 else 'stopped'
                    if device.get('status') == 'offline':
                        status = 'offline'

                    device_positions.append({
                        'device': device,
                        'position': last_position,
                        'status': status,
                        'speed_kmh': speed_kmh
                    })
                else:
                    device_positions.append({
                        'device': device,
                        'position': None,
                        'status': 'offline',
                        'speed_kmh': 0
                    })

            except Exception as e:
                logger.warning(f"Errore posizione dispositivo {device['id']}: {e}")

        return render_template('positions/live_tracking.html',
                               devices=devices,
                               device_positions=device_positions)

    except TraccarException as e:
        logger.error(f"Errore live tracking: {e}")
        flash(f'Errore caricamento tracking: {e}', 'danger')
        return render_template('positions/live_tracking.html', devices=[], device_positions=[])


@positions_bp.route('/history')
def position_history():
    """Storico posizioni con filtri"""
    try:
        traccar = get_traccar_api()
        devices = traccar.devices.get_devices()

        positions_data = []

        # Se richiesta con parametri, carica storico
        if request.args.get('load'):
            device_id = request.args.get('deviceId', type=int)
            from_date = request.args.get('from')
            to_date = request.args.get('to')

            if not device_id:
                flash('Seleziona un dispositivo', 'warning')
                return render_template('positions/history.html', devices=devices, positions=[])

            try:
                if from_date and to_date:
                    from_time = datetime.fromisoformat(from_date)
                    to_time = datetime.fromisoformat(to_date)
                else:
                    to_time = datetime.now()
                    from_time = to_time - timedelta(days=1)
            except:
                flash('Formato date non valido', 'danger')
                return render_template('positions/history.html', devices=devices, positions=[])

            positions_data = traccar.positions.get_positions(
                device_id=device_id,
                from_time=from_time,
                to_time=to_time
            )

            # Trova nome dispositivo
            device_name = f"Dispositivo {device_id}"
            try:
                device = next(d for d in devices if d['id'] == device_id)
                device_name = device['name']
            except:
                pass

            return render_template('positions/history.html',
                                   devices=devices,
                                   positions=positions_data,
                                   selected_device_id=device_id,
                                   device_name=device_name,
                                   from_date=from_date,
                                   to_date=to_date)

        return render_template('positions/history.html', devices=devices, positions=[])

    except TraccarException as e:
        logger.error(f"Errore storico posizioni: {e}")
        flash(f'Errore caricamento storico: {e}', 'danger')
        return render_template('positions/history.html', devices=[], positions=[])