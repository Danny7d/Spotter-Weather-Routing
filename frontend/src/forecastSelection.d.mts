import type { Checkpoint, CorridorHour, CorridorPointResult } from './types'

export function selectedForecastTime(departureUtc: string, offsetHours: number): Date
export function forecastHourFromInput(event: { currentTarget: { value: string } }): number
export function selectedForecastLabel(departureUtc: string, offsetHours: number): string
export function selectedForecastAt(point: CorridorPointResult | undefined, offsetHours: number): CorridorHour | null
export function checkpointForecast(checkpoint: Checkpoint, points: CorridorPointResult[] | null, offsetHours: number): CorridorHour | null
