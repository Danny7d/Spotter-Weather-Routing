import { useEffect, useState } from 'react'
import type { Checkpoint, RouteOption, TripPlan } from '../types'
import { RISK_COLORS, RISK_LABELS } from '../risk'

function formatTravelDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.round((seconds % 3600) / 60)
  return hours === 0 ? `${minutes} min` : `${hours}h ${minutes}m`
}

function toUtcLabel(isoUtc: string): string {
  const date = new Date(isoUtc)
  return `${date.toISOString().slice(0, 10)} ${date.toISOString().slice(11, 16)} UTC`
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
      className="inline-flex items-center rounded-[3px] px-1.5 py-0.5 text-[10px] font-semibold"
      style={{ backgroundColor: RISK_COLORS[level] ?? RISK_COLORS.unknown, color: textColor }}
    >
      {RISK_LABELS[level] ?? level}
    </span>
  )
}

function WeatherValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] font-medium text-[var(--subtle)]">{label}</div>
      <div className="mt-0.5 truncate text-[12px] font-medium tabular-nums text-[#35444d]">{value}</div>
    </div>
  )
}

function CheckpointRow({ cp }: { cp: Checkpoint }) {
  const weather = cp.weather
  const locationLabel = cp.is_origin
    ? 'Origin'
    : cp.is_destination
      ? 'Destination'
      : `Checkpoint ${cp.index}`

  return (
    <li className="checkpoint-row border-b border-[#e7ebeb] py-3 last:border-0">
      <div className="flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1">
        <span className={`text-[13px] text-[var(--ink)] ${cp.is_origin || cp.is_destination ? 'font-semibold' : 'font-medium'}`}>
          {locationLabel}
        </span>
        <RiskBadge level={cp.risk?.level ?? 'unknown'} />
        <span className="ml-auto text-[11px] font-medium tabular-nums text-[var(--muted)]">
          {cp.cumulative_distance_miles.toFixed(0)} mi <span className="px-0.5 text-[#aab5bc]">·</span> ETA {toUtcLabel(cp.arrival_utc)}
        </span>
      </div>

      {weather ? (
        <div className="mt-2 grid grid-cols-4 gap-2">
          <WeatherValue label="Wind" value={`${weather.wind_mph?.toFixed(0) ?? '—'} mph`} />
          <WeatherValue label="Temp" value={`${weather.temperature_f?.toFixed(0) ?? '—'}°F`} />
          <WeatherValue label="Rain" value={weather.rain_in_hr != null && weather.rain_in_hr > 0 ? `${weather.rain_in_hr.toFixed(2)} in/hr` : '—'} />
          <WeatherValue label="Snow" value={weather.snow_in_hr != null && weather.snow_in_hr > 0 ? `${weather.snow_in_hr.toFixed(2)} in/hr` : '—'} />
        </div>
      ) : (
        <div className="mt-1 text-[12px] text-[var(--subtle)]">Weather unavailable</div>
      )}

      {cp.risk?.factors && cp.risk.factors.length > 0 && (
        <div className="mt-2 border-l-2 border-[#ad751c] pl-2.5 text-[12px] leading-relaxed text-[#77501c]">
          {cp.risk.factors.join('; ')}
        </div>
      )}
    </li>
  )
}

function RiskMiles({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="min-w-0 border-r border-[#e5eaea] pl-2 first:pl-0 last:border-r-0">
      <div className="text-[10px] font-medium text-[var(--subtle)]">{label}</div>
      <div className="mt-0.5 text-[13px] font-semibold tabular-nums" style={{ color: value > 0 ? color : 'var(--muted)' }}>{value.toFixed(0)} mi</div>
    </div>
  )
}

interface RouteCardProps {
  route: RouteOption
  isSelected: boolean
  isRecommended: boolean
  isProvisional: boolean
  onSelect: () => void
}

function RouteCard({ route, isSelected, isRecommended, isProvisional, onSelect }: RouteCardProps) {
  const metrics = route.metrics
  const totalMiles = route.distance_miles || 1
  const noTravelPct = Math.min(100, (metrics.no_travel_miles / totalMiles) * 100)
  const severePct = Math.min(100 - noTravelPct, (metrics.severe_miles / totalMiles) * 100)
  const highPct = Math.min(100 - noTravelPct - severePct, (metrics.high_miles / totalMiles) * 100)
  const unknownPct = Math.min(100 - noTravelPct - severePct - highPct, (metrics.unknown_miles / totalMiles) * 100)
  const otherPct = 100 - noTravelPct - severePct - highPct - unknownPct
  const hasRiskMiles = metrics.no_travel_miles > 0 || metrics.severe_miles > 0 || metrics.high_miles > 0

  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={isSelected}
      className={`route-option interactive-card w-full border-b border-[#e1e7e7] px-3 py-3.5 text-left last:border-b-0 ${
        isSelected ? 'bg-[#eaf3f1]' : 'bg-transparent hover:bg-[#f3f7f6]'
      }`}
    >
      <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
        <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--muted)]">
          Route {route.id.replace('route-', '')}
        </span>
        {isRecommended && (
          <span className="rounded-[3px] bg-[var(--brand)] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.08em] text-white">
            Recommended
          </span>
        )}
        {isProvisional && (
          <span className="rounded-[3px] bg-[#ad751c] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.08em] text-white">
            Provisional
          </span>
        )}
        {metrics.has_no_travel && (
          <span className="rounded-[3px] bg-[#7f1d1d] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.06em] text-white">
            No Travel
          </span>
        )}
        {isSelected && <span className="ml-auto text-[10px] font-semibold text-[var(--brand)]">Selected</span>}
      </div>

      <div className="mt-2.5 flex items-end gap-3">
        <span className="text-[23px] font-semibold leading-none tracking-[-0.045em] tabular-nums text-[var(--ink)]">
          {route.distance_miles.toFixed(0)} <span className="text-[13px] font-medium tracking-normal text-[var(--muted)]">mi</span>
        </span>
        <span className="pb-0.5 text-[13px] text-[var(--muted)]">{formatTravelDuration(route.duration_seconds)}</span>
        <span className="ml-auto pb-0.5 text-right">
          <span className="block text-[10px] font-medium text-[var(--subtle)]">Average risk</span>
          <span className="text-[13px] font-semibold tabular-nums text-[var(--ink)]">
            {metrics.average_risk_score != null ? `${metrics.average_risk_score.toFixed(1)} / 5` : '—'}
          </span>
        </span>
      </div>

      <div className="mt-3 grid grid-cols-4 border-y border-[#e0e7e6] py-2">
        <RiskMiles label="No Travel" value={metrics.no_travel_miles} color="#7f1d1d" />
        <RiskMiles label="Severe" value={metrics.severe_miles} color="#b83333" />
        <RiskMiles label="High" value={metrics.high_miles} color="#a95514" />
        <RiskMiles label="Unknown" value={metrics.unknown_miles} color="#718096" />
      </div>

      <div
        className="mt-2 flex h-[4px] overflow-hidden rounded-sm bg-[#dbe1e2]"
        role="img"
        aria-label={`Route miles: ${metrics.no_travel_miles.toFixed(0)} no travel, ${metrics.severe_miles.toFixed(0)} severe, ${metrics.high_miles.toFixed(0)} high risk, ${metrics.unknown_miles.toFixed(0)} unknown, remaining miles are assessed lower risk`}
      >
        {noTravelPct > 0 && <div className="h-full bg-[#7f1d1d]" style={{ width: `${noTravelPct}%` }} />}
        {severePct > 0 && <div className="h-full bg-[#ef4444]" style={{ width: `${severePct}%` }} />}
        {highPct > 0 && <div className="h-full bg-[#f97316]" style={{ width: `${highPct}%` }} />}
        {unknownPct > 0 && <div className="h-full bg-[#9ca3af]" style={{ width: `${unknownPct}%` }} />}
        {otherPct > 0 && <div className="h-full bg-[#cbd5d8]" style={{ width: `${otherPct}%` }} />}
      </div>
      <div className="mt-1.5 flex justify-between text-[10px] text-[var(--subtle)]">
        <span>{hasRiskMiles ? 'Risk miles by severity' : 'No high, severe or no-travel miles'}</span>
        <span>{(metrics.weather_coverage * 100).toFixed(0)}% weather coverage</span>
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
  const recommendationStatus = plan.recommendation.status
  const [checkpointsExpanded, setCheckpointsExpanded] = useState(false)
  const allCheckpoints = selectedRoute?.checkpoints ?? []
  const collapseThreshold = 8
  const shouldCollapse = allCheckpoints.length > collapseThreshold
  const visibleCheckpoints = shouldCollapse && !checkpointsExpanded
    ? [...allCheckpoints.slice(0, 5), allCheckpoints[allCheckpoints.length - 1]]
    : allCheckpoints
  const hiddenCount = allCheckpoints.length - visibleCheckpoints.length

  useEffect(() => {
    setCheckpointsExpanded(false)
  }, [selectedRoute?.id])

  return (
    <div className="space-y-4">
      {plan.recommendation.status === 'safe' && plan.recommendation.safe ? (
        <div className="border-l-2 border-[var(--brand)] pl-3">
          <p className="text-[11px] font-semibold text-[var(--brand)]">
            Recommended route{recommendedId ? ` · ${recommendedId.replace('route-', 'Route ')}` : ''}
          </p>
          <p className="mt-1 text-[12px] leading-relaxed text-[var(--muted)]">{plan.recommendation.reason}</p>
        </div>
      ) : plan.recommendation.status === 'provisional' && recommendedId ? (
        <div className="border-l-2 border-[#ad751c] pl-3">
          <p className="text-[11px] font-semibold text-[#77501c]">
            Provisional route · {recommendedId.replace('route-', 'Route ')} · incomplete weather
          </p>
          <p className="mt-1 text-[12px] leading-relaxed text-[var(--muted)]">{plan.recommendation.reason}</p>
        </div>
      ) : (
        <div className="border-l-2 border-[#ad751c] pl-3">
          <p className="text-[11px] font-semibold text-[#77501c]">No route meets the safety criteria</p>
          <p className="mt-1 text-[12px] leading-relaxed text-[var(--muted)]">{plan.recommendation.reason}</p>
        </div>
      )}

      {plan.warnings.map((warning) => (
        <div key={warning} className="flex items-start gap-2 border-l-2 border-[#ad751c] bg-[#faf6ed] px-3 py-2.5 text-[12px] leading-relaxed text-[#77501c]">
          <span className="mt-0.5 shrink-0" aria-hidden="true">!</span>
          <span>{warning}</span>
        </div>
      ))}

      <section aria-label="Route options">
        <div className="mb-1 flex items-baseline justify-between border-b border-[var(--line)] pb-2">
          <h3 className="text-[14px] font-semibold tracking-[-0.02em] text-[var(--ink)]">Route options</h3>
          <span className="text-[11px] text-[var(--muted)]">{plan.routes.length} available</span>
        </div>
        {plan.routes.map((route) => (
          <RouteCard
            key={route.id}
            route={route}
            isSelected={route.id === selectedRoute?.id}
            isRecommended={route.id === recommendedId && recommendationStatus === 'safe'}
            isProvisional={route.id === recommendedId && recommendationStatus === 'provisional'}
            onSelect={() => onSelectRoute(route.id)}
          />
        ))}
      </section>

      {selectedRoute && (
        <section className="border-t border-[var(--line)] pt-4" aria-label="Selected route checkpoints">
          <div className="mb-2.5 flex items-start justify-between gap-2">
            <div>
              <p className="text-[11px] font-semibold text-[var(--brand)]">Route detail</p>
              <h3 className="mt-0.5 text-[15px] font-semibold tracking-[-0.02em] text-[var(--ink)]">
                Checkpoints · Route {selectedRoute.id.replace('route-', '')}
              </h3>
              <p className="mt-1 text-[11px] leading-relaxed text-[var(--muted)]">
                Departure {toUtcLabel(plan.departure_utc)} <span className="px-0.5">·</span> {plan.origin_timezone}
              </p>
            </div>
            <span className="shrink-0 pt-1 text-[11px] font-medium tabular-nums text-[var(--muted)]">
              {allCheckpoints.length} stops
            </span>
          </div>

          <ul id="route-checkpoints">
            {visibleCheckpoints.map((cp) => <CheckpointRow key={cp.index} cp={cp} />)}
          </ul>

          {shouldCollapse && (
            <button
              type="button"
              aria-expanded={checkpointsExpanded}
              aria-controls="route-checkpoints"
              onClick={() => setCheckpointsExpanded((v) => !v)}
              className="mt-2 w-full border-t border-[var(--line)] py-2.5 text-xs font-semibold text-[var(--brand)] transition-colors hover:bg-[#f4f9f8] focus-visible:outline-offset-2"
            >
              {checkpointsExpanded
                ? 'Show fewer checkpoints'
                : `Show ${hiddenCount} more checkpoint${hiddenCount !== 1 ? 's' : ''}`}
            </button>
          )}
        </section>
      )}
    </div>
  )
}
