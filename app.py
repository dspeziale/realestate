# app.py - Main Flask Application

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
import json
import os
from datetime import datetime, timedelta
from functools import wraps

from blueprints.api import api_bp
from blueprints.auth import auth_bp
from blueprints.dashboard import dashboard_bp
from blueprints.reports import reports_bp
from blueprints.vehicles import vehicles_bp
from core.traccar_framework import TraccarAPI

# Initialize Flask app first
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
CORS(app)

# Load configuration
with open('config.json', 'r') as f:
    config = json.load(f)

# Initialize Traccar API
traccar = TraccarAPI(
    host=config['traccar']['host'],
    port=config['traccar']['port'],
    username=config['traccar']['username'],
    password=config['traccar']['password'],
    protocol=config['traccar']['protocol'],
    debug=config['traccar']['debug']
)

# Store traccar instance in app config for blueprint access
app.config['TRACCAR_API'] = traccar

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
app.register_blueprint(vehicles_bp, url_prefix='/vehicles')
app.register_blueprint(reports_bp, url_prefix='/reports')
app.register_blueprint(api_bp, url_prefix='/api')

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        server_info = traccar.server.get_server_info()
        return jsonify({
            'status': 'healthy',
            'traccar_version': server_info.get('version'),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('errors/500.html'), 500

# Template filters
@app.template_filter('datetime')
def format_datetime(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value
    if isinstance(value, datetime):
        return value.strftime('%d/%m/%Y %H:%M')
    return value

@app.template_filter('distance')
def format_distance(meters):
    if meters is None:
        return '0 km'
    km = meters / 1000
    return f'{km:.2f} km'

@app.template_filter('speed')
def format_speed(knots):
    if knots is None:
        return '0 km/h'
    kmh = knots * 1.852
    return f'{kmh:.1f} km/h'

if __name__ == '__main__':
    app.run(
        host=config['flask']['host'],
        port=config['flask']['port'],
        debug=config['flask']['debug']
    )