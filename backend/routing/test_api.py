"""API-level tests for plan validation and error handling (no network)."""

from datetime import datetime

import pytest
from django.test import override_settings
from rest_framework.test import APIClient
from routing.serializers import PlanRequestSerializer

VALID_PAYLOAD = {
    'origin': 'Dallas, TX',
    'destination': 'Austin, TX',
    'departure_local': '2026-11-20T08:00:00',
    'load_weight_lbs': 30000,
    'checkpoint_interval_miles': 25,
}


@pytest.fixture
def client():
    return APIClient()


def test_plan_rejects_invalid_interval(client):
    payload = {**VALID_PAYLOAD, 'checkpoint_interval_miles': 15}
    response = client.post('/api/plan/', payload, format='json')
    assert response.status_code == 400
    assert 'checkpoint_interval_miles' in response.data['error']


def test_plan_rejects_missing_fields(client):
    response = client.post('/api/plan/', {}, format='json')
    assert response.status_code == 400


def test_plan_rejects_negative_load(client):
    payload = {**VALID_PAYLOAD, 'load_weight_lbs': -5}
    response = client.post('/api/plan/', payload, format='json')
    assert response.status_code == 400


def test_departure_local_preserves_naive_local_datetime():
    serializer = PlanRequestSerializer(data=VALID_PAYLOAD)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data['departure_local'].tzinfo is None


def test_departure_local_rejects_timezone_offsets():
    payload = {**VALID_PAYLOAD, 'departure_local': '2026-11-20T08:00:00-06:00'}
    serializer = PlanRequestSerializer(data=payload)
    assert not serializer.is_valid()
    assert 'without a timezone offset' in str(serializer.errors['departure_local'])


@override_settings(MAPBOX_ACCESS_TOKEN='')
def test_plan_without_mapbox_token_returns_clear_error(client):
    response = client.post('/api/plan/', VALID_PAYLOAD, format='json')
    assert response.status_code == 400
    assert 'MAPBOX_ACCESS_TOKEN' in response.data['error']


def test_geocode_requires_query_param(client):
    response = client.get('/api/geocode/')
    assert response.status_code == 400
    assert 'q' in response.data['error']


@override_settings(MAPBOX_ACCESS_TOKEN='')
def test_geocode_without_token_returns_clear_error(client):
    response = client.get('/api/geocode/?q=Dallas')
    assert response.status_code == 503
    assert 'MAPBOX_ACCESS_TOKEN' in response.data['error']


def test_dst_nonexistent_time_rejected():
    from rest_framework.exceptions import ValidationError
    from routing.services import _local_departure_to_utc

    # 2026-03-08 02:30 does not exist in America/New_York due to spring forward
    nonexistent = datetime(2026, 3, 8, 2, 30)
    with pytest.raises(ValidationError) as exc:
        _local_departure_to_utc(nonexistent, 'America/New_York')
    assert 'does not exist' in str(exc.value)


def test_dst_ambiguous_time_rejected():
    from rest_framework.exceptions import ValidationError
    from routing.services import _local_departure_to_utc

    # 2026-11-01 01:30 is ambiguous in America/New_York due to fall back
    ambiguous = datetime(2026, 11, 1, 1, 30)
    with pytest.raises(ValidationError) as exc:
        _local_departure_to_utc(ambiguous, 'America/New_York')
    assert 'ambiguous' in str(exc.value)


def test_past_departure_rejected():
    from rest_framework.exceptions import ValidationError
    from routing.services import _local_departure_to_utc

    past = datetime(2020, 1, 1, 12, 0)
    with pytest.raises(ValidationError) as exc:
        _local_departure_to_utc(past, 'America/Chicago')
    assert 'must be in the future' in str(exc.value)


def test_mapbox_error_does_not_leak_raw_body(caplog):
    import logging
    from unittest.mock import Mock, patch
    from routing.mapbox_client import geocode, get_directions, MapboxAPIError

    mock_resp = Mock()
    mock_resp.status_code = 502
    mock_resp.text = '<html>Mapbox Internal Secret Stacktrace</html>'

    with override_settings(MAPBOX_ACCESS_TOKEN='test-token'):
        with caplog.at_level(logging.ERROR):
            with patch('requests.get', return_value=mock_resp):
                with pytest.raises(MapboxAPIError) as exc_info:
                    geocode('Dallas')
                assert 'Internal Secret' not in str(exc_info.value)
                assert any('Internal Secret' in r.message for r in caplog.records)

        with caplog.at_level(logging.ERROR):
            with patch('requests.get', return_value=mock_resp):
                with pytest.raises(MapboxAPIError) as exc_info:
                    get_directions(-97.0, 32.0, -96.0, 32.0)
                assert 'Internal Secret' not in str(exc_info.value)
                assert any('Internal Secret' in r.message for r in caplog.records)


def test_mapbox_alternatives_parameter():
    from unittest.mock import Mock, patch
    from routing.mapbox_client import get_directions

    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {'routes': []}

    with override_settings(MAPBOX_ACCESS_TOKEN='test-token'):
        with patch('requests.get', return_value=mock_resp) as mock_get:
            get_directions(-97.0, 32.0, -96.0, 32.0, alternatives=True)
            assert mock_get.call_args[1]['params']['alternatives'] == 'true'

        with patch('requests.get', return_value=mock_resp) as mock_get:
            get_directions(-97.0, 32.0, -96.0, 32.0, alternatives=False)
            assert mock_get.call_args[1]['params']['alternatives'] == 'false'


@pytest.mark.parametrize(('route_count', 'warns'), [(1, True), (2, True), (3, False)])
def test_plan_preserves_available_route_count_and_warns_below_three(
        route_count, warns):
    from unittest.mock import patch
    from datetime import timedelta, timezone
    from routing.services import build_trip_plan

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    departure = now + timedelta(days=2)
    routes = [
        {
            'geometry': {
                'type': 'LineString',
                'coordinates': [[-97.0, 32.0], [-96.9, 32.1 + index * 0.01]],
            },
            'distance_miles': 10 + index,
            'duration_seconds': 900 + index * 60,
        }
        for index in range(route_count)
    ]
    origin = {'longitude': -97.0, 'latitude': 32.0,
              'display_name': 'Dallas', 'timezone': 'America/Chicago'}
    destination = {'longitude': -96.0, 'latitude': 30.0,
                   'display_name': 'Austin', 'timezone': 'America/Chicago'}

    with patch('routing.services.settings.MAPBOX_ACCESS_TOKEN', 'test-token'), \
         patch('routing.services.geocode_place', side_effect=[origin, destination]), \
         patch('routing.services.mapbox_client.get_directions', return_value=routes) as directions, \
         patch('routing.services.attach_weather_and_risk', side_effect=lambda found, _weight: (found, {})):
        plan = build_trip_plan('Dallas', 'Austin', departure, 30000, 25)

    assert len(plan['routes']) == route_count
    assert bool(plan['warnings']) is warns
    assert directions.call_args.kwargs['alternatives'] is True


def test_production_environment_variables_validation():
    import importlib
    import os
    from django.core.exceptions import ImproperlyConfigured
    import config.settings as app_settings

    # Simulating missing required env vars in production (DEBUG=False)
    original_debug = os.environ.get('DJANGO_DEBUG')
    original_key = os.environ.get('DJANGO_SECRET_KEY')
    original_token = os.environ.get('MAPBOX_ACCESS_TOKEN')
    original_hosts = os.environ.get('DJANGO_ALLOWED_HOSTS')
    try:
        os.environ['DJANGO_DEBUG'] = 'false'
        os.environ['DJANGO_SECRET_KEY'] = 'django-insecure-dev-only-change-me'
        os.environ['MAPBOX_ACCESS_TOKEN'] = ''
        os.environ['DJANGO_ALLOWED_HOSTS'] = ''
        with pytest.raises(ImproperlyConfigured) as exc_info:
            importlib.reload(app_settings)
        assert 'Missing required production environment variable' in str(exc_info.value)
    finally:
        if original_debug is not None:
            os.environ['DJANGO_DEBUG'] = original_debug
        else:
            os.environ.pop('DJANGO_DEBUG', None)
        if original_key is not None:
            os.environ['DJANGO_SECRET_KEY'] = original_key
        else:
            os.environ.pop('DJANGO_SECRET_KEY', None)
        if original_token is not None:
            os.environ['MAPBOX_ACCESS_TOKEN'] = original_token
        else:
            os.environ.pop('MAPBOX_ACCESS_TOKEN', None)
        if original_hosts is not None:
            os.environ['DJANGO_ALLOWED_HOSTS'] = original_hosts
        else:
            os.environ.pop('DJANGO_ALLOWED_HOSTS', None)
        importlib.reload(app_settings)

