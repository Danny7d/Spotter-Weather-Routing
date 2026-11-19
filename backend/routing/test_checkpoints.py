"""Tests for checkpoint generation and ETA calculation (no network)."""

from datetime import datetime, timedelta, timezone

from .checkpoints import (build_checkpoints, cumulative_route_distances,
                          haversine_miles, interpolate_position)

UTC = timezone.utc
DEPARTURE = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def straight_line_geometry(miles, step_miles=0.5):
    """GeoJSON LineString heading due east `miles` from (0,0).

    1 degree longitude at equator ~= 69.09 miles, so step ~0.5 mi.
    """
    steps = int(miles / step_miles)
    deg_per_mile = 1.0 / 69.093
    coordinates = [[i * step_miles * deg_per_mile, 0.0] for i in range(steps + 1)]
    coordinates[-1] = [miles * deg_per_mile, 0.0]
    return {'type': 'LineString', 'coordinates': coordinates}


def test_haversine_known_distance():
    # NYC to Philadelphia ~ 80-95 miles; just assert sane magnitude.
    dist = haversine_miles(40.7128, -74.0060, 39.9526, -75.1652)
    assert 75 < dist < 100


def test_cumulative_distances_start_at_zero_and_increase():
    geometry = straight_line_geometry(10)
    cumulative = cumulative_route_distances(geometry['coordinates'])
    assert cumulative[0] == 0.0
    assert all(b > a for a, b in zip(cumulative, cumulative[1:]))
    assert abs(cumulative[-1] - 10.0) < 0.5  # equator approximation


def test_interpolate_position_endpoints():
    geometry = straight_line_geometry(10)
    cumulative = cumulative_route_distances(geometry['coordinates'])
    assert interpolate_position(geometry['coordinates'], cumulative, 0)[0] == 0.0
    end = interpolate_position(geometry['coordinates'], cumulative, 999)
    assert abs(end[0] - geometry['coordinates'][-1][0]) < 1e-9


def test_checkpoints_include_origin_and_destination():
    geometry = straight_line_geometry(100)
    checkpoints = build_checkpoints(geometry, 100.0, 7200.0, DEPARTURE, 25)
    assert checkpoints[0]['is_origin'] is True
    assert checkpoints[-1]['is_destination'] is True
    assert len(checkpoints) == 5  # 0, 25, 50, 75, 100


def test_checkpoint_spacing_at_intervals():
    geometry = straight_line_geometry(100)
    for interval, expected_count in [(10, 11), (25, 5), (50, 3)]:
        checkpoints = build_checkpoints(geometry, 100.0, 7200.0, DEPARTURE, interval)
        assert len(checkpoints) == expected_count
        distances = [c['cumulative_distance_miles'] for c in checkpoints]
        assert distances[0] == 0.0
        assert distances[-1] == 100.0


def test_checkpoint_arrival_times_are_utc_and_ordered():
    geometry = straight_line_geometry(100)
    checkpoints = build_checkpoints(geometry, 100.0, 7200.0, DEPARTURE, 50)
    arrivals = [c['arrival_utc'] for c in checkpoints]
    assert all(a.tzinfo == UTC for a in arrivals)
    assert arrivals == sorted(arrivals)
    # 2h trip: mid-route checkpoint arrives ~1h after departure.
    assert checkpoints[1]['arrival_utc'] == DEPARTURE + timedelta(hours=1)
    assert checkpoints[-1]['arrival_utc'] == DEPARTURE + timedelta(hours=2)


def test_checkpoint_etas_follow_distance_not_geometry_vertices():
    # Evenly spaced checkpoints regardless of vertex density.
    geometry = straight_line_geometry(60)
    checkpoints = build_checkpoints(geometry, 60.0, 3600.0, DEPARTURE, 10)
    fractions = [c['cumulative_distance_miles'] / 60.0 for c in checkpoints]
    for checkpoint, fraction in zip(checkpoints, fractions):
        expected = DEPARTURE + timedelta(seconds=3600.0 * fraction)
        assert abs((checkpoint['arrival_utc'] - expected).total_seconds()) < 1
