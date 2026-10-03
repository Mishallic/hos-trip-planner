// Where everything sits on a daily log sheet, as plain numbers: the grid, the duty
// line and the selected stop. LogSheet only draws what these functions return.
//
// The layout follows the paper form (guide p. 15-19 and the blank daily log): four
// status lines under a band of hour labels, totals on the right. Times are exact
// minutes from the sheet's midnight; the 15-minute ticks are only the grid (ELDs
// record exact minutes, so nothing is rounded to them).

import type { DailyLog, DutyStatus } from '../../api/types'
import { parseInstant } from '../../lib/timeScale'

export const DAY_MIN = 24 * 60

/** The four duty status lines, top to bottom, as the form numbers them. */
export const ROWS: { status: DutyStatus; label: string[]; title: string }[] = [
  { status: 'off_duty', label: ['1. Off Duty'], title: 'Off duty' },
  { status: 'sleeper_berth', label: ['2. Sleeper', 'Berth'], title: 'Sleeper berth' },
  { status: 'driving', label: ['3. Driving'], title: 'Driving' },
  { status: 'on_duty', label: ['4. On Duty', '(not driving)'], title: 'On duty (not driving)' },
]

/** The sheet in SVG units. The SVG scales to its card, so only proportions matter. */
export const SHEET = {
  width: 1000,
  labelWidth: 116,
  totalsWidth: 96,
  headerHeight: 36,
  rowHeight: 42,
  /** Ticks hang from the top of each row: short on the quarters, taller on the half. */
  quarterTick: 0.22,
  halfTick: 0.46,
} as const

export const GRID = {
  left: SHEET.labelWidth,
  right: SHEET.width - SHEET.totalsWidth,
  top: SHEET.headerHeight,
  bottom: SHEET.headerHeight + ROWS.length * SHEET.rowHeight,
}
export const GRID_WIDTH = GRID.right - GRID.left

/** x of a minute of the day. Exact: 13:11 sits at 13:11, not at the nearest tick. */
export function minuteX(minute: number): number {
  return GRID.left + (minute / DAY_MIN) * GRID_WIDTH
}

export function rowIndex(status: DutyStatus): number {
  return ROWS.findIndex((row) => row.status === status)
}

export function rowTop(status: DutyStatus): number {
  return GRID.top + rowIndex(status) * SHEET.rowHeight
}

/** y of a status line: the middle of its row. */
export function statusY(status: DutyStatus): number {
  return rowTop(status) + SHEET.rowHeight / 2
}

export interface Tick {
  minute: number
  /** 'hour' lines run through all four rows; the others hang from each row's top. */
  kind: 'hour' | 'half' | 'quarter'
}

/** Every line of the grid between midnight and midnight, the outer edges excluded. */
export function gridTicks(): Tick[] {
  const ticks: Tick[] = []
  for (let minute = 15; minute < DAY_MIN; minute += 15) {
    const kind = minute % 60 === 0 ? 'hour' : minute % 30 === 0 ? 'half' : 'quarter'
    ticks.push({ minute, kind })
  }
  return ticks
}

/** The labels over the hour lines: Midnight, 1-11, Noon, 1-11, Midnight. */
export function hourLabels(): { minute: number; text: string[] }[] {
  return Array.from({ length: 25 }, (_, hour) => ({
    minute: hour * 60,
    text: hour % 24 === 0 ? ['Mid-', 'night'] : hour === 12 ? ['Noon'] : [String(hour % 12)],
  }))
}

export interface Segment {
  status: DutyStatus
  start: number
  end: number
}

/** One horizontal stretch of the duty line, on its status row. */
export interface Run extends Segment {
  x1: number
  x2: number
  y: number
}

export function dutyRuns(segments: Segment[]): Run[] {
  return segments.map((segment) => ({
    ...segment,
    x1: minuteX(segment.start),
    x2: minuteX(segment.end),
    y: statusY(segment.status),
  }))
}

/**
 * The duty line as one SVG path: along each run, then straight up or down to the
 * next status, so it is a single continuous stroke from midnight to midnight.
 */
export function dutyPath(segments: Segment[]): string {
  const runs = dutyRuns(segments)
  if (!runs.length) return ''
  const parts = [`M ${num(runs[0].x1)} ${num(runs[0].y)}`]
  runs.forEach((run, index) => {
    if (index > 0) parts.push(`V ${num(run.y)}`)
    parts.push(`H ${num(run.x2)}`)
  })
  return parts.join(' ')
}

/** A dot on both lines at every change of duty status, as drivers mark them. */
export function changeDots(segments: Segment[]): { x: number; y: number; minute: number }[] {
  const runs = dutyRuns(segments)
  return runs.slice(1).flatMap((run, index) => {
    const before = runs[index]
    if (before.status === run.status) return []
    return [
      { x: run.x1, y: before.y, minute: run.start },
      { x: run.x1, y: run.y, minute: run.start },
    ]
  })
}

/** Minutes of horizontal line on each status row, read back from the drawn runs. */
export function drawnMinutes(segments: Segment[]): Record<DutyStatus, number> {
  const totals: Record<DutyStatus, number> = { off_duty: 0, sleeper_berth: 0, driving: 0, on_duty: 0 }
  for (const run of dutyRuns(segments)) {
    totals[run.status] += ((run.x2 - run.x1) / GRID_WIDTH) * DAY_MIN
  }
  return totals
}

/**
 * Where a stop falls on one sheet, in minutes from that sheet's midnight, or null
 * when it falls on another day. A 10-hour rest from 17:30 shows on two sheets.
 */
export function stopOnSheet(
  stop: { start: string; end: string; status: DutyStatus },
  log: Pick<DailyLog, 'starts_at'>,
): Segment | null {
  const midnight = parseInstant(log.starts_at).utcMs
  const start = (parseInstant(stop.start).utcMs - midnight) / 60_000
  const end = (parseInstant(stop.end).utcMs - midnight) / 60_000
  if (end <= 0 || start >= DAY_MIN) return null
  return { status: stop.status, start: Math.max(0, start), end: Math.min(DAY_MIN, end) }
}

/** Short numbers in the path: 2 decimals keep it exact to well under a pixel. */
function num(value: number): string {
  return String(Math.round(value * 100) / 100)
}
