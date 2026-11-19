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
    weighted_score_sum = 0.0
    known_miles = 0.0
    has_no_travel = False

    for previous, current in zip(checkpoints, checkpoints[1:]):
        segment_miles = max(0.0, current['cumulative_distance_miles']
                            - previous['cumulative_distance_miles'])
        level = worse_risk(_checkpoint_level(previous), _checkpoint_level(current))

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
        'average_risk_score': round(average_risk_score, 3) if average_risk_score is not None else None,
        'weather_coverage': round(weather_coverage, 4),
        'has_no_travel': has_no_travel,
        'status': status,
    }


def rank_key(route):
    metrics = route['metrics']
    return (
        1 if metrics['has_no_travel'] else 0,
        1 if (metrics.get('weather_coverage') or 0.0) <= 0.0 else 0,
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

    Only routes without No Travel segments and with usable weather coverage
    (weather_coverage > 0) are eligible. Returns a dict with `safe` (bool),
    `route_id`, and a human-readable `reason`.
    """
    if not routes:
        return {
            'safe': False,
            'route_id': None,
            'reason': 'No evaluated routes available.',
        }

    safe_routes = [
        r for r in routes
        if not r['metrics']['has_no_travel'] and (r['metrics'].get('weather_coverage') or 0.0) > 0.0
    ]
    if not safe_routes:
        if all(r['metrics']['has_no_travel'] for r in routes):
            return {
                'safe': False,
                'route_id': None,
                'reason': 'No evaluated route is safe: every route contains No Travel weather conditions.',
            }
        return {
            'safe': False,
            'route_id': None,
            'reason': 'No route can be recommended: weather coverage is unavailable for evaluated routes.',
        }
    best = safe_routes[0]  # routes are already ranked
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
        'route_id': best['id'],
        'reason': f"Route {best['id']} recommended: " + '; '.join(reasons) + '.',
    }
