// Map tiles, in one place: Esri's World Dark Gray Canvas, with its reference layer
// for place labels. No account or key is needed, so nothing secret is in the code.

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

export const BASEMAP: Basemap = {
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
