"""Tests for weather attachment: missing data, API failure, unit flow."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from .openmeteo import WeatherAPIError, weather_at_utc
from .services import attach_weather_and_risk, corridor_forecast

UTC = timezone.utc
T0 = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def make_checkpoint(lat, lon, distance, arrival):
    return {
        'latitude': lat, 'longitude': lon,
        'cumulative_distance_miles': distance,
        'arrival_utc': arrival,
        'is_origin': distance == 0,
        'is_destination': False,
    }


def make_route(route_id, checkpoints, distance=100.0, duration=3600.0):
    return {
        'id': route_id,
        'geometry': {'type': 'LineString', 'coordinates': [[-97.0, 32.0], [-96.0, 32.0]]},
        'distance_miles': distance,
        'duration_seconds': duration,
        'checkpoints': checkpoints,
    }


def fake_forecast_entry(times, **series):
    return {'times': times, 'variables': series}


def test_weather_at_utc_matches_containing_hour():
    times = [T0, T0 + timedelta(hours=1), T0 + timedelta(hours=2)]
    entry = fake_forecast_entry(times, wind_speed_10m=[10, 20, 30])
    # 12:30 arrival -> hour 12 sample (index 0), NOT departure-time-only.
    assert weather_at_utc(entry, T0 + timedelta(minutes=30))['wind_speed_10m'] == 10
    assert weather_at_utc(entry, T0 + timedelta(hours=1, minutes=45))['wind_speed_10m'] == 20


def test_weather_at_utc_outside_range_returns_none():
    entry = fake_forecast_entry([T0], wind_speed_10m=[10])
    assert weather_at_utc(entry, T0 + timedelta(days=3)) is None


def test_attach_weather_marks_unknown_when_forecast_missing():
    checkpoints = [make_checkpoint(32.0, -97.0, 0, T0),
                   make_checkpoint(32.0, -96.0, 100, T0 + timedelta(hours=2))]
    routes = [make_route('r1', checkpoints)]
    with patch('weather.services.fetch_hourly_forecast', return_value={}):
        ranked, rec = attach_weather_and_risk(routes, 30000)
    for cp in ranked[0]['checkpoints']:
        assert cp['weather'] is None
        assert cp['risk']['level'] == 'unknown'
    assert ranked[0]['metrics']['weather_coverage'] == 0.0
    assert ranked[0]['metrics']['status'] == 'incomplete'


def test_attach_weather_classifies_and_converts_units():
    times = [T0 + timedelta(hours=h) for h in range(3)]
    # wind 80 km/h -> ~49.7 mph (severe band), rain 30 mm -> >1 in/hr no-travel
    entry = fake_forecast_entry(
        times,
        wind_speed_10m=[80.0] * 3,
        temperature_2m=[20.0] * 3,
        rain=[30.0] * 3,
        showers=[0.0] * 3,
        snowfall=[0.0] * 3,
    )
    checkpoints = [make_checkpoint(32.0, -97.0, 0, T0),
                   make_checkpoint(32.0, -96.0, 100, T0 + timedelta(hours=2))]
    routes = [make_route('r1', checkpoints)]
    with patch('weather.services.fetch_hourly_forecast', return_value={(32.0, -97.0): entry, (32.0, -96.0): entry}):
        ranked, rec = attach_weather_and_risk(routes, 10000)
    cp = ranked[0]['checkpoints'][0]
    assert abs(cp['weather']['wind_mph'] - 49.7) < 0.2
    assert cp['weather']['rain_in_hr'] > 1.0
    assert cp['risk']['level'] == 'no_travel'
    assert ranked[0]['metrics']['has_no_travel'] is True


def test_weather_api_failure_propagates_as_service_error():
    checkpoints = [make_checkpoint(32.0, -97.0, 0, T0),
                   make_checkpoint(32.0, -96.0, 100, T0 + timedelta(hours=1))]
    routes = [make_route('r1', checkpoints)]
    with patch('weather.services.fetch_hourly_forecast',
               side_effect=WeatherAPIError('boom')):
        with pytest.raises(WeatherAPIError):
            attach_weather_and_risk(routes, 10000)


def test_corridor_forecast_returns_inclusive_49_hourly_series():
    # 0-48 hours inclusive requires 49 hourly samples
    times = [T0 + timedelta(hours=h) for h in range(49)]
    entry = fake_forecast_entry(
        times,
        wind_speed_10m=[10.0] * 49,
        temperature_2m=[15.0] * 49,
        rain=[0.0] * 49,
        showers=[0.0] * 49,
        snowfall=[0.0] * 49,
    )
    points = [{'latitude': 32.0, 'longitude': -97.0, 'cumulative_distance_miles': 0}]
    with patch('weather.services.fetch_hourly_forecast', return_value={(32.0, -97.0): entry}):
        result = corridor_forecast(points, T0, 49, 10000)
    assert len(result) == 1
    assert len(result[0]['hours']) == 49
    assert result[0]['hours'][0]['offset_hours'] == 0
    assert result[0]['hours'][48]['offset_hours'] == 48
    assert result[0]['hours'][0]['risk_level'] == 'low'
    assert result[0]['hours'][48]['arrival_utc'].startswith('2026-11-22')


def test_corridor_forecast_handles_missing_data():
    points = [{'latitude': 32.0, 'longitude': -97.0, 'cumulative_distance_miles': 0}]
    with patch('weather.services.fetch_hourly_forecast', return_value={}):
        result = corridor_forecast(points, T0, 3, 10000)
    assert all(h['risk_level'] == 'unknown' for h in result[0]['hours'])


def test_openmeteo_error_does_not_leak_raw_body(caplog):
    import logging
    from unittest.mock import Mock
    from weather.openmeteo import fetch_hourly_forecast

    mock_resp = Mock()
    mock_resp.status_code = 500
    mock_resp.text = '<html>Internal Server Secret Traceback</html>'

    with caplog.at_level(logging.ERROR):
        with patch('requests.get', return_value=mock_resp):
            with pytest.raises(WeatherAPIError) as exc_info:
                fetch_hourly_forecast([(32.0, -97.0)], T0, T0 + timedelta(hours=1))

    # The exception detail must NOT contain the sensitive upstream response text
    assert 'Internal Server Secret' not in str(exc_info.value)
    # But it must be recorded in server-side logs
    assert any('Internal Server Secret' in record.message for record in caplog.records)


def test_corridor_forecast_serializer_validates_point_limit():
    from weather.serializers import CorridorForecastRequestSerializer

    valid_payload = {
        'points': [{'latitude': 32.0, 'longitude': -97.0, 'cumulative_distance_miles': i} for i in range(200)],
        'departure_utc': '2026-11-20T12:00:00Z',
        'load_weight_lbs': 30000,
        'forecast_hours': 49,
    }
    s_valid = CorridorForecastRequestSerializer(data=valid_payload)
    assert s_valid.is_valid()

    # Exceeding 200 points must be rejected
    invalid_payload = {
        **valid_payload,
        'points': [{'latitude': 32.0, 'longitude': -97.0, 'cumulative_distance_miles': i} for i in range(201)],
    }
    s_invalid = CorridorForecastRequestSerializer(data=invalid_payload)
    assert not s_invalid.is_valid()
    assert 'points' in s_invalid.errors
