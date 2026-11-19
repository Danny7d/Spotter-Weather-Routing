"""Weather retrieval and risk attachment for routes and corridor forecasts."""

from datetime import timedelta

from .metrics import compute_route_metrics, rank_routes, build_recommendation
from .openmeteo import fetch_hourly_forecast, weather_at_utc
from .risk import classify_checkpoint_risk
from .units import (celsius_to_fahrenheit, cm_per_hour_to_inches_per_hour,
                    kmh_to_mph, mm_per_hour_to_inches_per_hour)

FORECAST_SOURCE = 'open-meteo'


def _hourly_to_imperial(hourly_values):
    """Convert one Open-Meteo hourly sample to app units.

    Returns dict with wind_mph, rain_in_hr, snow_in_hr, temperature_f.
    Any missing input yields None for that field.
    """
    rain_mm = hourly_values.get('rain')
    showers_mm = hourly_values.get('showers')
    if rain_mm is None and showers_mm is None:
        rain_in_hr = None
    else:
        rain_in_hr = mm_per_hour_to_inches_per_hour((rain_mm or 0.0) + (showers_mm or 0.0))

    return {
        'wind_mph': kmh_to_mph(hourly_values.get('wind_speed_10m')),
        'rain_in_hr': rain_in_hr,
        'snow_in_hr': cm_per_hour_to_inches_per_hour(hourly_values.get('snowfall')),
        'temperature_f': celsius_to_fahrenheit(hourly_values.get('temperature_2m')),
    }


def attach_weather_and_risk(routes, load_weight_lbs):
    """Fetch weather for every checkpoint across all routes, classify risk,
    compute route metrics, rank routes, and build the recommendation.

    `routes` is a list of dicts each containing a `checkpoints` list whose
    entries have `latitude`, `longitude`, and `arrival_utc`. Mutates and
    returns the routes with `weather`, `risk`, `metrics`, and `rank` filled in,
    plus a top-level `recommendation` dict.
    """
    all_checkpoints = [cp for route in routes for cp in route['checkpoints']]
    if not all_checkpoints:
        return routes, build_recommendation([])

    points = sorted({(round(cp['latitude'], 4), round(cp['longitude'], 4))
                     for cp in all_checkpoints})
    start_utc = min(cp['arrival_utc'] for cp in all_checkpoints)
    end_utc = max(cp['arrival_utc'] for cp in all_checkpoints)

    forecasts = fetch_hourly_forecast(points, start_utc, end_utc)

    for checkpoint in all_checkpoints:
        key = (round(checkpoint['latitude'], 4), round(checkpoint['longitude'], 4))
        entry = forecasts.get(key)
        hourly = weather_at_utc(entry, checkpoint['arrival_utc']) if entry else None
        if hourly is None:
            checkpoint['weather'] = None
            checkpoint['risk'] = {
                'level': 'unknown',
                'wind_level': 'unknown',
                'rain_level': 'unknown',
                'snow_level': 'unknown',
                'load_rule': 'none',
                'factors': ['Weather forecast unavailable for this checkpoint'],
            }
            continue

        imperial = _hourly_to_imperial(hourly)
        checkpoint['weather'] = {
            **imperial,
            'forecast_hour_utc': checkpoint['arrival_utc'].replace(
                minute=0, second=0, microsecond=0).isoformat(),
            'source': FORECAST_SOURCE,
        }
        checkpoint['risk'] = classify_checkpoint_risk(
            imperial['wind_mph'], imperial['rain_in_hr'],
            imperial['snow_in_hr'], load_weight_lbs)

    for route in routes:
        route['metrics'] = compute_route_metrics(
            route['checkpoints'], route['distance_miles'], route['duration_seconds'])

    ranked = rank_routes(routes)
    recommendation = build_recommendation(ranked)
    return ranked, recommendation


def corridor_forecast(points, departure_utc, forecast_hours, load_weight_lbs):
    """Return per-point hourly risk series for the route weather-risk overlay.

    `points` is a list of dicts with latitude, longitude,
    cumulative_distance_miles. Returns a list of dicts with an `hours` array
    of {offset_hours, arrival_utc, weather..., risk_level}.
    """
    coords = [(round(p['latitude'], 4), round(p['longitude'], 4)) for p in points]
    start_utc = departure_utc
    end_utc = departure_utc + timedelta(hours=forecast_hours)
    forecasts = fetch_hourly_forecast(coords, start_utc, end_utc)

    result = []
    for point, key in zip(points, coords):
        entry = forecasts.get(key)
        hours = []
        for offset in range(forecast_hours):
            arrival = departure_utc + timedelta(hours=offset)
            hourly = weather_at_utc(entry, arrival) if entry else None
            if hourly is None:
                hours.append({
                    'offset_hours': offset,
                    'arrival_utc': arrival.isoformat(),
                    'risk_level': 'unknown',
                })
                continue
            imperial = _hourly_to_imperial(hourly)
            risk = classify_checkpoint_risk(
                imperial['wind_mph'], imperial['rain_in_hr'],
                imperial['snow_in_hr'], load_weight_lbs)
            hours.append({
                'offset_hours': offset,
                'arrival_utc': arrival.isoformat(),
                **imperial,
                'risk_level': risk['level'],
            })
        result.append({
            'latitude': point['latitude'],
            'longitude': point['longitude'],
            'cumulative_distance_miles': point['cumulative_distance_miles'],
            'hours': hours,
        })
    return result
