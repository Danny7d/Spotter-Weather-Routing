import { test } from 'node:test'
import assert from 'node:assert/strict'
import { isFutureDeparture, toNaiveLocalDateTime } from './departureDateTime.ts'

test('converts AM and PM without ambiguity', () => {
  assert.equal(toNaiveLocalDateTime('2026-11-20', '5', '30', 'AM'), '2026-11-20T05:30')
  assert.equal(toNaiveLocalDateTime('2026-11-20', '5', '30', 'PM'), '2026-11-20T17:30')
})

test('converts midnight and noon correctly', () => {
  assert.equal(toNaiveLocalDateTime('2026-11-20', '12', '00', 'AM'), '2026-11-20T00:00')
  assert.equal(toNaiveLocalDateTime('2026-11-20', '12', '00', 'PM'), '2026-11-20T12:00')
})

test('rejects invalid fields and invalid calendar dates', () => {
  assert.equal(toNaiveLocalDateTime('2026-11-20', '13', '00', 'AM'), null)
  assert.equal(toNaiveLocalDateTime('2026-11-20', '5', '60', 'PM'), null)
  assert.equal(toNaiveLocalDateTime('2026-02-30', '5', '30', 'AM'), null)
  assert.equal(toNaiveLocalDateTime('', '5', '30', 'AM'), null)
})

test('departure validation accepts future dates and rejects present or past dates', () => {
  const now = new Date(2026, 10, 20, 10, 0)
  assert.equal(isFutureDeparture('2026-11-20T10:01', now), true)
  assert.equal(isFutureDeparture('2026-11-20T10:00', now), false)
  assert.equal(isFutureDeparture('2026-11-20T09:59', now), false)
})
