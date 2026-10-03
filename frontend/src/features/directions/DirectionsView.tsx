import { Box, Card, Stack, Typography } from '@mui/material'
import { Navigation } from 'lucide-react'

import type { TripPlan } from '../../api/types'
import { hm, miles } from '../../lib/format'
import { color, layout, radius } from '../../theme/tokens'

const MOBILE = `@media (max-width: ${layout.mobile - 1}px)`

/** Placeholder: turn-by-turn directions per leg come in a later step. */
export function DirectionsView({ plan }: { plan: TripPlan }) {
  return (
    <Box sx={{ height: '100%', overflowY: 'auto', p: 3, [MOBILE]: { p: 2 } }}>
      <Typography variant="h5" component="h2" sx={{ mb: 2.5 }}>
        Directions
      </Typography>
      <Stack spacing={2} sx={{ maxWidth: 720 }}>
        {plan.route.legs.map((leg) => (
          <Card key={leg.to} sx={{ p: 2.5 }}>
            <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
              <Box sx={{ width: 40, height: 40, borderRadius: `${radius.chip}px`, display: 'grid', placeItems: 'center', background: color.chip, color: color.turquoise }}>
                <Navigation size={20} />
              </Box>
              <Box>
                <Typography variant="h6" component="h3">
                  To {leg.to === 'pickup' ? plan.summary.pickup : plan.summary.dropoff}
                </Typography>
                <Typography variant="body2">
                  {miles(leg.miles)} · {hm(leg.planned_min)} planned driving · {leg.steps.length} steps
                </Typography>
              </Box>
            </Stack>
          </Card>
        ))}
      </Stack>
    </Box>
  )
}
