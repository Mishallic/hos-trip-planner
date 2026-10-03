import {
  Box,
  Card,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material'
import { CircleCheck, ListChecks, Map as MapIcon, Truck } from 'lucide-react'
import { lazy, type ReactNode, Suspense, useEffect, useRef } from 'react'

import type { Clocks, Stop, TripPlan } from '../../api/types'
import { clockTime, hm, miles, STOP_LABEL } from '../../lib/format'
import { color, layout, radius, stopColor } from '../../theme/tokens'
import { StopIcon } from './StopIcon'

// Leaflet loads in its own chunk, only once there is a route to show.
const RouteMap = lazy(() => import('../route-map/RouteMap'))

const MOBILE = `@media (max-width: ${layout.mobile - 1}px)`

interface PlanViewProps {
  plan?: TripPlan
  form: ReactNode // the trip form, full or collapsed to one line
  planning: boolean
  selectedStop: number | null
  onSelectStop: (index: number) => void
}

export function PlanView({ plan, form, planning, selectedStop, onSelectStop }: PlanViewProps) {
  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: `${layout.sidebar}px minmax(0, 1fr)`,
        height: '100%',
        minHeight: 0,
        [MOBILE]: { gridTemplateColumns: 'minmax(0, 1fr)', height: 'auto' },
      }}
    >
      <Box
        data-scroll-container
        sx={{
          overflowY: 'auto',
          minWidth: 0,
          p: 2,
          borderRight: `1px solid ${color.borderSoft}`,
          // Mobile: the form comes first until there is a plan, then the results do.
          [MOBILE]: { borderRight: 0, overflow: 'visible', order: plan ? 2 : 1 },
        }}
      >
        <Stack spacing={2}>
          {form}
          {plan && <VerdictCard plan={plan} />}
          {plan && <StopList stops={plan.stops} selected={selectedStop} onSelect={onSelectStop} />}
        </Stack>
      </Box>

      <Box
        sx={{
          display: 'grid',
          gridTemplateRows: '1fr auto',
          minHeight: 0,
          p: 2,
          gap: 2,
          [MOBILE]: { order: plan ? 1 : 2, gridTemplateRows: '320px auto', pb: plan ? 0 : 2 },
        }}
      >
        {plan ? (
          <Suspense fallback={<MapEmpty planning />}>
            <RouteMap plan={plan} selectedStop={selectedStop} onSelectStop={onSelectStop} />
          </Suspense>
        ) : (
          <MapEmpty planning={planning} />
        )}
        {plan && <TimelineStrip plan={plan} />}
      </Box>
    </Box>
  )
}

function CardHeading({
  Icon,
  title,
  subtitle,
  hint,
}: {
  Icon: typeof Truck
  title: string
  subtitle: string
  hint?: string
}) {
  return (
    <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', mb: 2 }}>
      <IconChip>
        <Icon size={19} strokeWidth={1.9} />
      </IconChip>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="h6" component="h2" sx={{ lineHeight: 1.25 }}>
          {title}
        </Typography>
        <Typography variant="subtitle2" sx={{ fontSize: 12.5 }}>
          {subtitle}
        </Typography>
      </Box>
      {hint && <Typography variant="caption">{hint}</Typography>}
    </Stack>
  )
}

function IconChip({ children, tone = color.turquoise }: { children: ReactNode; tone?: string }) {
  return (
    <Box
      sx={{
        width: 40,
        height: 40,
        flexShrink: 0,
        borderRadius: `${radius.chip}px`,
        display: 'grid',
        placeItems: 'center',
        color: tone,
        background: `${tone}1A`,
        border: `1px solid ${tone}40`,
      }}
    >
      {children}
    </Box>
  )
}

/** Small uppercase badge on a tinted pill, like the feature cards' "ESSENTIAL". */
function Badge({ label, tone = color.turquoise }: { label: string; tone?: string }) {
  return (
    <Box
      component="span"
      sx={{
        px: 1,
        py: 0.25,
        borderRadius: `${radius.pill}px`,
        fontSize: 10.5,
        fontWeight: 700,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        color: tone,
        background: `${tone}1A`,
        border: `1px solid ${tone}33`,
      }}
    >
      {label}
    </Box>
  )
}

function VerdictCard({ plan }: { plan: TripPlan }) {
  const { summary, timeline } = plan
  const counts = summary.stop_counts
  return (
    <Card sx={{ p: 2.5 }}>
      <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', mb: 2 }}>
        <IconChip tone={color.mint}>
          <CircleCheck size={20} strokeWidth={2} />
        </IconChip>
        <Box>
          <Typography variant="h6" component="h2" sx={{ lineHeight: 1.2 }}>
            Arrives {clockTime(summary.dropoff_arrival)}
          </Typography>
          <Typography variant="body2">
            {miles(summary.total_miles)} · {summary.driving} driving · {summary.elapsed} total
          </Typography>
        </Box>
      </Stack>

      <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 0.75, mb: 2.5 }}>
        <Badge label={`${summary.sheets} log sheets`} />
        {counts.rest > 0 && <Badge label={`${counts.rest} rests`} tone={color.sky} />}
        {counts.break > 0 && <Badge label={`${counts.break} breaks`} />}
        {counts.fuel > 0 && <Badge label={`${counts.fuel} fuel`} tone={color.orange} />}
        {summary.restart_needed && <Badge label="34-hr restart" tone={color.amber} />}
      </Stack>

      <Typography variant="overline" sx={{ color: color.textMuted }}>
        Driver's clocks at the start
      </Typography>
      <ClockMeters clocks={timeline[0].clocks} />
    </Card>
  )
}

const METERS: { key: keyof Clocks; label: string; total: number }[] = [
  { key: 'driving_left_min', label: '11-hr drive', total: 660 },
  { key: 'window_left_min', label: '14-hr window', total: 840 },
  { key: 'break_left_min', label: '8-hr to break', total: 480 },
  { key: 'cycle_left_min', label: '70-hr cycle', total: 4200 },
]

function ClockMeters({ clocks }: { clocks: Clocks }) {
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5, mt: 1 }}>
      {METERS.map(({ key, label, total }) => {
        const left = clocks[key]
        const share = Math.max(0, Math.min(1, left / total))
        const tone = share > 0.25 ? color.turquoise : share > 0.1 ? color.orange : color.coral
        return (
          <Box
            key={key}
            sx={{
              p: 1.25,
              borderRadius: `${radius.button}px`,
              background: 'rgba(255, 255, 255, 0.025)',
              border: `1px solid ${color.borderSoft}`,
            }}
          >
            <Stack direction="row" sx={{ alignItems: 'baseline', justifyContent: 'space-between' }}>
              <Typography variant="caption">{label}</Typography>
              <Typography sx={{ fontWeight: 700, fontSize: 15 }}>{hm(left)}</Typography>
            </Stack>
            <Box sx={{ mt: 1, height: 4, borderRadius: 4, background: 'rgba(255,255,255,0.08)' }}>
              <Box sx={{ width: `${share * 100}%`, height: '100%', borderRadius: 4, background: tone }} />
            </Box>
          </Box>
        )
      })}
    </Box>
  )
}

interface StopListProps {
  stops: Stop[]
  selected: number | null
  onSelect: (index: number) => void
}

function StopList({ stops, selected, onSelect }: StopListProps) {
  const rows = useRef<(HTMLDivElement | null)[]>([])
  // Bring the selected stop into view inside the sidebar only. On mobile the page
  // itself scrolls, and jumping away from the map the user just tapped would be wrong.
  useEffect(() => {
    const row = selected === null ? null : rows.current[selected]
    const sidebar = row?.closest<HTMLElement>('[data-scroll-container]')
    if (!row || !sidebar || sidebar.scrollHeight <= sidebar.clientHeight) return
    const rowBox = row.getBoundingClientRect()
    const box = sidebar.getBoundingClientRect()
    if (rowBox.top < box.top) sidebar.scrollBy({ top: rowBox.top - box.top - 12, behavior: 'smooth' })
    else if (rowBox.bottom > box.bottom) sidebar.scrollBy({ top: rowBox.bottom - box.bottom + 12, behavior: 'smooth' })
  }, [selected])

  return (
    <Card sx={{ p: 2.5 }}>
      <CardHeading
        Icon={ListChecks}
        title="Stops"
        subtitle="Every stop and the rule behind it"
        hint={`${stops.length}`}
      />
      <Stack divider={<Box sx={{ borderTop: `1px solid ${color.borderSoft}` }} />}>
        {stops.map((stop, index) => (
          <Stack
            key={`${stop.kind}-${stop.start}`}
            ref={(row: HTMLDivElement | null) => {
              rows.current[index] = row
            }}
            direction="row"
            spacing={1.5}
            role="button"
            tabIndex={0}
            aria-pressed={index === selected}
            onClick={() => onSelect(index)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault()
                onSelect(index)
              }
            }}
            sx={{
              py: 1.25,
              px: 1,
              mx: -1,
              borderRadius: `${radius.button}px`,
              cursor: 'pointer',
              outline: 'none',
              background: index === selected ? 'rgba(64, 224, 208, 0.08)' : 'transparent',
              boxShadow: index === selected ? `inset 3px 0 0 ${stopColor[stop.kind]}` : 'none',
              '&:hover': { background: 'rgba(255, 255, 255, 0.03)' },
              '&:focus-visible': { boxShadow: `0 0 0 2px ${color.turquoise}` },
            }}
          >
            <StopIcon kind={stop.kind} />
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Stack direction="row" spacing={1} sx={{ justifyContent: 'space-between' }}>
                <Typography sx={{ fontWeight: 600, fontSize: 14 }} noWrap>
                  <Box component="span" sx={{ color: stopColor[stop.kind] }}>
                    {STOP_LABEL[stop.kind]}
                  </Box>{' '}
                  <Box component="span" sx={{ color: color.textMuted, fontWeight: 500 }}>
                    ({stop.place ?? `mile ${stop.mile}`})
                  </Box>
                </Typography>
                <Typography sx={{ fontSize: 13, color: color.textSecondary, whiteSpace: 'nowrap' }}>
                  {clockTime(stop.start)}
                </Typography>
              </Stack>
              <Typography variant="body2" sx={{ fontSize: 12.5, mt: 0.25 }}>
                {stop.explanation}
              </Typography>
            </Box>
          </Stack>
        ))}
      </Stack>
    </Card>
  )
}

function MapEmpty({ planning }: { planning: boolean }) {
  return (
    <Box
      sx={{
        borderRadius: `${radius.panel}px`,
        border: `1px dashed ${color.border}`,
        background: `radial-gradient(120% 100% at 35% 25%, #2A4352 0%, #22333B 50%, #1A2830 100%)`,
        display: 'grid',
        placeItems: 'center',
        textAlign: 'center',
        p: 3,
        minHeight: 0,
      }}
    >
      <Box sx={{ maxWidth: 360 }}>
        <Box sx={{ color: color.turquoise, display: 'flex', justifyContent: 'center', mb: 1.5 }}>
          <MapIcon size={34} strokeWidth={1.6} />
        </Box>
        <Typography variant="h6" component="p">
          {planning ? 'Planning the trip…' : 'Your route appears here'}
        </Typography>
        <Typography variant="body2" sx={{ mt: 0.75 }}>
          {planning
            ? 'Routing, placing every stop under the hours-of-service rules, and drawing the logs.'
            : 'Enter where the truck is, the pickup and the drop-off. Every rest, break and fuel stop is placed for you.'}
        </Typography>
      </Box>
    </Box>
  )
}

/** One line for the whole trip, like the driver app's progress strip. */
function TimelineStrip({ plan }: { plan: TripPlan }) {
  const total = plan.summary.total_miles
  return (
    <Card sx={{ px: 2.5, py: 1.75 }}>
      <Stack direction="row" spacing={2} sx={{ alignItems: 'center' }}>
        <Box sx={{ color: color.textSecondary, display: 'flex' }}>
          <Truck size={22} strokeWidth={1.8} />
        </Box>
        <Box sx={{ position: 'relative', flex: 1, height: 22 }}>
          <Box sx={{ position: 'absolute', top: 10, left: 0, right: 0, height: 2, background: 'rgba(196,208,212,0.22)', borderRadius: 2 }} />
          {plan.stops
            .filter((s) => s.kind !== 'pre_trip')
            .map((s) => (
              <Tooltip key={s.start} title={`${STOP_LABEL[s.kind]} · ${s.place ?? ''} · ${clockTime(s.start)}`}>
                <Box
                  sx={{
                    position: 'absolute',
                    top: 4,
                    left: `calc(${(s.mile / total) * 100}% - 7px)`,
                    width: 14,
                    height: 14,
                    borderRadius: '50%',
                    background: stopColor[s.kind],
                    border: '2px solid #0A1220',
                    boxShadow: `0 0 0 3px ${stopColor[s.kind]}33`,
                  }}
                />
              </Tooltip>
            ))}
        </Box>
        <Typography sx={{ fontWeight: 700, whiteSpace: 'nowrap' }}>{miles(total)}</Typography>
      </Stack>
    </Card>
  )
}
