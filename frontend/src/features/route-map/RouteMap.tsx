import 'leaflet/dist/leaflet.css'
import './routeMap.css'

import { Box } from '@mui/material'
import L from 'leaflet'
import { useEffect, useMemo, useRef } from 'react'

import type { Stop, TripPlan } from '../../api/types'
import { clockTime, STOP_LABEL } from '../../lib/format'
import { decodePolyline } from '../../lib/polyline'
import { color, radius, stopColor } from '../../theme/tokens'
import {
  type Basemap,
  createTileFallback,
  FALLBACK,
  FALLBACK_AFTER_MS,
  fetchTileImage,
  PRIMARY,
} from './basemaps'
import { iconFor } from './markers'
import { groupOf, groupStops, type StopGroup } from './stopGroups'


interface RouteMapProps {
  plan: TripPlan
  selectedStop: number | null
  onSelectStop: (index: number) => void
}

/** The route on a dark map, with one marker per stop spot. Clicking selects the stop. */
export default function RouteMap({ plan, selectedStop, onSelectStop }: RouteMapProps) {
  const element = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const markers = useRef<Map<string, L.Marker>>(new Map())
  const groups = useMemo(() => groupStops(plan.stops), [plan.stops])
  const selectedGroup = selectedStop === null ? undefined : groupOf(groups, selectedStop)

  // Keep the latest callback without rebuilding the map.
  const select = useRef(onSelectStop)
  useEffect(() => {
    select.current = onSelectStop
  }, [onSelectStop])

  // Build the map once per plan.
  useEffect(() => {
    if (!element.current) return
    const instance = L.map(element.current, { zoomControl: false, attributionControl: true })
    map.current = instance
    L.control.zoom({ position: 'bottomright' }).addTo(instance)
    instance.attributionControl.setPrefix(false)
    const stopWatchingTiles = addBasemap(instance)

    const line = decodePolyline(plan.route.polyline)
    L.polyline(line, { color: color.turquoise, weight: 12, opacity: 0.18, className: 'route-glow', interactive: false }).addTo(instance)
    L.polyline(line, { color: '#FFFFFF', weight: 3, opacity: 0.95, className: 'route-line', interactive: false }).addTo(instance)
    instance.fitBounds(L.latLngBounds(line), { padding: [48, 48] })

    const created = new Map<string, L.Marker>()
    for (const group of groups) {
      const marker = L.marker([group.lat, group.lon], {
        icon: iconFor(group, false),
        keyboard: true,
        title: markerTitle(group, plan.stops),
        zIndexOffset: group.kind === 'stop' ? 0 : 500,
      })
      marker.bindTooltip(markerTitle(group, plan.stops), { direction: 'top', className: 'route-tooltip' })
      marker.bindPopup(popupHtml(group, plan.stops), { className: 'route-popup', maxWidth: 300, autoPanPadding: [24, 24] })
      marker.on('click', () => select.current(group.stops[0]))
      marker.addTo(instance)
      created.set(group.key, marker)
    }
    markers.current = created

    // The map's box can change size (columns, mobile): keep Leaflet in step.
    const observer = new ResizeObserver(() => instance.invalidateSize())
    observer.observe(element.current)
    return () => {
      stopWatchingTiles()
      observer.disconnect()
      instance.remove()
      map.current = null
    }
  }, [plan, groups])

  // Follow the selection: enlarge the marker and open its popup.
  useEffect(() => {
    for (const group of groups) {
      markers.current.get(group.key)?.setIcon(iconFor(group, group.key === selectedGroup?.key))
    }
    const marker = selectedGroup && markers.current.get(selectedGroup.key)
    if (marker && !marker.isPopupOpen()) marker.openPopup()
  }, [groups, selectedGroup])

  return (
    <Box
      ref={element}
      role="region"
      aria-label="Route map"
      sx={{
        height: '100%',
        minHeight: 0,
        borderRadius: `${radius.panel}px`,
        overflow: 'hidden',
        border: `1px solid ${color.border}`,
        background: '#1A2830',
      }}
    />
  )
}

// In-flight tile requests, so a tile that leaves the view stops downloading.
const tileRequests = new WeakMap<HTMLElement, AbortController>()
const abortTile = (event: L.TileEvent) => tileRequests.get(event.tile)?.abort()

/**
 * A tile layer that loads each tile with fetch(), so an HTTP error is a tile error
 * even when the server sends an image with it (Stadia's 401 tile does).
 */
const StatusCheckedTileLayer = L.TileLayer.extend({
  onAdd(this: L.TileLayer, map: L.Map) {
    this.on('tileunload', abortTile)
    return L.TileLayer.prototype.onAdd.call(this, map)
  },
  createTile(this: L.TileLayer, coords: L.Coords, done: L.DoneCallback): HTMLElement {
    const tile = document.createElement('img')
    tile.alt = ''
    tile.setAttribute('role', 'presentation')
    const request = new AbortController()
    tileRequests.set(tile, request)
    fetchTileImage(this.getTileUrl(coords), fetch, request.signal)
      .then((blob) => {
        const url = URL.createObjectURL(blob)
        tile.onload = () => {
          URL.revokeObjectURL(url)
          done(undefined, tile)
        }
        tile.onerror = () => {
          URL.revokeObjectURL(url)
          done(new Error('tile image could not be decoded'), tile)
        }
        tile.src = url
      })
      .catch((error: Error) => {
        // A tile we cancelled is not a failure of the tile server.
        if (!request.signal.aborted) done(error, tile)
      })
    return tile
  },
}) as unknown as new (url: string, options?: L.TileLayerOptions) => L.TileLayer

function tileLayers(basemap: Basemap, checkStatus = false): L.TileLayer[] {
  return basemap.layers.map((layer) => {
    const options: L.TileLayerOptions = {
      // Leaflet shows the credits of the layers on the map, so they always match.
      attribution: basemap.attribution,
      className: layer.className,
      maxZoom: layer.maxZoom,
    }
    return checkStatus ? new StatusCheckedTileLayer(layer.url, options) : L.tileLayer(layer.url, options)
  })
}

/**
 * Stadia first. On repeated tile errors, or no tile at all within the timeout,
 * swap to Esri without a word, so the map is never blank. Returns a cleanup.
 */
function addBasemap(map: L.Map): () => void {
  const primary = tileLayers(PRIMARY, true)
  const fallback = createTileFallback()
  const useFallback = () => {
    primary.forEach((layer) => layer.remove())
    tileLayers(FALLBACK).forEach((layer) => layer.addTo(map))
  }
  for (const layer of primary) {
    layer.on('tileload', () => fallback.loaded())
    layer.on('tileerror', () => fallback.errored() && useFallback())
    layer.addTo(map)
  }
  const timer = window.setTimeout(() => fallback.timedOut() && useFallback(), FALLBACK_AFTER_MS)
  return () => window.clearTimeout(timer)
}

function markerTitle(group: StopGroup, stops: Stop[]): string {
  const first = stops[group.stops[0]]
  const what =
    group.kind === 'current' ? 'Start' : group.stops.map((i) => STOP_LABEL[stops[i].kind]).join(' + ')
  return `${what} · ${first.place ?? `mile ${first.mile}`}`
}

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
}

function popupHtml(group: StopGroup, stops: Stop[]): string {
  const first = stops[group.stops[0]]
  const heading = group.kind === 'current' ? 'Start' : first.place ?? `Mile ${first.mile}`
  const sub = group.kind === 'current' ? first.place ?? '' : `Mile ${first.mile.toLocaleString('en-US')}`
  const rows = group.stops
    .map((index) => {
      const stop = stops[index]
      return `
        <li>
          <div class="route-popup-row">
            <span class="route-popup-dot" style="background:${stopColor[stop.kind]}"></span>
            <strong style="color:${stopColor[stop.kind]}">${STOP_LABEL[stop.kind]}</strong>
            <span class="route-popup-time">${clockTime(stop.start)} – ${clockTime(stop.end, false)}</span>
          </div>
          <p>${escapeHtml(stop.explanation)}</p>
        </li>`
    })
    .join('')
  return `
    <div class="route-popup-head">
      <strong>${escapeHtml(heading)}</strong>
      <span>${escapeHtml(sub)}</span>
    </div>
    <ul>${rows}</ul>`
}
