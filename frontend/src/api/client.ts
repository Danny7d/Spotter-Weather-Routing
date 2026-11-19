import type { CorridorPointResult, GeocodeResult, TripPlan } from '../types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new ApiError(body.error ?? `Request failed (${response.status})`, response.status)
  }
  return body as T
}

export function geocode(query: string) {
  return request<{ results: GeocodeResult[] }>(`/api/geocode/?q=${encodeURIComponent(query)}`)
}

export interface PlanRequest {
  origin: string
  destination: string
  departure_local: string
  load_weight_lbs: number
  checkpoint_interval_miles: number
}

export function createPlan(payload: PlanRequest) {
  return request<TripPlan>('/api/plan/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchCorridorForecast(
  points: { latitude: number; longitude: number; cumulative_distance_miles: number }[],
  departureUtc: string,
  loadWeightLbs: number,
  forecastHours = 48,
) {
  return request<{ points: CorridorPointResult[] }>('/api/corridor-forecast/', {
    method: 'POST',
    body: JSON.stringify({
      points,
      departure_utc: departureUtc,
      load_weight_lbs: loadWeightLbs,
      forecast_hours: forecastHours,
    }),
  })
}
