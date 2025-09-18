# blueprints/dashboard.py
from flask import Blueprint, render_template, current_app, jsonify, redirect, url_for, session
from core.traccar_framework import TraccarException

dashboard_bp = Blueprint('dashboard', __name__, template_folder='../templates')


def login_required(f):
    """Decorator to check if user is logged in"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@dashboard_bp.route('/')
@login_required
def index():
    """Dashboard home page"""
    traccar = current_app.config['TRACCAR_API']

    try:
        # Get basic stats
        devices = traccar.devices.get_devices()

        stats = {
            'total_vehicles': len(devices),
            'active_vehicles': len([d for d in devices if d.get('status') == 'online']),
            'inactive_vehicles': len([d for d in devices if d.get('status') == 'offline']),
        }

        return render_template('dashboard/index.html', stats=stats)

    except TraccarException as e:
        return render_template('dashboard/index.html', error=str(e), stats={})


@dashboard_bp.route('/live-map')
@login_required
def live_map():
    """Live map view with filters"""
    traccar = current_app.config['TRACCAR_API']

    try:
        # Get devices
        devices = traccar.devices.get_devices()

        # Get groups
        groups = traccar.groups.get_groups()

        # Extract unique categories from devices
        categories = set()
        for device in devices:
            category = device.get('category')
            if category:
                categories.add(category)

        categories = sorted(list(categories))

        # Calculate stats
        stats = {
            'total_vehicles': len(devices),
            'active_vehicles': len([d for d in devices if d.get('status') == 'online']),
            'inactive_vehicles': len([d for d in devices if d.get('status') == 'offline']),
        }

        return render_template('dashboard/live_map.html',
                               stats=stats,
                               vehicles=devices,
                               groups=groups,
                               categories=categories)

    except TraccarException as e:
        return render_template('dashboard/live_map.html',
                               error=str(e),
                               stats={},
                               vehicles=[],
                               groups=[],
                               categories=[])