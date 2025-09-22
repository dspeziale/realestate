# blueprints/cache_management.py
"""
Blueprint per gestione centralizzata delle cache
Fornisce API REST per controllo e monitoraggio dei servizi cache
"""

from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import logging

logger = logging.getLogger('CacheManagementBlueprint')

cache_management_bp = Blueprint('cache_management', __name__)


@cache_management_bp.route('/statistics', methods=['GET'])
def get_all_cache_statistics():
    """
    Ottieni statistiche complete di tutte le cache
    GET /api/cache/statistics
    """
    try:
        cache_manager = current_app.config.get('CACHE_MANAGER')
        if not cache_manager:
            return jsonify({
                'success': False,
                'error': 'Cache manager non disponibile'
            }), 503

        stats = cache_manager.get_all_statistics()

        # Aggiungi informazioni di sistema
        system_info = {
            'app_name': current_app.config.get('CONFIG', {}).get('app', {}).get('name', 'Fleet Manager'),
            'version': current_app.config.get('CONFIG', {}).get('app', {}).get('version', '1.0.0'),
            'timestamp': datetime.now().isoformat()
        }

        return jsonify({
            'success': True,
            'statistics': stats,
            'system_info': system_info
        })

    except Exception as e:
        logger.error(f"Errore recupero statistiche cache: {e}")
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500


@cache_management_bp.route('/cleanup', methods=['POST'])
def cleanup_all_caches():
    """
    Pulizia manuale di tutte le cache registrate
    POST /api/cache/cleanup
    """
    try:
        cache_manager = current_app.config.get('CACHE_MANAGER')
        if not cache_manager:
            return jsonify({
                'success': False,
                'error': 'Cache manager non disponibile'
            }), 503

        results = cache_manager.cleanup_all_services()

        # Calcola statistiche aggregate
        total_deleted = sum(r.get('deleted_entries', 0) for r in results.values() if r.get('success'))
        success_count = sum(1 for r in results.values() if r.get('success'))
        total_services = len(results)

        return jsonify({
            'success': True,
            'message': f'Pulizia completata per {success_count}/{total_services} servizi',
            'results': results,
            'summary': {
                'total_services': total_services,
                'successful_services': success_count,
                'failed_services': total_services - success_count,
                'total_deleted_entries': total_deleted,
                'success_rate': (success_count / total_services * 100) if total_services > 0 else 0
            },
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Errore pulizia cache: {e}")
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500


@cache_management_bp.route('/optimize', methods=['POST'])
def optimize_all_caches():
    """
    Ottimizzazione manuale di tutte le cache che la supportano
    POST /api/cache/optimize
    """
    try:
        cache_manager = current_app.config.get('CACHE_MANAGER')
        if not cache_manager:
            return jsonify({
                'success': False,
                'error': 'Cache manager non disponibile'
            }), 503

        results = cache_manager.optimize_all_services()

        # Calcola statistiche
        success_count = sum(1 for r in results.values() if r.get('success'))
        total_services = len(results)

        return jsonify({
            'success': True,
            'message': f'Ottimizzazione completata per {success_count}/{total_services} servizi',
            'results': results,
            'summary': {
                'total_services': total_services,
                'successful_services': success_count,
                'failed_services': total_services - success_count,
                'success_rate': (success_count / total_services * 100) if total_services > 0 else 0
            },
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Errore ottimizzazione cache: {e}")
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500


@cache_management_bp.route('/services', methods=['GET'])
def get_registered_services():
    """
    Lista dei servizi cache registrati
    GET /api/cache/services
    """
    try:
        cache_manager = current_app.config.get('CACHE_MANAGER')
        if not cache_manager:
            return jsonify({
                'success': False,
                'error': 'Cache manager non disponibile'
            }), 503

        services_info = cache_manager.get_service_info()

        return jsonify({
            'success': True,
            'services': services_info,
            'count': len(services_info),
            'manager_status': {
                'running': cache_manager.running,
                'cleanup_interval_hours': cache_manager.cleanup_interval_hours
            },
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Errore recupero servizi cache: {e}")
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500


@cache_management_bp.route('/services/<service_name>/cleanup', methods=['POST'])
def cleanup_specific_service(service_name):
    """
    Pulizia di un servizio cache specifico
    POST /api/cache/services/<service_name>/cleanup
    """
    try:
        cache_manager = current_app.config.get('CACHE_MANAGER')
        if not cache_manager:
            return jsonify({
                'success': False,
                'error': 'Cache manager non disponibile'
            }), 503

        result = cache_manager.cleanup_service(service_name)

        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"Errore pulizia servizio {service_name}: {e}")
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500


@cache_management_bp.route('/services/<service_name>/optimize', methods=['POST'])
def optimize_specific_service(service_name):
    """
    Ottimizzazione di un servizio cache specifico
    POST /api/cache/services/<service_name>/optimize
    """
    try:
        cache_manager = current_app.config.get('CACHE_MANAGER')
        if not cache_manager:
            return jsonify({
                'success': False,
                'error': 'Cache manager non disponibile'
            }), 503

        result = cache_manager.optimize_service(service_name)

        status_code = 200 if result.get('success') else 400
        return jsonify(result), status_code

    except Exception as e:
        logger.error(f"Errore ottimizzazione servizio {service_name}: {e}")
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500


@cache_management_bp.route('/services/<service_name>/statistics', methods=['GET'])
def get_service_statistics(service_name):
    """
    Statistiche specifiche di un servizio cache
    GET /api/cache/services/<service_name>/statistics
    """
    try:
        cache_manager = current_app.config.get('CACHE_MANAGER')
        if not cache_manager:
            return jsonify({
                'success': False,
                'error': 'Cache manager non disponibile'
            }), 503

        # Verifica se il servizio esiste
        services_info = cache_manager.get_service_info()
        service_exists = any(s['name'] == service_name for s in services_info)

        if not service_exists:
            return jsonify({
                'success': False,
                'error': f'Servizio {service_name} non trovato'
            }), 404

        # Ottieni statistiche complete e filtra per il servizio richiesto
        all_stats = cache_manager.get_all_statistics()
        service_stats = all_stats.get('services', {}).get(service_name)

        if not service_stats:
            return jsonify({
                'success': False,
                'error': f'Statistiche non disponibili per {service_name}'
            }), 404

        return jsonify({
            'success': True,
            'service_name': service_name,
            'statistics': service_stats,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Errore statistiche servizio {service_name}: {e}")
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500


@cache_management_bp.route('/health', methods=['GET'])
def cache_health_check():
    """
    Health check specifico per il sistema cache
    GET /api/cache/health
    """
    try:
        cache_manager = current_app.config.get('CACHE_MANAGER')

        if not cache_manager:
            return jsonify({
                'success': False,
                'status': 'unhealthy',
                'error': 'Cache manager non configurato'
            }), 503

        services_info = cache_manager.get_service_info()

        # Test base del cache manager
        try:
            all_stats = cache_manager.get_all_statistics()
            manager_healthy = True
            manager_error = None
        except Exception as e:
            manager_healthy = False
            manager_error = str(e)

        health_status = {
            'success': True,
            'status': 'healthy' if manager_healthy else 'degraded',
            'cache_manager': {
                'status': 'healthy' if manager_healthy else 'error',
                'running': cache_manager.running,
                'error': manager_error,
                'cleanup_interval_hours': cache_manager.cleanup_interval_hours
            },
            'registered_services': {
                'count': len(services_info),
                'services': [s['name'] for s in services_info]
            },
            'timestamp': datetime.now().isoformat()
        }

        status_code = 200 if manager_healthy else 503
        return jsonify(health_status), status_code

    except Exception as e:
        logger.error(f"Errore health check cache: {e}")
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': 'Errore interno del server'
        }), 500


@cache_management_bp.route('/config', methods=['GET'])
def get_cache_config():
    """
    Configurazione corrente del sistema cache
    GET /api/cache/config
    """
    try:
        cache_manager = current_app.config.get('CACHE_MANAGER')
        if not cache_manager:
            return jsonify({
                'success': False,
                'error': 'Cache manager non disponibile'
            }), 503

        config = current_app.config.get('CONFIG', {})

        cache_config = {
            'geocoding': config.get('geocoding', {}),
            'cache': config.get('cache', {}),
            'performance': config.get('performance', {}),
            'manager': {
                'cleanup_interval_hours': cache_manager.cleanup_interval_hours,
                'running': cache_manager.running,
                'registered_services': len(cache_manager.registered_services)
            }
        }

        return jsonify({
            'success': True,
            'configuration': cache_config,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Errore recupero configurazione cache: {e}")
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500


# Error handlers per il blueprint
@cache_management_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint non trovato'
    }), 404


@cache_management_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'success': False,
        'error': 'Metodo HTTP non consentito'
    }), 405


@cache_management_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Errore interno del server'
    }), 500