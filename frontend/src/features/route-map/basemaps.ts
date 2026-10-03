// Map tiles, in one place. Stadia "Alidade Smooth Dark" is the primary basemap
// (domain authentication: no key in the code). Esri's Dark Gray Canvas takes over
// automatically if Stadia fails, so the map is never blank.

export interface TileSource {
  url: string
  className: string // CSS hook for the tint
  maxZoom: number
}

export interface Basemap {
  name: string
  layers: TileSource[]
  attribution: string
}

const OSM = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

export const PRIMARY: Basemap = {
  name: 'Stadia Alidade Smooth Dark',
  layers: [
    {
      url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png',
      className: 'tiles-stadia',
      maxZoom: 18,
    },
  ],
  attribution:
    '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a> ' +
    '&copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> ' +
    OSM,
}

export const FALLBACK: Basemap = {
  name: 'Esri Dark Gray Canvas',
  layers: [
    {
      url: 'https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
      className: 'tiles-esri-base',
      maxZoom: 16,
    },
    {
      url: 'https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
      className: 'tiles-esri-labels',
      maxZoom: 16,
    },
  ],
  attribution: `Tiles &copy; Esri &mdash; Esri, HERE, Garmin, ${OSM}`,
}

export const FALLBACK_AFTER_ERRORS = 3
export const FALLBACK_AFTER_MS = 8000

/**
 * Fetch one tile and fail on any HTTP error. An <img> cannot do this: Stadia
 * answers an unauthorised request with HTTP 401 *and a PNG* ("401 Error"), which
 * an image element loads happily, so the error would never surface.
 */
export async function fetchTileImage(
  url: string,
  fetchFn: typeof fetch = fetch,
  signal?: AbortSignal,
): Promise<Blob> {
  const response = await fetchFn(url, { mode: 'cors', credentials: 'omit', signal })
  if (!response.ok) throw new Error(`tile HTTP ${response.status}`)
  const type = response.headers.get('content-type') ?? ''
  if (!type.startsWith('image/')) throw new Error(`tile is not an image (${type || 'no type'})`)
  return response.blob()
}

/**
 * Decides when to give up on the primary tiles. Errors only count while they come
 * in a row: one tile that loads proves the server works and resets the count.
 * A server that never answers at all is caught by the load timeout instead.
 */
export function createTileFallback(errorsInARow = FALLBACK_AFTER_ERRORS) {
  let errors = 0
  let loaded = 0
  let switched = false

  const trigger = (condition: boolean) => {
    if (switched || !condition) return false
    switched = true
    return true
  }

  return {
    /** A primary tile loaded. */
    loaded() {
      loaded += 1
      errors = 0
    },
    /** A primary tile failed. True when it is time to switch. */
    errored(): boolean {
      errors += 1
      return trigger(errors >= errorsInARow)
    },
    /** The load timeout passed. True when nothing has loaded, so switch. */
    timedOut(): boolean {
      return trigger(loaded === 0)
    },
    get switched() {
      return switched
    },
  }
}
