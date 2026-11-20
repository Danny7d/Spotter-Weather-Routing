import { useEffect, useRef } from 'react'
import mapboxgl from 'mapbox-gl'
import type { CorridorPointResult, TripPlan } from '../types'
import { RISK_COLORS, ROUTE_COLORS } from '../risk'
import { worseRisk } from '../riskUtils'
import { checkpointMapForecast, selectedForecastAt } from '../forecastSelection.mjs'

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string | undefined

interface RouteMapProps {
  plan: TripPlan | null
  selectedRouteId: string | null
  onSelectRoute: (routeId: string) => void
  corridorPoints: CorridorPointResult[] | null
  overlayHour: number
  corridorLoading: boolean
}

function checkpointFeatures(plan: TripPlan, selectedRouteId: string | null, corridorPoints: CorridorPointResult[] | null, hour: number) {
  const features: GeoJSON.Feature[] = []
  plan.routes.forEach((route, routeIndex) => {
    route.checkpoints.forEach((cp) => {
      const forecast = checkpointMapForecast(route.id, selectedRouteId, cp, corridorPoints, hour)
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [cp.longitude, cp.latitude] },
        properties: {
          route_id: route.id,
          route_index: routeIndex,
          checkpoint_index: cp.index,
          risk_level: forecast.riskLevel,
          cumulative_distance_miles: cp.cumulative_distance_miles,
          arrival_utc: cp.arrival_utc,
          is_origin: cp.is_origin,
          is_destination: cp.is_destination,
          weather: forecast.weather,
          forecast_utc: forecast.forecastUtc,
          risk: forecast.riskLevel === 'unknown' ? null : { level: forecast.riskLevel },
        },
      })
    })
  })
  return { type: 'FeatureCollection' as const, features }
}

function routeFeatures(plan: TripPlan, selectedRouteId: string | null) {
  return {
    type: 'FeatureCollection' as const,
    features: plan.routes.map((route, index) => ({
      type: 'Feature' as const,
      geometry: route.geometry,
      properties: {
        route_id: route.id,
        color: ROUTE_COLORS[index % ROUTE_COLORS.length],
        selected: route.id === selectedRouteId ? 1 : 0,
      },
    })),
  }
}

function overlayFeatures(points: CorridorPointResult[], hour: number) {
  const features: GeoJSON.Feature[] = []
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i]
    const b = points[i + 1]
    const riskA = selectedForecastAt(a, hour)?.risk_level ?? 'unknown'
    const riskB = selectedForecastAt(b, hour)?.risk_level ?? 'unknown'
    const level = worseRisk(riskA, riskB)
    features.push({
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: [
          [a.longitude, a.latitude],
          [b.longitude, b.latitude],
        ],
      },
      properties: { color: RISK_COLORS[level] ?? RISK_COLORS.unknown, risk_level: level },
    })
  }
  return { type: 'FeatureCollection' as const, features }
}

export function RouteMap({ plan, selectedRouteId, onSelectRoute, corridorPoints, overlayHour, corridorLoading }: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<mapboxgl.Map | null>(null)
  const popupRef = useRef<mapboxgl.Popup | null>(null)
  const onSelectRef = useRef(onSelectRoute)
  useEffect(() => {
    onSelectRef.current = onSelectRoute
  }, [onSelectRoute])

  // Initialize map once.
  useEffect(() => {
    if (!MAPBOX_TOKEN || !containerRef.current || mapRef.current) return
    mapboxgl.accessToken = MAPBOX_TOKEN
    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: 'mapbox://styles/mapbox/light-v11',
      center: [-98, 39],
      zoom: 3,
    })
    map.addControl(new mapboxgl.NavigationControl(), 'top-right')
    map.on('load', () => {
      map.addSource('routes', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      map.addSource('checkpoints', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      map.addSource('risk-overlay', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })

      map.addLayer({
        id: 'route-line-casing',
        type: 'line',
        source: 'routes',
        paint: {
          'line-color': '#ffffff',
          'line-width': ['case', ['==', ['get', 'selected'], 1], 11, 6],
          'line-opacity': 0.96,
        },
      })
      map.addLayer({
        id: 'route-lines',
        type: 'line',
        source: 'routes',
        paint: {
          'line-color': ['get', 'color'],
          // Selected route is thicker and fully opaque; others are thin and faded.
          'line-width': ['case', ['==', ['get', 'selected'], 1], 7, 3],
          'line-opacity': ['case', ['==', ['get', 'selected'], 1], 1, 0.72],
        },
      })
      // Draw forecast risk above both the casing and base route lines, while
      // keeping checkpoint markers above the overlay.
      map.addLayer({
        id: 'risk-overlay-line',
        type: 'line',
        source: 'risk-overlay',
        paint: { 'line-color': ['get', 'color'], 'line-width': 7, 'line-opacity': 0.85 },
      })
      map.addLayer({
        id: 'checkpoint-circles',
        type: 'circle',
        source: 'checkpoints',
        paint: {
          // Origin and destination get a larger dot; selected-route checkpoints medium; others small.
          'circle-radius': [
            'case',
            ['==', ['get', 'is_origin'], true], 9,
            ['==', ['get', 'is_destination'], true], 9,
            ['==', ['get', 'selected_route'], 1], 7,
            5,
          ],
          'circle-color': [
            'case',
            // Origin and destination pins are always white — their position matters, not their risk color.
            ['==', ['get', 'is_origin'], true], '#ffffff',
            ['==', ['get', 'is_destination'], true], '#ffffff',
            [
              'match', ['get', 'risk_level'],
              'low', RISK_COLORS.low,
              'moderate', RISK_COLORS.moderate,
              'high', RISK_COLORS.high,
              'severe', RISK_COLORS.severe,
              'no_travel', RISK_COLORS.no_travel,
              RISK_COLORS.unknown,
            ],
          ],
          // Origin/destination use a dark navy stroke; regular checkpoints use white.
          'circle-stroke-color': [
            'case',
            ['==', ['get', 'is_origin'], true], '#1e293b',
            ['==', ['get', 'is_destination'], true], '#1e293b',
            '#ffffff',
          ],
          'circle-stroke-width': [
            'case',
            ['==', ['get', 'is_origin'], true], 2.5,
            ['==', ['get', 'is_destination'], true], 2.5,
            1.5,
          ],
        },
      })

      map.on('click', 'checkpoint-circles', (e) => {
        const feature = e.features?.[0]
        if (!feature) return

        const props = feature.properties as Record<string, unknown>
        const weather = props.weather as {
          wind_mph?: number | null
          rain_in_hr?: number | null
          snow_in_hr?: number | null
          temperature_f?: number | null
        } | null

        // Format arrival time as "YYYY-MM-DD HH:MM UTC" without string surgery.
        const arrivalDate = new Date(String(props.arrival_utc))
        const arrivalLabel = arrivalDate.toISOString().slice(0, 16).replace('T', ' ') + ' UTC'
        const forecastDate = props.forecast_utc ? new Date(String(props.forecast_utc)) : null
        const forecastLabel = forecastDate && !Number.isNaN(forecastDate.getTime())
          ? forecastDate.toISOString().slice(0, 16).replace('T', ' ') + ' UTC'
          : null

        // Determine a human-readable label for the checkpoint position.
        const locationLabel = props.is_origin
          ? 'Origin'
          : props.is_destination
            ? 'Destination'
            : `Checkpoint ${props.checkpoint_index}`

        // Format weather values — show a dash when a measurement is missing or zero precip.
        const windMph = weather?.wind_mph != null ? `${weather.wind_mph.toFixed(0)} mph` : '—'
        const tempF = weather?.temperature_f != null ? `${weather.temperature_f.toFixed(0)}°F` : '—'
        const rainIn = weather?.rain_in_hr != null && weather.rain_in_hr > 0
          ? `${weather.rain_in_hr.toFixed(2)} in/hr`
          : '—'
        const snowIn = weather?.snow_in_hr != null && weather.snow_in_hr > 0
          ? `${weather.snow_in_hr.toFixed(2)} in/hr`
          : '—'

        const riskLabel = String(props.risk_level).replace('_', ' ')
        const distanceMi = Number(props.cumulative_distance_miles).toFixed(0)
        const riskColor = {
          low: '#22c55e', moderate: '#eab308', high: '#f97316',
          severe: '#ef4444', no_travel: '#7f1d1d', unknown: '#9ca3af',
        }[String(props.risk_level)] ?? '#9ca3af'

        const popupHtml = `
          <div style="font-family:'Inter',ui-sans-serif,system-ui,sans-serif;font-size:13px;line-height:1.6;min-width:200px">
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:3px">
              <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${riskColor};flex-shrink:0"></span>
              <span style="font-weight:600">${locationLabel}</span>
            </div>
            <div style="color:#64717d;font-size:12px;margin-bottom:7px;padding-left:14px">
              ${distanceMi} mi along route &middot; ${riskLabel} risk
            </div>
            <div style="color:#34424c;font-size:13px;margin-bottom:5px;padding-left:14px">
              ETA ${arrivalLabel}${forecastLabel ? `<br>Forecast ${forecastLabel}` : ''}
            </div>
            ${
              weather
                ? `<div style="display:grid;grid-template-columns:1fr 1fr;gap:3px 12px;font-size:13px;color:#34424c;padding-left:14px">
                    <span>Wind ${windMph}</span><span>${tempF}</span>
                    <span>Rain ${rainIn}</span><span>Snow ${snowIn}</span>
                   </div>`
                : `<div style="color:#82909c;font-size:13px;padding-left:14px">Weather unavailable</div>`
            }
          </div>
        `

        const geometry = e.features?.[0]?.geometry as GeoJSON.Point | undefined
        if (!geometry) return
        popupRef.current?.remove()
        popupRef.current = new mapboxgl.Popup({ closeButton: true, maxWidth: '280px' })
          .setLngLat(geometry.coordinates as [number, number])
          .setHTML(popupHtml)
          .addTo(map)
      })
      map.on('mouseenter', 'checkpoint-circles', () => {
        map.getCanvas().style.cursor = 'pointer'
      })
      map.on('mouseleave', 'checkpoint-circles', () => {
        map.getCanvas().style.cursor = ''
      })
      map.on('mouseenter', 'route-lines', () => {
        map.getCanvas().style.cursor = 'pointer'
      })
      map.on('mouseleave', 'route-lines', () => {
        map.getCanvas().style.cursor = ''
      })
    })
    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  // Update route geometry only when the plan or selected route changes.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !plan) return
    const apply = () => {
      ;(map.getSource('routes') as mapboxgl.GeoJSONSource)?.setData(routeFeatures(plan, selectedRouteId))
      const bounds = new mapboxgl.LngLatBounds()
      plan.routes.forEach((r) => {
        r.geometry.coordinates.forEach((c) => bounds.extend(c as [number, number]))
      })
      if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 60, duration: 800 })
    }
    if (map.isStyleLoaded()) apply()
    else map.once('load', apply)
  }, [plan, selectedRouteId])

  // Checkpoint weather and risk follow the same selected forecast hour as the line overlay.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !plan) return
    const cps = checkpointFeatures(plan, selectedRouteId, corridorPoints, overlayHour)
    cps.features.forEach((feature) => {
      feature.properties = { ...feature.properties, selected_route: feature.properties?.route_id === selectedRouteId ? 1 : 0 }
    })
    const apply = () => (map.getSource('checkpoints') as mapboxgl.GeoJSONSource)?.setData(cps)
    if (map.isStyleLoaded()) apply()
    else map.once('load', apply)
  }, [plan, selectedRouteId, corridorPoints, overlayHour])

  // Update risk overlay when corridor data or hour changes.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const data = corridorPoints
      ? overlayFeatures(corridorPoints, overlayHour)
      : { type: 'FeatureCollection' as const, features: [] }
    const apply = () => {
      ;(map.getSource('risk-overlay') as mapboxgl.GeoJSONSource)?.setData(data)
    }
    if (map.isStyleLoaded()) apply()
    else map.once('load', apply)
  }, [corridorPoints, overlayHour])

  // Route line click -> select route.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !plan) return
    const handler = (e: mapboxgl.MapMouseEvent) => {
      const feature = e.features?.[0]
      const routeId = feature?.properties?.route_id as string | undefined
      if (routeId) onSelectRef.current(routeId)
    }
    map.on('click', 'route-lines', handler)
    return () => {
      map.off('click', 'route-lines', handler)
    }
  }, [plan])

  if (!MAPBOX_TOKEN) {
    return (
      <div className="panel flex h-full items-center justify-center p-6 text-center text-sm text-[var(--muted)]">
        Map unavailable: set <code>VITE_MAPBOX_TOKEN</code> in <code>frontend/.env</code> to display routes.
        Route data is still available in the panel.
      </div>
    )
  }

  return (
    <div className="relative h-full w-full overflow-hidden rounded-[9px] border border-[#d3dddf] bg-[#e8edef]">
      <div ref={containerRef} className="h-full w-full" />

      {/* Empty-state overlay — shown before the first route plan is loaded */}
      {!plan && (
        <div className="pointer-events-none absolute left-4 top-4 max-w-[285px] border-l-2 border-[var(--brand)] bg-white/95 px-3 py-2.5 sm:left-5 sm:top-5">
          <p className="text-[12px] font-semibold text-[var(--ink)]">Route intelligence</p>
          <p className="mt-0.5 text-[11px] leading-relaxed text-[var(--muted)]">Plan a trip to view route options, checkpoints, and forecast risk.</p>
        </div>
      )}

      {/* Floating pill shown while the weather corridor is loading */}
      {corridorLoading && (
        <div role="status" className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full border border-[#dce4e6] bg-white/95 px-3.5 py-2 text-xs font-semibold text-[#46545f] shadow-lg backdrop-blur-sm">
          <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-[var(--brand)]" />Loading weather overlay…
        </div>
      )}
    </div>
  )
}
