// The shape of POST /api/trips/plan. Times are ISO strings with the home
// terminal's UTC offset; minutes on a log sheet count from that day's midnight.

export type DutyStatus = 'off_duty' | 'sleeper_berth' | 'driving' | 'on_duty'
export type StopKind = 'pre_trip' | 'pickup' | 'dropoff' | 'fuel' | 'break' | 'rest' | 'restart'
export type EventKind = StopKind | 'driving'
export type StopReason =
  | 'driving_limit'
  | 'duty_window'
  | 'break_required'
  | 'cycle_limit'
  | 'fuel_interval'

export interface Summary {
  from: string
  pickup: string
  dropoff: string
  total_miles: number
  driving: string
  driving_min: number
  elapsed: string
  elapsed_min: number
  start: string
  pickup_arrival: string
  dropoff_arrival: string
  end: string
  stop_counts: Record<StopKind, number>
  restart_needed: boolean
  sheets: number
}

export interface Stop {
  kind: StopKind
  status: DutyStatus
  start: string
  end: string
  duration_min: number
  mile: number
  lat: number
  lon: number
  place: string | null
  reason: StopReason | null
  explanation: string
}

export interface Clocks {
  driving_left_min: number
  window_left_min: number
  break_left_min: number
  cycle_left_min: number
}

export interface TimelineEvent {
  kind: EventKind
  status: DutyStatus
  start: string
  end: string
  start_mile: number
  end_mile: number
  clocks: Clocks
}

export interface RouteStep {
  instruction: string
  miles: number
  lat: number
  lon: number
}

export interface RouteLeg {
  to: 'pickup' | 'dropoff'
  miles: number
  router_min: number
  planned_min: number
  steps: RouteStep[]
}

export interface Remark {
  minute: number
  time: string
  status: DutyStatus
  label: string
  place: string | null
  mile: number
  reasons: StopReason[]
}

export interface DailyLog {
  date: string
  starts_at: string
  segments: { status: DutyStatus; start: number; end: number }[]
  totals_min: Record<DutyStatus, number>
  totals_hm: Record<DutyStatus, string>
  on_duty_hours: number
  miles_today: number
  from: string | null
  to: string | null
  remarks: Remark[]
  brackets: { start: number; end: number; place: string | null }[]
  recap: {
    on_duty_today_min: number
    cycle_used_min: number
    available_tomorrow_min: number
    approximate: boolean
  }
  /** Why a sheet that looks over a limit is not, e.g. 13 hours of driving across two shifts. */
  notes?: string[]
}

export interface LogHeader {
  driver?: string
  carrier?: string
  truck?: string
  trailer?: string
  shipper?: string
  commodity?: string
  load_id?: string
  home_terminal?: string
  time_zone: string
  utc_offset: string
}

export interface TripPlan {
  summary: Summary
  /** Things to know about the plan, e.g. a ferry crossing planned as driving. */
  warnings?: string[]
  stops: Stop[]
  timeline: TimelineEvent[]
  route: { polyline: string; legs: RouteLeg[] }
  logs: DailyLog[]
  log_header: LogHeader
}
