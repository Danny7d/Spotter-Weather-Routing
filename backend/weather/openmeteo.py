"""Client for the Open-Meteo forecast API (no API key required).

All timestamps are handled in UTC: we request `timezone=UTC` hourly data and
match each checkpoint's `arrival_utc` to the forecast hour that contains it.
"""

import logging
from datetime import datetime, timedelta, timezone

import requests
from django.conf import settings
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)

FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
COORDINATES_PER_REQUEST = 25

HOURLY_VARIABLES = 'wind_speed_10m,temperature_2m,rain,showers,snowfall'


class WeatherAPIError(APIException):
    """Raised when Open-Meteo returns an error or is unreachable."""

    status_code = 503
    default_detail = 'Weather forecast service is unavailable.'


def _parse_iso_hour(value):
    """Parse an Open-Meteo hourly timestamp ('2026-11-20T08:00') as UTC."""
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def fetch_hourly_forecast(points, start_utc, end_utc):
    """Fetch hourly forecasts for multiple coordinates in batched requests.

    `points` is a list of (latitude, longitude) tuples.
    `start_utc`/`end_utc` are timezone-aware datetimes; they are expanded to
    full UTC days because the API works on calendar dates.

    Returns a dict mapping (latitude, longitude) rounded to 4 decimals ->
    {'times': [datetime, ...], 'variables': {name: [values]}}.
    Coordinates that fail are omitted from the result.
    """
    if not points:
        return {}

    start_date = start_utc.date() - timedelta(days=1)
    end_date = end_utc.date() + timedelta(days=1)

    results = {}
    for chunk_start in range(0, len(points), COORDINATES_PER_REQUEST):
        chunk = points[chunk_start:chunk_start + COORDINATES_PER_REQUEST]
        latitudes = ','.join(f'{lat:.4f}' for lat, _ in chunk)
        longitudes = ','.join(f'{lon:.4f}' for _, lon in chunk)
        params = {
            'latitude': latitudes,
            'longitude': longitudes,
            'hourly': HOURLY_VARIABLES,
            'timezone': 'UTC',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            # Default units are requested (km/h wind, mm precipitation,
            # cm snowfall, degC) and converted explicitly in weather.units.
        }
        try:
            response = requests.get(FORECAST_URL, params=params,
                                    timeout=settings.EXTERNAL_API_TIMEOUT_SECONDS * 2)
        except requests.RequestException as exc:
            logger.error('Open-Meteo network error: %s', exc)
            raise WeatherAPIError('Weather forecast service is temporarily unavailable.') from exc
        if response.status_code != 200:
            logger.error('Open-Meteo forecast error: status=%s, response=%s', response.status_code, response.text)
            raise WeatherAPIError(f'Weather forecast failed with status {response.status_code}.')

        payload = response.json()
        # Single coordinate returns a dict; multiple return a list.
        locations = payload if isinstance(payload, list) else [payload]
        for (lat, lon), location in zip(chunk, locations):
            hourly = location.get('hourly') or {}
            times = [_parse_iso_hour(t) for t in hourly.get('time', [])]
            variables = {name: hourly.get(name, []) for name in HOURLY_VARIABLES.split(',')}
            results[(round(lat, 4), round(lon, 4))] = {'times': times, 'variables': variables}
    return results


def weather_at_utc(forecast_entry, arrival_utc):
    """Return weather variables for the forecast hour containing `arrival_utc`.

    Returns None when the timestamp falls outside the available forecast.
    """
    times = forecast_entry['times']
    variables = forecast_entry['variables']
    target_hour = arrival_utc.replace(minute=0, second=0, microsecond=0)
    try:
        index = times.index(target_hour)
    except ValueError:
        return None
    values = {}
    for name, series in variables.items():
        values[name] = series[index] if index < len(series) else None
    return values
