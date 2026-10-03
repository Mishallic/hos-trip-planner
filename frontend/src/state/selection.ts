import { useCallback, useMemo, useReducer } from 'react'

// One selected stop, shared by the map, the timeline strip, the stop list and the
// driver's clocks. Stops are identified by their index in plan.stops.

export interface SelectionState {
  /** The plan the selection belongs to. A new plan starts with nothing selected. */
  planKey: unknown
  stop: number | null
  /**
   * Bumped by every explicit selection, even of the stop already selected, so the
   * views can bring it back into sight: reopen a closed popup, scroll to the row.
   */
  request: number
  /** Bumped by every "centre the map on this stop" request. */
  centreRequest: number
  /**
   * The last centre request the map carried out. Kept here rather than in the map,
   * so a request made before the map has loaded is still carried out when it does.
   */
  centred: number
}

export type SelectionAction =
  | { type: 'select'; planKey: unknown; stop: number }
  | { type: 'centre'; planKey: unknown; stop: number }
  | { type: 'centred'; request: number }

export const initialSelection: SelectionState = {
  planKey: null,
  stop: null,
  request: 0,
  centreRequest: 0,
  centred: 0,
}

/** The next stop up or down the list, staying inside it. From nothing: first or last. */
export function stepStop(stop: number | null, by: 1 | -1, count: number): number | null {
  if (count <= 0) return null
  if (stop === null) return by > 0 ? 0 : count - 1
  return Math.min(count - 1, Math.max(0, stop + by))
}

export function selectionReducer(state: SelectionState, action: SelectionAction): SelectionState {
  if (action.type === 'centred') {
    return action.request === state.centred ? state : { ...state, centred: action.request }
  }
  // A different plan: drop the old selection, but keep counting requests so a
  // request for the new plan is never mistaken for one already handled.
  const current = action.planKey === state.planKey ? state : { ...state, planKey: action.planKey, stop: null }
  switch (action.type) {
    case 'select':
      return { ...current, stop: action.stop, request: current.request + 1 }
    case 'centre':
      return {
        ...current,
        stop: action.stop,
        request: current.request + 1,
        centreRequest: current.centreRequest + 1,
      }
  }
}

/** The selected stop for the plan on screen; null if the selection was for another plan. */
export function selectedStopFor(state: SelectionState, planKey: unknown): number | null {
  return state.planKey === planKey ? state.stop : null
}

export interface StopSelection {
  selected: number | null
  /** Changes with every explicit selection, including a repeat of the current one. */
  request: number
  select: (stop: number) => void
  /** Select a stop and centre the map on it. */
  centre: (stop: number) => void
  centreRequest: number
  /** The last centre request carried out; the map reports it with markCentred. */
  centred: number
  markCentred: (request: number) => void
}

export function useStopSelection(plan: { stops: unknown[] } | undefined): StopSelection {
  const [state, dispatch] = useReducer(selectionReducer, initialSelection)
  const select = useCallback((stop: number) => dispatch({ type: 'select', planKey: plan, stop }), [plan])
  const centre = useCallback((stop: number) => dispatch({ type: 'centre', planKey: plan, stop }), [plan])
  const markCentred = useCallback((request: number) => dispatch({ type: 'centred', request }), [])
  const selected = selectedStopFor(state, plan)
  const { request, centreRequest, centred } = state
  return useMemo(
    () => ({ selected, request, select, centre, centreRequest, centred, markCentred }),
    [selected, request, select, centre, centreRequest, centred, markCentred],
  )
}
