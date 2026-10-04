import { describe, expect, it } from 'vitest'

import { SAMPLE_TRIPS, sampleStart } from './samples'

describe('sampleStart', () => {
  it('is tomorrow at 07:00, whatever the time now', () => {
    expect(sampleStart(new Date(2026, 9, 4, 23, 30))).toBe('2026-10-05T07:00')
    expect(sampleStart(new Date(2026, 9, 4, 0, 5))).toBe('2026-10-05T07:00')
  })

  it('rolls over the month and the year', () => {
    expect(sampleStart(new Date(2026, 9, 31, 12, 0))).toBe('2026-11-01T07:00')
    expect(sampleStart(new Date(2026, 11, 31, 12, 0))).toBe('2027-01-01T07:00')
  })
})

describe('sample trips', () => {
  it('are picked places, so they plan without a search', () => {
    for (const { form } of SAMPLE_TRIPS) {
      for (const place of [form.current, form.pickup, form.dropoff]) expect(place.lat).toBeTypeOf('number')
    }
  })
})
