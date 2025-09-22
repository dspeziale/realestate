# blueprints/api.py - FIXED VERSION
import csv
import io

from flask import Blueprint, jsonify, current_app, request, Response
from datetime import datetime, timedelta
from core.traccar_framework import TraccarException
import logging

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/vehicles')
def get_vehicles():
    """Get all vehicles with current status"""
    traccar = current_app.config['TRACCAR_API']

    # Get optional filters
    group_id = request.args.get('group_id', type=int)
    category = request.args.get('category')
    status_filter = request.args.get('status')

    try:
        # Get devices
        devices = traccar.devices.get_devices()

        # Get all positions once
        all_positions = traccar.positions.get_positions()
        position_map = {p['deviceId']: p for p in all_positions}

        # Build vehicle data
        vehicles = []
        for device in devices:
            pos = position_map.get(device['id'], {})

            # Calculate speed (knots to km/h)
            speed = round(pos.get('speed', 0) * 1.852, 1) if pos.get('speed') else 0

            vehicle = {
                'id': device['id'],
                'name': device['name'],
                'status': device.get('status', 'offline'),
                'category': device.get('category'),
                'groupId': device.get('groupId'),
                'latitude': pos.get('latitude'),
                'longitude': pos.get('longitude'),
                'speed': speed,
                'course': pos.get('course', 0),
                'lastUpdate': pos.get('deviceTime', pos.get('serverTime')),
                'attributes': device.get('attributes', {}),
                'latest_position': pos
            }

            # Apply filters
            if group_id and vehicle['groupId'] != group_id:
                continue

            if category and vehicle['category'] != category:
                continue

            if status_filter:
                if status_filter == 'active' and not (vehicle['status'] == 'online' and speed > 0):
                    continue
                if status_filter == 'stopped' and (vehicle['status'] == 'online' and speed > 0):
                    continue

            vehicles.append(vehicle)

        return jsonify(vehicles)

    except TraccarException as e:
        logger.error(f"TraccarException in get_vehicles: {e}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Exception in get_vehicles: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/vehicles/<int:vehicle_id>')
def get_vehicle(vehicle_id):
    """Get specific vehicle details - FIXED VERSION"""
    traccar = current_app.config['TRACCAR_API']

    try:
        # Get device info
        devices = traccar.devices.get_devices()
        device = next((d for d in devices if d['id'] == vehicle_id), None)

        if not device:
            return jsonify({'error': 'Vehicle not found'}), 404

        # Get position - TRY/CATCH per gestire errori
        try:
            # Get ALL positions first
            all_positions = traccar.positions.get_positions()
            # Find position for this device
            pos = next((p for p in all_positions if p.get('deviceId') == vehicle_id), {})

            # If not found, try with device_id parameter
            if not pos:
                positions = traccar.positions.get_positions(device_id=vehicle_id)
                pos = positions[0] if positions else {}
        except Exception as e:
            logger.warning(f"Error getting position for vehicle {vehicle_id}: {e}")
            pos = {}

        vehicle = {
            'id': device['id'],
            'name': device['name'],
            'status': device.get('status', 'offline'),
            'category': device.get('category'),
            'groupId': device.get('groupId'),
            'latitude': pos.get('latitude'),
            'longitude': pos.get('longitude'),
            'speed': round(pos.get('speed', 0) * 1.852, 1) if pos.get('speed') else 0,
            'course': pos.get('course', 0),
            'altitude': pos.get('altitude', 0),
            'accuracy': pos.get('accuracy', 0),
            'lastUpdate': pos.get('deviceTime', pos.get('serverTime')),
            'attributes': device.get('attributes', {}),
            'address': pos.get('address', 'Unknown location')
        }

        return jsonify(vehicle)

    except TraccarException as e:
        logger.error(f"TraccarException getting vehicle {vehicle_id}: {e}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Exception getting vehicle {vehicle_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/vehicles/<int:vehicle_id>/track')
def get_vehicle_track(vehicle_id):
    """Get vehicle tracking positions"""
    traccar = current_app.config['TRACCAR_API']

    try:
        # Get recent positions (last hour by default)
        from_time = request.args.get('from')
        if from_time:
            from_time = datetime.fromisoformat(from_time)
        else:
            from_time = datetime.now() - timedelta(hours=1)

        to_time = datetime.now()

        positions = traccar.positions.get_positions(
            device_id=vehicle_id,
            from_time=from_time,
            to_time=to_time
        )

        # Convert positions to simplified format
        track = []
        for pos in positions:
            track.append({
                'latitude': pos.get('latitude'),
                'longitude': pos.get('longitude'),
                'speed': pos.get('speed', 0),
                'course': pos.get('course', 0),
                'altitude': pos.get('altitude', 0),
                'deviceTime': pos.get('deviceTime'),
                'serverTime': pos.get('serverTime'),
                'accuracy': pos.get('accuracy', 0)
            })

        return jsonify(track)

    except TraccarException as e:
        logger.error(f"Error getting track for vehicle {vehicle_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/vehicles/positions')
def get_all_positions():
    """Get latest positions for all vehicles"""
    traccar = current_app.config['TRACCAR_API']

    try:
        # Get all positions
        positions = traccar.positions.get_positions()

        # Format positions
        result = []
        for pos in positions:
            result.append({
                'deviceId': pos.get('deviceId'),
                'latitude': pos.get('latitude'),
                'longitude': pos.get('longitude'),
                'speed': round(pos.get('speed', 0) * 1.852, 1) if pos.get('speed') else 0,
                'course': pos.get('course', 0),
                'altitude': pos.get('altitude', 0),
                'accuracy': pos.get('accuracy', 0),
                'deviceTime': pos.get('deviceTime'),
                'serverTime': pos.get('serverTime'),
                'address': pos.get('address', '')
            })

        return jsonify(result)

    except TraccarException as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/stats')
def get_stats():
    """Get fleet statistics - ADDED ENDPOINT"""
    traccar = current_app.config['TRACCAR_API']

    try:
        devices = traccar.devices.get_devices()
        positions = traccar.positions.get_positions()

        # Calculate stats
        total_vehicles = len(devices)
        online_vehicles = len([d for d in devices if d.get('status') == 'online'])

        # Calculate average speed from positions
        speeds = []
        for pos in positions:
            speed_kmh = pos.get('speed', 0) * 1.852
            if speed_kmh > 0:
                speeds.append(speed_kmh)

        avg_speed = round(sum(speeds) / len(speeds), 1) if speeds else 0
        moving_vehicles = len(speeds)

        stats = {
            'totalVehicles': total_vehicles,
            'onlineVehicles': online_vehicles,
            'offlineVehicles': total_vehicles - online_vehicles,
            'averageSpeed': avg_speed,
            'movingVehicles': moving_vehicles,
            'efficiency': round((online_vehicles / total_vehicles * 100) if total_vehicles > 0 else 0, 1)
        }

        return jsonify(stats)

    except TraccarException as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected error in stats: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/groups')
def get_groups():
    """Get all groups"""
    traccar = current_app.config['TRACCAR_API']

    try:
        groups = traccar.groups.get_groups()
        return jsonify(groups)
    except TraccarException as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/categories')
def get_categories():
    """Get all unique categories from devices"""
    traccar = current_app.config['TRACCAR_API']

    try:
        devices = traccar.devices.get_devices()
        categories = list(set(d.get('category') for d in devices if d.get('category')))
        return jsonify(sorted(categories))
    except TraccarException as e:
        return jsonify({'error': str(e)}), 500


# blueprints/api.py - AGGIUNGI QUESTO ENDPOINT

@api_bp.route('/vehicles/<int:vehicle_id>/export')
def export_vehicle_data(vehicle_id):
    """Export vehicle data to CSV"""
    traccar = current_app.config['TRACCAR_API']

    try:
        # Get parameters
        days = request.args.get('days', default=7, type=int)
        if days > 30:
            days = 30

        format_type = request.args.get('format', default='csv')

        from_time = datetime.now() - timedelta(days=days)
        to_time = datetime.now()

        # Get vehicle info
        devices = traccar.devices.get_devices()
        vehicle = next((d for d in devices if d['id'] == vehicle_id), None)
        if not vehicle:
            return jsonify({'error': 'Vehicle not found'}), 404

        # Get positions
        positions = traccar.positions.get_positions(
            device_id=vehicle_id,
            from_time=from_time,
            to_time=to_time
        )

        if format_type == 'csv':
            # Create CSV
            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow([
                'Timestamp',
                'Latitude',
                'Longitude',
                'Speed (km/h)',
                'Course',
                'Altitude',
                'Address'
            ])

            # Data rows
            for pos in positions:
                writer.writerow([
                    pos.get('deviceTime', pos.get('serverTime', '')),
                    pos.get('latitude', ''),
                    pos.get('longitude', ''),
                    round(pos.get('speed', 0) * 1.852, 2) if pos.get('speed') else 0,
                    pos.get('course', 0),
                    pos.get('altitude', 0),
                    pos.get('address', '')
                ])

            # Create response
            output.seek(0)
            filename = f"{vehicle['name']}_positions_{days}days.csv"

            return Response(
                output.getvalue(),
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename={filename}'}
            )

    except TraccarException as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Error exporting vehicle data: {e}")
        return jsonify({'error': str(e)}), 500


# blueprints/api.py - AGGIUNGI QUESTI ENDPOINT PER I REPORT CON INDIRIZZI

@api_bp.route('/reports/preview', methods=['POST'])
def preview_report():
    """Anteprima veloce del report prima della generazione completa"""
    traccar = current_app.config['TRACCAR_API']
    geocoding_service = current_app.config.get('GEOCODING_SERVICE')

    data = request.get_json()
    report_type = data.get('type')
    device_ids = data.get('device_ids', [])
    from_date = datetime.fromisoformat(data.get('from'))
    to_date = datetime.fromisoformat(data.get('to'))

    try:
        # Calcola statistiche preliminari
        devices = traccar.devices.get_devices()
        selected_devices = [d for d in devices if d['id'] in device_ids]

        # Calcola dimensione stimata del report
        time_span_hours = (to_date - from_date).total_seconds() / 3600
        estimated_positions = len(device_ids) * max(1, int(time_span_hours / 0.5))  # 1 posizione ogni 30 min

        preview_info = {
            'report_type': report_type,
            'device_count': len(device_ids),
            'device_names': [d['name'] for d in selected_devices],
            'time_span_hours': round(time_span_hours, 1),
            'estimated_records': min(estimated_positions, 10000),  # Cap per performance
            'geocoding_available': geocoding_service is not None,
            'estimated_processing_time': min(30, max(5, len(device_ids) * 2)),  # 5-30 secondi
        }

        if geocoding_service:
            stats = geocoding_service.get_statistics()
            preview_info['geocoding_cache_size'] = stats.get('cache_stats', {}).get('total_addresses', 0)

        return jsonify({
            'success': True,
            'preview': preview_info
        })

    except Exception as e:
        logger.error(f"Error in report preview: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/reports/batch-geocode', methods=['POST'])
def batch_geocode_coordinates():
    """Geocoding batch per coordinate multiple"""
    geocoding_service = current_app.config.get('GEOCODING_SERVICE')

    if not geocoding_service:
        return jsonify({'error': 'Geocoding service not available'}), 503

    data = request.get_json()
    coordinates = data.get('coordinates', [])  # Lista di [lat, lng]

    if not coordinates or len(coordinates) > 100:  # Limite per evitare abusi
        return jsonify({'error': 'Invalid coordinates list (max 100)'}), 400

    try:
        results = []
        for i, coord in enumerate(coordinates):
            if len(coord) != 2:
                results.append({'error': 'Invalid coordinate format'})
                continue

            lat, lng = coord
            try:
                address = geocoding_service.reverse_geocode(lat, lng)
                results.append({
                    'address': address or 'Address not found',
                    'coordinates': [lat, lng]
                })
            except Exception as e:
                logger.warning(f"Geocoding error for {lat}, {lng}: {e}")
                results.append({
                    'error': str(e),
                    'coordinates': [lat, lng]
                })

        return jsonify({
            'success': True,
            'results': results,
            'processed_count': len(coordinates)
        })

    except Exception as e:
        logger.error(f"Error in batch geocoding: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/reports/enhance-data', methods=['POST'])
def enhance_report_data():
    """Arricchisce dati esistenti con indirizzi"""
    geocoding_service = current_app.config.get('GEOCODING_SERVICE')

    if not geocoding_service:
        return jsonify({'error': 'Geocoding service not available'}), 503

    data = request.get_json()
    report_data = data.get('data', [])
    report_type = data.get('type')

    if not report_data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        enhanced_data = []

        for item in report_data:
            enhanced_item = item.copy()

            if report_type == 'trips':
                # Aggiungi indirizzi per viaggi
                if 'startLat' in item and 'startLon' in item:
                    enhanced_item['startAddress'] = geocoding_service.reverse_geocode(
                        item['startLat'], item['startLon']
                    ) or 'Indirizzo non trovato'

                if 'endLat' in item and 'endLon' in item:
                    enhanced_item['endAddress'] = geocoding_service.reverse_geocode(
                        item['endLat'], item['endLon']
                    ) or 'Indirizzo non trovato'

            elif report_type == 'stops':
                # Aggiungi indirizzo per soste
                if 'latitude' in item and 'longitude' in item:
                    enhanced_item['address'] = geocoding_service.reverse_geocode(
                        item['latitude'], item['longitude']
                    ) or 'Indirizzo non trovato'

            elif report_type == 'route':
                # Aggiungi indirizzo per posizioni
                if 'latitude' in item and 'longitude' in item:
                    enhanced_item['address'] = geocoding_service.reverse_geocode(
                        item['latitude'], item['longitude']
                    ) or 'Indirizzo non trovato'

            enhanced_data.append(enhanced_item)

        return jsonify({
            'success': True,
            'data': enhanced_data,
            'enhanced_count': len(enhanced_data)
        })

    except Exception as e:
        logger.error(f"Error enhancing report data: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/reports/statistics', methods=['GET'])
def get_report_statistics():
    """Statistiche sui report generati e uso geocoding"""
    traccar = current_app.config['TRACCAR_API']
    geocoding_service = current_app.config.get('GEOCODING_SERVICE')

    try:
        # Statistiche base
        devices = traccar.devices.get_devices()
        positions = traccar.positions.get_positions()

        stats = {
            'devices': {
                'total': len(devices),
                'online': len([d for d in devices if d.get('status') == 'online']),
                'offline': len([d for d in devices if d.get('status') == 'offline'])
            },
            'positions': {
                'total': len(positions),
                'today': len([p for p in positions if is_today(p.get('deviceTime', p.get('serverTime')))])
            }
        }

        # Statistiche geocoding se disponibile
        if geocoding_service:
            geo_stats = geocoding_service.get_statistics()
            stats['geocoding'] = {
                'available': True,
                'cache_addresses': geo_stats.get('cache_stats', {}).get('total_addresses', 0),
                'hit_rate_percent': geo_stats.get('cache_stats', {}).get('hit_rate_percent', 0),
                'cache_size_mb': geo_stats.get('cache_stats', {}).get('db_size_mb', 0)
            }
        else:
            stats['geocoding'] = {'available': False}

        # Capacità report stimata
        stats['report_capacity'] = {
            'max_devices_per_report': 50,
            'max_days_per_report': 90,
            'estimated_max_records': 50000,
            'supports_addresses': geocoding_service is not None
        }

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error getting report statistics: {e}")
        return jsonify({'error': str(e)}), 500


def is_today(timestamp_str):
    """Controlla se un timestamp è di oggi"""
    if not timestamp_str:
        return False
    try:
        ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        today = datetime.now(ts.tzinfo).date()
        return ts.date() == today
    except:
        return False