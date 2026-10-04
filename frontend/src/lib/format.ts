import type { StopKind, TripPlan } from '../api/types'

/** Minutes as h:mm, e.g. 660 -> "11:00". */
export function hm(minutes: number): string {
  const whole = Math.max(0, Math.round(minutes))
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`
}

/** The wall-clock time in an ISO string, kept in the trip's own offset: "Mon 07:30". */
export function clockTime(iso: string, withDay = true): string {
  const [date, rest] = iso.split('T')
  const time = rest.slice(0, 5)
  if (!withDay) return time
  const weekday = new Date(`${date}T12:00:00Z`).toLocaleDateString('en-US', {
    weekday: 'short',
    timeZone: 'UTC',
  })
  return `${weekday} ${time}`
}

/** "Fri 16 Oct 18:49": with the date, for trips long enough to repeat a weekday. */
export function clockDate(iso: string): string {
  const [date] = iso.split('T')
  const day = new Date(`${date}T12:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
  const [weekday, time] = clockTime(iso).split(' ')
  return `${weekday} ${day} ${time}`
}

/** The arrival as shown everywhere: with its date once the trip spans 6 days or more. */
export function arrivalTime(startIso: string, arrivalIso: string): string {
  const days = (Date.parse(arrivalIso) - Date.parse(startIso)) / 86_400_000
  return days >= 6 ? clockDate(arrivalIso) : clockTime(arrivalIso)
}

/**
 * From start to end, naming the end's day only when it differs: "Wed 17:30 – 18:00",
 * but "Mon 19:30 – Wed 05:30", so a 34-hour restart never reads as overnight. The
 * dates compare as written, since every time in a plan carries the same offset.
 */
export function timeRange(start: string, end: string): string {
  return `${clockTime(start)} – ${clockTime(end, start.slice(0, 10) !== end.slice(0, 10))}`
}

/**
 * The home terminal's zone as people write it, "CDT" or "MST", or "UTC-05:00" where
 * there is no short name. Every time in a plan is in it, at the start's offset (D17).
 */
export function zoneOf(plan: Pick<TripPlan, 'summary' | 'log_header'>): string {
  const { time_zone: timeZone, utc_offset: offset } = plan.log_header
  try {
    const name = new Intl.DateTimeFormat('en-US', { timeZone, timeZoneName: 'short' })
      .formatToParts(new Date(Date.parse(plan.summary.start)))
      .find((part) => part.type === 'timeZoneName')?.value
    if (name && !name.startsWith('GMT')) return name
  } catch {
    // An unknown zone name: fall back to the offset.
  }
  return `UTC${offset}`
}

/** "1 break", "2 breaks". */
export function count(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`
}

export function miles(value: number): string {
  return `${value.toLocaleString('en-US', { maximumFractionDigits: 0 })} mi`
}

export const STOP_LABEL: Record<StopKind, string> = {
  pre_trip: 'Pre-trip',
  pickup: 'Pickup',
  dropoff: 'Drop-off',
  fuel: 'Fuel',
  break: '30-min break',
  rest: '10-hr rest',
  restart: '34-hr restart',
}
