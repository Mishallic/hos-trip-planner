import { describe, expect, it } from 'vitest'

import type { Stop, TripPlan } from '../../api/types'
import multiDay from '../../fixtures/plan-multi-day.json'
import restart from '../../fixtures/plan-restart.json'
import { declutter, groupOf, groupStops, type StopGroup } from './stopGroups'

const kinds = (plan: TripPlan) =>
  groupStops(plan.stops).map((g) => [g.kind, g.stops.map((i) => plan.stops[i].kind).join('+')])

describe('groupStops', () => {
  it('merges a rest with the pre-trip that follows it', () => {
    expect(kinds(multiDay as TripPlan)).toEqual([
      ['current', 'pre_trip'],
      ['pickup', 'pickup'],
      ['stop', 'rest+pre_trip'],
      ['stop', 'fuel'],
      ['stop', 'rest+pre_trip'],
      ['dropoff', 'dropoff'],
    ])
  })

  it('merges fuel before a rest, and a restart, into single markers', () => {
    expect(kinds(restart as TripPlan)).toEqual([
      ['current', 'pre_trip'],
      ['pickup', 'pickup'],
      ['stop', 'restart+pre_trip'],
      ['stop', 'fuel'],
      ['stop', 'rest+pre_trip'],
      ['stop', 'break'],
      ['stop', 'fuel+rest+pre_trip'],
      ['dropoff', 'dropoff'],
    ])
  })

  it('colours a shared marker by its most significant stop', () => {
    const groups = groupStops((restart as TripPlan).stops)

    expect(groups.map((g) => g.mainKind)).toEqual([
      'pre_trip',
      'pickup',
      'restart',
      'fuel',
      'rest',
      'break',
      'rest',
      'dropoff',
    ])
  })

  it('a trip starting at the pickup shows the pickup pin there', () => {
    const at = (kind: Stop['kind'], mile: number) => ({ kind, mile, lat: 0, lon: 0 }) as Stop
    const groups = groupStops([at('pre_trip', 0), at('pickup', 0), at('dropoff', 300)])

    expect(groups.map((g) => g.kind)).toEqual(['pickup', 'dropoff'])
  })

  it('finds the marker for a stop', () => {
    const groups = groupStops((multiDay as TripPlan).stops)

    expect(groupOf(groups, 3)?.stops).toEqual([2, 3])
  })
})

describe('declutter', () => {
  // The restart trip's markers laid out in a row, 10 px apart: everything overlaps.
  const groups = groupStops((restart as TripPlan).stops)
  const inRow = (gap: number) => (group: StopGroup) => ({ x: groups.indexOf(group) * gap, y: 0 })
  const keys = (shown: { group: StopGroup }[]) => shown.map((m) => m.group.kind + ':' + m.group.mainKind)

  it('shows every marker when none are close', () => {
    expect(declutter(groups, inRow(100), 30)).toHaveLength(groups.length)
  })

  it('keeps the start, pickup and drop-off and hides stops close to a shown marker', () => {
    const shown = declutter(groups, inRow(10), 30)

    expect(keys(shown)).toContain('current:pre_trip')
    expect(keys(shown)).toContain('pickup:pickup')
    expect(keys(shown)).toContain('dropoff:dropoff')
    const hidden = shown.reduce((n, m) => n + m.hidden.length, 0)
    expect(shown.length + hidden).toBe(groups.length) // nothing lost: each stop hides under one marker
    expect(hidden).toBeGreaterThan(0)
  })

  it('puts the more significant stop on top: a restart before a break', () => {
    const restartGroup = groups.find((g) => g.mainKind === 'restart')!
    const breakGroup = groups.find((g) => g.mainKind === 'break')!
    const together = () => ({ x: 0, y: 0 })

    const shown = declutter([breakGroup, restartGroup], together, 30)

    expect(shown.map((m) => m.group)).toEqual([restartGroup])
    expect(shown[0].hidden).toEqual([breakGroup])
  })

  it('always shows the selected stop', () => {
    const breakGroup = groups.find((g) => g.mainKind === 'break')!

    const shown = declutter(groups, () => ({ x: 0, y: 0 }), 30, breakGroup.key)

    expect(shown.map((m) => m.group)).toContain(breakGroup)
  })
})
