# blueprints/geocoding.py
"""
Geocoding API Blueprint - Endpoint per servizio di geocoding
"""

from flask import Blueprint, jsonify, request, current_app
from core.services.geocoding_service import GeocodingService
import logging

geocoding_bp = Blueprint('geocoding', __name__)
logger = logging.getLogger('GeocodingAPI')

# Inizializza il servizio (verrà fatto nell'app principale)
geocoding_service = None


def init_geocoding_service(app):
    """Inizializza il servizio geocoding con configurazione app"""
    global geocoding_service

    config = app.config.get('CONFIG', {})
    google_config = config.get('google_maps', {})
    geocoding_config = config.get('geocoding', {})

    geocoding_service = GeocodingService(
        api_key=google_config.get('api_key'),
        cache_db_path=geocoding_config.get('cache_db_path', 'geocoding_cache.db')
    )

    logger.info("🌍 Geocoding service inizializzato per Flask API")
    return geocoding_service


@geocoding_bp.route('/reverse', methods=['GET', 'POST'])
def reverse_geocode():
    """
    Reverse geocoding - ottieni indirizzo da coordinate

    GET params:
        - lat: latitudine
        - lon: longitudine
        - language: lingua (opzionale, default: it)

    POST body:
        {
            "latitude": 41.9028,
            "longitude": 12.4964,
            "language": "it"
        }
    """
    if request.method == 'POST':
        data = request.get_json()
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        language = data.get('language', 'it')
    else:
        latitude = request.args.get('lat', type=float)
        longitude = request.args.get('lon', type=float)
        language = request.args.get('language', 'it')

    if latitude is None or longitude is None:
        return jsonify({
            'error': 'Missing required parameters: latitude and longitude'
        }), 400

    try:
        address = geocoding_service.get_address_from_coords(latitude, longitude, language)

        if address:
            return jsonify({
                'success': True,
                'address': {
                    'formatted': address.formatted_address,
                    'street': address.street,
                    'city': address.city,
                    'state': address.state,
                    'country': address.country,
                    'postal_code': address.postal_code
                },
                'coordinates': {
                    'latitude': latitude,
                    'longitude': longitude
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Address not found'
            }), 404

    except Exception as e:
        logger.error(f"Errore geocoding: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@geocoding_bp.route('/batch', methods=['POST'])
def batch_reverse_geocode():
    """
    Batch reverse geocoding - geocodifica multiple coordinate

    POST body:
        {
            "coordinates": [
                {"latitude": 41.9028, "longitude": 12.4964},
                {"latitude": 45.4642, "longitude": 9.1900}
            ],
            "language": "it"
        }
    """
    data = request.get_json()
    coordinates = data.get('coordinates', [])
    language = data.get('language', 'it')

    if not coordinates:
        return jsonify({'error': 'No coordinates provided'}), 400

    results = []

    for coord in coordinates:
        lat = coord.get('latitude')
        lon = coord.get('longitude')

        if lat is not None and lon is not None:
            address = geocoding_service.get_address_from_coords(lat, lon, language)

            results.append({
                'coordinates': {'latitude': lat, 'longitude': lon},
                'address': {
                    'formatted': address.formatted_address,
                    'city': address.city,
                    'country': address.country
                } if address else None
            })

    return jsonify({
        'success': True,
        'count': len(results),
        'results': results
    })


@geocoding_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """Ottieni statistiche del servizio geocoding"""
    stats = geocoding_service.get_statistics()

    return jsonify({
        'success': True,
        'statistics': stats
    })


@geocoding_bp.route('/cache/cleanup', methods=['POST'])
def cleanup_cache():
    """Pulisci cache scaduta"""
    deleted_count = geocoding_service.cleanup_cache()

    return jsonify({
        'success': True,
        'deleted_entries': deleted_count
    })


@geocoding_bp.route('/traccar/positions', methods=['GET'])
def get_traccar_positions_with_addresses():
    """
    Ottieni posizioni Traccar con indirizzi geocodificati

    Query params:
        - device_id: ID dispositivo (opzionale)
        - limit: numero massimo risultati (default: 10)
    """
    traccar = current_app.config.get('TRACCAR_API')

    device_id = request.args.get('device_id', type=int)
    limit = request.args.get('limit', 10, type=int)

    try:
        # Ottieni posizioni da Traccar
        if device_id:
            positions = traccar.get_positions(device_id=device_id)
        else:
            positions = traccar.get_positions()

        # Limita risultati
        positions = positions[:limit]

        # Arricchisci con geocoding
        enriched_positions = []

        for pos in positions:
            address = geocoding_service.get_address_from_coords(
                pos['latitude'],
                pos['longitude']
            )

            enriched_pos = {
                'device_id': pos['deviceId'],
                'position': {
                    'latitude': pos['latitude'],
                    'longitude': pos['longitude'],
                    'speed': pos.get('speed', 0),
                    'course': pos.get('course', 0)
                },
                'address': {
                    'formatted': address.formatted_address,
                    'city': address.city,
                    'country': address.country
                } if address else None,
                'timestamp': pos.get('fixTime') or pos.get('deviceTime')
            }

            enriched_positions.append(enriched_pos)

        return jsonify({
            'success': True,
            'count': len(enriched_positions),
            'positions': enriched_positions
        })

    except Exception as e:
        logger.error(f"Errore recupero posizioni: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@geocoding_bp.route('/traccar/device/<int:device_id>/location', methods=['GET'])
def get_device_location_with_address(device_id):
    """Ottieni posizione corrente dispositivo con indirizzo"""
    traccar = current_app.config.get('TRACCAR_API')

    try:
        positions = traccar.get_positions(device_id=device_id)

        if not positions:
            return jsonify({
                'success': False,
                'error': 'No position found for device'
            }), 404

        # Ultima posizione
        latest_pos = positions[0]

        # Geocodifica
        address = geocoding_service.get_address_from_coords(
            latest_pos['latitude'],
            latest_pos['longitude']
        )

        # Info dispositivo
        device = traccar.get_device(device_id)

        return jsonify({
            'success': True,
            'device': {
                'id': device_id,
                'name': device.get('name'),
                'status': device.get('status')
            },
            'location': {
                'latitude': latest_pos['latitude'],
                'longitude': latest_pos['longitude'],
                'speed': latest_pos.get('speed', 0),
                'course': latest_pos.get('course', 0),
                'altitude': latest_pos.get('altitude', 0)
            },
            'address': {
                'formatted': address.formatted_address,
                'street': address.street,
                'city': address.city,
                'state': address.state,
                'country': address.country,
                'postal_code': address.postal_code
            } if address else None,
            'timestamp': latest_pos.get('fixTime') or latest_pos.get('deviceTime')
        })

    except Exception as e:
        logger.error(f"Errore recupero location: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500