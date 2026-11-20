import test from 'node:test'
import assert from 'node:assert/strict'
import { checkpointForecast, selectedForecastAt, selectedForecastTime } from './forecastSelection.mjs'

const departure = '2026-11-20T12:00:00Z'
const point = {
  latitude: 32,
  longitude: -97,
  cumulative_distance_miles: 0,
  hours: [
    { offset_hours: 0, arrival_utc: departure, risk_level: 'low', wind_mph: 10 },
    { offset_hours: 24, arrival_utc: '2026-11-21T12:00:00Z', risk_level: 'high', wind_mph: 40 },
    { offset_hours: 48, arrival_utc: '2026-11-22T12:00:00Z', risk_level: 'severe', wind_mph: 55 },
  ],
}

test('selected forecast time advances from departure by the chosen offset', () => {
  assert.equal(selectedForecastTime(departure, 0).toISOString(), '2026-11-20T12:00:00.000Z')
  assert.equal(selectedForecastTime(departure, 24).toISOString(), '2026-11-21T12:00:00.000Z')
  assert.equal(selectedForecastTime(departure, 48).toISOString(), '2026-11-22T12:00:00.000Z')
})

test('selected offset chooses weather and risk for the map', () => {
  assert.equal(selectedForecastAt(point, 0).wind_mph, 10)
  assert.equal(selectedForecastAt(point, 24).wind_mph, 40)
  assert.equal(selectedForecastAt(point, 48).risk_level, 'severe')
})

test('checkpoint forecast uses its matching coordinate and selected hour', () => {
  const checkpoint = { latitude: 32.00001, longitude: -97, }
  assert.equal(checkpointForecast(checkpoint, [point], 24).risk_level, 'high')
  assert.equal(checkpointForecast(checkpoint, [point], 48).risk_level, 'severe')
})

test('missing samples stay unavailable instead of reusing static checkpoint risk', () => {
  assert.equal(selectedForecastAt(point, 12), null)
  const missing = { ...point, hours: [{ offset_hours: 24, risk_level: 'unknown' }] }
  assert.equal(checkpointForecast({ latitude: 32, longitude: -97 }, [missing], 24), null)
})

test('repeated backward and forward selections return the matching sample each time', () => {
  const sequence = [48, 0, 24, 48, 0]
  assert.deepEqual(sequence.map((hour) => selectedForecastAt(point, hour)?.risk_level),
    ['severe', 'low', 'high', 'severe', 'low'])
})
