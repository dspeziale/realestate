# blueprints/api.py - API endpoints for AJAX calls
from flask import Blueprint, jsonify, current_app
from core.traccar_framework import TraccarException

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/vehicles')
def get_vehicles():
    """Get all vehicles with current status"""
    traccar = current_app.config['TRACCAR_API']

    try:
        # Get devices
        devices = traccar.devices.get_devices()

        # Get positions for all devices
        positions = traccar.positions.get_positions()

        # Create position lookup
        position_map = {p['deviceId']: p for p in positions}

        # Build vehicle data
        vehicles = []
        for device in devices:
            pos = position_map.get(device['id'], {})

            vehicle = {
                'id': device['id'],
                'name': device['name'],
                'status': device.get('status', 'offline'),
                'latitude': pos.get('latitude'),
                'longitude': pos.get('longitude'),
                'speed': round(pos.get('speed', 0) * 1.852, 1) if pos.get('speed') else 0,  # knots to km/h
                'course': pos.get('course', 0),
                'lastUpdate': pos.get('deviceTime', pos.get('serverTime')),
                'attributes': device.get('attributes', {}),
                'route': f"{device.get('attributes', {}).get('origin', 'Unknown')} → {device.get('attributes', {}).get('destination', 'Unknown')}",
                'progress': device.get('attributes', {}).get('progress', 0)
            }
            vehicles.append(vehicle)

        return jsonify(vehicles)

    except TraccarException as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/vehicles/<int:vehicle_id>')
def get_vehicle(vehicle_id):
    """Get specific vehicle details"""
    traccar = current_app.config['TRACCAR_API']

    try:
        devices = traccar.devices.get_devices()
        device = next((d for d in devices if d['id'] == vehicle_id), None)

        if not device:
            return jsonify({'error': 'Vehicle not found'}), 404

        # Get position
        positions = traccar.positions.get_positions(device_id=vehicle_id)
        pos = positions[0] if positions else {}

        vehicle = {
            'id': device['id'],
            'name': device['name'],
            'status': device.get('status', 'offline'),
            'latitude': pos.get('latitude'),
            'longitude': pos.get('longitude'),
            'speed': round(pos.get('speed', 0) * 1.852, 1) if pos.get('speed') else 0,
            'course': pos.get('course', 0),
            'lastUpdate': pos.get('deviceTime', pos.get('serverTime')),
            'attributes': device.get('attributes', {}),
            'address': pos.get('address', 'Unknown location')
        }

        return jsonify(vehicle)

    except TraccarException as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/stats')
def get_stats():
    """Get fleet statistics"""
    traccar = current_app.config['TRACCAR_API']

    try:
        devices = traccar.devices.get_devices()
        positions = traccar.positions.get_positions()

        # Calculate stats
        total_vehicles = len(devices)
        online_vehicles = len([d for d in devices if d.get('status') == 'online'])

        # Calculate total distance (example - you might want to use reports API)
        total_distance = sum([
            round(p.get('attributes', {}).get('totalDistance', 0) / 1000, 1)
            for p in positions
        ])

        # Calculate average speed
        speeds = [p.get('speed', 0) * 1.852 for p in positions if p.get('speed', 0) > 0]
        avg_speed = round(sum(speeds) / len(speeds), 1) if speeds else 0

        stats = {
            'totalVehicles': total_vehicles,
            'onlineVehicles': online_vehicles,
            'offlineVehicles': total_vehicles - online_vehicles,
            'totalDistance': round(total_distance, 1),
            'averageSpeed': avg_speed,
            'efficiency': round((online_vehicles / total_vehicles * 100) if total_vehicles > 0 else 0, 1)
        }

        return jsonify(stats)

    except TraccarException as e:
        return jsonify({'error': str(e)}), 500