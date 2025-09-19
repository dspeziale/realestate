# app.py - Updated version with enhanced API endpoints

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
import json
import os
from datetime import datetime, timedelta
from functools import wraps

# Import blueprints
from blueprints.api import api_bp
from blueprints.auth import auth_bp
from blueprints.dashboard import dashboard_bp
from blueprints.reports import reports_bp
from blueprints.vehicles import vehicles_bp
from blueprints.alerts import alerts_bp

# Import framework and models
from core.traccar_framework import TraccarAPI
from models.database import Database

# Initialize Flask app
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

# Initialize Database
db = Database(config['database']['path'])

# Store instances in app config for blueprint access
app.config['TRACCAR_API'] = traccar
app.config['DATABASE'] = db
app.config['CONFIG'] = config

# Register all blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
app.register_blueprint(vehicles_bp, url_prefix='/vehicles')
app.register_blueprint(reports_bp, url_prefix='/reports')
app.register_blueprint(alerts_bp, url_prefix='/alerts')
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
    """Root route - redirect based on auth status"""
    if 'user' in session:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))


@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        server_info = traccar.server.get_server_info()

        # Check database
        try:
            alerts = db.get_alerts(limit=1)
            db_status = 'healthy'
        except Exception as e:
            db_status = f'error: {str(e)}'

        return jsonify({
            'status': 'healthy',
            'traccar': {
                'connected': True,
                'version': server_info.get('version')
            },
            'database': {
                'status': db_status
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/status')
@login_required
def status():
    """System status page"""
    try:
        server_info = traccar.server.get_server_info()
        devices = traccar.devices.get_devices()
        alerts = db.get_alerts(limit=10)

        stats = {
            'traccar_version': server_info.get('version'),
            'total_devices': len(devices),
            'online_devices': len([d for d in devices if d.get('status') == 'online']),
            'recent_alerts': len(alerts),
            'database_path': config['database']['path']
        }

        return render_template('status.html', stats=stats, server_info=server_info)
    except Exception as e:
        return render_template('status.html', error=str(e))


# Error handlers
@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def internal_error(e):
    return render_template('errors/500.html'), 500


@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


# Template filters
@app.template_filter('datetime')
def format_datetime(value):
    """Format datetime for display"""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value
    if isinstance(value, datetime):
        return value.strftime('%d/%m/%Y %H:%M')
    return value


@app.template_filter('date')
def format_date(value):
    """Format date only"""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value
    if isinstance(value, datetime):
        return value.strftime('%d/%m/%Y')
    return value


@app.template_filter('time')
def format_time(value):
    """Format time only"""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value
    if isinstance(value, datetime):
        return value.strftime('%H:%M:%S')
    return value


@app.template_filter('distance')
def format_distance(meters):
    """Format distance in meters to km"""
    if meters is None:
        return '0 km'
    km = meters / 1000
    return f'{km:.2f} km'


@app.template_filter('speed')
def format_speed(knots):
    """Convert knots to km/h"""
    if knots is None:
        return '0 km/h'
    kmh = knots * 1.852
    return f'{kmh:.1f} km/h'


@app.template_filter('duration')
def format_duration(seconds):
    """Format duration in seconds to human readable"""
    if seconds is None:
        return '0s'

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f'{int(hours)}h {int(minutes)}m'
    elif minutes > 0:
        return f'{int(minutes)}m {int(secs)}s'
    else:
        return f'{int(secs)}s'


@app.template_filter('timeago')
def format_timeago(value):
    """Format datetime as time ago"""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value

    if isinstance(value, datetime):
        now = datetime.now(value.tzinfo) if value.tzinfo else datetime.now()
        diff = now - value

        seconds = diff.total_seconds()

        if seconds < 60:
            return 'just now'
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f'{minutes}m ago'
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f'{hours}h ago'
        else:
            days = int(seconds / 86400)
            return f'{days}d ago'

    return value


# Context processor - add global variables to all templates
@app.context_processor
def inject_globals():
    """Inject global variables into templates"""
    return {
        'app_name': config['app']['name'],
        'company_name': config['app']['company'],
        'current_year': datetime.now().year
    }


# Before request handler
@app.before_request
def before_request():
    """Execute before each request"""
    # Make session permanent
    session.permanent = True
    app.permanent_session_lifetime = timedelta(hours=24)

    # Log request (if debug enabled)
    if config['flask']['debug']:
        app.logger.debug(f'{request.method} {request.path}')


# After request handler
@app.after_request
def after_request(response):
    """Execute after each request"""
    # Add security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'

    return response


# Startup check
def startup_check():
    """Perform startup checks"""
    print("\n" + "=" * 60)
    print("🚀 Fleet Manager Pro - Starting Up")
    print("=" * 60)

    # Check Traccar connection
    print("\n📡 Checking Traccar connection...")
    try:
        server_info = traccar.server.get_server_info()
        print(f"✅ Connected to Traccar v{server_info.get('version')}")
        print(f"   Server: {config['traccar']['protocol']}://{config['traccar']['host']}:{config['traccar']['port']}")
    except Exception as e:
        print(f"❌ Failed to connect to Traccar: {e}")
        print("⚠️  Application will start but some features may not work")

    # Check database
    print("\n💾 Checking database...")
    try:
        db.get_alerts(limit=1)
        print(f"✅ Database ready at {config['database']['path']}")
    except Exception as e:
        print(f"⚠️  Database warning: {e}")

    print("\n" + "=" * 60)
    print(f"✨ Application ready!")
    print(f"🌐 Access at: http://{config['flask']['host']}:{config['flask']['port']}")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    # Perform startup checks
    startup_check()

    # Run Flask app
    app.run(
        host=config['flask']['host'],
        port=config['flask']['port'],
        debug=config['flask']['debug'],
        threaded=True
    )