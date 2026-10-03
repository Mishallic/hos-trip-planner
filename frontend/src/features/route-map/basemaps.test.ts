import { describe, expect, it } from 'vitest'

import { createTileFallback, FALLBACK, PRIMARY } from './basemaps'

describe('tile fallback', () => {
  it('switches after three errors in a row', () => {
    const fallback = createTileFallback()

    expect([fallback.errored(), fallback.errored(), fallback.errored()]).toEqual([false, false, true])
    expect(fallback.switched).toBe(true)
  })

  it('a tile that loads resets the count', () => {
    const fallback = createTileFallback()
    fallback.errored()
    fallback.errored()
    fallback.loaded()

    expect([fallback.errored(), fallback.errored()]).toEqual([false, false])
    expect(fallback.switched).toBe(false)
  })

  it('switches only once', () => {
    const fallback = createTileFallback(1)

    expect(fallback.errored()).toBe(true)
    expect(fallback.errored()).toBe(false)
    expect(fallback.timedOut()).toBe(false)
  })

  it('switches on timeout when nothing loaded, as when the server never answers', () => {
    expect(createTileFallback().timedOut()).toBe(true)
  })

  it('does not switch on timeout once tiles are loading', () => {
    const fallback = createTileFallback()
    fallback.loaded()

    expect(fallback.timedOut()).toBe(false)
  })
})

describe('basemaps', () => {
  it('use Stadia first and Esri as the fallback, each with its own credits', () => {
    expect(PRIMARY.layers[0].url).toContain('tiles.stadiamaps.com/tiles/alidade_smooth_dark')
    expect(PRIMARY.attribution).toContain('Stadia Maps')
    expect(FALLBACK.layers[0].url).toContain('World_Dark_Gray_Base')
    expect(FALLBACK.attribution).toContain('Esri')
    for (const basemap of [PRIMARY, FALLBACK]) expect(basemap.attribution).toContain('OpenStreetMap')
  })

  it('keep keys out of the code', () => {
    for (const basemap of [PRIMARY, FALLBACK]) {
      for (const layer of basemap.layers) expect(layer.url).not.toMatch(/api_key|apikey|token|key=/i)
    }
  })
})
