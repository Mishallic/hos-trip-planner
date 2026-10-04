import { describe, expect, it } from 'vitest'

import { arrivalTime, clockTime, count, timeRange, zoneOf } from './format'

describe('clockTime', () => {
  it('keeps the trip offset instead of the viewer time zone', () => {
    expect(clockTime('2026-10-05T07:00-07:00')).toBe('Mon 07:00')
    expect(clockTime('2026-10-05T23:30+05:30', false)).toBe('23:30')
  })
})

describe('timeRange', () => {
  it('leaves the day off an end on the same date', () => {
    expect(timeRange('2026-10-07T17:30-07:00', '2026-10-07T18:00-07:00')).toBe('Wed 17:30 – 18:00')
  })

  it('names the end day when the stop runs past midnight', () => {
    expect(timeRange('2026-10-07T17:30-07:00', '2026-10-08T03:30-07:00')).toBe('Wed 17:30 – Thu 03:30')
  })

  it('shows a 34-hour restart ending two days later', () => {
    expect(timeRange('2026-10-05T19:30-07:00', '2026-10-07T05:30-07:00')).toBe('Mon 19:30 – Wed 05:30')
  })
})

describe('count', () => {
  it('uses the singular only for one', () => {
    expect(count(1, 'break')).toBe('1 break')
    expect(count(0, 'break')).toBe('0 breaks')
    expect(count(2, 'log sheet')).toBe('2 log sheets')
  })
})

describe('arrivalTime', () => {
  it('names the date once the trip is long enough to repeat a weekday', () => {
    expect(arrivalTime('2026-10-05T07:00-04:00', '2026-10-07T05:24-04:00')).toBe('Wed 05:24')
    expect(arrivalTime('2026-10-05T07:00-04:00', '2026-10-16T18:49-04:00')).toBe('Fri 16 Oct 18:49')
  })
})

describe('zoneOf', () => {
  const plan = (timeZone: string, start: string, offset: string) => ({
    summary: { start } as never,
    log_header: { time_zone: timeZone, utc_offset: offset },
  })

  it('names the home terminal zone as people write it', () => {
    expect(zoneOf(plan('America/Chicago', '2026-10-05T07:00-05:00', '-05:00'))).toBe('CDT')
    expect(zoneOf(plan('America/Chicago', '2026-12-05T07:00-06:00', '-06:00'))).toBe('CST')
    expect(zoneOf(plan('America/Phoenix', '2026-10-05T07:00-07:00', '-07:00'))).toBe('MST')
  })

  it('falls back to the offset for a zone without a short name', () => {
    expect(zoneOf(plan('Mars/Base', '2026-10-05T07:00-05:00', '-05:00'))).toBe('UTC-05:00')
  })
})
