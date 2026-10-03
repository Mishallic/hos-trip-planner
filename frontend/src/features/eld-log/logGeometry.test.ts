import { describe, expect, it } from 'vitest'

import type { DailyLog, DutyStatus, TripPlan } from '../../api/types'
import johnDoe from '../../fixtures/log-john-doe.json'
import multiDay from '../../fixtures/plan-multi-day.json'
import restart from '../../fixtures/plan-restart.json'
import short from '../../fixtures/plan-short.json'
import {
  changeDots,
  DAY_MIN,
  dutyPath,
  GRID,
  GRID_WIDTH,
  gridTicks,
  hourLabels,
  flagReach,
  minuteX,
  remarkLayout,
  SHEET,
  ROWS,
  statusY,
  stopOnSheet,
} from './logGeometry'

// The guide's completed grid (p. 18-19): John Doe, Richmond, VA to Newark, NJ.
const doe = johnDoe as DailyLog
const SHEETS: [string, DailyLog][] = [
  ['John Doe', doe],
  ...[short, multiDay, restart].flatMap((plan) =>
    (plan as unknown as TripPlan).logs.map((log): [string, DailyLog] => [log.date, log]),
  ),
]

/** The duty line as drawn: the path's points, read back from its "M x y H x V y ..." string. */
function drawn(d: string) {
  const commands = d.match(/[MHV] [-\d.]+(?: [-\d.]+)?/g) ?? []
  let x = 0
  let y = 0
  const moves = commands.filter((c) => c.startsWith('M')).length
  const horizontal: { y: number; length: number; from: number; to: number }[] = []
  const corners: number[] = []
  for (const command of commands) {
    const [op, a, b] = command.split(' ')
    if (op === 'M') [x, y] = [Number(a), Number(b)]
    if (op === 'H') {
      horizontal.push({ y, length: Number(a) - x, from: x, to: Number(a) })
      x = Number(a)
    }
    if (op === 'V') {
      corners.push(x)
      y = Number(a)
    }
  }
  return { moves, horizontal, corners, start: horizontal[0]?.from, end: x }
}

const toMinutes = (length: number) => (length / GRID_WIDTH) * DAY_MIN
const rowOf = (y: number) => ROWS.find((row) => Math.abs(statusY(row.status) - y) < 0.01)!.status

describe('the grid', () => {
  it('has a line every 15 minutes: hours through every row, taller ticks on the half hour', () => {
    const ticks = gridTicks()
    const count = (kind: string) => ticks.filter((t) => t.kind === kind).length

    expect([count('hour'), count('half'), count('quarter')]).toEqual([23, 24, 48])
    expect(ticks.find((t) => t.minute === 12 * 60)?.kind).toBe('hour')
    expect(ticks.find((t) => t.minute === 12 * 60 + 30)?.kind).toBe('half')
    expect(ticks.find((t) => t.minute === 12 * 60 + 45)?.kind).toBe('quarter')
  })

  it('labels the hours Midnight, 1-11, Noon, 1-11, Midnight', () => {
    const labels = hourLabels().map((label) => label.text.join(''))

    expect(labels).toEqual([
      'Mid-night', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11',
      'Noon', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', 'Mid-night',
    ])
  })

  it('places minutes exactly, not on the nearest tick', () => {
    expect(minuteX(0)).toBe(GRID.left)
    expect(minuteX(DAY_MIN)).toBe(GRID.right)
    expect(minuteX(791)).toBeCloseTo(GRID.left + (791 / 1440) * GRID_WIDTH, 9) // 13:11, a fuel stop
    expect(minuteX(791)).not.toBe(minuteX(795))
  })
})

describe("John Doe's day (guide p. 18)", () => {
  const line = drawn(dutyPath(doe.segments))

  it('changes status exactly where the guide does', () => {
    const hm = line.corners.map((x) => {
      const minute = Math.round(toMinutes(x - GRID.left))
      return `${Math.floor(minute / 60)}:${String(minute % 60).padStart(2, '0')}`
    })

    expect(hm).toEqual(['6:00', '7:30', '9:00', '9:30', '12:00', '13:00', '15:00', '15:30', '16:00', '17:45', '19:00', '21:00'])
  })

  it('totals 10:00 off duty, 1:45 sleeper berth, 7:45 driving and 4:30 on duty', () => {
    const totals = { off_duty: 0, sleeper_berth: 0, driving: 0, on_duty: 0 } as Record<DutyStatus, number>
    for (const run of line.horizontal) totals[rowOf(run.y)] += toMinutes(run.length)

    expect(Object.values(totals).map(Math.round)).toEqual([600, 105, 465, 270])
  })

  it('puts a dot on both lines at each of the 12 changes', () => {
    const dots = changeDots(doe.segments)

    expect(dots).toHaveLength(24)
    expect(dots[0]).toMatchObject({ minute: 360, y: statusY('off_duty') })
    expect(dots[1]).toMatchObject({ minute: 360, y: statusY('on_duty') })
  })
})

describe.each(SHEETS)('the duty line on %s', (_, log) => {
  const line = drawn(dutyPath(log.segments))

  it('is one continuous stroke from midnight to midnight', () => {
    expect(line.moves).toBe(1)
    expect(line.start).toBeCloseTo(GRID.left, 2)
    expect(line.end).toBeCloseTo(GRID.right, 2)
    line.horizontal.forEach((run, i) => {
      expect(run.length).toBeGreaterThan(0)
      if (i > 0) expect(run.from).toBe(line.horizontal[i - 1].to)
    })
  })

  it("draws each row exactly as long as that row's total", () => {
    const totals = { off_duty: 0, sleeper_berth: 0, driving: 0, on_duty: 0 } as Record<DutyStatus, number>
    for (const run of line.horizontal) totals[rowOf(run.y)] += toMinutes(run.length)

    for (const row of ROWS) expect(totals[row.status]).toBeCloseTo(log.totals_min[row.status], 1)
    expect(Object.values(log.totals_min).reduce((a, b) => a + b)).toBe(DAY_MIN)
  })
})

describe('stopOnSheet', () => {
  const day = (date: string) => ({ starts_at: `${date}T00:00-07:00` })
  const rest = { status: 'sleeper_berth' as const, start: '2026-10-07T17:30-07:00', end: '2026-10-08T03:30-07:00' }

  it('places a stop in minutes from the sheet midnight', () => {
    const fuel = { status: 'on_duty' as const, start: '2026-10-07T13:11-07:00', end: '2026-10-07T13:41-07:00' }

    expect(stopOnSheet(fuel, day('2026-10-07'))).toEqual({ status: 'on_duty', start: 791, end: 821 })
  })

  it('splits a rest across midnight onto both sheets', () => {
    expect(stopOnSheet(rest, day('2026-10-07'))).toEqual({ status: 'sleeper_berth', start: 1050, end: 1440 })
    expect(stopOnSheet(rest, day('2026-10-08'))).toEqual({ status: 'sleeper_berth', start: 0, end: 210 })
    expect(stopOnSheet(rest, day('2026-10-09'))).toBeNull()
    expect(stopOnSheet(rest, day('2026-10-06'))).toBeNull()
  })

  it('spreads the 34-hour restart over three sheets', () => {
    const plan = restart as unknown as TripPlan
    const stop = plan.stops.find((s) => s.kind === 'restart')!
    const spans = plan.logs.map((log) => stopOnSheet(stop, log))

    expect(spans).toEqual([
      { status: 'off_duty', start: 1170, end: 1440 },
      { status: 'off_duty', start: 0, end: 1440 },
      { status: 'off_duty', start: 0, end: 330 },
      null,
      null,
    ])
  })
})

describe('remarkLayout', () => {
  it("flags John Doe's six stops with their places, as on the guide's grid", () => {
    const { brackets, flags } = remarkLayout(doe)

    expect(brackets).toHaveLength(6)
    expect(flags.map((f) => f.text.split(' · ')[0])).toEqual([
      'Richmond, VA',
      'Fredericksburg, VA',
      'Baltimore, MD',
      'Philadelphia, PA',
      'Cherry Hill, NJ',
      'Newark, NJ',
    ])
    expect(flags[1].text).toBe('Fredericksburg, VA · Fuel')
  })

  it('hangs each flag from the middle of its bracket', () => {
    const { brackets, flags } = remarkLayout(doe)

    expect(flags[0].anchorX).toBeCloseTo((minuteX(360) + minuteX(450)) / 2, 6)
    expect(brackets[0]).toMatchObject({ x1: minuteX(360), x2: minuteX(450) })
  })

  it('spreads flags that would overlap and keeps them in time order', () => {
    const log = {
      brackets: [
        { start: 600, end: 630, place: 'A' },
        { start: 640, end: 670, place: 'B' },
        { start: 680, end: 700, place: 'C' },
      ],
      remarks: [],
    }
    const xs = remarkLayout(log).flags.map((f) => f.x)

    xs.slice(1).forEach((x, i) => expect(x - xs[i]).toBeGreaterThanOrEqual(22))
  })

  it('names a stretch carried over from the day before', () => {
    const plan = restart as unknown as TripPlan
    const dayBefore = plan.logs[0].remarks.at(-1)!
    const { flags } = remarkLayout(plan.logs[1], dayBefore)

    expect(flags).toEqual([expect.objectContaining({ text: 'near Houck, AZ · 34-hour restart (continued)' })])
  })

  it("lets the day's own stop name a stretch carried over from the day before", () => {
    const plan = restart as unknown as TripPlan
    const carried = plan.logs[1].remarks.at(-1) ?? plan.logs[0].remarks.at(-1)!
    const { flags } = remarkLayout(plan.logs[2], carried)

    expect(flags[0].text).toBe('near Houck, AZ · Pre-trip inspection')
  })

  it('keeps every flag inside the sheet, late ones pulled back', () => {
    const log = {
      brackets: [
        { start: 1300, end: 1380, place: 'Rancho Santa Margarita, CA' },
        { start: 1400, end: 1440, place: 'Mount Pleasant Township, PA' },
      ],
      remarks: [
        { minute: 1300, status: 'on_duty' as const, label: 'Drop-off', place: 'x', mile: 0, time: '21:40', reasons: [] },
        { minute: 1400, status: 'off_duty' as const, label: 'Off duty', place: 'x', mile: 0, time: '23:20', reasons: [] },
      ],
    }
    const { flags } = remarkLayout(log)

    for (const flag of flags) expect(flag.x + flagReach(flag.text)).toBeLessThanOrEqual(SHEET.width)
    expect(flags[1].x - flags[0].x).toBeGreaterThanOrEqual(22)
  })

  it('cuts the place, not the activities, when a flag is too long', () => {
    const log = {
      brackets: [{ start: 0, end: 60, place: 'near Rancho Santa Margarita Heights, CA' }],
      remarks: [
        { minute: 0, status: 'on_duty' as const, label: 'Pre-trip inspection, Pickup', place: 'x', mile: 0, time: '00:00', reasons: [] },
      ],
    }

    expect(remarkLayout(log).flags[0].text).toMatch(/…, CA|… · Pre-trip inspection, Pickup$/)
    expect(remarkLayout(log).flags[0].text.endsWith('Pre-trip inspection, Pickup')).toBe(true)
  })

  it('cuts very long flag text', () => {
    const log = { brackets: [{ start: 0, end: 60, place: 'Rancho Santa Margarita, CA' }], remarks: [
      { minute: 0, status: 'on_duty' as const, label: 'Pre-trip inspection, Pickup, Fuel, 30-minute break, Loading, Scale', place: 'x', mile: 0, time: '00:00', reasons: [] },
    ] }

    expect(remarkLayout(log).flags[0].text).toHaveLength(60)
    expect(remarkLayout(log).flags[0].text.endsWith('…')).toBe(true)
  })
})
