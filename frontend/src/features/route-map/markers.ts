import L from 'leaflet'
import {
  BedDouble,
  ClipboardCheck,
  Coffee,
  createElement,
  Flag,
  Fuel,
  type IconNode,
  Package,
  RotateCcw,
  Truck,
} from 'lucide'

import type { StopKind } from '../../api/types'
import { color, stopColor } from '../../theme/tokens'
import type { StopGroup } from './stopGroups'

const STOP_ICONS: Record<StopKind, IconNode> = {
  pre_trip: ClipboardCheck,
  pickup: Package,
  dropoff: Flag,
  fuel: Fuel,
  break: Coffee,
  rest: BedDouble,
  restart: RotateCcw,
}

function svg(icon: IconNode, size: number, stroke: string): string {
  const element = createElement(icon, { width: size, height: size, stroke, 'stroke-width': 2.2 })
  return element.outerHTML
}

/** "+3": stops near this marker, hidden under it at this zoom. */
function moreBadge(more: number): string {
  return more > 0 ? `<span class="route-dot-count">+${more}</span>` : ''
}

/** A teardrop pin with an icon, for pickup (green) and drop-off (red), as in the driver app. */
function pin(fill: string, icon: IconNode, selected: boolean, more: number): L.DivIcon {
  const size = selected ? 46 : 38
  return L.divIcon({
    className: `route-marker route-pin${selected ? ' is-selected' : ''}`,
    iconSize: [size, size * 1.25],
    iconAnchor: [size / 2, size * 1.25],
    popupAnchor: [0, -size * 1.15],
    tooltipAnchor: [0, -size * 1.1],
    html: `
      <svg viewBox="0 0 40 50" width="${size}" height="${size * 1.25}" aria-hidden="true">
        <path d="M20 49 C9 35 2 27 2 18 a18 18 0 1 1 36 0 c0 9 -7 17 -18 31Z"
              fill="${fill}" stroke="${color.bgDeep}" stroke-width="2"/>
      </svg>
      <span class="route-pin-icon">${svg(icon, size * 0.42, color.bgDeep)}</span>${moreBadge(more)}`,
  })
}

/** A round marker in the stop's colour, the same circle as in the stop list. */
function dot(kind: StopKind, count: number, selected: boolean): L.DivIcon {
  const size = selected ? 36 : 28
  const badge = count > 1 ? `<span class="route-dot-count">${count}</span>` : ''
  return L.divIcon({
    className: `route-marker route-dot${selected ? ' is-selected' : ''}`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
    tooltipAnchor: [0, -size / 2],
    html: `<span class="route-dot-body" style="--tone:${stopColor[kind]}">${svg(STOP_ICONS[kind], size * 0.5, color.bgDeep)}</span>${badge}`,
  })
}

/** The truck: where the driver is now. */
function truck(selected: boolean, more: number): L.DivIcon {
  const size = selected ? 44 : 38
  return L.divIcon({
    className: `route-marker route-truck${selected ? ' is-selected' : ''}`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
    tooltipAnchor: [0, -size / 2],
    html: `<span class="route-truck-body">${svg(Truck, size * 0.5, color.text)}</span>${moreBadge(more)}`,
  })
}

/** A group's marker; `more` counts the stops of nearby markers hidden under it. */
export function iconFor(group: StopGroup, selected: boolean, more = 0): L.DivIcon {
  switch (group.kind) {
    case 'current':
      return truck(selected, more)
    case 'pickup':
      return pin(stopColor.pickup, STOP_ICONS.pickup, selected, more)
    case 'dropoff':
      return pin(stopColor.dropoff, STOP_ICONS.dropoff, selected, more)
    default:
      return dot(group.mainKind, group.stops.length + more, selected)
  }
}
