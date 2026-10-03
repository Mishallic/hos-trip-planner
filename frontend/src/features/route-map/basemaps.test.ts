import { describe, expect, it } from 'vitest'

import { createTileFallback, FALLBACK, fetchTileImage, PRIMARY } from './basemaps'

const png = new Uint8Array([0x89, 0x50, 0x4e, 0x47])
const fakeFetch = (status: number, type = 'image/png') =>
  (async () => new Response(png, { status, headers: { 'content-type': type } })) as typeof fetch

describe('fetchTileImage', () => {
  it('returns the image when the server says OK', async () => {
    const blob = await fetchTileImage('https://tiles.example/1/2/3.png', fakeFetch(200))

    expect(blob.size).toBe(4)
  })

  it('fails on a 401 even though the body is a PNG, as Stadia sends', async () => {
    await expect(fetchTileImage('https://tiles.example/1/2/3.png', fakeFetch(401))).rejects.toThrow(
      'tile HTTP 401',
    )
  })

  it('fails on rate limits and server errors', async () => {
    for (const status of [429, 500, 503]) {
      await expect(fetchTileImage('x', fakeFetch(status))).rejects.toThrow(`tile HTTP ${status}`)
    }
  })

  it('fails when an OK response is not an image', async () => {
    await expect(fetchTileImage('x', fakeFetch(200, 'text/html'))).rejects.toThrow('not an image')
  })

  it('passes the abort signal through, so unloaded tiles stop downloading', async () => {
    let seen: AbortSignal | null | undefined
    const spy = (async (_url: RequestInfo | URL, init?: RequestInit) => {
      seen = init?.signal
      return new Response(png, { status: 200, headers: { 'content-type': 'image/png' } })
    }) as typeof fetch
    const controller = new AbortController()

    await fetchTileImage('x', spy, controller.signal)

    expect(seen).toBe(controller.signal)
  })

  it('fails when the network fails', async () => {
    const offline = (async () => {
      throw new TypeError('Failed to fetch')
    }) as typeof fetch

    await expect(fetchTileImage('x', offline)).rejects.toThrow('Failed to fetch')
  })
})

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
