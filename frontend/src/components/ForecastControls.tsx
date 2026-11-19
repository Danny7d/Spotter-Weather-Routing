import { RISK_COLORS, RISK_LABELS } from '../risk'
import type { RiskLevel } from '../types'

// All six risk levels shown in the legend, left-to-right, low to unknown.
const LEGEND_LEVELS: RiskLevel[] = ['low', 'moderate', 'high', 'severe', 'no_travel', 'unknown']

interface ForecastControlsProps {
  departureUtc: string
  forecastHours: number
  hour: number
  onHourChange: (hour: number) => void
  loading: boolean
  error: string | null
  pointCount: number
}

export function ForecastControls({
  departureUtc,
  forecastHours,
  hour,
  onHourChange,
  loading,
  error,
  pointCount,
}: ForecastControlsProps) {
  const departure = new Date(departureUtc)

  // Calculate the absolute wall-clock time the slider is pointing at.
  const selectedTime = new Date(departure.getTime() + hour * 3_600_000)

  // Format as "Thu 20 Nov · 08:00 UTC" for operator-friendly reading.
  const selectedTimeLabel =
    selectedTime.toUTCString().replace(/^(\w+),\s(\d+)\s(\w+)\s(\d+)\s(\d+:\d+).*$/, '$1 $2 $3 · $5') + ' UTC'

  return (
    <section className="panel px-4 py-3.5 sm:px-5" aria-label="Route forecast controls">
      <div className="flex flex-col gap-3.5">
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--brand)]">Forecast timeline</p>
            <h3 className="mt-0.5 text-[14px] font-semibold text-[var(--ink)]">Weather-risk overlay</h3>
            <p className="mt-0.5 text-xs text-[var(--muted)]">
              {loading
                ? 'Loading forecast data…'
                : `${pointCount} sample points · +${hour}h from departure`}
            </p>
          </div>

          <div className="grid grid-cols-3 gap-x-3 gap-y-1.5 sm:gap-x-4" aria-label="Risk level legend">
            {LEGEND_LEVELS.map((level) => (
              <span key={level} className="flex items-center gap-1.5 text-[11px] font-medium text-[#53616b] sm:text-xs">
                <span
                  className="inline-block h-2.5 w-2.5 shrink-0 rounded-full ring-1 ring-black/5"
                  style={{ backgroundColor: RISK_COLORS[level] }}
                />
                {RISK_LABELS[level]}
              </span>
            ))}
          </div>
        </div>

        <div className="rounded-[10px] border border-[#e7ecee] bg-[#f8fafb] px-3.5 py-3">
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
            <span className="text-[13px] font-semibold tabular-nums text-[var(--ink)]">{selectedTimeLabel}</span>
            <span className="rounded-md bg-white px-2 py-1 text-[11px] font-semibold tabular-nums text-[var(--brand)] ring-1 ring-[#e1e9e8]">+{hour}h from departure</span>
          </div>
          <div className="mt-3.5">
            <input
              type="range"
              min={0}
              max={forecastHours - 1}
              step={1}
              value={hour}
              aria-label="Forecast hour offset"
              aria-valuetext={`${hour} hours after departure`}
              onChange={(e) => onHourChange(Number(e.target.value))}
              className="forecast-range h-2 w-full cursor-pointer appearance-none rounded-full bg-[#dce5e5] accent-[var(--brand)]"
            />
            <div className="mt-2 flex justify-between text-[10px] font-medium tabular-nums text-[var(--subtle)]">
              <span>Departure</span>
              <span>+24 hours</span>
              <span>+48 hours</span>
            </div>
          </div>
        </div>

        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}

        <p className="text-[11px] text-[var(--subtle)]">Forecast via Open-Meteo <span className="px-1">·</span> Risk follows sampled route points</p>
      </div>
    </section>
  )
}
