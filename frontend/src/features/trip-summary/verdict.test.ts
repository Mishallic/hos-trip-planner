import { describe, expect, it } from 'vitest'

import type { TripPlan } from '../../api/types'
import multiDay from '../../fixtures/plan-multi-day.json'
import restart from '../../fixtures/plan-restart.json'
import short from '../../fixtures/plan-short.json'
import { verdictFor } from './verdict'

const verdict = (plan: unknown) => verdictFor((plan as TripPlan).summary, (plan as TripPlan).stops)

describe('verdictFor', () => {
  it('says when the load is delivered and how many days it takes', () => {
    expect(verdict(multiDay)).toMatchObject({ text: 'Delivers Wed 05:24 · 3 days', tone: 'ok' })
  })

  it('names the home terminal zone with the delivery time when given', () => {
    const plan = multiDay as unknown as TripPlan
    expect(verdictFor(plan.summary, plan.stops, 'CDT').text).toBe('Delivers Wed 05:24 CDT · 3 days')
  })

  it('uses the singular for a one-day trip', () => {
    expect(verdict(short).text).toMatch(/ · 1 day$/)
  })

  it('names the restart and the time it adds', () => {
    expect(verdict(restart)).toMatchObject({ text: 'Needs 34-hr restart (+1.4 days)', tone: 'warn' })
  })

  it('counts the restarts when there is more than one', () => {
    const plan = restart as unknown as TripPlan
    const once = plan.stops.find((s) => s.kind === 'restart')!
    const twice = verdictFor(plan.summary, [...plan.stops, { ...once, start: '2026-10-09T05:00-07:00' }])

    expect(twice.text).toBe('Needs 2 × 34-hr restarts (+2.8 days)')
    expect(twice.detail).toMatch(/^The 70-hour cycle can't cover the whole trip, so the driver takes 2 restarts, 68 hours off in all\./)
  })

  it('times the trip to the drop-off arrival, not to the end of unloading', () => {
    // Mon 07:00 to the Wed 05:24 arrival; summary.elapsed (47:24) includes the hour of unloading.
    expect(verdict(multiDay).detail).toBe('23:24 of driving, 46:24 from start to drop-off.')
  })

  it('never says only "within limits"', () => {
    for (const plan of [short, multiDay, restart]) expect(verdict(plan).text).not.toMatch(/within/i)
  })
})
