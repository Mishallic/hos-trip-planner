import { describe, expect, it } from 'vitest'

import {
  emptyForm,
  formFromParams,
  paramsFromForm,
  requestFromForm,
  validateForm,
  viewFromParams,
  withView,
} from './urlState'

const picked = {
  ...emptyForm(),
  current: { label: 'Chicago, IL', lat: 41.87556, lon: -87.62442 },
  pickup: { label: 'Indianapolis, IN', lat: 39.76838, lon: -86.15804 },
  dropoff: { label: 'Denver' },
  cycleUsedHours: '20',
  startTime: '2026-10-05T07:00',
}

describe('url state', () => {
  it('round-trips a form through the URL', () => {
    const form = { ...picked, header: { ...picked.header, driver: 'J. Doe', truck: '1042' } }

    expect(formFromParams(paramsFromForm(form))).toEqual(form)
  })

  it('keeps the URL short and readable', () => {
    expect(paramsFromForm(picked).toString()).toBe(
      'from=Chicago%2C+IL&from_at=41.87556%2C-87.62442&pickup=Indianapolis%2C+IN' +
        '&pickup_at=39.76838%2C-86.15804&dropoff=Denver&cycle=20&start=2026-10-05T07%3A00',
    )
  })

  it('marks a start pinned from "now", and only when there is a start', () => {
    const pinned = { ...picked, startAuto: true }

    expect(paramsFromForm(pinned).get('now')).toBe('1')
    expect(formFromParams(paramsFromForm(pinned)).startAuto).toBe(true)
    expect(paramsFromForm({ ...pinned, startTime: '' }).has('now')).toBe(false)
    expect(formFromParams(new URLSearchParams('now=1')).startAuto).toBe(false)
  })

  it('ignores coordinates without a label', () => {
    const form = formFromParams(new URLSearchParams('from_at=41,-87'))

    expect(form.current).toEqual({ label: '' })
  })
})

describe('request', () => {
  it('sends picked places as coordinates and typed text as a query', () => {
    const request = requestFromForm(picked)

    expect(request?.current).toEqual({ label: 'Chicago, IL', lat: 41.87556, lon: -87.62442 })
    expect(request?.dropoff).toEqual({ query: 'Denver' })
    expect(request?.cycle_used_hours).toBe(20)
    expect(request?.start_time).toBe('2026-10-05T07:00')
    expect(request).not.toHaveProperty('home_tz')
  })

  it('is not ready until every place is filled in', () => {
    expect(requestFromForm({ ...picked, dropoff: { label: ' ' } })).toBeNull()
  })

  it('omits empty log header fields', () => {
    const form = { ...picked, header: { ...picked.header, carrier: '  ' } }

    expect(requestFromForm(form)).not.toHaveProperty('carrier')
  })
})

describe('validation', () => {
  it('requires places and a cycle between 0 and 70', () => {
    const errors = validateForm({ ...emptyForm(), cycleUsedHours: '71' })

    expect(errors).toEqual({
      current: 'Required',
      pickup: 'Required',
      dropoff: 'Required',
      cycle_used_hours: 'Between 0 and 70 hours',
    })
  })

  it('accepts a complete form', () => {
    expect(validateForm(picked)).toEqual({})
  })
})

describe('view', () => {
  it('is the plan unless the URL names logs or directions', () => {
    expect(viewFromParams(new URLSearchParams(''))).toBe('plan')
    expect(viewFromParams(new URLSearchParams('view=logs'))).toBe('logs')
    expect(viewFromParams(new URLSearchParams('view=directions'))).toBe('directions')
    expect(viewFromParams(new URLSearchParams('view=elsewhere'))).toBe('plan')
  })

  it('is written next to the trip, and left out for the plan', () => {
    const params = paramsFromForm(picked)

    expect(withView(params, 'logs').get('view')).toBe('logs')
    expect(withView(withView(params, 'logs'), 'plan').has('view')).toBe(false)
    expect(withView(params, 'logs').get('cycle')).toBe('20')
  })
})
