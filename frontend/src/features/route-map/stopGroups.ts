import type { Stop, StopKind } from '../../api/types'

/** Stops within this many miles of each other share one marker. */
const SAME_SPOT_MILES = 0.5

export type MarkerKind = 'current' | 'pickup' | 'dropoff' | 'stop'

export interface StopGroup {
  key: string
  kind: MarkerKind
  /** The kind that sets the marker's colour and icon when kind is 'stop'. */
  mainKind: StopKind
  lat: number
  lon: number
  mile: number
  /** Indexes into plan.stops, in time order. */
  stops: number[]
}

// When several stops share a marker, the most significant one sets its look.
const PRIORITY: StopKind[] = ['dropoff', 'pickup', 'restart', 'rest', 'fuel', 'break', 'pre_trip']

/** The kind that should represent several stops shown as one mark. */
export function mostSignificant(kinds: StopKind[]): StopKind {
  return PRIORITY.find((kind) => kinds.includes(kind)) ?? kinds[0]
}

/** One marker per spot: a 10-hour rest and the next pre-trip become a single marker. */
export function groupStops(stops: Stop[]): StopGroup[] {
  const groups: StopGroup[] = []
  stops.forEach((stop, index) => {
    const last = groups[groups.length - 1]
    if (last && Math.abs(stop.mile - last.mile) <= SAME_SPOT_MILES) {
      last.stops.push(index)
      return
    }
    groups.push({
      key: `${stop.mile}-${index}`,
      kind: 'stop',
      mainKind: stop.kind,
      lat: stop.lat,
      lon: stop.lon,
      mile: stop.mile,
      stops: [index],
    })
  })

  for (const group of groups) {
    const kinds = group.stops.map((i) => stops[i].kind)
    group.mainKind = mostSignificant(kinds)
    if (kinds.includes('dropoff')) group.kind = 'dropoff'
    else if (kinds.includes('pickup')) group.kind = 'pickup'
    else if (group.mile <= SAME_SPOT_MILES) group.kind = 'current' // where the truck is now
  }
  return groups
}

/** The group that holds a stop, for selecting a marker from the stop list. */
export function groupOf(groups: StopGroup[], stopIndex: number): StopGroup | undefined {
  return groups.find((group) => group.stops.includes(stopIndex))
}
