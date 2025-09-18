# blueprints/api.py
from flask import Blueprint, jsonify, current_app, request
from datetime import datetime, timedelta
from core.traccar_framework import TraccarException

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/vehicles')
def get_vehicles():
    """Get all vehicles with current status"""
    traccar = current_app.config['TRACCAR_API']

    # Get optional filters
    group_id = request.args.get('group_id', type=int)
    category = request.args.get('category')
    status_filter = request.args.get('status')  # 'active', 'stopped', 'all'

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
                'route': f"{device.get('attributes', {}).get('origin', 'Sconosciuto')} → {device.get('attributes', {}).get('destination', 'Sconosciuto')}"
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
            'category': device.get('category'),
            'groupId': device.get('groupId'),
            'latitude': pos.get('latitude'),
            'longitude': pos.get('longitude'),
            'speed': round(pos.get('speed', 0) * 1.852, 1) if pos.get('speed') else 0,
            'course': pos.get('course', 0),
            'lastUpdate': pos.get('deviceTime', pos.get('serverTime')),
            'attributes': device.get('attributes', {}),
            'address': pos.get('address', 'Posizione sconosciuta')
        }

        return jsonify(vehicle)

    except TraccarException as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/vehicles/<int:vehicle_id>/track')
def get_vehicle_track(vehicle_id):
    """Get vehicle tracking positions for live tracking"""
    traccar = current_app.config['TRACCAR_API']

    try:
        # Get recent positions (last hour by default)
        from datetime import datetime, timedelta

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
                'serverTime': pos.get('serverTime')
            })

        return jsonify(track)

    except TraccarException as e:
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

        # Calculate average speed
        speeds = [p.get('speed', 0) * 1.852 for p in positions if p.get('speed', 0) > 0]
        avg_speed = round(sum(speeds) / len(speeds), 1) if speeds else 0

        stats = {
            'totalVehicles': total_vehicles,
            'onlineVehicles': online_vehicles,
            'offlineVehicles': total_vehicles - online_vehicles,
            'averageSpeed': avg_speed,
            'movingVehicles': len([p for p in positions if p.get('speed', 0) > 0]),
            'efficiency': round((online_vehicles / total_vehicles * 100) if total_vehicles > 0 else 0, 1)
        }

        return jsonify(stats)

    except TraccarException as e:
        return jsonify({'error': str(e)}), 500