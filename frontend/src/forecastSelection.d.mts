import type { Checkpoint, CorridorHour, CorridorPointResult } from './types'

export function selectedForecastTime(departureUtc: string, offsetHours: number): Date
export function selectedForecastAt(point: CorridorPointResult | undefined, offsetHours: number): CorridorHour | null
export function checkpointForecast(checkpoint: Checkpoint, points: CorridorPointResult[] | null, offsetHours: number): CorridorHour | null
