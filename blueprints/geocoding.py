# blueprints/geocoding.py
"""
Blueprint per API Geocoding con cache SQLite
Fornisce endpoint REST per servizi di geocoding
"""

from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
import logging

logger = logging.getLogger('GeocodingBlueprint')

geocoding_bp = Blueprint('geocoding', __name__)


def init_geocoding_service(app):
    """Inizializza il servizio geocoding nel contesto dell'app"""
    with app.app_context():
        app.geocoding_service = current_app.config.get('GEOCODING_SERVICE')


@geocoding_bp.route('/reverse', methods=['POST'])
def reverse_geocode():
    """
    Reverse geocoding: coordinate -> indirizzo
    POST /api/geocoding/reverse
    Body: {"latitude": 45.0642, "longitude": 7.6614, "force_refresh": false}
    """
    try:
        data = request.get_json()

        if not data or 'latitude' not in data or 'longitude' not in data:
            return jsonify({
                'success': False,
                'error': 'Parametri latitude e longitude richiesti'
            }), 400

        latitude = float(data['latitude'])
        longitude = float(data['longitude'])
        force_refresh = data.get('force_refresh', False)

        # Validazione coordinate
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            return jsonify({
                'success': False,
                'error': 'Coordinate non valide'
            }), 400

        geocoding_service = current_app.config.get('GEOCODING_SERVICE')
        if not geocoding_service:
            return jsonify({
                'success': False,
                'error': 'Servizio geocoding non disponibile'
            }), 503

        # Esegui reverse geocoding
        address = geocoding_service.get_address_from_coordinates(
            latitude, longitude, force_refresh
        )

        if address:
            return jsonify({
                'success': True,
                'address': {
                    'formatted_address': address.formatted_address,
                    'street': address.street,
                    'city': address.city,
                    'state': address.state,
                    'country': address.country,
                    'postal_code': address.postal_code,
                    'latitude': address.latitude,
                    'longitude': address.longitude
                },
                'source': 'cache' if not force_refresh else 'api',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Indirizzo non trovato per le coordinate specificate',
                'latitude': latitude,
                'longitude': longitude
            }), 404

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Parametri non validi: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"Errore reverse geocoding: {e}")
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500


@geocoding_bp.route('/batch', methods=['POST'])
def batch_geocode():
    """
    Batch reverse geocoding per multiple coordinate
    POST /api/geocoding/batch
    Body: {"coordinates": [[45.0642, 7.6614], [45.0700, 7.6700]]}
    """
    try:
        data = request.get_json()

        if not data or 'coordinates' not in data:
            return jsonify({
                'success': False,
                'error': 'Array coordinates richiesto'
            }), 400

        coordinates = data['coordinates']

        if not isinstance(coordinates, list) or len(coordinates) == 0:
            return jsonify({
                'success': False,
                'error': 'Array coordinates deve contenere almeno una coordinata'
            }), 400

        if len(coordinates) > 100:  # Limite per evitare sovraccarico
            return jsonify({
                'success': False,
                'error': 'Massimo 100 coordinate per richiesta batch'
            }), 400

        # Valida e converti coordinate
        coord_tuples = []
        for i, coord in enumerate(coordinates):
            if not isinstance(coord, list) or len(coord) != 2:
                return jsonify({
                    'success': False,
                    'error': f'Coordinata {i} deve essere [lat, lon]'
                }), 400

            try:
                lat, lon = float(coord[0]), float(coord[1])
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    return jsonify({
                        'success': False,
                        'error': f'Coordinata {i} non valida: [{lat}, {lon}]'
                    }), 400
                coord_tuples.append((lat, lon))
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': f'Coordinata {i} deve essere numerica'
                }), 400

        geocoding_service = current_app.config.get('GEOCODING_SERVICE')
        if not geocoding_service:
            return jsonify({
                'success': False,
                'error': 'Servizio geocoding non disponibile'
            }), 503

        # Esegui batch geocoding
        results = geocoding_service.batch_geocode(coord_tuples)

        # Formatta risultati
        formatted_results = []
        for lat, lon in coord_tuples:
            address = results.get((lat, lon))
            if address:
                formatted_results.append({
                    'latitude': lat,
                    'longitude': lon,
                    'success': True,
                    'address': {
                        'formatted_address': address.formatted_address,
                        'street': address.street,
                        'city': address.city,
                        'state': address.state,
                        'country': address.country,
                        'postal_code': address.postal_code
                    }
                })
            else:
                formatted_results.append({
                    'latitude': lat,
                    'longitude': lon,
                    'success': False,
                    'error': 'Indirizzo non trovato'
                })

        successful_count = len(results)

        return jsonify({
            'success': True,
            'results': formatted_results,
            'summary': {
                'total_requested': len(coordinates),
                'successful': successful_count,
                'failed': len(coordinates) - successful_count,
                'success_rate': (successful_count / len(coordinates)) * 100
            },
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Errore batch geocoding: {e}")
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500


@geocoding_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """
    Ottieni statistiche del servizio geocoding
    GET /api/geocoding/statistics
    """
    try:
        geocoding_service = current_app.config.get('GEOCODING_SERVICE')
        if not geocoding_service:
            return jsonify({
                'success': False,
                'error': 'Servizio geocoding non disponibile'
            }), 503

        stats = geocoding_service.get_statistics()

        return jsonify({
            'success': True,
            'statistics': stats,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Errore recupero statistiche: {e}")
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500


@geocoding_bp.route('/cache/cleanup', methods=['POST'])
def cleanup_cache():
    """
    Pulizia manuale della cache
    POST /api/geocoding/cache/cleanup
    """
    try:
        geocoding_service = current_app.config.get('GEOCODING_SERVICE')
        if not geocoding_service:
            return jsonify({
                'success': False,
                'error': 'Servizio geocoding non disponibile'
            }), 503

        deleted_count = geocoding_service.cleanup_cache()

        return jsonify({
            'success': True,
            'message': f'Cache pulita: {deleted_count} indirizzi rimossi',
            'deleted_entries': deleted_count,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Errore pulizia cache: {e}")
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500


@geocoding_bp.route('/cache/optimize', methods=['POST'])
def optimize_cache():
    """
    Ottimizza database cache
    POST /api/geocoding/cache/optimize
    """
    try:
        geocoding_service = current_app.config.get('GEOCODING_SERVICE')
        if not geocoding_service:
            return jsonify({
                'success': False,
                'error': 'Servizio geocoding non disponibile'
            }), 503

        geocoding_service.optimize_cache()

        return jsonify({
            'success': True,
            'message': 'Database cache ottimizzato',
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"Errore ottimizzazione cache: {e}")
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500


@geocoding_bp.route('/search', methods=['GET'])
def search_addresses():
    """
    Ricerca indirizzi nella cache
    GET /api/geocoding/search?country=Italy&city=Milano&limit=50
    """
    try:
        geocoding_service = current_app.config.get('GEOCODING_SERVICE')
        if not geocoding_service:
            return jsonify({
                'success': False,
                'error': 'Servizio geocoding non disponibile'
            }), 503

        country = request.args.get('country')
        city = request.args.get('city')
        state = request.args.get('state')
        limit = min(int(request.args.get('limit', 50)), 200)  # Max 200

        addresses = geocoding_service.cache.get_addresses_by_region(
            country=country,
            state=state,
            city=city,
            limit=limit
        )

        return jsonify({
            'success': True,
            'addresses': addresses,
            'filters': {
                'country': country,
                'state': state,
                'city': city,
                'limit': limit
            },
            'count': len(addresses),
            'timestamp': datetime.now().isoformat()
        })

    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Parametro limit non valido: {str(e)}'
        }), 400
    except Exception as e:
        logger.error(f"Errore ricerca indirizzi: {e}")
        return jsonify({
            'success': False,
            'error': 'Errore interno del server'
        }), 500


@geocoding_bp.route('/health', methods=['GET'])
def health_check():
    """
    Health check del servizio geocoding
    GET /api/geocoding/health
    """
    try:
        geocoding_service = current_app.config.get('GEOCODING_SERVICE')

        if not geocoding_service:
            return jsonify({
                'success': False,
                'status': 'unhealthy',
                'error': 'Servizio geocoding non configurato'
            }), 503

        # Test connessione cache
        try:
            stats = geocoding_service.cache.get_statistics()
            cache_healthy = True
            cache_error = None
        except Exception as e:
            cache_healthy = False
            cache_error = str(e)

        health_status = {
            'success': True,
            'status': 'healthy' if cache_healthy else 'degraded',
            'service': 'geocoding',
            'cache': {
                'status': 'healthy' if cache_healthy else 'error',
                'error': cache_error,
                'total_addresses': stats.get('cache_stats', {}).get('total_addresses', 0) if cache_healthy else 0
            },
            'api': {
                'status': 'configured' if geocoding_service.api_key else 'missing_key'
            },
            'timestamp': datetime.now().isoformat()
        }

        status_code = 200 if cache_healthy else 503
        return jsonify(health_status), status_code

    except Exception as e:
        logger.error(f"Errore health check: {e}")
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': 'Errore interno del server'
        }), 500


# Error handlers per il blueprint
@geocoding_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint non trovato'
    }), 404


@geocoding_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'success': False,
        'error': 'Metodo HTTP non consentito'
    }), 405


@geocoding_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Errore interno del server'
    }), 500