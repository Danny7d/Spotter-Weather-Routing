import { test } from 'node:test'
import assert from 'node:assert/strict'
import { toNaiveLocalDateTime } from './departureDateTime.ts'

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

test('origin-local date fields do not depend on the browser timezone', () => {
  const originalTimezone = process.env.TZ
  try {
    // Apia skipped this entire local calendar date. It is still a valid
    // origin-local date for locations that did not skip it.
    process.env.TZ = 'Pacific/Apia'
    assert.equal(toNaiveLocalDateTime('2011-12-30', '7', '00', 'AM'), '2011-12-30T07:00')
  } finally {
    if (originalTimezone === undefined) delete process.env.TZ
    else process.env.TZ = originalTimezone
  }
})
