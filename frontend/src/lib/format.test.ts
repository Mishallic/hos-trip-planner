import { describe, expect, it } from 'vitest'

import { clockTime, count, timeRange } from './format'

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
