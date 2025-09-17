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


# ✅ CORREZIONE: Rinomina da position_history a history per compatibilità
@positions_bp.route('/history')
def history():
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

            try:
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

                # Aggiungi statistiche sulla rotta
                route_stats = {
                    'total_points': len(positions_data),
                    'distance_km': 0,
                    'max_speed_kmh': 0,
                    'avg_speed_kmh': 0,
                    'duration_hours': 0
                }

                if positions_data:
                    # Calcola statistiche di base
                    speeds = [float(p.get('speed', 0)) * 1.852 for p in positions_data]
                    route_stats['max_speed_kmh'] = max(speeds) if speeds else 0
                    route_stats['avg_speed_kmh'] = sum(speeds) / len(speeds) if speeds else 0

                    # Calcola durata
                    if len(positions_data) > 1:
                        try:
                            start_time = datetime.fromisoformat(positions_data[-1].get('deviceTime', '').replace('Z', '+00:00'))
                            end_time = datetime.fromisoformat(positions_data[0].get('deviceTime', '').replace('Z', '+00:00'))
                            duration = end_time - start_time
                            route_stats['duration_hours'] = duration.total_seconds() / 3600
                        except:
                            pass

                return render_template('positions/history.html',
                                       devices=devices,
                                       positions=positions_data,
                                       selected_device_id=device_id,
                                       device_name=device_name,
                                       route_stats=route_stats,
                                       from_date=from_date,
                                       to_date=to_date)

            except Exception as e:
                logger.error(f"Errore caricamento posizioni: {e}")
                flash(f'Errore caricamento posizioni: {e}', 'danger')
                return render_template('positions/history.html', devices=devices, positions=[])

        return render_template('positions/history.html', devices=devices, positions=[])

    except TraccarException as e:
        logger.error(f"Errore storico posizioni: {e}")
        flash(f'Errore caricamento storico: {e}', 'danger')
        return render_template('positions/history.html', devices=[], positions=[])


# ✅ AGGIUNTA: Alias per compatibilità con vecchi riferimenti
@positions_bp.route('/position_history')
def position_history():
    """Alias per history() per compatibilità"""
    return redirect(url_for('positions.history', **request.args))


@positions_bp.route('/api/live')
def api_live_positions():
    """API JSON per posizioni live (per aggiornamenti AJAX)"""
    try:
        traccar = get_traccar_api()
        devices = traccar.devices.get_devices()

        device_positions = []

        for device in devices[:20]:  # Limite per performance
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
                    'uniqueId': device.get('uniqueId', ''),
                    'status': status,
                    'speed_kmh': speed_kmh,
                    'last_update': last_position.get('deviceTime', '') if last_position else '',
                    'position': {
                        'latitude': last_position.get('latitude') if last_position else None,
                        'longitude': last_position.get('longitude') if last_position else None,
                        'accuracy': last_position.get('accuracy') if last_position else None,
                        'altitude': last_position.get('altitude') if last_position else None,
                        'course': last_position.get('course') if last_position else None
                    }
                })

            except Exception as e:
                logger.warning(f"API: Errore posizione dispositivo {device['id']}: {e}")

        return jsonify({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'device_count': len(device_positions),
            'positions': device_positions
        })

    except Exception as e:
        logger.error(f"Errore API live positions: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@positions_bp.route('/api/history')
def api_history():
    """API JSON per storico posizioni"""
    try:
        traccar = get_traccar_api()

        device_id = request.args.get('deviceId', type=int)
        from_date = request.args.get('from')
        to_date = request.args.get('to')
        limit = request.args.get('limit', 1000, type=int)

        if not device_id:
            return jsonify({'success': False, 'error': 'Device ID richiesto'}), 400

        try:
            if from_date and to_date:
                from_time = datetime.fromisoformat(from_date)
                to_time = datetime.fromisoformat(to_date)
            else:
                to_time = datetime.now()
                from_time = to_time - timedelta(days=1)
        except:
            return jsonify({'success': False, 'error': 'Formato date non valido'}), 400

        positions = traccar.positions.get_positions(
            device_id=device_id,
            from_time=from_time,
            to_time=to_time,
            limit=limit
        )

        # Formatta posizioni per risposta JSON
        formatted_positions = []
        for pos in positions:
            formatted_positions.append({
                'latitude': pos.get('latitude'),
                'longitude': pos.get('longitude'),
                'speed_kmh': float(pos.get('speed', 0)) * 1.852,
                'course': pos.get('course'),
                'altitude': pos.get('altitude'),
                'accuracy': pos.get('accuracy'),
                'timestamp': pos.get('deviceTime'),
                'server_time': pos.get('serverTime'),
                'valid': pos.get('valid', True)
            })

        return jsonify({
            'success': True,
            'device_id': device_id,
            'from_time': from_time.isoformat(),
            'to_time': to_time.isoformat(),
            'position_count': len(formatted_positions),
            'positions': formatted_positions
        })

    except Exception as e:
        logger.error(f"Errore API history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@positions_bp.route('/export/<int:device_id>')
def export_positions(device_id):
    """Esportazione posizioni in CSV"""
    try:
        traccar = get_traccar_api()

        from_date = request.args.get('from')
        to_date = request.args.get('to')

        try:
            if from_date and to_date:
                from_time = datetime.fromisoformat(from_date)
                to_time = datetime.fromisoformat(to_date)
            else:
                to_time = datetime.now()
                from_time = to_time - timedelta(days=1)
        except:
            flash('Formato date non valido', 'danger')
            return redirect(url_for('positions.history'))

        positions = traccar.positions.get_positions(
            device_id=device_id,
            from_time=from_time,
            to_time=to_time
        )

        if not positions:
            flash('Nessuna posizione trovata per l\'esportazione', 'warning')
            return redirect(url_for('positions.history'))

        # Genera CSV
        from io import StringIO
        import csv
        from flask import make_response

        output = StringIO()
        writer = csv.writer(output)

        # Header CSV
        writer.writerow([
            'Timestamp', 'Latitude', 'Longitude', 'Speed (km/h)',
            'Course', 'Altitude', 'Accuracy', 'Valid'
        ])

        # Dati
        for pos in positions:
            writer.writerow([
                pos.get('deviceTime', ''),
                pos.get('latitude', ''),
                pos.get('longitude', ''),
                f"{float(pos.get('speed', 0)) * 1.852:.2f}",
                pos.get('course', ''),
                pos.get('altitude', ''),
                pos.get('accuracy', ''),
                'Yes' if pos.get('valid', True) else 'No'
            ])

        # Prepara risposta CSV
        csv_data = output.getvalue()
        output.close()

        response = make_response(csv_data)
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=positions_{device_id}_{from_time.strftime("%Y%m%d")}_{to_time.strftime("%Y%m%d")}.csv'

        return response

    except Exception as e:
        logger.error(f"Errore esportazione posizioni: {e}")
        flash('Errore durante l\'esportazione', 'danger')
        return redirect(url_for('positions.history'))