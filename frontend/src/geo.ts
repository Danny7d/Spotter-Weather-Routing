/** Geographic helpers mirroring the backend checkpoint math. */

const EARTH_RADIUS_MILES = 3958.7613

export function haversineMiles(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const phi1 = (lat1 * Math.PI) / 180
  const phi2 = (lat2 * Math.PI) / 180
  const dphi = ((lat2 - lat1) * Math.PI) / 180
  const dlambda = ((lon2 - lon1) * Math.PI) / 180
  const a =
    Math.sin(dphi / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlambda / 2) ** 2
  return 2 * EARTH_RADIUS_MILES * Math.asin(Math.sqrt(a))
}

export function cumulativeDistances(coordinates: [number, number][]): number[] {
  const cumulative = [0]
  for (let i = 1; i < coordinates.length; i++) {
    const [lon1, lat1] = coordinates[i - 1]
    const [lon2, lat2] = coordinates[i]
    cumulative.push(cumulative[i - 1] + haversineMiles(lat1, lon1, lat2, lon2))
  }
  return cumulative
}

export function interpolatePosition(
  coordinates: [number, number][],
  cumulative: number[],
  targetMiles: number,
): [number, number] {
  if (targetMiles <= 0) return coordinates[0]
  const total = cumulative[cumulative.length - 1]
  if (targetMiles >= total || total === 0) return coordinates[coordinates.length - 1]
  for (let i = 1; i < cumulative.length; i++) {
    if (cumulative[i] >= targetMiles) {
      const spanStart = cumulative[i - 1]
      const spanEnd = cumulative[i]
      const fraction = spanEnd > spanStart ? (targetMiles - spanStart) / (spanEnd - spanStart) : 0
      const lon = coordinates[i - 1][0] + fraction * (coordinates[i][0] - coordinates[i - 1][0])
      const lat = coordinates[i - 1][1] + fraction * (coordinates[i][1] - coordinates[i - 1][1])
      return [lon, lat]
    }
  }
  return coordinates[coordinates.length - 1]
}

/** Sample points along a route geometry every ~`spacingMiles`, capped at `maxPoints` (default 200). */
export function sampleRoutePoints(
  geometry: GeoJSON.LineString,
  spacingMiles: number,
  maxPoints: number = 200,
): { latitude: number; longitude: number; cumulative_distance_miles: number }[] {
  const coordinates = geometry.coordinates as [number, number][]
  const cumulative = cumulativeDistances(coordinates)
  const total = cumulative[cumulative.length - 1]
  const effectiveSpacing = Math.max(spacingMiles, maxPoints > 1 ? total / (maxPoints - 1) : 1)
  const points: { latitude: number; longitude: number; cumulative_distance_miles: number }[] = []
  for (let d = 0; d <= total; d += effectiveSpacing) {
    const [lon, lat] = interpolatePosition(coordinates, cumulative, Math.min(d, total))
    points.push({ latitude: lat, longitude: lon, cumulative_distance_miles: Math.min(d, total) })
  }
  // Ensure exact destination is included.
  const last = points[points.length - 1]
  if (last && Math.abs(last.cumulative_distance_miles - total) > 0.01) {
    const [lon, lat] = coordinates[coordinates.length - 1]
    points.push({ latitude: lat, longitude: lon, cumulative_distance_miles: total })
  }
  if (points.length > maxPoints) {
    const step = (points.length - 1) / (maxPoints - 1)
    const downsampled: typeof points = []
    for (let i = 0; i < maxPoints - 1; i++) {
      downsampled.push(points[Math.round(i * step)])
    }
    downsampled.push(points[points.length - 1])
    return downsampled
  }
  return points
}
