import { describe, expect, it } from 'vitest'

import type { TripPlan } from '../api/types'
import restart from '../fixtures/plan-restart.json'
import { clusterByPosition, parseInstant, timeScale } from './timeScale'

describe('parseInstant', () => {
  it('reads the offset the API sends', () => {
    expect(parseInstant('2026-10-05T07:00-05:00')).toEqual({
      utcMs: Date.UTC(2026, 9, 5, 12, 0),
      offsetMin: -300,
    })
    expect(parseInstant('2026-10-05T07:00+05:30').offsetMin).toBe(330)
    expect(parseInstant('2026-10-05T07:00:00Z').offsetMin).toBe(0)
  })

  it('rejects a time without an offset', () => {
    expect(() => parseInstant('2026-10-05T07:00')).toThrow('offset')
  })
})

describe('timeScale', () => {
  it('positions times by elapsed time, not by miles', () => {
    // A 10-hour trip: 07:00 to 17:00.
    const scale = timeScale('2026-10-05T07:00-05:00', '2026-10-05T17:00-05:00')

    expect(scale.at('2026-10-05T07:00-05:00')).toBe(0)
    expect(scale.at('2026-10-05T09:30-05:00')).toBeCloseTo(0.25)
    expect(scale.at('2026-10-05T17:00-05:00')).toBe(1)
  })

  it('clamps times outside the trip', () => {
    const scale = timeScale('2026-10-05T07:00-05:00', '2026-10-05T17:00-05:00')

    expect(scale.at('2026-10-05T06:00-05:00')).toBe(0)
    expect(scale.at('2026-10-06T06:00-05:00')).toBe(1)
  })

  it('marks each midnight in the trip offset, with weekday labels', () => {
    // Mon 07:00 to Wed 07:00: 48 hours, midnights at 17/48 and 41/48.
    const scale = timeScale('2026-10-05T07:00-05:00', '2026-10-07T07:00-05:00')

    expect(scale.days.map((d) => d.label)).toEqual(['Mon', 'Tue', 'Wed'])
    expect(scale.days.map((d) => d.date)).toEqual(['2026-10-05', '2026-10-06', '2026-10-07'])
    expect(scale.days[1].position).toBeCloseTo(17 / 48)
    expect(scale.days[2].position).toBeCloseTo(41 / 48)
  })

  it('uses the trip offset for midnight, not the viewer’s time zone', () => {
    // 23:00 at UTC-07:00 is already the next day in UTC; the first midnight is 1 h in.
    const scale = timeScale('2026-10-05T23:00-07:00', '2026-10-06T03:00-07:00')

    expect(scale.days.map((d) => d.label)).toEqual(['Mon', 'Tue'])
    expect(scale.days[1].position).toBeCloseTo(1 / 4)
  })

  it('adds no separator when the trip ends exactly at midnight', () => {
    const scale = timeScale('2026-10-05T20:00-05:00', '2026-10-06T00:00-05:00')

    expect(scale.days.map((d) => d.label)).toEqual(['Mon'])
  })

  it('makes the 34-hour restart a visibly long segment on a real plan', () => {
    const plan = restart as TripPlan
    const scale = timeScale(plan.summary.start, plan.summary.end)
    const width = (kind: string) => {
      const stop = plan.stops.find((s) => s.kind === kind)!
      return scale.at(stop.end) - scale.at(stop.start)
    }

    expect(width('restart')).toBeCloseTo(34 / (plan.summary.elapsed_min / 60), 3)
    expect(width('restart')).toBeGreaterThan(width('rest') * 3)
    expect(width('rest')).toBeGreaterThan(width('fuel') * 15)
    expect(scale.days).toHaveLength(plan.logs.length)
  })
})

describe('clusterByPosition', () => {
  it('merges points closer than the gap and keeps the rest apart', () => {
    const points = [0, 0.004, 0.3, 0.31, 0.5].map((position, value) => ({ position, value }))

    expect(clusterByPosition(points, 0.012)).toEqual([
      { position: 0, values: [0, 1] },
      { position: 0.3, values: [2, 3] },
      { position: 0.5, values: [4] },
    ])
  })

  it('handles no points', () => {
    expect(clusterByPosition([], 0.01)).toEqual([])
  })
})
