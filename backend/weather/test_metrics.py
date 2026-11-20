"""Route metrics and ranking tests (segment-mile methodology)."""

from datetime import datetime, timedelta, timezone

from .metrics import (build_recommendation, compute_route_metrics,
                      rank_routes)

UTC = timezone.utc
T0 = datetime(2026, 11, 20, tzinfo=UTC)


def checkpoint(distance, level='low', minutes=0):
    return {
        'cumulative_distance_miles': distance,
        'arrival_utc': T0 + timedelta(minutes=minutes),
        'risk': {'level': level},
    }


def make_route(route_id, checkpoints, distance=100.0, duration=3600.0,
               has_no_travel=False):
    return {
        'id': route_id,
        'distance_miles': distance,
        'duration_seconds': duration,
        'checkpoints': checkpoints,
        'metrics': has_no_travel and {
            'severe_miles': 0, 'high_miles': 0, 'no_travel_miles': 10,
            'average_risk_score': 3.0, 'weather_coverage': 1.0,
            'has_no_travel': True, 'status': 'no_travel',
        } or {},
    }


# ---------- Segment metrics ----------

def test_segment_gets_worse_endpoint_risk():
    # Checkpoint at mile 50 is severe; adjacent 25-mi segments become severe.
    checkpoints = [
        checkpoint(0, 'low'),
        checkpoint(25, 'low'),
        checkpoint(50, 'severe'),
        checkpoint(75, 'low'),
        checkpoint(100, 'low'),
    ]
    metrics = compute_route_metrics(checkpoints, 100.0, 3600.0)
    # Segments 25-50 and 50-75 are severe (25 mi each).
    assert metrics['severe_miles'] == 50.0
    assert metrics['high_miles'] == 0.0


def test_high_miles_counted_separately_from_severe():
    checkpoints = [
        checkpoint(0, 'high'),
        checkpoint(50, 'high'),
        checkpoint(100, 'low'),
    ]
    metrics = compute_route_metrics(checkpoints, 100.0, 3600.0)
    assert metrics['high_miles'] == 100.0  # segment 0-50 high; 50-100 worse=high
    assert metrics['severe_miles'] == 0.0


def test_no_travel_miles_and_flag():
    checkpoints = [
        checkpoint(0, 'low'),
        checkpoint(50, 'no_travel'),
        checkpoint(100, 'low'),
    ]
    metrics = compute_route_metrics(checkpoints, 100.0, 3600.0)
    assert metrics['has_no_travel'] is True
    assert metrics['no_travel_miles'] == 100.0
    assert metrics['status'] == 'no_travel'


def test_known_no_travel_checkpoint_still_excludes_partially_unknown_route():
    metrics = compute_route_metrics(
        [checkpoint(0, 'no_travel'), checkpoint(50, 'unknown')], 50.0, 3600.0)
    assert metrics['has_no_travel'] is True
    assert metrics['no_travel_miles'] == 0.0
    assert metrics['unknown_miles'] == 50.0
    assert metrics['status'] == 'no_travel'


def test_average_risk_is_distance_weighted():
    # 50 mi low (score 1) + 50 mi severe (score 4) -> avg 2.5
    checkpoints = [
        checkpoint(0, 'low'),
        checkpoint(50, 'low'),
        checkpoint(100, 'severe'),
    ]
    metrics = compute_route_metrics(checkpoints, 100.0, 3600.0)
    # Segment 0-50: worse(low,low)=low. Segment 50-100: worse(low,severe)=severe.
    assert metrics['average_risk_score'] == 2.5


def test_unknown_weather_excluded_not_treated_as_low():
    checkpoints = [
        checkpoint(0, 'low'),
        checkpoint(50, 'unknown'),
        checkpoint(100, 'unknown'),
    ]
    metrics = compute_route_metrics(checkpoints, 100.0, 3600.0)
    # Neither segment is fully assessed because each has an unknown endpoint.
    assert metrics['weather_coverage'] == 0.0
    assert metrics['unknown_miles'] == 100.0
    assert metrics['average_risk_score'] is None
    assert metrics['status'] == 'incomplete'


def test_fully_unknown_route_has_no_average_and_zero_coverage():
    checkpoints = [checkpoint(0, 'unknown'), checkpoint(100, 'unknown')]
    metrics = compute_route_metrics(checkpoints, 100.0, 3600.0)
    assert metrics['weather_coverage'] == 0.0
    assert metrics['average_risk_score'] is None
    assert metrics['unknown_miles'] == 100.0
    assert metrics['status'] == 'incomplete'


def test_clean_route_status_ok():
    checkpoints = [checkpoint(0, 'low'), checkpoint(100, 'moderate')]
    metrics = compute_route_metrics(checkpoints, 100.0, 3600.0)
    assert metrics['status'] == 'ok'
    assert metrics['weather_coverage'] == 1.0
    assert metrics['unknown_miles'] == 0.0


def test_unknown_mileage_is_not_counted_as_low_or_high_risk_mileage():
    checkpoints = [checkpoint(0, 'low'), checkpoint(25, 'high'), checkpoint(50, 'unknown')]
    metrics = compute_route_metrics(checkpoints, 50.0, 3600.0)
    assert metrics['high_miles'] == 25.0
    assert metrics['unknown_miles'] == 25.0
    assert metrics['weather_coverage'] == 0.5


def test_partial_segment_metrics_produce_provisional_recommendation():
    route = make_route('partial', [
        checkpoint(0, 'low'),
        checkpoint(50, 'low'),
        checkpoint(100, 'unknown'),
    ])
    route['metrics'] = compute_route_metrics(route['checkpoints'], 100.0, 3600.0)
    recommendation = build_recommendation(rank_routes([route]))
    assert route['metrics']['weather_coverage'] == 0.5
    assert route['metrics']['unknown_miles'] == 50.0
    assert recommendation['safe'] is False
    assert recommendation['status'] == 'provisional'
    assert recommendation['route_id'] == 'partial'


# ---------- Ranking ----------

def _route_with_metrics(route_id, severe, high, avg, duration, distance=100.0):
    route = make_route(route_id, [], distance, duration)
    route['metrics'] = {
        'severe_miles': severe, 'high_miles': high,
        'average_risk_score': avg, 'weather_coverage': 1.0,
        'has_no_travel': False, 'status': 'ok',
        'no_travel_miles': 0,
    }
    return route


def test_ranking_severe_miles_dominates():
    # Route B has more high miles and longer time but fewer severe miles.
    routes = [
        _route_with_metrics('a', severe=10, high=0, avg=2.0, duration=100),
        _route_with_metrics('b', severe=5, high=50, avg=4.0, duration=900),
    ]
    ranked = rank_routes(routes)
    assert ranked[0]['id'] == 'b'
    assert ranked[0]['rank'] == 1


def test_ranking_high_miles_second_priority():
    routes = [
        _route_with_metrics('a', severe=5, high=30, avg=1.0, duration=100),
        _route_with_metrics('b', severe=5, high=10, avg=4.5, duration=900),
    ]
    ranked = rank_routes(routes)
    assert ranked[0]['id'] == 'b'  # fewer high miles wins despite worse avg/time


def test_ranking_average_risk_third_priority():
    routes = [
        _route_with_metrics('a', severe=5, high=10, avg=4.0, duration=100),
        _route_with_metrics('b', severe=5, high=10, avg=2.0, duration=900),
    ]
    ranked = rank_routes(routes)
    assert ranked[0]['id'] == 'b'


def test_ranking_travel_time_fourth_priority():
    routes = [
        _route_with_metrics('a', severe=5, high=10, avg=2.0, duration=900),
        _route_with_metrics('b', severe=5, high=10, avg=2.0, duration=100),
    ]
    ranked = rank_routes(routes)
    assert ranked[0]['id'] == 'b'


def test_four_ranking_priorities_are_preserved_between_partial_routes():
    routes = [
        _route_with_metrics('a', severe=10, high=0, avg=1.0, duration=100),
        _route_with_metrics('b', severe=5, high=20, avg=4.0, duration=900),
    ]
    for route in routes:
        route['metrics'].update({
            'weather_coverage': 0.5,
            'unknown_miles': 50.0,
            'status': 'incomplete',
        })
    assert rank_routes(routes)[0]['id'] == 'b'


def test_ranking_no_travel_routes_sort_last():
    safe = _route_with_metrics('safe', severe=50, high=50, avg=5.0, duration=100)
    unsafe = make_route('unsafe', [])
    unsafe['metrics'] = {
        'severe_miles': 0, 'high_miles': 0, 'no_travel_miles': 5,
        'average_risk_score': 1.0, 'weather_coverage': 1.0,
        'has_no_travel': True, 'status': 'no_travel',
    }
    ranked = rank_routes([unsafe, safe])
    assert ranked[0]['id'] == 'safe'
    assert ranked[1]['id'] == 'unsafe'


def test_ranking_deterministic_tiebreak_on_distance_and_id():
    a1 = _route_with_metrics('a', 0, 0, 1.0, 100, distance=200)
    a2 = _route_with_metrics('a', 0, 0, 1.0, 100, distance=100)
    ranked = rank_routes([a1, a2])
    assert ranked[0]['distance_miles'] == 100


# ---------- Recommendation ----------

def test_recommendation_picks_top_safe_route():
    routes = [
        _route_with_metrics('a', severe=10, high=0, avg=2.0, duration=100),
        _route_with_metrics('b', severe=5, high=10, avg=2.5, duration=200),
    ]
    routes = rank_routes(routes)
    rec = build_recommendation(routes)
    assert rec['safe'] is True
    assert rec['route_id'] == 'b'
    assert 'recommend' in rec['reason'].lower() or 'Route b' in rec['reason']


def test_recommendation_skips_no_travel_route():
    safe = _route_with_metrics('safe', severe=50, high=50, avg=5.0, duration=900)
    unsafe = make_route('unsafe', [])
    unsafe['metrics'] = {
        'severe_miles': 0, 'high_miles': 0, 'no_travel_miles': 5,
        'average_risk_score': 1.0, 'weather_coverage': 1.0,
        'has_no_travel': True, 'status': 'no_travel',
    }
    routes = rank_routes([unsafe, safe])  # already correct usage
    rec = build_recommendation(routes)
    assert rec['safe'] is True
    assert rec['route_id'] == 'safe'


def test_recommendation_all_no_travel_is_unsafe():
    unsafe1 = make_route('u1', [])
    unsafe2 = make_route('u2', [])
    for r in (unsafe1, unsafe2):
        r['metrics'] = {
            'severe_miles': 0, 'high_miles': 0, 'no_travel_miles': 5,
            'average_risk_score': 1.0, 'weather_coverage': 1.0,
            'has_no_travel': True, 'status': 'no_travel',
        }
    routes = rank_routes([unsafe1, unsafe2])
    rec = build_recommendation(routes)
    assert rec['safe'] is False
    assert rec['status'] == 'unavailable'
    assert rec['route_id'] is None
    assert 'no evaluated route is safe' in rec['reason'].lower()


def test_recommendation_zero_weather_coverage_prevented():
    # Route with zero weather coverage must NOT be recommended
    r1 = make_route('r1', [])
    r1['metrics'] = {
        'severe_miles': 0, 'high_miles': 0, 'no_travel_miles': 0,
        'average_risk_score': None, 'weather_coverage': 0.0,
        'has_no_travel': False, 'status': 'incomplete',
    }
    routes = rank_routes([r1])
    rec = build_recommendation(routes)
    assert rec['safe'] is False
    assert rec['status'] == 'unavailable'
    assert rec['route_id'] is None
    assert 'weather coverage is unavailable' in rec['reason'].lower()


def test_recommendation_favors_route_with_usable_coverage_over_zero_coverage():
    # r1 has 0 coverage, r2 has 1.0 coverage but some high risk
    r1 = make_route('r1', [], distance=100.0, duration=100.0)
    r1['metrics'] = {
        'severe_miles': 0, 'high_miles': 0, 'no_travel_miles': 0,
        'average_risk_score': None, 'weather_coverage': 0.0,
        'has_no_travel': False, 'status': 'incomplete',
    }
    r2 = make_route('r2', [], distance=100.0, duration=120.0)
    r2['metrics'] = {
        'severe_miles': 0, 'high_miles': 10, 'no_travel_miles': 0,
        'average_risk_score': 2.0, 'weather_coverage': 1.0,
        'has_no_travel': False, 'status': 'ok',
    }
    routes = rank_routes([r1, r2])
    # r2 should rank ahead of r1 despite having high miles because r1 has 0 weather coverage
    assert routes[0]['id'] == 'r2'
    rec = build_recommendation(routes)
    assert rec['safe'] is True
    assert rec['route_id'] == 'r2'


def test_incomplete_route_is_provisional_not_safe():
    route = _route_with_metrics('partial', severe=0, high=0, avg=1.0, duration=100)
    route['metrics'].update({
        'weather_coverage': 0.75,
        'unknown_miles': 25.0,
        'status': 'incomplete',
    })
    rec = build_recommendation(rank_routes([route]))
    assert rec['safe'] is False
    assert rec['status'] == 'provisional'
    assert rec['route_id'] == 'partial'
    assert '25.00 mi unassessed' in rec['reason']
    assert 'cannot be confirmed' in rec['reason']


def test_complete_route_is_preferred_to_better_ranked_partial_route():
    partial = _route_with_metrics('partial', severe=0, high=0, avg=1.0, duration=100)
    partial['metrics'].update({'weather_coverage': 0.75, 'unknown_miles': 25.0, 'status': 'incomplete'})
    complete = _route_with_metrics('complete', severe=1, high=1, avg=2.0, duration=200)
    rec = build_recommendation(rank_routes([partial, complete]))
    assert rec['safe'] is True
    assert rec['status'] == 'safe'
    assert rec['route_id'] == 'complete'


def test_incomplete_no_travel_route_is_not_a_provisional_candidate():
    partial_unsafe = _route_with_metrics('unsafe', severe=0, high=0, avg=1.0, duration=100)
    partial_unsafe['metrics'].update({
        'weather_coverage': 0.75,
        'unknown_miles': 25.0,
        'has_no_travel': True,
        'status': 'no_travel',
    })
    rec = build_recommendation(rank_routes([partial_unsafe]))
    assert rec['safe'] is False
    assert rec['status'] == 'unavailable'
    assert rec['route_id'] is None

