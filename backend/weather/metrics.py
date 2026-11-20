"""Route-level risk metrics and recommendation ranking.

Methodology (documented per assessment requirements):

- Each checkpoint receives a risk classification (low/moderate/high/severe/
  no_travel/unknown) from weather + load rules.
- For every segment between consecutive checkpoints, the segment is assigned
  the *worse* of its two endpoint risk levels, and is weighted by the
  segment's distance in miles.
- severe_miles / high_miles / no_travel_miles are the sums of segment
  distances whose assigned level equals that category.
- average_risk_score is the distance-weighted mean of numeric risk scores
  (low=1 ... no_travel=5) over segments with known weather. Segments with
  unknown weather are excluded from the average and counted in
  weather_coverage instead - unknown is never silently treated as low risk.
- weather_coverage is the fraction of total route miles with known weather.

Ranking priority (lexicographic, lower is better):
  1. has_no_travel (routes with any No Travel segment always sort last)
  2. severe_miles
  3. high_miles
  4. average_risk_score
  5. duration_seconds
  6. distance_miles, then route id - deterministic tie-breakers
"""

from .risk import RISK_HIGH, RISK_NO_TRAVEL, RISK_SEVERE, RISK_UNKNOWN, worse_risk

RISK_SCORE = {
    'low': 1,
    'moderate': 2,
    'high': 3,
    'severe': 4,
    'no_travel': 5,
}


def _checkpoint_level(checkpoint):
    risk = checkpoint.get('risk') or {}
    return risk.get('level', RISK_UNKNOWN)


def compute_route_metrics(checkpoints, route_distance_miles, duration_seconds):
    """Compute segment-based risk metrics for one route's checkpoints."""
    severe_miles = 0.0
    high_miles = 0.0
    no_travel_miles = 0.0
    unknown_miles = 0.0
    weighted_score_sum = 0.0
    known_miles = 0.0
    # A known No Travel checkpoint makes the route ineligible even when the
    # adjacent segment cannot be fully assessed because its other endpoint is unknown.
    has_no_travel = any(_checkpoint_level(checkpoint) == RISK_NO_TRAVEL for checkpoint in checkpoints)

    for previous, current in zip(checkpoints, checkpoints[1:]):
        segment_miles = max(0.0, current['cumulative_distance_miles']
                            - previous['cumulative_distance_miles'])
        previous_level = _checkpoint_level(previous)
        current_level = _checkpoint_level(current)
        if previous_level == RISK_UNKNOWN or current_level == RISK_UNKNOWN:
            unknown_miles += segment_miles
            continue

        level = worse_risk(previous_level, current_level)

        if level == RISK_SEVERE:
            severe_miles += segment_miles
        elif level == RISK_HIGH:
            high_miles += segment_miles
        elif level == RISK_NO_TRAVEL:
            no_travel_miles += segment_miles
            has_no_travel = True

        if level != RISK_UNKNOWN:
            known_miles += segment_miles
            weighted_score_sum += RISK_SCORE[level] * segment_miles

    total_segment_miles = sum(
        max(0.0, cur['cumulative_distance_miles'] - prev['cumulative_distance_miles'])
        for prev, cur in zip(checkpoints, checkpoints[1:])
    ) or route_distance_miles
    if len(checkpoints) < 2 and route_distance_miles > 0:
        unknown_miles = route_distance_miles

    average_risk_score = (weighted_score_sum / known_miles) if known_miles > 0 else None
    weather_coverage = (known_miles / total_segment_miles) if total_segment_miles > 0 else 0.0

    if has_no_travel:
        status = 'no_travel'
    elif weather_coverage < 1.0:
        status = 'incomplete'
    else:
        status = 'ok'

    return {
        'severe_miles': round(severe_miles, 2),
        'high_miles': round(high_miles, 2),
        'no_travel_miles': round(no_travel_miles, 2),
        'unknown_miles': round(unknown_miles, 2),
        'average_risk_score': round(average_risk_score, 3) if average_risk_score is not None else None,
        'weather_coverage': round(weather_coverage, 4),
        'has_no_travel': has_no_travel,
        'status': status,
    }


def rank_key(route):
    metrics = route['metrics']
    coverage = metrics.get('weather_coverage') or 0.0
    fully_assessed = (
        coverage >= 1.0
        and metrics.get('status', 'ok') != 'incomplete'
        and metrics.get('unknown_miles', 0.0) <= 0.0
    )
    return (
        1 if metrics['has_no_travel'] else 0,
        0 if fully_assessed else 1 if coverage > 0.0 else 2,
        metrics['severe_miles'],
        metrics['high_miles'],
        metrics['average_risk_score'] if metrics['average_risk_score'] is not None else float('inf'),
        route['duration_seconds'],
        route['distance_miles'],
        route['id'],
    )


def rank_routes(routes):
    """Sort routes and assign `rank` (1-based). Returns a new sorted list."""
    ordered = sorted(routes, key=rank_key)
    for position, route in enumerate(ordered, start=1):
        route['rank'] = position
    return ordered


def build_recommendation(routes):
    """Pick the recommended route and explain why.

    A safe recommendation requires complete weather coverage and no No Travel
    segments. If only partially assessed routes remain, return the best one as
    provisional (`safe=False`, `status='provisional'`) so the UI can display it
    without presenting it as verified safe.
    """
    if not routes:
        return {
            'safe': False,
            'status': 'unavailable',
            'route_id': None,
            'reason': 'No evaluated routes available.',
        }

    safe_routes = [
        r for r in routes
        if not r['metrics']['has_no_travel']
        and (r['metrics'].get('weather_coverage') or 0.0) >= 1.0
        and r['metrics'].get('status', 'ok') == 'ok'
        and r['metrics'].get('unknown_miles', 0.0) <= 0.0
    ]
    if safe_routes:
        best = safe_routes[0]
        recommendation_status = 'safe'
    else:
        provisional_routes = [
            r for r in routes
            if not r['metrics']['has_no_travel']
            and (r['metrics'].get('weather_coverage') or 0.0) > 0.0
            and (
                (r['metrics'].get('weather_coverage') or 0.0) < 1.0
                or r['metrics'].get('status') == 'incomplete'
                or r['metrics'].get('unknown_miles', 0.0) > 0.0
            )
        ]
        if provisional_routes:
            best = provisional_routes[0]
            metrics = best['metrics']
            coverage = (metrics.get('weather_coverage') or 0.0) * 100
            unknown_miles = metrics.get('unknown_miles', 0.0)
            return {
                'safe': False,
                'status': 'provisional',
                'route_id': best['id'],
                'reason': (
                    f"Provisional route {best['id']} selected with {coverage:.1f}% "
                    f"weather coverage and {unknown_miles:.2f} mi unassessed. "
                    'Weather coverage is incomplete, so route safety cannot be confirmed.'
                ),
            }
        if all(r['metrics']['has_no_travel'] for r in routes):
            reason = 'No evaluated route is safe: every route contains No Travel weather conditions.'
        else:
            reason = 'No route can be recommended: weather coverage is unavailable for evaluated routes.'
        return {'safe': False, 'status': 'unavailable', 'route_id': None, 'reason': reason}

    metrics = best['metrics']
    reasons = []
    if metrics['severe_miles'] == 0 and metrics['high_miles'] == 0:
        reasons.append('no Severe or High risk miles')
    else:
        reasons.append(f"fewest Severe miles ({metrics['severe_miles']} mi) and High miles ({metrics['high_miles']} mi) among safe routes")
    if metrics['average_risk_score'] is not None:
        reasons.append(f"lowest average risk score ({metrics['average_risk_score']})")
    reasons.append('shortest travel time among equally safe options' if len(safe_routes) > 1 else 'only safe route evaluated')
    return {
        'safe': True,
        'status': recommendation_status,
        'route_id': best['id'],
        'reason': f"Route {best['id']} recommended: " + '; '.join(reasons) + '.',
    }
