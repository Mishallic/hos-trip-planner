export type LatLon = [number, number]

/** Decode Google's encoded polyline format, as sent by the API (precision 5). */
export function decodePolyline(encoded: string, precision = 5): LatLon[] {
  const points: LatLon[] = []
  const factor = 10 ** precision
  let index = 0
  let lat = 0
  let lon = 0
  while (index < encoded.length) {
    for (const axis of [0, 1]) {
      let shift = 0
      let result = 0
      let byte: number
      do {
        byte = encoded.charCodeAt(index++) - 63
        result |= (byte & 0x1f) << shift
        shift += 5
      } while (byte >= 0x20)
      const delta = result & 1 ? ~(result >> 1) : result >> 1
      if (axis === 0) lat += delta
      else lon += delta
    }
    points.push([lat / factor, lon / factor])
  }
  return points
}
