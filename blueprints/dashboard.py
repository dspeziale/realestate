from flask import Blueprint, render_template, current_app, jsonify
from datetime import datetime, timedelta
from core.traccar_framework import TraccarException

dashboard_bp = Blueprint('dashboard', __name__, template_folder='../templates')


@dashboard_bp.route('/')
def index():
    return render_template('dashboard/index.html')


@dashboard_bp.route('/live-map')
def live_map():
    traccar = current_app.config['TRACCAR_API']

    try:
        devices = traccar.devices.get_devices()

        stats = {
            'total_vehicles': len(devices),
            'active_vehicles': len([d for d in devices if d.get('status') == 'online']),
            'inactive_vehicles': len([d for d in devices if d.get('status') == 'offline']),
        }

        return render_template('dashboard/live_map.html',
                               stats=stats,
                               vehicles=devices)

    except TraccarException as e:
        return render_template('dashboard/live_map.html',
                               error=str(e),
                               stats={},
                               vehicles=[])