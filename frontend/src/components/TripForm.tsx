import { useEffect, useRef, useState } from 'react'
import { geocode } from '../api/client'
import type { GeocodeResult } from '../types'
import { toNaiveLocalDateTime, type Meridiem } from './departureDateTime'

interface PlaceFieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  placeholder: string
}

function PlaceField({ label, value, onChange, placeholder }: PlaceFieldProps) {
  const [suggestions, setSuggestions] = useState<GeocodeResult[]>([])
  const [open, setOpen] = useState(false)
  const [activeSuggestion, setActiveSuggestion] = useState(0)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Sequence counter to discard stale geocoding responses.
  const requestSeqRef = useRef(0)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (value.trim().length < 3) {
      setSuggestions([])
      setOpen(false)
      return
    }
    const currentSeq = ++requestSeqRef.current
    debounceRef.current = setTimeout(async () => {
      try {
        const { results } = await geocode(value.trim())
        if (requestSeqRef.current !== currentSeq) return
        setSuggestions(results.slice(0, 5))
        setOpen(results.length > 0)
      } catch {
        if (requestSeqRef.current !== currentSeq) return
        setSuggestions([])
        setOpen(false)
      }
    }, 350)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [value])

  return (
    <div className="relative">
      <label className="mb-1.5 block text-[12px] font-medium text-[var(--ink)]">{label}</label>
      <input
        role="combobox"
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => suggestions.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        aria-expanded={open && suggestions.length > 0}
        aria-autocomplete="list"
        aria-controls={open ? `${label.toLowerCase()}-suggestions` : undefined}
        aria-activedescendant={open && suggestions[activeSuggestion] ? `${label.toLowerCase()}-option-${activeSuggestion}` : undefined}
        onKeyDown={(event) => {
          if (!open || suggestions.length === 0) return
          if (event.key === 'ArrowDown') {
            event.preventDefault()
            setActiveSuggestion((index) => (index + 1) % suggestions.length)
          } else if (event.key === 'ArrowUp') {
            event.preventDefault()
            setActiveSuggestion((index) => (index - 1 + suggestions.length) % suggestions.length)
          } else if (event.key === 'Enter' && suggestions[activeSuggestion]) {
            event.preventDefault()
            onChange(suggestions[activeSuggestion].display_name)
            setOpen(false)
          } else if (event.key === 'Escape') {
            setOpen(false)
          }
        }}
        placeholder={placeholder}
        className="field-control w-full px-3 text-sm"
        autoComplete="off"
      />
      {open && suggestions.length > 0 && (
        <div id={`${label.toLowerCase()}-suggestions`} role="listbox" className="absolute z-40 mt-1.5 w-full overflow-hidden rounded-[10px] border border-[var(--line)] bg-white py-1 shadow-[0_10px_28px_rgb(23_33_43/14%)]">
          {suggestions.map((suggestion, index) => (
              <button
                key={suggestion.place_id}
                id={`${label.toLowerCase()}-option-${index}`}
                type="button"
                role="option"
                aria-selected={index === activeSuggestion}
                className={`w-full px-3 py-2 text-left text-sm leading-snug text-[var(--ink)] transition-colors hover:bg-[#f1f6f5] focus:bg-[#f1f6f5] focus:outline-none ${index === activeSuggestion ? 'bg-[#f1f6f5]' : ''}`}
                onMouseDown={() => {
                  onChange(suggestion.display_name)
                  setOpen(false)
                }}
              >
                {suggestion.display_name}
              </button>
          ))}
        </div>
      )}
    </div>
  )
}

// Small section label used to visually group related fields.
function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="mb-2 text-[13px] font-semibold tracking-[-0.01em] text-[var(--ink)]">{children}</p>
  )
}

export interface TripFormValues {
  origin: string
  destination: string
  departureLocal: string
  loadWeightLbs: number
  intervalMiles: number
}

interface TripFormProps {
  onSubmit: (values: TripFormValues) => void
  loading: boolean
  serverError: string | null
}

export function TripForm({ onSubmit, loading, serverError }: TripFormProps) {
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [departureDate, setDepartureDate] = useState('')
  const [departureHour, setDepartureHour] = useState('')
  const [departureMinute, setDepartureMinute] = useState('00')
  const [departureMeridiem, setDepartureMeridiem] = useState<Meridiem>('AM')
  const [loadWeight, setLoadWeight] = useState('40000')
  const [interval, setInterval] = useState('25')
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!origin.trim() || !destination.trim()) {
      setError('Origin and destination are required.')
      return
    }
    const departureLocal = toNaiveLocalDateTime(
      departureDate,
      departureHour,
      departureMinute,
      departureMeridiem,
    )
    if (!departureLocal) {
      setError('Departure date and time are required.')
      return
    }
    const load = Number(loadWeight)
    if (!Number.isFinite(load) || load < 0 || load > 200000) {
      setError('Load weight must be between 0 and 200,000 lb.')
      return
    }
    setError(null)
    onSubmit({
      origin: origin.trim(),
      destination: destination.trim(),
      departureLocal,
      loadWeightLbs: Math.round(load),
      intervalMiles: Number(interval),
    })
  }

  // Shared input class — defined once so all fields look identical.
  const inputClass = 'field-control w-full px-3 text-sm'

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* ROUTE section */}
      <div>
        <SectionLabel>Route</SectionLabel>
        <div className="space-y-3">
          <PlaceField
            label="Origin"
            value={origin}
            onChange={setOrigin}
            placeholder="e.g. Dallas, TX"
          />
          <PlaceField
            label="Destination"
            value={destination}
            onChange={setDestination}
            placeholder="e.g. Austin, TX"
          />
        </div>
      </div>

      {/* SCHEDULE section */}
      <div>
        <SectionLabel>Schedule</SectionLabel>
        <div>
          <label className="mb-1.5 block text-[12px] font-medium text-[var(--ink)]">
            Departure date &amp; time
            <span className="ml-1 font-normal text-[var(--muted)]">(origin time)</span>
          </label>
          {/*
            Departure compound field: date + hour + minute + AM/PM grouped visually
            inside a shared container so they read as one input, not four.
          */}
          <div className="rounded-[8px] border border-[#dfe6e9] bg-[#f7f9fa] p-1.5">
            <div className="grid grid-cols-3 gap-2">
              <input
                aria-label="Departure date"
                type="date"
                value={departureDate}
                onChange={(e) => setDepartureDate(e.target.value)}
                className={`col-span-3 min-w-0 ${inputClass}`}
              />
              <input
                aria-label="Departure hour"
                type="number"
                min={1}
                max={12}
                step={1}
                inputMode="numeric"
                placeholder="Hour"
                value={departureHour}
                onChange={(e) => setDepartureHour(e.target.value)}
                className={`min-w-0 ${inputClass}`}
              />
              <input
                aria-label="Departure minutes"
                type="number"
                min={0}
                max={59}
                step={1}
                inputMode="numeric"
                placeholder="Min"
                value={departureMinute}
                onChange={(e) => setDepartureMinute(e.target.value)}
                className={`min-w-0 ${inputClass}`}
              />
              <select
                aria-label="AM or PM"
                value={departureMeridiem}
                onChange={(e) => setDepartureMeridiem(e.target.value as Meridiem)}
                className={`min-w-0 px-2 ${inputClass}`}
              >
                <option value="AM">AM</option>
                <option value="PM">PM</option>
              </select>
            </div>
          </div>
          <p className="mt-1.5 text-[11px] leading-relaxed text-[var(--muted)]">Departure uses the origin city’s timezone.</p>
        </div>
      </div>

      {/* LOAD section */}
      <div>
        <SectionLabel>Load</SectionLabel>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1.5 block text-[12px] font-medium text-[var(--ink)]">Weight (lb)</label>
            <input
              type="number"
              min={0}
              max={200000}
              step={100}
              value={loadWeight}
              onChange={(e) => setLoadWeight(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className="mb-1.5 block text-[12px] font-medium text-[var(--ink)]">Checkpoint interval</label>
            <select
              value={interval}
              onChange={(e) => setInterval(e.target.value)}
              className={inputClass}
            >
              <option value="10">Every 10 mi</option>
              <option value="25">Every 25 mi</option>
              <option value="50">Every 50 mi</option>
            </select>
          </div>
        </div>
      </div>

      {/* Validation error — styled prominently with an icon */}
      {(error || serverError) && (
        <div role="alert" className="flex items-start gap-2 rounded-[9px] border border-red-200 bg-red-50 p-2.5 text-sm text-red-800">
          <span className="mt-0.5 shrink-0">⚠</span>
          <span>{error ?? serverError}</span>
        </div>
      )}

      <button
        type="submit"
        disabled={loading}
        className="button-primary w-full px-4 text-sm font-semibold"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2"><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/35 border-t-white" aria-hidden="true" />Planning route…</span>
        ) : 'Plan route'}
      </button>
    </form>
  )
}
