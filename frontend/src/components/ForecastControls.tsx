import { RISK_COLORS, RISK_LABELS } from '../risk'
import type { RiskLevel } from '../types'

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
  const selectedTime = new Date(departure.getTime() + hour * 3_600_000)
  const selectedTimeLabel = selectedTime
    .toUTCString()
    .replace(/^(\w+),\s(\d+)\s(\w+)\s(\d+)\s(\d+:\d+).*$/, '$1 $2 $3 · $5') + ' UTC'

  return (
    <section className="forecast-panel" aria-label="Route forecast controls">
      <div className="flex flex-wrap items-start justify-between gap-x-5 gap-y-3">
        <div>
          <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
            <h3 className="text-[14px] font-semibold tracking-[-0.02em] text-[var(--ink)]">Forecast timeline</h3>
            <span className="text-[11px] text-[var(--muted)]">
              {loading ? 'Updating corridor…' : `${pointCount} route samples`}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="text-[15px] font-semibold tracking-[-0.02em] tabular-nums text-[var(--ink)]">{selectedTimeLabel}</span>
            <span className="text-[12px] font-semibold tabular-nums text-[var(--brand)]">+{hour}h</span>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-x-3 gap-y-1.5 sm:grid-cols-6 sm:gap-x-3.5" aria-label="Risk level legend">
          {LEGEND_LEVELS.map((level) => (
            <span key={level} className="flex items-center gap-1.5 text-[11px] font-medium text-[#53616b]">
              <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: RISK_COLORS[level] }} />
              {RISK_LABELS[level]}
            </span>
          ))}
        </div>
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
          className="forecast-range h-2 w-full cursor-pointer appearance-none rounded-full bg-[#dce5e5]"
        />
        <div className="mt-1.5 flex justify-between text-[10px] font-medium tabular-nums text-[var(--subtle)]">
          <span>Departure</span>
          <span>+24h</span>
          <span>+48h</span>
        </div>
      </div>

      {error && <p role="alert" className="mt-2 text-[12px] text-red-700">{error}</p>}
    </section>
  )
}
