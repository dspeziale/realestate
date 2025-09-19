# blueprints/api.py - FIXED VERSION

from flask import Blueprint, jsonify, current_app, request
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