// Turn-by-turn directions with the planned stops slotted in where they happen.
// Steps come per leg from the router; stops carry the mile they happen at.

import type { RouteLeg, RouteStep, Stop } from '../../api/types'

export type DirectionRow =
  | { kind: 'step'; step: RouteStep; index: number; mile: number }
  | { kind: 'stop'; stop: Stop; index: number }

export interface LegDirections {
  leg: RouteLeg
  /** Miles along the whole trip where the leg starts. */
  startMile: number
  rows: DirectionRow[]
}

/**
 * Each leg's steps in order, with every stop that falls on the leg placed before the
 * first step that starts past it. A stop at a leg's end (the pickup) follows that
 * leg's arrival; the stops before any driving open the first leg.
 */
export function directionRows(legs: RouteLeg[], stops: Stop[]): LegDirections[] {
  let startMile = 0
  let next = 0 // the next stop to place, in time order
  return legs.map((leg, legIndex) => {
    const endMile = startMile + leg.miles
    const last = legIndex === legs.length - 1
    const rows: DirectionRow[] = []
    let mile = startMile
    // Step distances are rounded: scale them so the leg's steps end exactly at its end.
    const stepped = leg.steps.reduce((sum, step) => sum + step.miles, 0)
    const scale = stepped > 0 ? leg.miles / stepped : 1
    const placeStopsBefore = (limit: number, inclusive: boolean) => {
      while (next < stops.length && (inclusive ? stops[next].mile <= limit + 1e-6 : stops[next].mile < limit - 1e-6)) {
        rows.push({ kind: 'stop', stop: stops[next], index: next })
        next++
      }
    }
    leg.steps.forEach((step, index) => {
      // The leg's closing "arrive" step comes before what happens on arrival.
      // Anything that happens on the road before the end still goes before it.
      const arrival = index === leg.steps.length - 1 && step.miles === 0
      if (arrival) placeStopsBefore(endMile, false)
      else placeStopsBefore(mile, true)
      rows.push({ kind: 'step', step, index, mile })
      mile += step.miles * scale
    })
    // What is left on this leg: everything up to its end, and on the last leg, all.
    placeStopsBefore(last ? Infinity : endMile, true)
    const result = { leg, startMile, rows }
    startMile = endMile
    return result
  })
}
