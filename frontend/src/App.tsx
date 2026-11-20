import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { createPlan, fetchCorridorForecast, ApiError } from './api/client'
import type { PlanRequest } from './api/client'
import type { CorridorPointResult, TripPlan } from './types'
import { TripForm, type TripFormValues } from './components/TripForm'
import { RoutePanel } from './components/RoutePanel'
import { ForecastControls } from './components/ForecastControls'
import { sampleRoutePoints } from './geo'

const RouteMap = lazy(() => import('./components/RouteMap').then((m) => ({ default: m.RouteMap })))

const FORECAST_HOURS = 49 // hour offsets 0..48 to cover the full 0-48h slider range

// Animated skeleton shown in the left panel while the route plan is loading.
function RouteSkeleton() {
  return (
    <div role="status" aria-label="Loading route options" className="space-y-3 border-t border-[var(--line)] pt-4">
      <div className="h-4 w-28 animate-pulse rounded bg-[#e2e8e9]" />
      {[0, 1].map((i) => (
        <div key={i} className="animate-pulse border-b border-[var(--line)] py-4">
          <div className="h-3 w-24 rounded bg-[#e2e8e9]" />
          <div className="mt-3 h-6 w-40 rounded bg-[#edf1f2]" />
          <div className="mt-3 h-2 w-full rounded bg-[#edf1f2]" />
        </div>
      ))}
    </div>
  )
}

export default function App() {
  const [plan, setPlan] = useState<TripPlan | null>(null)
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [corridorCache, setCorridorCache] = useState<Record<string, CorridorPointResult[]>>({})
  const [corridorLoading, setCorridorLoading] = useState(false)
  const [corridorError, setCorridorError] = useState<string | null>(null)
  const [overlayHour, setOverlayHour] = useState(0)
  const corridorRequestRef = useRef(0)

  const handlePlanSubmit = useCallback(async (values: TripFormValues) => {
    setLoading(true)
    setError(null)
    setPlan(null)
    setCorridorCache({})
    setOverlayHour(0)
    try {
      const payload: PlanRequest = {
        origin: values.origin,
        destination: values.destination,
        departure_local: values.departureLocal,
        load_weight_lbs: values.loadWeightLbs,
        checkpoint_interval_miles: values.intervalMiles,
      }
      const result = await createPlan(payload)
      setPlan(result)
      setSelectedRouteId(result.recommendation.route_id ?? result.routes[0]?.id ?? null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to plan route. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [])

  const selectedRoute = plan?.routes.find((r) => r.id === selectedRouteId) ?? null

  // Fetch corridor forecast for the selected route (cached per route).
  useEffect(() => {
    if (!plan || !selectedRoute) return
    if (corridorCache[selectedRoute.id]) return

    const requestId = ++corridorRequestRef.current
    setCorridorLoading(true)
    setCorridorError(null)

    const spacing = Math.max(2, selectedRoute.distance_miles / 60)
    // Include checkpoint coordinates in the same cached corridor request so the
    // markers can use the selected hour without another request per slider move.
    const checkpointPoints = selectedRoute.checkpoints.map((cp) => ({
      latitude: cp.latitude,
      longitude: cp.longitude,
      cumulative_distance_miles: cp.cumulative_distance_miles,
    }))
    const sampledPoints = sampleRoutePoints(selectedRoute.geometry, spacing, 200)
    const pointKey = (point: { latitude: number; longitude: number }) =>
      `${point.latitude.toFixed(4)},${point.longitude.toFixed(4)}`
    const unique = new Map<string, typeof checkpointPoints[number]>()
    checkpointPoints.forEach((point) => unique.set(pointKey(point), point))
    sampledPoints.forEach((point) => {
      if (unique.size < 200 && !unique.has(pointKey(point))) unique.set(pointKey(point), point)
    })
    const points = [...unique.values()]

    fetchCorridorForecast(points, plan.departure_utc, plan.load_weight_lbs, FORECAST_HOURS)
      .then(({ points: results }) => {
        if (corridorRequestRef.current !== requestId) return
        setCorridorCache((prev) => ({ ...prev, [selectedRoute.id]: results }))
      })
      .catch((err) => {
        if (corridorRequestRef.current !== requestId) return
        setCorridorError(err instanceof ApiError ? err.message : 'Forecast overlay unavailable.')
      })
      .finally(() => {
        if (corridorRequestRef.current === requestId) setCorridorLoading(false)
      })
  }, [plan, selectedRoute, corridorCache])

  const corridorPoints = selectedRoute ? corridorCache[selectedRoute.id] ?? null : null

  return (
    <div className="min-h-screen bg-[var(--canvas)] text-[var(--ink)]">
      {/* App header */}
      <header className="relative z-30 border-b border-[var(--line)] bg-white">
        <div className="mx-auto flex h-[60px] max-w-[1800px] items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-[9px] bg-[var(--brand)]" aria-hidden="true">
              <svg viewBox="0 0 32 32" className="h-6 w-6" fill="none">
                <path d="M6 22.5 13 9.5l7 13M9.5 17h10" stroke="white" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="24" cy="9" r="4.5" fill="#BDE7DC" />
                <path d="M24 6.8v4.4M21.8 9h4.4" stroke="#176B68" strokeWidth="1.3" strokeLinecap="round" />
              </svg>
            </span>
            <div>
              <div className="flex items-baseline gap-2">
                <h1 className="text-[17px] font-bold leading-tight tracking-[-0.04em] text-[var(--ink)]">Spotter</h1>
                <span className="hidden text-[11px] font-medium text-[var(--subtle)] sm:inline">Freight intelligence</span>
              </div>
              <p className="text-xs leading-tight text-[var(--muted)]">Weather-aware truck routing</p>
            </div>
          </div>
          <div className="hidden items-center gap-2 text-xs font-medium text-[var(--muted)] sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--brand)]" aria-hidden="true" />
            Weather-aware routing
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-[1800px] gap-3 px-3 py-3 sm:px-5 lg:h-[calc(100dvh-60px)] lg:grid-cols-[392px_minmax(0,1fr)] lg:gap-0 lg:px-0 lg:py-0">
        {/* Left column: form + route results — sticky on large screens */}
        <aside className="min-w-0 space-y-4 lg:h-full lg:overflow-y-auto lg:border-r lg:border-[var(--line)] lg:bg-[#f8faf9] lg:px-5 lg:py-5 xl:px-6">
          <section className="panel p-4 sm:p-5 lg:rounded-none lg:border-0 lg:bg-transparent lg:p-0 lg:shadow-none">
            <div className="mb-4 border-b border-[var(--line)] pb-3.5 lg:mb-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold text-[var(--brand)]">Trip planning</p>
                  <h2 className="mt-1 text-[20px] font-semibold tracking-[-0.035em] text-[var(--ink)]">Plan a trip</h2>
                </div>
              </div>
              <p className="mt-1 text-[13px] text-[var(--muted)]">Compare routes against forecast risk.</p>
            </div>
            <TripForm onSubmit={handlePlanSubmit} loading={loading} />
          </section>

          {loading && <RouteSkeleton />}

          {/* Top-level API error (not a route error) */}
          {error && (
            <div role="alert" className="flex items-start gap-2 border-l-2 border-red-600 bg-[#fff8f7] px-3 py-2.5 text-sm text-red-800">
              <span className="mt-0.5 shrink-0">⚠</span>
              <span>{error}</span>
            </div>
          )}

          {plan && (
            <RoutePanel
              plan={plan}
              selectedRouteId={selectedRouteId}
              onSelectRoute={setSelectedRouteId}
            />
          )}
        </aside>

        {/* Right column: map + forecast controls — sticky on large screens */}
        <section className="flex min-h-0 min-w-0 flex-col gap-3.5 lg:h-full lg:px-5 lg:py-4 xl:px-6" aria-label="Route map and forecast">
          <div className="min-h-[460px] flex-1 overflow-hidden sm:min-h-[520px] lg:min-h-0">
            <Suspense
              fallback={
                <div className="flex h-full min-h-[460px] items-center justify-center rounded-[10px] bg-[#e8edef] text-sm text-[var(--muted)] lg:min-h-0">
                  Loading map…
                </div>
              }
            >
              <RouteMap
                plan={plan}
                selectedRouteId={selectedRouteId}
                onSelectRoute={setSelectedRouteId}
                corridorPoints={corridorPoints}
                overlayHour={overlayHour}
                corridorLoading={corridorLoading}
              />
            </Suspense>
          </div>

          {plan && selectedRoute && (
            <ForecastControls
              departureUtc={plan.departure_utc}
              forecastHours={FORECAST_HOURS}
              hour={overlayHour}
              onHourChange={setOverlayHour}
              loading={corridorLoading}
              error={corridorError}
              pointCount={corridorPoints?.length ?? 0}
              forecastAvailable={Boolean(corridorPoints?.some((point) => point.hours.some((item) => item.offset_hours === overlayHour && item.risk_level !== 'unknown')))}
            />
          )}
        </section>
      </main>
    </div>
  )
}
