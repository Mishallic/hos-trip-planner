import type { Stop, Summary } from '../../api/types'
import { arrivalTime, count, hm } from '../../lib/format'
import { parseInstant } from '../../lib/timeScale'

export interface Verdict {
  text: string
  tone: 'ok' | 'warn'
  /** A longer explanation for the badge's tooltip. */
  detail: string
}

/**
 * The header badge: when the load arrives, or what stands in the way. Never a bare
 * "within limits", which every plan is by construction.
 */
export function verdictFor(summary: Summary, stops: Stop[], zone = ''): Verdict {
  const days = count(summary.sheets, 'day')
  const arrives = `${arrivalTime(summary.start, summary.dropoff_arrival)}${zone ? ` ${zone}` : ''}`
  if (summary.restart_needed) {
    const restarts = stops.filter((s) => s.kind === 'restart')
    const restartMin = restarts.reduce((sum, s) => sum + s.duration_min, 0)
    const several = restarts.length > 1
    return {
      text: `Needs ${several ? `${restarts.length} × 34-hr restarts` : '34-hr restart'} (+${(restartMin / 1440).toFixed(1)} days)`,
      tone: 'warn',
      detail:
        `The 70-hour cycle can't cover the whole trip, so the driver takes ${several ? `${restarts.length} restarts, ` : ''}` +
        `${Math.round(restartMin / 60)} hours off${several ? ' in all' : ''}. Delivers ${arrives}, ${days} of logs.`,
    }
  }
  // To the drop-off's arrival, as the badge says; summary.elapsed also counts the unloading.
  const toArrivalMin = (parseInstant(summary.dropoff_arrival).utcMs - parseInstant(summary.start).utcMs) / 60_000
  return {
    text: `Delivers ${arrives} · ${days}`,
    tone: 'ok',
    detail: `${summary.driving} of driving, ${hm(toArrivalMin)} from start to drop-off.`,
  }
}
