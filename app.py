# app.py
"""
Fleet Manager Pro - Applicazione principale con gestione cache avanzata
Integra Traccar API, Database SQLite, Geocoding Service e Cache Manager
"""

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_cors import CORS
import json
import os
import logging
from datetime import datetime, timedelta
from functools import wraps
import atexit

# Import blueprints
from blueprints.api import api_bp
from blueprints.auth import auth_bp
from blueprints.dashboard import dashboard_bp
from blueprints.reports import reports_bp
from blueprints.vehicles import vehicles_bp
from blueprints.alerts import alerts_bp

# Import framework e modelli
from core.traccar_framework import TraccarAPI
from models.database import Database

# Import servizi cache
from core.services.cache_manager import cache_manager

# Import geocoding service e blueprint
try:
    from blueprints.geocoding import geocoding_bp, init_geocoding_service
    from core.services.geocoding_service import GeocodingService

    GEOCODING_AVAILABLE = True
except ImportError:
    print("⚠️ Geocoding module not available")
    GEOCODING_AVAILABLE = False

# Import status blueprint
try:
    from blueprints.status import status_bp

    STATUS_AVAILABLE = True
except ImportError:
    print("⚠️ Status module not available")
    STATUS_AVAILABLE = False

# Import cache management blueprint
try:
    from blueprints.cache_management import cache_management_bp

    CACHE_MANAGEMENT_AVAILABLE = True
except ImportError:
    print("⚠️ Cache management module not available")
    CACHE_MANAGEMENT_AVAILABLE = False


# Configura logging
def setup_logging():
    """Configura sistema di logging"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)

        log_config = config.get('logging', {})
        log_file = log_config.get('file', 'logs/fleet_manager.log')
        log_level = getattr(logging, log_config.get('level', 'INFO').upper())
        log_format = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Crea directory logs
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # Configura logging
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )

    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logging.error(f"Errore configurazione logging: {e}")


# Jinja2 Filters
def datetime_filter(value, format='%d/%m/%Y %H:%M'):
    """Filtro Jinja2 per formattare date"""
    if not value:
        return 'N/A'

    try:
        # Se è già un oggetto datetime
        if isinstance(value, datetime):
            return value.strftime(format)

        # Se è una stringa, prova a parsarla
        if isinstance(value, str):
            # Gestisci formati ISO con Z
            if value.endswith('Z'):
                value = value[:-1] + '+00:00'
            elif '+' not in value and value.count(':') >= 2:
                value += '+00:00'

            # Prova diversi formati
            formats = [
                '%Y-%m-%dT%H:%M:%S%z',
                '%Y-%m-%dT%H:%M:%S.%f%z',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%d %H:%M:%S',
                '%d/%m/%Y %H:%M:%S',
                '%d/%m/%Y %H:%M'
            ]

            for fmt in formats:
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.strftime(format)
                except ValueError:
                    continue

        return str(value)
    except Exception as e:
        return f'Invalid date: {value}'


def datetime_ago_filter(value):
    """Filtro per mostrare tempo relativo"""
    if not value:
        return 'N/A'

    try:
        if isinstance(value, str):
            if value.endswith('Z'):
                value = value[:-1] + '+00:00'
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        elif isinstance(value, datetime):
            dt = value
        else:
            return 'N/A'

        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt

        if diff.days > 0:
            return f'{diff.days} giorni fa'
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f'{hours} ore fa'
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f'{minutes} minuti fa'
        else:
            return 'Ora'

    except Exception:
        return 'N/A'


def currency_filter(value):
    """Filtro per valuta"""
    try:
        return f"€{float(value):,.2f}"
    except:
        return "€0,00"


def filesize_filter(value):
    """Filtro per dimensione file"""
    try:
        bytes_value = float(value)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"
    except:
        return "0 B"


def register_jinja_filters(app):
    """Registra tutti i filtri Jinja2"""
    app.jinja_env.filters['datetime'] = datetime_filter
    app.jinja_env.filters['datetimeformat'] = datetime_filter  # Alias
    app.jinja_env.filters['datetime_ago'] = datetime_ago_filter
    app.jinja_env.filters['currency'] = currency_filter
    app.jinja_env.filters['filesize'] = filesize_filter

    # Filtro per round se non presente
    if 'round' not in app.jinja_env.filters:
        app.jinja_env.filters['round'] = lambda x, n=0: round(float(x or 0), n)


# Decorator per login richiesto
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated_function


def create_app():
    """Factory per creare l'app Flask"""
    # Setup logging
    setup_logging()
    logger = logging.getLogger('FleetApp')

    # Carica configurazione
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        logger.info("📋 Configurazione caricata")
    except Exception as e:
        logger.error(f"❌ Errore caricamento config: {e}")
        raise

    # Inizializza Flask app
    app = Flask(__name__)
    app.config['SECRET_KEY'] = config.get('app', {}).get('secret_key', os.urandom(24))
    app.config['SESSION_PERMANENT'] = False

    # Abilita CORS se configurato
    if config.get('security', {}).get('enable_cors', True):
        CORS(app)

    # Registra filtri Jinja2
    register_jinja_filters(app)

    # Crea directory necessarie
    db_path = config['database']['path']
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"📁 Directory database creata: {db_dir}")

    # Inizializza Traccar API
    traccar = TraccarAPI(
        host=config['traccar']['host'],
        port=config['traccar']['port'],
        username=config['traccar']['username'],
        password=config['traccar']['password'],
        protocol=config['traccar'].get('protocol', 'http'),
        debug=config['traccar'].get('debug', False)
    )

    # Inizializza Database
    db = Database(db_path)

    # Inizializza Geocoding Service
    geocoding_service = None
    if GEOCODING_AVAILABLE and config.get('features', {}).get('geocoding_enabled', True):
        try:
            geocoding_config = config.get('geocoding', {})
            google_config = config.get('google_maps', {})

            # Crea directory per cache geocoding
            cache_db_path = geocoding_config.get('cache_db_path', 'data/geocoding_cache.db')
            cache_dir = os.path.dirname(cache_db_path)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)

            api_key = google_config.get('api_key', '')
            if api_key:
                geocoding_service = GeocodingService(
                    api_key=api_key,
                    cache_db_path=cache_db_path,
                    max_age_days=geocoding_config.get('max_age_days', 90),
                    precision=geocoding_config.get('precision', 5)
                )

                # Registra geocoding service nel cache manager
                cache_manager.register_service(
                    name='geocoding',
                    service_instance=geocoding_service,
                    cleanup_method='cleanup_cache',
                    optimize_method='optimize_cache',
                    stats_method='get_statistics'
                )

                logger.info("✅ Geocoding service inizializzato e registrato")
            else:
                logger.warning("⚠️ Google Maps API key mancante")
        except Exception as e:
            logger.error(f"❌ Errore inizializzazione geocoding: {e}")

    # Avvia cache manager automatico se abilitato
    if config.get('geocoding', {}).get('enable_auto_cleanup', True):
        cleanup_interval = config.get('geocoding', {}).get('cleanup_interval_hours', 24)
        cache_manager.cleanup_interval_hours = cleanup_interval
        cache_manager.start_automatic_cleanup()
        logger.info(f"🔄 Cache manager automatico avviato (intervallo: {cleanup_interval}h)")

    # Memorizza istanze nell'app config per l'accesso dai blueprint
    app.config['TRACCAR_API'] = traccar
    app.config['DATABASE'] = db
    app.config['CONFIG'] = config
    app.config['GEOCODING_SERVICE'] = geocoding_service
    app.config['CACHE_MANAGER'] = cache_manager

    # Registra tutti i blueprint
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(vehicles_bp, url_prefix='/vehicles')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(alerts_bp, url_prefix='/alerts')
    app.register_blueprint(api_bp, url_prefix='/api')

    # Registra status blueprint se disponibile
    if STATUS_AVAILABLE:
        app.register_blueprint(status_bp, url_prefix='/status')
        logger.info("✅ Status blueprint registrato")

    # Registra cache management blueprint se disponibile
    if CACHE_MANAGEMENT_AVAILABLE:
        app.register_blueprint(cache_management_bp, url_prefix='/api/cache')
        logger.info("✅ Cache management blueprint registrato")

    # Registra geocoding blueprint se disponibile
    if GEOCODING_AVAILABLE and geocoding_service:
        app.register_blueprint(geocoding_bp, url_prefix='/api/geocoding')
        with app.app_context():
            init_geocoding_service(app)
        logger.info("✅ Geocoding blueprint registrato")

    # Routes principali
    @app.route('/')
    def index():
        """Route principale - redirect in base allo stato auth"""
        if 'user' in session:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))

    @app.route('/health')
    def health():
        """Health check endpoint completo"""
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'services': {}
        }

        overall_healthy = True

        # Check Traccar
        try:
            server_info = traccar.server.get_server_info()
            health_status['services']['traccar'] = {
                'status': 'healthy',
                'version': server_info.get('version'),
                'host': f"{config['traccar']['host']}:{config['traccar']['port']}"
            }
        except Exception as e:
            health_status['services']['traccar'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            overall_healthy = False

        # Check Database
        try:
            db.get_alerts(limit=1)
            health_status['services']['database'] = {
                'status': 'healthy',
                'path': config['database']['path']
            }
        except Exception as e:
            health_status['services']['database'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            overall_healthy = False

        # Check Geocoding Service
        if geocoding_service:
            try:
                stats = geocoding_service.get_statistics()
                health_status['services']['geocoding'] = {
                    'status': 'healthy',
                    'cache_addresses': stats.get('cache_stats', {}).get('total_addresses', 0),
                    'hit_rate': stats.get('cache_stats', {}).get('hit_rate_percent', 0)
                }
            except Exception as e:
                health_status['services']['geocoding'] = {
                    'status': 'degraded',
                    'error': str(e)
                }
        else:
            health_status['services']['geocoding'] = {
                'status': 'disabled',
                'message': 'Geocoding service not configured'
            }

        # Check Cache Manager
        try:
            cache_info = cache_manager.get_service_info()
            health_status['services']['cache_manager'] = {
                'status': 'healthy',
                'running': cache_manager.running,
                'registered_services': len(cache_info),
                'cleanup_interval_hours': cache_manager.cleanup_interval_hours
            }
        except Exception as e:
            health_status['services']['cache_manager'] = {
                'status': 'unhealthy',
                'error': str(e)
            }

        health_status['status'] = 'healthy' if overall_healthy else 'degraded'
        status_code = 200 if overall_healthy else 503

        return jsonify(health_status), status_code

    # Route diretta per compatibility con il template esistente
    @app.route('/status')
    def status_redirect():
        """Redirect al blueprint status per compatibility"""
        if STATUS_AVAILABLE:
            return redirect(url_for('status.index'))
        else:
            # Fallback se status blueprint non disponibile
            return redirect(url_for('health'))

    @app.before_request
    def before_request():
        """Eseguito prima di ogni richiesta"""
        # Rate limiting se abilitato
        if config.get('security', {}).get('enable_rate_limiting', False):
            # Implementa rate limiting qui se necessario
            pass

    @app.after_request
    def after_request(response):
        """Eseguito dopo ogni richiesta"""
        # Aggiungi header di sicurezza
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # CORS headers se abilitato
        if config.get('security', {}).get('enable_cors', True):
            allowed_origins = config.get('security', {}).get('allowed_origins', ['*'])
            if '*' in allowed_origins:
                response.headers['Access-Control-Allow-Origin'] = '*'

        return response

    @app.teardown_appcontext
    def cleanup(error=None):
        """Pulizia risorse al termine del contesto"""
        if error:
            logger.error(f"Errore nel contesto app: {error}")

    def shutdown_handler():
        """Handler per shutdown dell'applicazione"""
        logger.info("🛑 Shutdown dell'applicazione in corso...")

        # Ferma cache manager
        cache_manager.stop_automatic_cleanup()

        # Chiudi geocoding service
        if geocoding_service:
            try:
                geocoding_service.close()
                logger.info("🌍 Geocoding service chiuso")
            except Exception as e:
                logger.error(f"Errore chiusura geocoding service: {e}")

        # Chiudi database
        try:
            if hasattr(db, 'close'):
                db.close()
                logger.info("📊 Database chiuso")
        except Exception as e:
            logger.error(f"Errore chiusura database: {e}")

        logger.info("✅ Shutdown completato")

    # Registra handler per shutdown
    atexit.register(shutdown_handler)
    app.shutdown_handler = shutdown_handler  # Per accesso esterno

    return app


def startup_check(app):
    """Controlli di avvio dell'applicazione"""
    config = app.config['CONFIG']
    traccar = app.config['TRACCAR_API']
    db = app.config['DATABASE']
    geocoding_service = app.config.get('GEOCODING_SERVICE')

    print("\n" + "=" * 70)
    print("🚀 Fleet Manager Pro - Enhanced Edition v2.0")
    print("=" * 70)

    # Check Traccar
    print("\n📡 Controllo connessione Traccar...")
    try:
        server_info = traccar.server.get_server_info()
        print(f"✅ Connesso a Traccar v{server_info.get('version')}")
        print(
            f"   Server: {config['traccar'].get('protocol', 'http')}://{config['traccar']['host']}:{config['traccar']['port']}")
    except Exception as e:
        print(f"❌ Errore connessione Traccar: {e}")
        print("⚠️ L'applicazione partirà ma alcune funzioni potrebbero non funzionare")

    # Check database
    print("\n💾 Controllo database...")
    try:
        db.get_alerts(limit=1)
        print(f"✅ Database operativo: {config['database']['path']}")
    except Exception as e:
        print(f"⚠️ Warning database: {e}")

    # Check geocoding service
    print("\n🌍 Controllo servizio Geocoding...")
    if geocoding_service:
        try:
            stats = geocoding_service.get_statistics()
            cache_stats = stats.get('cache_stats', {})
            print(f"✅ Servizio Geocoding attivo")
            print(f"   Cache DB: {config.get('geocoding', {}).get('cache_db_path', 'N/A')}")
            print(f"   Indirizzi in cache: {cache_stats.get('total_addresses', 0)}")
            print(f"   Dimensione cache: {cache_stats.get('db_size_mb', 0):.2f} MB")
            print(f"   Hit rate: {cache_stats.get('hit_rate_percent', 0):.1f}%")
        except Exception as e:
            print(f"⚠️ Errore servizio Geocoding: {e}")
    else:
        print("⚠️ Servizio Geocoding non configurato")

    # Check cache manager
    print("\n🔧 Controllo Cache Manager...")
    try:
        services_info = cache_manager.get_service_info()
        print(f"✅ Cache Manager attivo")
        print(f"   Servizi registrati: {len(services_info)}")
        print(f"   Pulizia automatica: {'Attiva' if cache_manager.running else 'Inattiva'}")
        print(f"   Intervallo pulizia: {cache_manager.cleanup_interval_hours}h")

        for service in services_info:
            print(f"   - {service['name']}: cleanup={service['cleanup_method']}")
    except Exception as e:
        print(f"⚠️ Errore Cache Manager: {e}")

    # Check blueprints
    print("\n🔌 Blueprint registrati...")
    if STATUS_AVAILABLE:
        print("✅ Status Blueprint: /status")
    if CACHE_MANAGEMENT_AVAILABLE:
        print("✅ Cache Management Blueprint: /api/cache")
    if GEOCODING_AVAILABLE and geocoding_service:
        print("✅ Geocoding Blueprint: /api/geocoding")

    print("\n" + "=" * 70)
    print("✨ Applicazione pronta!")
    print(f"🌐 URL: http://localhost:5000")
    print(f"📊 Dashboard: http://localhost:5000/dashboard")
    print(f"📱 Health check: http://localhost:5000/health")
    if STATUS_AVAILABLE:
        print(f"🔧 System status: http://localhost:5000/status")
    if CACHE_MANAGEMENT_AVAILABLE:
        print(f"🗂️ Cache stats: http://localhost:5000/api/cache/statistics")
    print("=" * 70)
    print()


if __name__ == '__main__':
    # Crea l'app
    app = create_app()
    config = app.config['CONFIG']

    # Esegui controlli di startup
    startup_check(app)

    try:
        app.run(
            debug=config.get('app', {}).get('debug', False),
            host='0.0.0.0',
            port=5000
        )
    except KeyboardInterrupt:
        print("\n🛑 Interruzione da tastiera ricevuta")
        if hasattr(app, 'shutdown_handler'):
            app.shutdown_handler()
    except Exception as e:
        logger = logging.getLogger('FleetApp')
        logger.error(f"❌ Errore avvio applicazione: {e}")
        if hasattr(app, 'shutdown_handler'):
            app.shutdown_handler()
        raise