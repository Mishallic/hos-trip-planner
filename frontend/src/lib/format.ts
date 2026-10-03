import type { StopKind } from '../api/types'

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
