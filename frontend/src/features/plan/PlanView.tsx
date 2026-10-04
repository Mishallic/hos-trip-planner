import { Box, ButtonBase, Typography } from '@mui/material'
import { ArrowRight, Map as MapIcon } from 'lucide-react'
import { lazy, type ReactNode, Suspense, useEffect, useRef } from 'react'

import type { TripPlan } from '../../api/types'
import { ErrorBoundary } from '../../components/ErrorBoundary'
import type { StopSelection } from '../../state/selection'
import type { TripForm } from '../../state/urlState'
import { zoneOf } from '../../lib/format'
import { color, gradient, layout, radius } from '../../theme/tokens'
import { StopList } from '../itinerary/StopList'
import { TimelineStrip } from '../itinerary/TimelineStrip'
import { ClocksCard } from '../trip-summary/ClocksCard'
import { VerdictCard } from '../trip-summary/VerdictCard'
import { SAMPLE_TRIPS } from './samples'

// Leaflet loads in its own chunk, only once there is a route to show.
const RouteMap = lazy(() => import('../route-map/RouteMap'))

const MOBILE = `@media (max-width: ${layout.mobile - 1}px)`
/** Too narrow for the sidebar beside a useful map: the map goes on top, the sidebar under it. */
const STACKED = '@media (max-width: 1023px)'
// The clocks stay pinned at the top of the sidebar while the stops scroll under
// them, so selecting a stop never scrolls them away. Only where there is room.
const PIN_CLOCKS = '@media (min-width: 1024px) and (min-height: 600px)'

interface PlanViewProps {
  plan?: TripPlan
  form: ReactNode // the trip form, full or collapsed to one line
  planning: boolean
  /** One selected stop shared by the map, timeline, list and clocks. */
  selection: StopSelection
  /** Plan one of the sample trips offered while the map is empty. */
  onSample: (form: TripForm) => void
}

export function PlanView({ plan, form, planning, selection, onSample }: PlanViewProps) {
  const sidebar = useRef<HTMLDivElement>(null)
  const pinned = useRef<HTMLDivElement>(null)
  const hasPlan = Boolean(plan)

  // The browser scrolls a row into view itself when Tab or Shift+Tab focuses it.
  // Tell the sidebar how much of its top the pinned clocks cover, so that row never
  // ends up underneath them.
  useEffect(() => {
    const side = sidebar.current
    const box = pinned.current
    if (!side || !box || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(() => side.style.setProperty('--pinned-height', `${box.offsetHeight}px`))
    observer.observe(box)
    return () => observer.disconnect()
  }, [hasPlan])

  return (
    <Box
      data-print-light
      sx={{
        display: 'grid',
        gridTemplateColumns: `${layout.sidebar}px minmax(0, 1fr)`,
        height: '100%',
        minHeight: 0,
        // The view scrolls as one; on a phone the page itself does.
        [STACKED]: { gridTemplateColumns: 'minmax(0, 1fr)', gridAutoRows: 'max-content', alignContent: 'start', overflowY: 'auto' },
        [MOBILE]: { height: 'auto', overflowY: 'visible' },
        // On paper: the trip, its summary and every stop, one column, no map.
        '@media print': { display: 'block', height: 'auto' },
      }}
    >
      <Box
        ref={sidebar}
        data-scroll-container
        sx={{
          overflowY: 'auto',
          minWidth: 0,
          p: 2,
          borderRight: `1px solid ${color.borderSoft}`,
          [PIN_CLOCKS]: { scrollPaddingTop: 'calc(var(--pinned-height, 0px) + 12px)' },
          // Mobile: the form comes first until there is a plan, then the results do.
          [STACKED]: { borderRight: 0, overflow: 'visible', order: plan ? 2 : 1 },
          '@media print': { overflow: 'visible', border: 0, p: 0 },
        }}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {plan && (
            <Typography data-print-only variant="h6" component="p" sx={{ display: 'none' }}>
              HOS Trip Planner · {plan.summary.from} → {plan.summary.pickup} → {plan.summary.dropoff}
            </Typography>
          )}
          <Box data-no-print={plan ? true : undefined}>{form}</Box>
          {/* The results can fail to draw; the form above them never goes away. */}
          <ErrorBoundary key={planIdentity(plan)}>
          {plan && <VerdictCard plan={plan} />}
          {plan && (
            <Box
              ref={pinned}
              data-sticky
              sx={{
                [PIN_CLOCKS]: {
                  position: 'sticky',
                  // Sticky offsets count from inside the sidebar's padding; this pins
                  // the box to the sidebar's top edge and its padding covers the gap.
                  top: (theme) => theme.spacing(-2),
                  zIndex: 2,
                  // Painted with the page's own fixed background, so nothing scrolling
                  // underneath shows through around the card.
                  mx: -2,
                  px: 2,
                  mt: -2,
                  pt: 2,
                  background: gradient.page,
                  backgroundColor: color.bgMid,
                  backgroundAttachment: 'fixed',
                },
              }}
            >
              <ClocksCard plan={plan} selectedStop={selection.selected} />
            </Box>
          )}
          {plan && <StopList stops={plan.stops} selection={selection} zone={zoneOf(plan)} />}
          </ErrorBoundary>
        </Box>
      </Box>

      <Box
        data-no-print
        sx={{
          display: 'grid',
          gridTemplateRows: '1fr auto',
          minHeight: 0,
          minWidth: 0,
          p: 2,
          gap: 2,
          [STACKED]: { order: plan ? 1 : 2, gridTemplateRows: plan ? '400px auto' : 'auto', pb: plan ? 0 : 2 },
          [MOBILE]: { gridTemplateRows: plan ? '320px auto' : 'auto' },
        }}
      >
        <ErrorBoundary key={planIdentity(plan)}>
        {plan ? (
          <Suspense fallback={<MapPanel title="Loading the map…" />}>
            <RouteMap plan={plan} selection={selection} />
          </Suspense>
        ) : planning ? (
          <MapPanel
            title="Planning the trip…"
            text="Routing, placing every stop under the hours-of-service rules, and drawing the logs."
          />
        ) : (
          <MapPanel
            title="Your route appears here"
            text="Enter where the truck is, the pickup and the drop-off. Every rest, break and fuel stop is placed for you."
          >
            <SampleTrips onSample={onSample} />
          </MapPanel>
        )}
        {plan && <TimelineStrip plan={plan} selection={selection} />}
        </ErrorBoundary>
      </Box>
    </Box>
  )
}

/** The map's place before there is a map: what goes there, or what is happening. */
function MapPanel({ title, text, children }: { title: string; text?: string; children?: ReactNode }) {
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
        [STACKED]: { minHeight: 320 },
      }}
    >
      <Box sx={{ maxWidth: 440, width: '100%' }}>
        <Box sx={{ color: color.turquoise, display: 'flex', justifyContent: 'center', mb: 1.5 }}>
          <MapIcon size={34} strokeWidth={1.6} />
        </Box>
        <Typography variant="h6" component="p">
          {title}
        </Typography>
        {text && (
          <Typography variant="body2" sx={{ mt: 0.75 }}>
            {text}
          </Typography>
        )}
        {children}
      </Box>
    </Box>
  )
}

/** One click to a full plan: each sample shows a different side of the rules. */
function SampleTrips({ onSample }: { onSample: (form: TripForm) => void }) {
  return (
    <Box component="section" aria-labelledby="sample-trips" sx={{ mt: 3, textAlign: 'left' }}>
      <Typography id="sample-trips" variant="overline" component="h2" sx={{ display: 'block', color: color.textMuted, textAlign: 'center', mb: 1 }}>
        Or try a sample trip
      </Typography>
      <Box component="ul" sx={{ listStyle: 'none', m: 0, p: 0, display: 'grid', gap: 1 }}>
        {SAMPLE_TRIPS.map((sample) => (
          <li key={sample.title}>
            <ButtonBase
              onClick={() => onSample(sample.form)}
              sx={{
                width: '100%',
                justifyContent: 'space-between',
                gap: 1.5,
                px: 2,
                py: 1.25,
                textAlign: 'left',
                borderRadius: `${radius.button}px`,
                border: `1px solid ${color.border}`,
                background: 'rgba(5, 6, 15, 0.35)',
                transition: 'background 120ms, border-color 120ms',
                '&:hover': { background: color.chip, borderColor: color.turquoise },
                '&.Mui-focusVisible': { outline: `2px solid ${color.turquoise}`, outlineOffset: 2 },
              }}
            >
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontSize: 14, fontWeight: 600 }}>{sample.title}</Typography>
                <Typography sx={{ fontSize: 12.5, color: color.textMuted }}>{sample.shows}</Typography>
              </Box>
              <ArrowRight size={18} color={color.turquoise} aria-hidden />
            </ButtonBase>
          </li>
        ))}
      </Box>
    </Box>
  )
}

const planIdentity = (plan?: TripPlan) => (plan ? `${plan.summary.start}|${plan.summary.dropoff_arrival}` : 'none')
