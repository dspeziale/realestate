# blueprints/api.py - Nuove route per live map

from flask import Blueprint, current_app, jsonify
from core.traccar_framework import TraccarException
from datetime import datetime, timedelta

api_bp = Blueprint('api', __name__)


@api_bp.route('/vehicles/positions')
def get_all_positions():
    """Get all vehicles with their latest positions"""
    traccar = current_app.config['TRACCAR_API']

    try:
        devices = traccar.devices.get_devices()

        result = []
        for device in devices:
            try:
                positions = traccar.positions.get_positions(device_id=device['id'])
                device['latest_position'] = positions[-1] if positions else None
            except:
                device['latest_position'] = None
            result.append(device)

        return jsonify(result)
    except TraccarException as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/vehicles/<int:vehicle_id>/detail')
def get_vehicle_detail(vehicle_id):
    """Get detailed info for a specific vehicle"""
    traccar = current_app.config['TRACCAR_API']

    try:
        devices = traccar.devices.get_devices()
        vehicle = next((d for d in devices if d['id'] == vehicle_id), None)

        if not vehicle:
            return jsonify({'error': 'Vehicle not found'}), 404

        # Get latest position
        positions = traccar.positions.get_positions(device_id=vehicle_id)
        vehicle['latest_position'] = positions[-1] if positions else None

        # Get summary for today
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)

        try:
            summary = traccar.reports.get_summary_report(
                device_ids=[vehicle_id],
                from_time=today,
                to_time=tomorrow
            )
            vehicle['today_summary'] = summary[0] if summary else None
        except:
            vehicle['today_summary'] = None

        return jsonify(vehicle)

    except TraccarException as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/vehicles/<int:vehicle_id>/track')
def track_vehicle(vehicle_id):
    """Get tracking data for vehicle"""
    traccar = current_app.config['TRACCAR_API']

    try:
        # Get positions from last 24 hours
        from_time = datetime.now() - timedelta(hours=24)
        to_time = datetime.now()

        positions = traccar.positions.get_positions(
            device_id=vehicle_id,
            from_time=from_time,
            to_time=to_time
        )

        return jsonify(positions)

    except TraccarException as e:
        return jsonify({'error': str(e)}), 500