import 'leaflet/dist/leaflet.css'
import './routeMap.css'

import { Box } from '@mui/material'
import L from 'leaflet'
import { useEffect, useMemo, useRef } from 'react'

import type { Stop, TripPlan } from '../../api/types'
import { STOP_LABEL, timeRange } from '../../lib/format'
import { decodePolyline } from '../../lib/polyline'
import type { StopSelection } from '../../state/selection'
import { color, radius, stopColor } from '../../theme/tokens'
import { BASEMAP } from './basemaps'
import { iconFor } from './markers'
import { groupOf, groupStops, type StopGroup } from './stopGroups'

/** Zoom used when centring on a stop from far out, so the spot is recognisable. */
const CENTRE_MIN_ZOOM = 7

/** Pickup and drop-off pins sit above stop dots; the selected marker above both. */
const zIndexFor = (group: StopGroup, selected: boolean) => (selected ? 1000 : group.kind === 'stop' ? 0 : 500)

interface RouteMapProps {
  plan: TripPlan
  selection: StopSelection
}

/** The route on a dark map, with one marker per stop spot. Clicking selects the stop. */
export default function RouteMap({ plan, selection }: RouteMapProps) {
  const { selected: selectedStop, request, select: onSelectStop, centreRequest, centred, markCentred } = selection
  const element = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const markers = useRef<Map<string, L.Marker>>(new Map())
  const groups = useMemo(() => groupStops(plan.stops), [plan.stops])
  const selectedGroup = selectedStop === null ? undefined : groupOf(groups, selectedStop)

  // Keep the latest callback and selection without rebuilding the map.
  const select = useRef(onSelectStop)
  const current = useRef(selectedStop)
  useEffect(() => {
    select.current = onSelectStop
    current.current = selectedStop
  }, [onSelectStop, selectedStop])

  // Build the map once per plan.
  useEffect(() => {
    if (!element.current) return
    const instance = L.map(element.current, { zoomControl: false, attributionControl: true })
    map.current = instance
    L.control.zoom({ position: 'bottomright' }).addTo(instance)
    instance.attributionControl.setPrefix(false)
    addBasemap(instance)

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
        zIndexOffset: zIndexFor(group, false),
      })
      marker.bindTooltip(markerTitle(group, plan.stops), { direction: 'top', className: 'route-tooltip' })
      marker.bindPopup(popupHtml(group, plan.stops), { className: 'route-popup', maxWidth: 300, autoPanPadding: [24, 24] })
      // A spot selects its first stop, unless one of its stops is selected already:
      // then a click only opens or closes the popup, as Leaflet does on its own.
      const pick = () => {
        if (current.current === null || !group.stops.includes(current.current)) select.current(group.stops[0])
      }
      marker.on('click', pick)
      // Markers are buttons for the keyboard too. Leaflet toggles the popup on Enter
      // (keypress) but never fires a click, so select after it; Space does both.
      marker.on('keypress', (event) => {
        if ((event as L.LeafletKeyboardEvent).originalEvent.key === 'Enter') pick()
      })
      marker.on('keydown', (event) => {
        const key = (event as L.LeafletKeyboardEvent).originalEvent
        if (key.key !== ' ') return
        key.preventDefault()
        pick()
        marker.togglePopup()
      })
      marker.addTo(instance)
      created.set(group.key, marker)
    }
    markers.current = created

    // The map's box can change size (columns, mobile): keep Leaflet in step. When the
    // layout itself changes (side by side to stacked), fit the route again, unless the
    // user has already moved the map.
    const bounds = L.latLngBounds(line)
    let moved = false
    instance.on('dragstart', () => {
      moved = true
    })
    let size = { width: element.current.clientWidth, height: element.current.clientHeight }
    const changed = (before: number, after: number) => Math.abs(after - before) > before * 0.15
    const observer = new ResizeObserver(() => {
      instance.invalidateSize()
      const box = element.current
      if (!box) return
      const now = { width: box.clientWidth, height: box.clientHeight }
      if (!moved && (changed(size.width, now.width) || changed(size.height, now.height))) {
        instance.fitBounds(bounds, { padding: [48, 48] })
      }
      size = now
    })
    observer.observe(element.current)
    return () => {
      observer.disconnect()
      instance.remove()
      map.current = null
    }
  }, [plan, groups])

  // Follow the selection: enlarge the marker, lift it above its neighbours and open
  // its popup. Every request runs this, so selecting a stop again reopens a popup
  // the user closed, and Leaflet pans it back into view.
  useEffect(() => {
    for (const group of groups) {
      const isSelected = group.key === selectedGroup?.key
      const marker = markers.current.get(group.key)
      marker?.setIcon(iconFor(group, isSelected))
      marker?.setZIndexOffset(zIndexFor(group, isSelected))
    }
    const marker = selectedGroup && markers.current.get(selectedGroup.key)
    if (!marker) return
    // A popup opened by a click sits on the small icon: move it up to the large one.
    if (marker.isPopupOpen()) marker.getPopup()?.update()
    else marker.openPopup()
  }, [groups, selectedGroup, request])

  // "Centre the map on this stop" (Enter in the stop list). Each request is carried
  // out once, including one made while the map was still loading; an old request
  // never pulls the map back after the user pans away.
  useEffect(() => {
    if (centreRequest === centred) return
    markCentred(centreRequest)
    if (!map.current || !selectedGroup) return
    const zoom = Math.max(map.current.getZoom(), CENTRE_MIN_ZOOM)
    map.current.setView([selectedGroup.lat, selectedGroup.lon], zoom, { animate: true })
    // In a stacked layout the map may be scrolled out of sight: bring it back.
    const box = element.current?.getBoundingClientRect()
    if (box && (box.bottom < 80 || box.top > window.innerHeight)) element.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [centreRequest, centred, markCentred, selectedGroup])

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

/** The basemap's layers on the map. Leaflet shows their credits, so they always match. */
function addBasemap(map: L.Map) {
  for (const layer of BASEMAP.layers) {
    L.tileLayer(layer.url, { attribution: BASEMAP.attribution, className: layer.className, maxZoom: layer.maxZoom }).addTo(map)
  }
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
            <span class="route-popup-time">${timeRange(stop.start, stop.end)}</span>
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
