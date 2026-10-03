import { describe, expect, it } from 'vitest'

import { initialSelection, selectedStopFor, selectionReducer, stepStop } from './selection'

const planA = { id: 'a' }
const planB = { id: 'b' }

describe('stepStop', () => {
  it('moves one stop and stays inside the list', () => {
    expect(stepStop(2, 1, 5)).toBe(3)
    expect(stepStop(2, -1, 5)).toBe(1)
    expect(stepStop(4, 1, 5)).toBe(4)
    expect(stepStop(0, -1, 5)).toBe(0)
  })

  it('starts at the first stop going down, the last going up', () => {
    expect(stepStop(null, 1, 5)).toBe(0)
    expect(stepStop(null, -1, 5)).toBe(4)
  })

  it('selects nothing in an empty list', () => {
    expect(stepStop(null, 1, 0)).toBeNull()
  })
})

describe('selectionReducer', () => {
  it('selects a stop', () => {
    const state = selectionReducer(initialSelection, { type: 'select', planKey: planA, stop: 3 })

    expect(selectedStopFor(state, planA)).toBe(3)
  })

  it('counts every selection, even of the stop already selected', () => {
    const first = selectionReducer(initialSelection, { type: 'select', planKey: planA, stop: 3 })
    const again = selectionReducer(first, { type: 'select', planKey: planA, stop: 3 })

    expect(again.stop).toBe(3)
    expect([first.request, again.request]).toEqual([1, 2])
  })

  it('centring selects the stop and counts a new request', () => {
    const first = selectionReducer(initialSelection, { type: 'centre', planKey: planA, stop: 2 })
    const second = selectionReducer(first, { type: 'centre', planKey: planA, stop: 2 })

    expect(first.stop).toBe(2)
    expect([first.centreRequest, second.centreRequest]).toEqual([1, 2])
    expect(second.request).toBe(2)
  })

  it('remembers which centre request the map carried out', () => {
    let state = selectionReducer(initialSelection, { type: 'centre', planKey: planA, stop: 2 })
    expect(state.centreRequest).not.toBe(state.centred) // still to do, e.g. before the map has loaded

    state = selectionReducer(state, { type: 'centred', request: state.centreRequest })
    expect(state.centred).toBe(state.centreRequest)
    expect(selectionReducer(state, { type: 'centred', request: state.centred })).toBe(state)
  })

  it('a new plan starts with nothing selected', () => {
    const state = selectionReducer(initialSelection, { type: 'select', planKey: planA, stop: 3 })

    expect(selectedStopFor(state, planB)).toBeNull()
  })

  it('selecting in a new plan replaces the old plan and index', () => {
    let state = selectionReducer(initialSelection, { type: 'select', planKey: planA, stop: 6 })
    state = selectionReducer(state, { type: 'select', planKey: planB, stop: 1 })

    expect(state).toMatchObject({ planKey: planB, stop: 1 })
    expect(selectedStopFor(state, planA)).toBeNull()
  })

  it('keeps counting requests across plans', () => {
    let state = selectionReducer(initialSelection, { type: 'centre', planKey: planA, stop: 1 })
    state = selectionReducer(state, { type: 'centred', request: 1 })
    state = selectionReducer(state, { type: 'centre', planKey: planB, stop: 0 })

    expect(state).toMatchObject({ request: 2, centreRequest: 2, centred: 1 })
  })
})
