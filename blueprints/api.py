"""
Blueprint per API JSON
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, session
from emulator.traccar_framework import TraccarAPI, TraccarException

logger = logging.getLogger('api_blueprint')

api_bp = Blueprint('api', __name__)


def get_traccar_api():
    """Ottiene istanza TraccarAPI dalla sessione"""
    from app import get_traccar_api
    return get_traccar_api()

# AGGIUNTA in blueprints/api.py - Aggiungi questo endpoint dopo get_device_positions:

@api_bp.route('/device/stats')
def get_device_stats():
    """Statistiche dei dispositivi (alias per dashboard stats)"""
    try:
        traccar = get_traccar_api()
        devices = traccar.devices.get_devices()

        online_devices = sum(1 for d in devices if d.get('status') == 'online')
        offline_devices = len(devices) - online_devices
        moving_devices = 0

        # Calcola dispositivi in movimento
        for device in devices[:10]:  # Limite per performance
            try:
                if device.get('status') == 'online':
                    positions = traccar.positions.get_positions(device_id=device['id'], limit=1)
                    if positions:
                        speed = float(positions[0].get('speed', 0)) * 1.852
                        if speed > 5:
                            moving_devices += 1
            except:
                pass

        return jsonify({
            'success': True,
            'total': len(devices),          # Per compatibilità con template
            'online': online_devices,       # Per compatibilità con template
            'offline': offline_devices,     # Per compatibilità con template
            'moving': moving_devices,       # Per compatibilità con template
            'total_devices': len(devices),  # Nome corretto
            'online_devices': online_devices,
            'offline_devices': offline_devices,
            'moving_devices': moving_devices,
            'timestamp': datetime.now().isoformat()
        })

    except TraccarException as e:
        logger.error(f"Errore API device stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/dashboard/stats')
def get_dashboard_stats():
    """Statistiche dashboard in tempo reale"""
    try:
        traccar = get_traccar_api()
        devices = traccar.devices.get_devices()

        online_devices = sum(1 for d in devices if d.get('status') == 'online')
        offline_devices = len(devices) - online_devices
        moving_devices = 0

        # Calcola dispositivi in movimento
        for device in devices[:10]:  # Limite per performance
            try:
                if device.get('status') == 'online':
                    positions = traccar.positions.get_positions(device_id=device['id'], limit=1)
                    if positions:
                        speed = float(positions[0].get('speed', 0)) * 1.852
                        if speed > 5:
                            moving_devices += 1
            except:
                pass

        return jsonify({
            'success': True,
            'total_devices': len(devices),
            'online_devices': online_devices,
            'offline_devices': offline_devices,
            'moving_devices': moving_devices,
            'recent_alerts': 0,
            'timestamp': datetime.now().isoformat()
        })

    except TraccarException as e:
        logger.error(f"Errore API dashboard: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/devices/positions')
def get_device_positions():
    """Posizioni attuali di tutti i dispositivi per mappa"""
    try:
        traccar = get_traccar_api()
        devices = traccar.devices.get_devices()

        device_positions = []

        for device in devices:
            try:
                positions = traccar.positions.get_positions(device_id=device['id'], limit=1)
                last_position = positions[0] if positions else None

                status = device.get('status', 'unknown')
                speed_kmh = 0

                if last_position:
                    speed_knots = last_position.get('speed', 0)
                    speed_kmh = float(speed_knots) * 1.852

                    if speed_kmh > 5:
                        status = 'moving'
                    elif status == 'online':
                        status = 'stopped'

                device_positions.append({
                    'deviceId': device['id'],
                    'deviceName': device['name'],
                    'uniqueId': device['uniqueId'],
                    'status': status,
                    'speed': speed_kmh,
                    'position': {
                        'latitude': last_position.get('latitude') if last_position else None,
                        'longitude': last_position.get('longitude') if last_position else None,
                        'serverTime': last_position.get('serverTime') if last_position else None,
                        'address': last_position.get('address', '') if last_position else ''
                    } if last_position else None
                })

            except Exception as e:
                logger.warning(f"Errore posizione dispositivo {device['id']}: {e}")
                device_positions.append({
                    'deviceId': device['id'],
                    'deviceName': device['name'],
                    'uniqueId': device['uniqueId'],
                    'status': 'error',
                    'speed': 0,
                    'position': None
                })

        return jsonify(device_positions)

    except TraccarException as e:
        logger.error(f"Errore API posizioni: {e}")
        return jsonify([]), 500


@api_bp.route('/health')
def health_check():
    """Health check dell'applicazione"""
    try:
        traccar = get_traccar_api()
        traccar_ok = traccar.test_connection()

        status = 'healthy' if traccar_ok else 'degraded'

        return jsonify({
            'status': status,
            'timestamp': datetime.now().isoformat(),
            'services': {
                'traccar': traccar_ok,
                'session': 'user_id' in session
            }
        }), 200 if traccar_ok else 503

    except Exception as e:
        logger.error(f"Errore health check: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503