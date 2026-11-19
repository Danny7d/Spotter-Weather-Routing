export type RiskLevel =
  | 'low'
  | 'moderate'
  | 'high'
  | 'severe'
  | 'no_travel'
  | 'unknown'

export interface WeatherSample {
  wind_mph: number | null
  rain_in_hr: number | null
  snow_in_hr: number | null
  temperature_f: number | null
  forecast_hour_utc: string
  source: string
}

export interface RiskInfo {
  level: RiskLevel
  wind_level: RiskLevel
  rain_level: RiskLevel
  snow_level: RiskLevel
  load_rule: string
  factors: string[]
}

export interface Checkpoint {
  index: number
  latitude: number
  longitude: number
  cumulative_distance_miles: number
  arrival_utc: string
  is_origin: boolean
  is_destination: boolean
  weather: WeatherSample | null
  risk: RiskInfo
}

export interface RouteMetrics {
  severe_miles: number
  high_miles: number
  no_travel_miles: number
  average_risk_score: number | null
  weather_coverage: number
  has_no_travel: boolean
  status: 'ok' | 'incomplete' | 'no_travel'
}

export interface RouteOption {
  id: string
  geometry: GeoJSON.LineString
  distance_miles: number
  duration_seconds: number
  checkpoints: Checkpoint[]
  metrics: RouteMetrics
  rank: number
}

export interface PlaceInfo {
  query: string
  latitude: number
  longitude: number
  display_name: string
  timezone: string | null
}

export interface Recommendation {
  safe: boolean
  route_id: string | null
  reason: string
}

export interface TripPlan {
  origin: PlaceInfo
  destination: PlaceInfo
  departure_local: string
  departure_utc: string
  origin_timezone: string
  load_weight_lbs: number
  checkpoint_interval_miles: number
  routes: RouteOption[]
  recommendation: Recommendation
  warnings: string[]
}

export interface GeocodeResult {
  place_id: string
  display_name: string
  latitude: number
  longitude: number
}

export interface CorridorHour {
  offset_hours: number
  arrival_utc: string
  wind_mph?: number | null
  rain_in_hr?: number | null
  snow_in_hr?: number | null
  temperature_f?: number | null
  risk_level: RiskLevel
}

export interface CorridorPointResult {
  latitude: number
  longitude: number
  cumulative_distance_miles: number
  hours: CorridorHour[]
}
