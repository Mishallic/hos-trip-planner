import { describe, expect, it } from 'vitest'

import { color } from '../../theme/tokens'
import { clockTone } from './clockTone'

describe('clockTone', () => {
  it('is coral when a clock has run out', () => {
    expect(clockTone(0)).toBe(color.coral)
  })

  it('is amber under one hour', () => {
    expect(clockTone(1)).toBe(color.amber)
    expect(clockTone(59)).toBe(color.amber)
  })

  it('is turquoise from one hour up', () => {
    expect(clockTone(60)).toBe(color.turquoise)
    expect(clockTone(660)).toBe(color.turquoise)
  })
})
