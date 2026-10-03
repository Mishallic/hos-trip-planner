// Positions on a strip scaled by TIME, and the day boundaries of the trip.
//
// The API sends every time as an ISO string with the home terminal's offset,
// fixed for the whole trip (D17), e.g. "2026-10-05T07:00-05:00". Days on the
// strip therefore start at the same midnights as the log sheets.

const MINUTE = 60_000
const DAY = 24 * 60 * MINUTE

export interface Instant {
  utcMs: number
  offsetMin: number
}

/** Parse the API's ISO time: date, hours and minutes (seconds optional), and an offset. */
export function parseInstant(iso: string): Instant {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/.exec(iso)
  if (!match) throw new Error(`not an ISO time with an offset: ${iso}`)
  const [, year, month, day, hour, minute, zone] = match
  const offsetMin =
    zone === 'Z' ? 0 : (zone[0] === '-' ? -1 : 1) * (Number(zone.slice(1, 3)) * 60 + Number(zone.slice(4, 6)))
  const wallClockMs = Date.UTC(+year, +month - 1, +day, +hour, +minute)
  return { utcMs: wallClockMs - offsetMin * MINUTE, offsetMin }
}

export interface DayMark {
  /** 0..1 along the strip. The first day starts at 0. */
  position: number
  /** "Mon" */
  label: string
  /** "2026-10-05" */
  date: string
}

export interface TimeScale {
  /** 0..1 position of a time between the trip's start and end, clamped. */
  at(iso: string): number
  /** The day the trip starts, then one mark per midnight before the trip ends. */
  days: DayMark[]
}

export function timeScale(startIso: string, endIso: string): TimeScale {
  const start = parseInstant(startIso)
  const end = parseInstant(endIso)
  const span = Math.max(1, end.utcMs - start.utcMs)
  const toPosition = (utcMs: number) => Math.min(1, Math.max(0, (utcMs - start.utcMs) / span))

  // Midnights in the trip's own offset, the same one the log sheets use.
  const offsetMs = start.offsetMin * MINUTE
  const startWallClock = start.utcMs + offsetMs
  const days: DayMark[] = [{ position: 0, label: weekday(startWallClock), date: isoDate(startWallClock) }]
  for (let midnight = Math.floor(startWallClock / DAY) * DAY + DAY; midnight - offsetMs < end.utcMs; midnight += DAY) {
    days.push({ position: toPosition(midnight - offsetMs), label: weekday(midnight), date: isoDate(midnight) })
  }

  return { at: (iso) => toPosition(parseInstant(iso).utcMs), days }
}

export interface Cluster<T> {
  position: number
  values: T[]
}

/**
 * Merge points closer than `minGap` (0..1) into one, so dots never overlap.
 * Input must be in position order; each cluster sits at its first point.
 */
export function clusterByPosition<T>(points: { position: number; value: T }[], minGap: number): Cluster<T>[] {
  const clusters: Cluster<T>[] = []
  for (const point of points) {
    const last = clusters[clusters.length - 1]
    if (last && point.position - last.position < minGap) last.values.push(point.value)
    else clusters.push({ position: point.position, values: [point.value] })
  }
  return clusters
}

function weekday(wallClockMs: number): string {
  return new Date(wallClockMs).toLocaleDateString('en-US', { weekday: 'short', timeZone: 'UTC' })
}

function isoDate(wallClockMs: number): string {
  return new Date(wallClockMs).toISOString().slice(0, 10)
}
