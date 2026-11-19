"""Checkpoint generation along a route geometry.

Checkpoints are placed every `interval_miles` of cumulative route distance,
always including the origin (distance 0) and destination (total distance).

Distance along the route is measured by haversine over the GeoJSON
LineString coordinates and then normalized so the final cumulative distance
equals the authoritative route distance reported by the routing API.
Arrival times are interpolated linearly by distance fraction, i.e. the route
is assumed to be traversed at a constant average speed.
"""

import math
from datetime import timedelta

EARTH_RADIUS_MILES = 3958.7613
METERS_PER_MILE = 1609.344


def haversine_miles(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points in miles."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def cumulative_route_distances(coordinates):
    """Return cumulative miles at each LineString vertex.

    `coordinates` is a list of [lon, lat] pairs. Returns a list aligned with
    the input vertices, starting at 0.0.
    """
    cumulative = [0.0]
    for previous, current in zip(coordinates, coordinates[1:]):
        cumulative.append(cumulative[-1] + haversine_miles(
            previous[1], previous[0], current[1], current[0]))
    return cumulative


def interpolate_position(coordinates, cumulative, target_miles):
    """Interpolate a [lon, lat] position at `target_miles` along the route."""
    if target_miles <= 0:
        return list(coordinates[0])
    total = cumulative[-1]
    if target_miles >= total or total == 0:
        return list(coordinates[-1])

    for index in range(1, len(cumulative)):
        if cumulative[index] >= target_miles:
            span_start = cumulative[index - 1]
            span_end = cumulative[index]
            fraction = (target_miles - span_start) / (span_end - span_start) if span_end > span_start else 0.0
            lon = coordinates[index - 1][0] + fraction * (coordinates[index][0] - coordinates[index - 1][0])
            lat = coordinates[index - 1][1] + fraction * (coordinates[index][1] - coordinates[index - 1][1])
            return [lon, lat]
    return list(coordinates[-1])


def build_checkpoints(geometry, route_distance_miles, route_duration_seconds,
                      departure_utc, interval_miles):
    """Build the ordered checkpoint list for one route.

    Returns a list of dicts with: index, latitude, longitude,
    cumulative_distance_miles, arrival_utc (datetime, UTC), is_origin,
    is_destination.
    """
    coordinates = geometry['coordinates']
    raw_cumulative = cumulative_route_distances(coordinates)
    geometry_length = raw_cumulative[-1]

    # Normalize so cumulative distance matches the routing API's distance.
    scale = (route_distance_miles / geometry_length) if geometry_length > 0 else 1.0
    cumulative = [d * scale for d in raw_cumulative]
    total_distance = cumulative[-1]

    target_distances = [0.0]
    next_target = float(interval_miles)
    while next_target < total_distance:
        target_distances.append(next_target)
        next_target += interval_miles
    if target_distances[-1] < total_distance - 1e-9:
        target_distances.append(total_distance)

    checkpoints = []
    for index, distance in enumerate(target_distances):
        lon, lat = interpolate_position(coordinates, cumulative, distance)
        fraction = (distance / total_distance) if total_distance > 0 else 0.0
        elapsed_seconds = route_duration_seconds * fraction
        checkpoints.append({
            'index': index,
            'latitude': lat,
            'longitude': lon,
            'cumulative_distance_miles': distance,
            'arrival_utc': departure_utc + timedelta(seconds=elapsed_seconds),
            'is_origin': index == 0,
            'is_destination': index == len(target_distances) - 1,
        })
    return checkpoints
