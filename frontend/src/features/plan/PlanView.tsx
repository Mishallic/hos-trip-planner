import { Box, Typography } from '@mui/material'
import { Map as MapIcon } from 'lucide-react'
import { lazy, type ReactNode, Suspense, useEffect, useRef } from 'react'

import type { TripPlan } from '../../api/types'
import type { StopSelection } from '../../state/selection'
import { ErrorBoundary } from '../../components/ErrorBoundary'
import { color, gradient, layout, radius } from '../../theme/tokens'
import { StopList } from '../itinerary/StopList'
import { TimelineStrip } from '../itinerary/TimelineStrip'
import { ClocksCard } from '../trip-summary/ClocksCard'
import { VerdictCard } from '../trip-summary/VerdictCard'

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
}

export function PlanView({ plan, form, planning, selection }: PlanViewProps) {
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
      sx={{
        display: 'grid',
        gridTemplateColumns: `${layout.sidebar}px minmax(0, 1fr)`,
        height: '100%',
        minHeight: 0,
        // The view scrolls as one; on a phone the page itself does.
        [STACKED]: { gridTemplateColumns: 'minmax(0, 1fr)', gridAutoRows: 'max-content', alignContent: 'start', overflowY: 'auto' },
        [MOBILE]: { height: 'auto', overflowY: 'visible' },
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
        }}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {form}
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
          {plan && <StopList stops={plan.stops} selection={selection} />}
          </ErrorBoundary>
        </Box>
      </Box>

      <Box
        sx={{
          display: 'grid',
          gridTemplateRows: '1fr auto',
          minHeight: 0,
          minWidth: 0,
          p: 2,
          gap: 2,
          [STACKED]: { order: plan ? 1 : 2, gridTemplateRows: '400px auto', pb: plan ? 0 : 2 },
          [MOBILE]: { gridTemplateRows: '320px auto' },
        }}
      >
        <ErrorBoundary key={planIdentity(plan)}>
        {plan ? (
          <Suspense fallback={<MapEmpty planning />}>
            <RouteMap plan={plan} selection={selection} />
          </Suspense>
        ) : (
          <MapEmpty planning={planning} />
        )}
        {plan && <TimelineStrip plan={plan} selection={selection} />}
        </ErrorBoundary>
      </Box>
    </Box>
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

const planIdentity = (plan?: TripPlan) => (plan ? `${plan.summary.start}|${plan.summary.dropoff_arrival}` : 'none')
