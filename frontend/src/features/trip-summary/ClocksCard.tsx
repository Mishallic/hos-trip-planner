import { Box, Card, Typography } from '@mui/material'

import type { TripPlan } from '../../api/types'
import { clockTime, STOP_LABEL, zoneOf } from '../../lib/format'
import { color, stopTextColor } from '../../theme/tokens'
import { ClockMeters } from './ClockMeters'

/** The driver's clocks as the selected stop begins; at the start of the trip by default. */
export function ClocksCard({ plan, selectedStop }: { plan: TripPlan; selectedStop: number | null }) {
  const { timeline, stops } = plan
  const stop = selectedStop === null ? undefined : stops[selectedStop]
  const event = stop && timeline.find((e) => e.start === stop.start && e.kind === stop.kind)
  const clocks = (event ?? timeline[0]).clocks
  const where = stop ?? stops[0]

  return (
    <Card sx={{ p: 2.5 }}>
      <Typography variant="overline" component="h2" sx={{ color: color.textMuted, display: 'block' }}>
        Driver's clocks
      </Typography>
      <Typography aria-live="polite" sx={{ fontSize: 13.5, fontWeight: 600, lineHeight: 1.4 }}>
        {stop ? (
          <>
            At{' '}
            <Box component="span" sx={{ color: stopTextColor[stop.kind] }}>
              {STOP_LABEL[stop.kind]}
            </Box>
          </>
        ) : (
          'At the start'
        )}
        <Box component="span" sx={{ color: color.textMuted, fontWeight: 500 }}>
          {' '}
          · {where.place ?? `mile ${where.mile}`} ·{' '}
          <Box component="span" sx={{ whiteSpace: 'nowrap' }}>
            {clockTime(where.start)} {zoneOf(plan)}
          </Box>
        </Box>
      </Typography>
      <ClockMeters clocks={clocks} />
      {/* One line either way, so the card keeps its height when a stop is selected. */}
      <Typography data-no-print variant="caption" component="p" noWrap sx={{ mt: 1 }}>
        {stop ? 'Time left on each limit as this stop begins.' : 'Select a stop to see the clocks there.'}
      </Typography>
    </Card>
  )
}
