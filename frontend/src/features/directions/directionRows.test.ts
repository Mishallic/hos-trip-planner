import { describe, expect, it } from 'vitest'

import type { TripPlan } from '../../api/types'
import multiDay from '../../fixtures/plan-multi-day.json'
import restart from '../../fixtures/plan-restart.json'
import short from '../../fixtures/plan-short.json'
import { directionRows } from './directionRows'

const PLANS: [string, TripPlan][] = [
  ['short', short as unknown as TripPlan],
  ['multi-day', multiDay as unknown as TripPlan],
  ['restart', restart as unknown as TripPlan],
]

describe.each(PLANS)('directions for the %s plan', (_, plan) => {
  const legs = directionRows(plan.route.legs, plan.stops)
  const rows = legs.flatMap((leg) => leg.rows)

  it('lists every step of every leg once, in order', () => {
    legs.forEach((leg, i) => {
      const steps = leg.rows.filter((row) => row.kind === 'step').map((row) => row.index)
      expect(steps).toEqual(plan.route.legs[i].steps.map((_, j) => j))
    })
  })

  it('places every stop exactly once, in time order', () => {
    const stops = rows.filter((row) => row.kind === 'stop').map((row) => row.index)
    expect(stops).toEqual(plan.stops.map((_, i) => i))
  })

  it('puts the pickup at the end of the first leg and the drop-off last', () => {
    const lastOfFirst = legs[0].rows.at(-1)
    expect(lastOfFirst?.kind === 'stop' && lastOfFirst.stop.kind).toBe('pickup')
    const end = rows.at(-1)
    expect(end?.kind === 'stop' && end.stop.kind).toBe('dropoff')
  })

  it('never puts a stop after a step that starts beyond it', () => {
    let mile = 0
    for (const row of rows) {
      if (row.kind === 'step') mile = row.mile
      else expect(row.stop.mile).toBeGreaterThanOrEqual(mile - 1e-6)
    }
  })
})

it('puts a stop on the last stretch of road before the arrival', () => {
  const step = (instruction: string, miles: number) => ({ instruction, miles, lat: 0, lon: 0 })
  const leg = { to: 'pickup' as const, miles: 100, router_min: 100, planned_min: 110, steps: [step('Head east', 10), step('Take I-10', 90), step('Arrive at the pickup', 0)] }
  const stop = (kind: string, mile: number) => ({ kind, mile }) as unknown as TripPlan['stops'][number]
  const rows = directionRows([leg], [stop('break', 50), stop('pickup', 100)])[0].rows

  expect(rows.map((row) => (row.kind === 'step' ? row.step.instruction : row.stop.kind))).toEqual([
    'Head east', 'Take I-10', 'break', 'Arrive at the pickup', 'pickup',
  ])
})
