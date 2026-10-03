import { describe, expect, it } from 'vitest'

import type { Stop, TripPlan } from '../../api/types'
import multiDay from '../../fixtures/plan-multi-day.json'
import restart from '../../fixtures/plan-restart.json'
import { groupOf, groupStops } from './stopGroups'

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
