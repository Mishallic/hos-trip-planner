import {
  Box,
  Card,
  Chip,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material'
import { CircleCheck, ListChecks, Map as MapIcon, Truck } from 'lucide-react'
import { type ReactNode, useMemo } from 'react'

import type { Clocks, Stop, TripPlan } from '../../api/types'
import { clockTime, hm, miles, STOP_LABEL } from '../../lib/format'
import { decodePolyline } from '../../lib/polyline'
import { color, layout, radius, stopColor } from '../../theme/tokens'
import { StopIcon } from './StopIcon'

const MOBILE = `@media (max-width: ${layout.mobile - 1}px)`

interface PlanViewProps {
  plan?: TripPlan
  form: ReactNode // the trip form, full or collapsed to one line
  planning: boolean
}

export function PlanView({ plan, form, planning }: PlanViewProps) {
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
          {plan && <StopList stops={plan.stops} />}
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
        {plan ? <MapPreview plan={plan} /> : <MapEmpty planning={planning} />}
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

function StopList({ stops }: { stops: Stop[] }) {
  return (
    <Card sx={{ p: 2.5 }}>
      <CardHeading
        Icon={ListChecks}
        title="Stops"
        subtitle="Every stop and the rule behind it"
        hint={`${stops.length}`}
      />
      <Stack divider={<Box sx={{ borderTop: `1px solid ${color.borderSoft}` }} />}>
        {stops.map((stop) => (
          <Stack key={`${stop.kind}-${stop.start}`} direction="row" spacing={1.5} sx={{ py: 1.25 }}>
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

/** Placeholder until the Leaflet map (chunk 16): the route drawn from its polyline. */
function MapPreview({ plan }: { plan: TripPlan }) {
  const { path, project } = useMemo(() => {
    const points = decodePolyline(plan.route.polyline)
    const lats = points.map((p) => p[0])
    const lons = points.map((p) => p[1])
    const [minLat, maxLat] = [Math.min(...lats), Math.max(...lats)]
    const [minLon, maxLon] = [Math.min(...lons), Math.max(...lons)]
    const k = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180)
    const width = (maxLon - minLon) * k
    const height = maxLat - minLat
    const scale = 860 / Math.max(width, height * 1.6)
    const project = ([lat, lon]: [number, number]) => [
      70 + ((lon - minLon) * k * scale * 1000) / 1000 + (860 - width * scale) / 2,
      70 + (maxLat - lat) * scale + (520 - height * scale) / 2,
    ]
    const path = points.map((p, i) => `${i ? 'L' : 'M'}${project(p).map((v) => v.toFixed(1)).join(' ')}`).join('')
    return { path, project }
  }, [plan.route.polyline])

  const first = plan.stops[0]
  const last = plan.stops[plan.stops.length - 1]
  return (
    <Box
      sx={{
        position: 'relative',
        borderRadius: `${radius.panel}px`,
        overflow: 'hidden',
        border: `1px solid ${color.border}`,
        background: `radial-gradient(120% 100% at 35% 25%, #2A4352 0%, #22333B 50%, #1A2830 100%)`,
        minHeight: 0,
      }}
    >
      <svg viewBox="0 0 1000 660" preserveAspectRatio="xMidYMid meet" width="100%" height="100%">
        <defs>
          <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M40 0H0V40" fill="none" stroke="rgba(196,208,212,0.07)" />
          </pattern>
          <filter id="glow" x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="3" />
          </filter>
        </defs>
        <rect width="1000" height="660" fill="url(#grid)" />
        <path d={path} fill="none" stroke={color.turquoise} strokeOpacity="0.35" strokeWidth="8" filter="url(#glow)" />
        <path d={path} fill="none" stroke="#FFFFFF" strokeWidth="2.6" strokeLinejoin="round" />
        {plan.stops
          .filter((s) => s.kind !== 'pre_trip')
          .map((s) => {
            const [x, y] = project([s.lat, s.lon])
            return <circle key={s.start} cx={x} cy={y} r="6" fill={stopColor[s.kind]} stroke="#05060F" strokeWidth="2" />
          })}
        {[
          { stop: first, letter: 'A', fill: color.coral },
          { stop: last, letter: 'B', fill: color.turquoise },
        ].map(({ stop, letter, fill }) => {
          const [x, y] = project([stop.lat, stop.lon])
          return (
            <g key={letter} transform={`translate(${x} ${y})`}>
              <path d="M0 0 C-14 -18 -16 -26 -16 -32 a16 16 0 1 1 32 0 c0 6 -2 14 -16 32Z" fill={fill} stroke="#05060F" strokeWidth="1.5" />
              <text x="0" y="-27" textAnchor="middle" fontSize="16" fontWeight="800" fill="#FFFFFF" fontFamily="Manrope Variable">
                {letter}
              </text>
              <text x="0" y="24" textAnchor="middle" fontSize="15" fontWeight="700" fill="#FFFFFF" fontFamily="DM Sans Variable" stroke="#0E1A21" strokeWidth="4" paintOrder="stroke" strokeLinejoin="round">
                {stop.place}
              </text>
            </g>
          )
        })}
      </svg>
      <Chip
        size="small"
        label="Route preview · interactive map next"
        sx={{
          position: 'absolute',
          top: 14,
          left: 14,
          background: 'rgba(5, 6, 15, 0.7)',
          color: color.textSecondary,
          border: `1px solid ${color.borderSoft}`,
        }}
      />
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
