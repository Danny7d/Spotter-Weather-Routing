"""Thin client for the Mapbox Directions and Geocoding APIs.

All Mapbox credentials stay server-side; the frontend never sees the token.
"""

import logging
import requests
from django.conf import settings
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)

DIRECTIONS_URL = 'https://api.mapbox.com/directions/v5/mapbox/driving'
GEOCODING_URL = 'https://api.mapbox.com/search/geocode/v6/forward'


class MapboxAPIError(APIException):
    """Raised when Mapbox returns an error, is unreachable, or is not configured."""

    status_code = 503
    default_detail = 'Mapbox routing service is unavailable.'


def _require_token():
    token = settings.MAPBOX_ACCESS_TOKEN
    if not token:
        raise MapboxAPIError(
            'MAPBOX_ACCESS_TOKEN is not configured. Set it in backend/.env '
            'to enable routing and geocoding.'
        )
    return token


def geocode(query, limit=5):
    """Forward-geocode a free-text place name.

    Returns a list of dicts: {place_id, display_name, latitude, longitude}.
    """
    params = {
        'q': query,
        'limit': limit,
        'access_token': _require_token(),
    }
    try:
        response = requests.get(GEOCODING_URL, params=params,
                                timeout=settings.EXTERNAL_API_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.error('Mapbox geocoding network error: %s', exc)
        raise MapboxAPIError('Geocoding service is temporarily unavailable.') from exc

    if response.status_code != 200:
        logger.error('Mapbox geocoding error: status=%s, response=%s', response.status_code, response.text)
        raise MapboxAPIError(f'Geocoding failed with status {response.status_code}.')

    features = response.json().get('features', [])
    results = []
    for feature in features:
        coords = feature.get('geometry', {}).get('coordinates', [])
        if len(coords) < 2:
            continue
        results.append({
            'place_id': feature.get('properties', {}).get('mapbox_id', ''),
            'display_name': feature.get('properties', {}).get('full_address', ''),
            'longitude': coords[0],
            'latitude': coords[1],
        })
    return results


def get_directions(origin_lon, origin_lat, dest_lon, dest_lat, alternatives=True):
    """Request driving directions between two points.

    Returns a list of route dicts with keys:
      geometry (GeoJSON LineString), distance_miles, duration_seconds,
      and per-step detail for checkpoint interpolation.
    """
    coordinates = f'{origin_lon},{origin_lat};{dest_lon},{dest_lat}'
    alt_param = 'true' if alternatives else 'false'
    params = {
        'geometries': 'geojson',
        'overview': 'full',
        'alternatives': alt_param,
        'steps': 'true',
        'access_token': _require_token(),
    }
    url = f'{DIRECTIONS_URL}/{coordinates}'
    try:
        response = requests.get(url, params=params,
                                timeout=settings.EXTERNAL_API_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.error('Mapbox directions network error: %s', exc)
        raise MapboxAPIError('Directions service is temporarily unavailable.') from exc

    if response.status_code != 200:
        logger.error('Mapbox directions error: status=%s, response=%s', response.status_code, response.text)
        raise MapboxAPIError(f'Directions request failed with status {response.status_code}.')

    routes = []
    for route in response.json().get('routes', []):
        routes.append({
            'geometry': route.get('geometry'),
            'distance_miles': route.get('distance', 0.0) / 1609.344,
            'duration_seconds': route.get('duration', 0.0),
            'legs': route.get('legs', []),
        })
    return routes
