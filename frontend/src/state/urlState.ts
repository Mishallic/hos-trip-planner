import type { PlaceRequest, PlanRequest } from '../api/client'

// The trip's inputs live in the URL, so a plan link is shareable and reproducible.

export interface PlaceValue {
  label: string
  lat?: number
  lon?: number
}

export const HEADER_FIELDS = [
  'driver',
  'carrier',
  'truck',
  'trailer',
  'shipper',
  'commodity',
  'load_id',
  'home_terminal',
] as const
export type HeaderField = (typeof HEADER_FIELDS)[number]

export interface TripForm {
  current: PlaceValue
  pickup: PlaceValue
  dropoff: PlaceValue
  cycleUsedHours: string
  startTime: string // local "YYYY-MM-DDTHH:MM" at the home terminal; empty = now
  homeTz: string // IANA name; empty = the current location's zone
  header: Record<HeaderField, string>
}

const PLACES = ['current', 'pickup', 'dropoff'] as const
const PARAM: Record<(typeof PLACES)[number], string> = {
  current: 'from',
  pickup: 'pickup',
  dropoff: 'dropoff',
}

export function emptyForm(): TripForm {
  return {
    current: { label: '' },
    pickup: { label: '' },
    dropoff: { label: '' },
    cycleUsedHours: '0',
    startTime: '',
    homeTz: '',
    header: Object.fromEntries(HEADER_FIELDS.map((f) => [f, ''])) as Record<HeaderField, string>,
  }
}

export function formFromParams(params: URLSearchParams): TripForm {
  const form = emptyForm()
  for (const place of PLACES) {
    const label = params.get(PARAM[place]) ?? ''
    const [lat, lon] = (params.get(`${PARAM[place]}_at`) ?? '').split(',').map(Number)
    form[place] = Number.isFinite(lat) && Number.isFinite(lon) && label ? { label, lat, lon } : { label }
  }
  form.cycleUsedHours = params.get('cycle') ?? '0'
  form.startTime = params.get('start') ?? ''
  form.homeTz = params.get('tz') ?? ''
  for (const field of HEADER_FIELDS) form.header[field] = params.get(field) ?? ''
  return form
}

export function paramsFromForm(form: TripForm): URLSearchParams {
  const params = new URLSearchParams()
  for (const place of PLACES) {
    const value = form[place]
    if (!value.label.trim()) continue
    params.set(PARAM[place], value.label.trim())
    if (value.lat !== undefined && value.lon !== undefined) {
      params.set(`${PARAM[place]}_at`, `${value.lat},${value.lon}`)
    }
  }
  params.set('cycle', form.cycleUsedHours.trim() || '0')
  if (form.startTime) params.set('start', form.startTime)
  if (form.homeTz) params.set('tz', form.homeTz)
  for (const field of HEADER_FIELDS) {
    const value = form.header[field].trim()
    if (value) params.set(field, value)
  }
  return params
}

function placeRequest(value: PlaceValue): PlaceRequest {
  if (value.lat !== undefined && value.lon !== undefined) {
    return { label: value.label.trim(), lat: value.lat, lon: value.lon }
  }
  return { query: value.label.trim() }
}

/** The API request for a form, or null while a required input is missing. */
export function requestFromForm(form: TripForm): PlanRequest | null {
  const cycle = Number(form.cycleUsedHours)
  if (PLACES.some((place) => !form[place].label.trim())) return null
  if (!Number.isFinite(cycle) || cycle < 0 || cycle > 70) return null
  const request: PlanRequest = {
    current: placeRequest(form.current),
    pickup: placeRequest(form.pickup),
    dropoff: placeRequest(form.dropoff),
    cycle_used_hours: cycle,
  }
  if (form.startTime) request.start_time = form.startTime
  if (form.homeTz) request.home_tz = form.homeTz
  for (const field of HEADER_FIELDS) {
    const value = form.header[field].trim()
    if (value) request[field] = value
  }
  return request
}

/** Problems to show before sending anything, keyed by form field. */
export function validateForm(form: TripForm): Partial<Record<string, string>> {
  const errors: Partial<Record<string, string>> = {}
  for (const place of PLACES) {
    const label = form[place].label.trim()
    if (!label) errors[place] = 'Required'
    else if (form[place].lat === undefined && label.length < 3) errors[place] = 'Type at least 3 characters'
  }
  const cycle = Number(form.cycleUsedHours)
  if (form.cycleUsedHours.trim() === '' || !Number.isFinite(cycle) || cycle < 0 || cycle > 70) {
    errors.cycle_used_hours = 'Between 0 and 70 hours'
  }
  return errors
}
