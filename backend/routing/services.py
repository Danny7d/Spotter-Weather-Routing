"""Trip planning orchestration: geocoding -> routing -> checkpoints."""

import hashlib
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from rest_framework.exceptions import ValidationError
from timezonefinder import TimezoneFinder

from weather.services import attach_weather_and_risk

from . import mapbox_client
from .checkpoints import build_checkpoints

_time_finder = TimezoneFinder()


def geocode_place(query):
    """Resolve a free-text place to coordinates + IANA timezone."""
    results = mapbox_client.geocode(query, limit=1)
    if not results:
        raise ValidationError(f'Could not find a location matching "{query}".')
    place = results[0]
    place['timezone'] = _time_finder.timezone_at(lat=place['latitude'], lng=place['longitude'])
    return place


def _local_departure_to_utc(departure_local, origin_timezone):
    """Interpret a naive local datetime in the origin's timezone -> UTC."""
    if not origin_timezone:
        raise ValidationError(
            'Could not determine the origin timezone from its coordinates.')
    try:
        zone = ZoneInfo(origin_timezone)
    except Exception as exc:
        raise ValidationError(f'Invalid origin timezone: {origin_timezone}') from exc

    naive = departure_local.replace(tzinfo=None) if departure_local.tzinfo is not None else departure_local
    candidates = []
    for fold in (0, 1):
        aware = naive.replace(tzinfo=zone, fold=fold)
        utc = aware.astimezone(dt_timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None) == naive:
            candidates.append(utc)
    unique = set(candidates)
    if not unique:
        raise ValidationError('Departure time does not exist in the origin timezone due to a daylight-saving transition.')
    if len(unique) > 1:
        raise ValidationError('Departure time is ambiguous in the origin timezone due to a daylight-saving transition.')
    departure_utc = unique.pop()
    if departure_utc <= datetime.now(dt_timezone.utc):
        raise ValidationError('Departure time must be in the future in the origin timezone.')
    return departure_utc


def _geometry_key(geometry):
    coords = geometry.get('coordinates', []) if geometry else []
    digest = hashlib.md5(repr(coords).encode()).hexdigest()
    return digest


def _build_route_option(index, raw_route, departure_utc, interval_miles):
    route_id = f'route-{index}'
    checkpoints = build_checkpoints(
        raw_route['geometry'], raw_route['distance_miles'],
        raw_route['duration_seconds'], departure_utc, interval_miles)
    return {
        'id': route_id,
        'geometry': raw_route['geometry'],
        'distance_miles': round(raw_route['distance_miles'], 2),
        'duration_seconds': round(raw_route['duration_seconds'], 1),
        'checkpoints': checkpoints,
    }


def build_trip_plan(origin_query, destination_query, departure_local,
                    load_weight_lbs, interval_miles):
    """Full pipeline: geocode, route, checkpoint, weather, risk, rank."""
    if not settings.MAPBOX_ACCESS_TOKEN:
        raise ValidationError(
            'MAPBOX_ACCESS_TOKEN is not configured; routing is unavailable. '
            'Set it in backend/.env.')

    origin = geocode_place(origin_query)
    destination = geocode_place(destination_query)

    if not origin.get('timezone'):
        raise ValidationError(
            f'Could not determine a timezone for "{origin_query}". '
            'Please try a location on land.')

    departure_utc = _local_departure_to_utc(departure_local, origin['timezone'])

    raw_routes = mapbox_client.get_directions(
        origin['longitude'], origin['latitude'],
        destination['longitude'], destination['latitude'], alternatives=True)

    # Drop exact-duplicate geometries Mapbox sometimes returns as alternatives.
    seen = set()
    unique_routes = []
    for raw in raw_routes:
        key = _geometry_key(raw.get('geometry'))
        if key not in seen:
            seen.add(key)
            unique_routes.append(raw)

    routes = [
        _build_route_option(i + 1, raw, departure_utc, interval_miles)
        for i, raw in enumerate(unique_routes)
    ]

    warnings = []
    if len(routes) < 3:
        warnings.append(
            f'The routing provider returned {len(routes)} route option(s); '
            'fewer than three alternatives were available for this trip.')

    routes, recommendation = attach_weather_and_risk(routes, load_weight_lbs)

    return {
        'origin': {
            'query': origin_query,
            'latitude': origin['latitude'],
            'longitude': origin['longitude'],
            'display_name': origin.get('display_name', ''),
            'timezone': origin['timezone'],
        },
        'destination': {
            'query': destination_query,
            'latitude': destination['latitude'],
            'longitude': destination['longitude'],
            'display_name': destination.get('display_name', ''),
            'timezone': destination.get('timezone'),
        },
        'departure_local': departure_local.isoformat(),
        'departure_utc': departure_utc.isoformat(),
        'origin_timezone': origin['timezone'],
        'load_weight_lbs': load_weight_lbs,
        'checkpoint_interval_miles': interval_miles,
        'routes': routes,
        'recommendation': recommendation,
        'warnings': warnings,
    }
