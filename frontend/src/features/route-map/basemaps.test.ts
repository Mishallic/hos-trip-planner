import { describe, expect, it } from 'vitest'

import { BASEMAP } from './basemaps'

describe('the basemap', () => {
  it('is Esri Dark Gray: the base and its labels on top', () => {
    expect(BASEMAP.layers.map((layer) => layer.className)).toEqual(['tiles-esri-base', 'tiles-esri-labels'])
    expect(BASEMAP.layers[0].url).toContain('World_Dark_Gray_Base')
    expect(BASEMAP.layers[1].url).toContain('World_Dark_Gray_Reference')
  })

  it('credits Esri and OpenStreetMap', () => {
    expect(BASEMAP.attribution).toContain('Esri')
    expect(BASEMAP.attribution).toContain('OpenStreetMap')
  })

  it('needs no key and loads over https', () => {
    for (const layer of BASEMAP.layers) {
      expect(layer.url).toMatch(/^https:\/\//)
      expect(layer.url).not.toMatch(/key|token/i)
    }
  })
})
