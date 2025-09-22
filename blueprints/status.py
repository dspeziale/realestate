# blueprints/status.py
"""
Status Blueprint - Sistema di monitoraggio e diagnostica
Fornisce informazioni dettagliate sullo stato del sistema
"""

from flask import Blueprint, render_template, current_app, jsonify
from datetime import datetime
import os
import sqlite3
import logging

logger = logging.getLogger('StatusBlueprint')

status_bp = Blueprint('status', __name__, template_folder='../templates')


def login_required(f):
    """Decorator per verificare se l'utente è loggato"""
    from functools import wraps
    from flask import session, redirect, url_for

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated_function


@status_bp.route('/')
@login_required
def index():
    """Pagina principale dello stato del sistema"""
    try:
        # Raccoglie informazioni da tutti i servizi
        traccar = current_app.config['TRACCAR_API']
        db = current_app.config['DATABASE']
        config = current_app.config['CONFIG']
        geocoding_service = current_app.config.get('GEOCODING_SERVICE')
        cache_manager = current_app.config.get('CACHE_MANAGER')

        status_info = {
            'timestamp': datetime.now().isoformat(),
            'services': {},
            'system': {}
        }

        # Status Traccar Server
        try:
            server_info = traccar.server.get_server_info()
            devices = traccar.devices.get_devices()

            status_info['services']['traccar'] = {
                'status': 'healthy',
                'version': server_info.get('version', 'Unknown'),
                'host': f"{config['traccar']['host']}:{config['traccar']['port']}",
                'total_devices': len(devices),
                'online_devices': len([d for d in devices if d.get('status') == 'online']),
                'offline_devices': len([d for d in devices if d.get('status') == 'offline']),
                'registration': server_info.get('registration', False),
                'map_provider': server_info.get('map', 'Default'),
                'coordinate_format': server_info.get('coordinateFormat', 'Default')
            }
        except Exception as e:
            status_info['services']['traccar'] = {
                'status': 'error',
                'error': str(e)
            }

        # Status Database
        try:
            alerts = db.get_alerts(limit=5)
            db_path = config['database']['path']
            db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

            # Test integrità database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            conn.close()

            status_info['services']['database'] = {
                'status': 'healthy' if integrity_result == 'ok' else 'warning',
                'path': db_path,
                'size_mb': round(db_size / (1024 * 1024), 2),
                'integrity': integrity_result,
                'recent_alerts_count': len(alerts),
                'type': config['database'].get('type', 'sqlite')
            }
        except Exception as e:
            status_info['services']['database'] = {
                'status': 'error',
                'error': str(e)
            }

        # Status Geocoding Service
        if geocoding_service:
            try:
                geo_stats = geocoding_service.get_statistics()
                cache_stats = geo_stats.get('cache_stats', {})

                status_info['services']['geocoding'] = {
                    'status': 'healthy',
                    'cache_addresses': cache_stats.get('total_addresses', 0),
                    'cache_size_mb': round(cache_stats.get('db_size_mb', 0), 2),
                    'hit_rate_percent': cache_stats.get('hit_rate_percent', 0),
                    'api_calls_session': geo_stats.get('service_stats', {}).get('api_calls_session', 0),
                    'cache_hits_session': geo_stats.get('service_stats', {}).get('cache_hits_session', 0),
                    'top_countries': geo_stats.get('geographic_distribution', {}).get('top_countries', [])[:5]
                }
            except Exception as e:
                status_info['services']['geocoding'] = {
                    'status': 'error',
                    'error': str(e)
                }
        else:
            status_info['services']['geocoding'] = {
                'status': 'disabled',
                'message': 'Geocoding service not configured'
            }

        # Status Cache Manager
        if cache_manager:
            try:
                cache_info = cache_manager.get_service_info()
                cache_stats = cache_manager.get_all_statistics()

                status_info['services']['cache_manager'] = {
                    'status': 'healthy',
                    'running': cache_manager.running,
                    'registered_services': len(cache_info),
                    'cleanup_interval_hours': cache_manager.cleanup_interval_hours,
                    'services': cache_info
                }
            except Exception as e:
                status_info['services']['cache_manager'] = {
                    'status': 'error',
                    'error': str(e)
                }
        else:
            status_info['services']['cache_manager'] = {
                'status': 'disabled',
                'message': 'Cache manager not initialized'
            }

        # Informazioni sistema
        status_info['system'] = {
            'app_name': config.get('app', {}).get('name', 'Fleet Manager Pro'),
            'app_version': config.get('app', {}).get('version', '1.0.0'),
            'python_version': f"{__import__('sys').version_info.major}.{__import__('sys').version_info.minor}.{__import__('sys').version_info.micro}",
            'config_features': config.get('features', {}),
            'uptime': datetime.now().isoformat()  # Placeholder per uptime
        }

        # Calcola stato generale
        service_statuses = [s.get('status') for s in status_info['services'].values()]
        if 'error' in service_statuses:
            overall_status = 'degraded'
        elif 'warning' in service_statuses:
            overall_status = 'warning'
        else:
            overall_status = 'healthy'

        status_info['overall_status'] = overall_status

        return render_template('status/index.html', status_info=status_info)

    except Exception as e:
        logger.error(f"Errore recupero status: {e}")
        return render_template('status/index.html',
                               error=f"Errore recupero informazioni sistema: {str(e)}")


@status_bp.route('/api')
def api_status():
    """API endpoint per status in formato JSON"""
    try:
        traccar = current_app.config['TRACCAR_API']
        db = current_app.config['DATABASE']
        config = current_app.config['CONFIG']
        geocoding_service = current_app.config.get('GEOCODING_SERVICE')
        cache_manager = current_app.config.get('CACHE_MANAGER')

        status = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'services': {}
        }

        # Check Traccar
        try:
            server_info = traccar.server.get_server_info()
            devices = traccar.devices.get_devices()
            status['services']['traccar'] = {
                'status': 'healthy',
                'version': server_info.get('version'),
                'devices_total': len(devices),
                'devices_online': len([d for d in devices if d.get('status') == 'online'])
            }
        except Exception as e:
            status['services']['traccar'] = {'status': 'error', 'error': str(e)}
            status['overall_status'] = 'degraded'

        # Check Database
        try:
            db.get_alerts(limit=1)
            status['services']['database'] = {
                'status': 'healthy',
                'path': config['database']['path']
            }
        except Exception as e:
            status['services']['database'] = {'status': 'error', 'error': str(e)}
            status['overall_status'] = 'degraded'

        # Check Geocoding
        if geocoding_service:
            try:
                stats = geocoding_service.get_statistics()
                status['services']['geocoding'] = {
                    'status': 'healthy',
                    'cache_addresses': stats.get('cache_stats', {}).get('total_addresses', 0)
                }
            except Exception as e:
                status['services']['geocoding'] = {'status': 'error', 'error': str(e)}
        else:
            status['services']['geocoding'] = {'status': 'disabled'}

        # Check Cache Manager
        if cache_manager:
            try:
                services_info = cache_manager.get_service_info()
                status['services']['cache_manager'] = {
                    'status': 'healthy',
                    'running': cache_manager.running,
                    'registered_services': len(services_info)
                }
            except Exception as e:
                status['services']['cache_manager'] = {'status': 'error', 'error': str(e)}
        else:
            status['services']['cache_manager'] = {'status': 'disabled'}

        return jsonify(status)

    except Exception as e:
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'error',
            'error': str(e)
        }), 500


@status_bp.route('/health')
def health_check():
    """Health check semplificato"""
    try:
        traccar = current_app.config['TRACCAR_API']
        server_info = traccar.server.get_server_info()

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'traccar_version': server_info.get('version')
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 503


# Error handlers
@status_bp.errorhandler(404)
def not_found(error):
    return render_template('errors/404.html'), 404


@status_bp.errorhandler(500)
def internal_error(error):
    logger.error(f"Errore interno status blueprint: {error}")
    return render_template('errors/500.html'), 500