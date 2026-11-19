import { useEffect, useState } from 'react'
import type { Checkpoint, RouteOption, TripPlan } from '../types'
import { RISK_COLORS, RISK_LABELS } from '../risk'

// Formats a duration in seconds into "2h 15m" or "45 min".
function formatTravelDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.round((seconds % 3600) / 60)
  if (hours === 0) return `${minutes} min`
  return `${hours}h ${minutes}m`
}

// Formats an ISO UTC string into "2026-11-20 14:00 UTC" using the Date API — no string surgery.
function toUtcLabel(isoUtc: string): string {
  const date = new Date(isoUtc)
  const datePart = date.toISOString().slice(0, 10)
  const timePart = date.toISOString().slice(11, 16)
  return `${datePart} ${timePart} UTC`
}

function RiskBadge({ level }: { level: string }) {
  const textColor = level === 'no_travel'
    ? '#ffffff'
    : level === 'severe'
      ? '#641d1d'
      : level === 'high'
        ? '#482407'
        : level === 'moderate'
          ? '#463700'
          : level === 'low'
            ? '#12452d'
            : '#34424c'

  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold"
      style={{ backgroundColor: RISK_COLORS[level] ?? RISK_COLORS.unknown, color: textColor }}
    >
      {RISK_LABELS[level] ?? level}
    </span>
  )
}

function CheckpointRow({ cp }: { cp: Checkpoint }) {
  const weather = cp.weather

  // Determine a human-readable label for this checkpoint's position.
  const locationLabel = cp.is_origin
    ? '○ Origin'
    : cp.is_destination
      ? '● Destination'
      : `Checkpoint ${cp.index}`

  return (
    <li className="flex items-start justify-between gap-2 border-b border-[#edf0f2] py-3 text-sm last:border-0">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`text-slate-800 ${cp.is_origin || cp.is_destination ? 'font-semibold' : 'font-medium'}`}>
            {locationLabel}
          </span>
          <RiskBadge level={cp.risk?.level ?? 'unknown'} />
        </div>

        <div className="mt-1 text-[13px] text-[var(--muted)]">
          {cp.cumulative_distance_miles.toFixed(0)} mi <span className="px-1 text-[#aab5bc]">·</span> ETA {toUtcLabel(cp.arrival_utc)}
        </div>

        {weather && (
          // Two-column mini-grid: Wind | Temp on row 1, Rain | Snow on row 2.
          <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[13px] text-[#46545f]">
            <span>Wind {weather.wind_mph?.toFixed(0) ?? '—'} mph</span>
            <span>{weather.temperature_f?.toFixed(0) ?? '—'}°F</span>
            {/* Only show precipitation values if non-zero; otherwise show a dash. */}
            <span>Rain {weather.rain_in_hr != null && weather.rain_in_hr > 0 ? `${weather.rain_in_hr.toFixed(2)} in/hr` : '—'}</span>
            <span>Snow {weather.snow_in_hr != null && weather.snow_in_hr > 0 ? `${weather.snow_in_hr.toFixed(2)} in/hr` : '—'}</span>
          </div>
        )}

        {!weather && (
          <div className="mt-1 text-[13px] text-[var(--subtle)]">Weather unavailable</div>
        )}

        {cp.risk?.factors && cp.risk.factors.length > 0 && (
          <div className="mt-1.5 text-[13px] leading-relaxed text-[#85501a]">{cp.risk.factors.join('; ')}</div>
        )}
      </div>
    </li>
  )
}

interface RouteCardProps {
  route: RouteOption
  isSelected: boolean
  isRecommended: boolean
  onSelect: () => void
}

function RouteCard({ route, isSelected, isRecommended, onSelect }: RouteCardProps) {
  const metrics = route.metrics

  // Build a proportional risk bar: no_travel | severe | high | clear.
  const totalMiles = route.distance_miles || 1
  const noTravelPct = Math.min(100, (metrics.no_travel_miles / totalMiles) * 100)
  const severePct = Math.min(100 - noTravelPct, (metrics.severe_miles / totalMiles) * 100)
  const highPct = Math.min(100 - noTravelPct - severePct, (metrics.high_miles / totalMiles) * 100)
  const clearPct = 100 - noTravelPct - severePct - highPct

  const hasRiskMiles =
    metrics.no_travel_miles > 0 || metrics.severe_miles > 0 || metrics.high_miles > 0

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={isSelected}
      className={`interactive-card w-full rounded-[11px] border p-3.5 text-left ${
        isSelected ? 'border-[var(--brand)] bg-[#fbfefd] shadow-[0_0_0_1px_rgb(23_107_104/8%)]' : 'border-[var(--line)] bg-white hover:border-[#aab8c0] hover:shadow-sm'
      }`}
    >
      {/* Card header: route name + status badges */}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="text-[13px] font-semibold text-[var(--ink)]">Route {route.id.replace('route-', '')}</span>
        {isRecommended && (
          <span className="inline-flex items-center gap-1 rounded-full bg-[var(--brand-soft)] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-[var(--brand)]">
            <span aria-hidden="true">✓</span> Recommended
          </span>
        )}
        {metrics.has_no_travel && (
          <span className="rounded-full bg-[#f8e9e9] px-2 py-0.5 text-[10px] font-semibold text-[#7f1d1d]">
            No Travel
          </span>
        )}
      </div>

      {/* Route identity and travel time */}
      <div className="mt-2 flex items-baseline gap-x-3 gap-y-1">
        <span className="text-[19px] font-semibold leading-none tracking-[-0.04em] text-[var(--ink)]">{route.distance_miles.toFixed(0)} <span className="text-[12px] font-medium tracking-normal text-[var(--muted)]">mi</span></span>
        <span className="text-[13px] text-[var(--muted)]">{formatTravelDuration(route.duration_seconds)}</span>
        <span className="ml-auto text-[11px] font-medium text-[var(--subtle)]">{metrics.average_risk_score != null ? `Avg risk ${metrics.average_risk_score.toFixed(1)} / 5` : 'Risk unavailable'}</span>
      </div>

      {/* Risk mile summary — no_travel first, then severe/high, or a green clear line */}
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px]">
        {hasRiskMiles ? (
          <>
            {metrics.no_travel_miles > 0 && (
              <span className="font-semibold text-[#7f1d1d]">
                {metrics.no_travel_miles.toFixed(0)} mi no-travel
              </span>
            )}
            {metrics.severe_miles > 0 && (
              <span className="font-medium text-[#c83f3f]">{metrics.severe_miles.toFixed(0)} mi severe</span>
            )}
            {metrics.high_miles > 0 && (
              <span className="font-medium text-[#bd6418]">{metrics.high_miles.toFixed(0)} mi high risk</span>
            )}
          </>
        ) : (
          <span className="font-medium text-[#397b68]">No high, severe or no-travel miles</span>
        )}
        {metrics.weather_coverage < 1 && (
          <span className="ml-auto text-[var(--muted)]">
            {(metrics.weather_coverage * 100).toFixed(0)}% coverage
          </span>
        )}
      </div>

      {/* Proportional risk bar: dark-red = no_travel, red = severe, orange = high, green = clear */}
      <div className="mt-3 flex h-[5px] overflow-hidden rounded-full bg-[#edf1f2]" role="img" aria-label={`Route miles: ${metrics.no_travel_miles.toFixed(0)} no travel, ${metrics.severe_miles.toFixed(0)} severe, ${metrics.high_miles.toFixed(0)} high risk, remaining miles include lower or unknown risk`}>
        {noTravelPct > 0 && (
          <div className="h-full bg-[#7f1d1d]" style={{ width: `${noTravelPct}%` }} />
        )}
        {severePct > 0 && (
          <div className="h-full bg-[#ef4444]" style={{ width: `${severePct}%` }} />
        )}
        {highPct > 0 && (
          <div className="h-full bg-[#f97316]" style={{ width: `${highPct}%` }} />
        )}
        {clearPct > 0 && (
          <div className="h-full bg-[#cbd5d8]" style={{ width: `${clearPct}%` }} />
        )}
      </div>
    </button>
  )
}

interface RoutePanelProps {
  plan: TripPlan
  selectedRouteId: string | null
  onSelectRoute: (routeId: string) => void
}

export function RoutePanel({ plan, selectedRouteId, onSelectRoute }: RoutePanelProps) {
  const selectedRoute = plan.routes.find((r) => r.id === selectedRouteId) ?? plan.routes[0]
  const recommendedId = plan.recommendation.route_id

  // Checkpoint list collapse state — reset whenever the user switches routes.
  const [checkpointsExpanded, setCheckpointsExpanded] = useState(false)
  const allCheckpoints = selectedRoute?.checkpoints ?? []

  // Show origin + up to 4 intermediates + destination when collapsed.
  const COLLAPSE_THRESHOLD = 8
  const shouldCollapse = allCheckpoints.length > COLLAPSE_THRESHOLD
  const visibleCheckpoints =
    shouldCollapse && !checkpointsExpanded
      ? [...allCheckpoints.slice(0, 5), allCheckpoints[allCheckpoints.length - 1]]
      : allCheckpoints
  const hiddenCount = allCheckpoints.length - visibleCheckpoints.length

  // Reset to collapsed view whenever the selected route changes.
  useEffect(() => {
    setCheckpointsExpanded(false)
  }, [selectedRoute?.id])

  return (
    <div className="space-y-3.5">
      {/* Recommendation banner */}
      {plan.recommendation.safe ? (
        <div className="rounded-[11px] border border-[#b9d9d3] bg-[#eef7f5] p-3.5">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-semibold text-[var(--brand)]">Recommended route identified</span>
            {recommendedId && (
              <span className="rounded-full bg-white px-2 py-0.5 text-[11px] font-semibold text-[var(--brand)]">
                Route {recommendedId.replace('route-', '')}
              </span>
            )}
          </div>
          <p className="mt-1 text-[13px] leading-relaxed text-[#355e58]">{plan.recommendation.reason}</p>
        </div>
      ) : (
        <div className="rounded-[11px] border border-[#d9dfe3] bg-[#f7f9fa] p-3.5">
          <p className="text-[13px] font-semibold text-[var(--ink)]">No route meets the safety criteria</p>
          <p className="mt-1 text-[13px] leading-relaxed text-[var(--muted)]">{plan.recommendation.reason}</p>
        </div>
      )}

      {/* General warnings from the backend */}
      {plan.warnings.map((warning) => (
        <div
          key={warning}
          className="flex items-start gap-2 rounded-[10px] border border-[#e8d7b4] bg-[#fcf8ef] p-3 text-[13px] leading-relaxed text-[#77501c]"
        >
          <span className="mt-0.5 shrink-0" aria-hidden="true">!</span>
          <span>{warning}</span>
        </div>
      ))}

      {/* Route comparison cards */}
      <div className="space-y-2.5">
        {plan.routes.map((route) => (
          <RouteCard
            key={route.id}
            route={route}
            isSelected={route.id === selectedRoute?.id}
            isRecommended={route.id === recommendedId}
            onSelect={() => onSelectRoute(route.id)}
          />
        ))}
      </div>

      {/* Checkpoint list for the selected route — collapsible when long */}
      {selectedRoute && (
        <div className="panel p-3.5">
          <div className="mb-2 flex items-start justify-between gap-2">
            <div>
              <h3 className="text-[13px] font-semibold text-[var(--ink)]">
                Checkpoints — Route {selectedRoute.id.replace('route-', '')}
              </h3>
              <p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">
                Departure {toUtcLabel(plan.departure_utc)} &middot; timezone{' '}
                <span className="font-medium">{plan.origin_timezone}</span>
              </p>
            </div>
            <span className="shrink-0 rounded-full bg-[#f0f3f4] px-2 py-1 text-[10px] font-semibold text-[var(--muted)]">
              {allCheckpoints.length} stops
            </span>
          </div>

          <ul id="route-checkpoints">
            {visibleCheckpoints.map((cp) => (
              <CheckpointRow key={cp.index} cp={cp} />
            ))}
          </ul>

          {/* Collapse / expand toggle */}
          {shouldCollapse && (
            <button
              type="button"
              aria-expanded={checkpointsExpanded}
              aria-controls="route-checkpoints"
              onClick={() => setCheckpointsExpanded((v) => !v)}
              className="mt-2 w-full rounded-[8px] border border-[var(--line)] py-2 text-xs font-semibold text-[var(--brand)] transition-colors hover:bg-[#f4f9f8] focus-visible:outline-offset-2"
            >
              {checkpointsExpanded
                ? 'Show fewer checkpoints'
                : `Show ${hiddenCount} more checkpoint${hiddenCount !== 1 ? 's' : ''}`}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
