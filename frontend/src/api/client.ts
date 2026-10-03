import type { TripPlan } from './types'

export interface PlaceOption {
  label: string
  lat: number
  lon: number
}

export type PlaceRequest = { label: string; lat: number; lon: number } | { query: string }

export interface PlanRequest {
  current: PlaceRequest
  pickup: PlaceRequest
  dropoff: PlaceRequest
  cycle_used_hours: number
  start_time?: string
  home_tz?: string
  driver?: string
  carrier?: string
  truck?: string
  trailer?: string
  shipper?: string
  commodity?: string
  load_id?: string
  home_terminal?: string
}

/** An error from the API, with the field it concerns when there is one. */
export class ApiError extends Error {
  status: number
  code: string
  field?: string
  fields?: Record<string, unknown>
  retryAfter?: number

  constructor(status: number, body: unknown) {
    const error = (body as { error?: Record<string, unknown> })?.error ?? {}
    super(String(error.message ?? 'Something went wrong. Try again.'))
    this.status = status
    this.code = String(error.code ?? 'unknown')
    this.field = error.field as string | undefined
    this.fields = error.fields as Record<string, unknown> | undefined
    this.retryAfter = error.retry_after as number | undefined
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api/${path}`, init)
  } catch {
    throw new ApiError(0, { error: { code: 'network', message: 'Cannot reach the server. Check your connection.' } })
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, body)
  return body as T
}

export function planTrip(body: PlanRequest, signal?: AbortSignal): Promise<TripPlan> {
  return request<TripPlan>('trips/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
}

export async function searchPlaces(query: string, signal?: AbortSignal): Promise<PlaceOption[]> {
  const params = new URLSearchParams({ q: query })
  const { places } = await request<{ places: PlaceOption[] }>(`places?${params}`, { signal })
  return places
}
