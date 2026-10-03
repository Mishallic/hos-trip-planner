import { Box, Card, Stack, Typography } from '@mui/material'
import { CircleCheck, RotateCcw } from 'lucide-react'

import type { TripPlan } from '../../api/types'
import { Badge, IconChip } from '../../components/CardParts'
import { clockTime, count, miles } from '../../lib/format'
import { color } from '../../theme/tokens'

/** Arrival and the trip in numbers. */
export function VerdictCard({ plan }: { plan: TripPlan }) {
  const { summary } = plan
  const counts = summary.stop_counts

  return (
    <Card sx={{ p: 2.5 }}>
      <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', mb: 2 }}>
        <IconChip tone={summary.restart_needed ? color.amber : color.mint}>
          {summary.restart_needed ? <RotateCcw size={19} strokeWidth={2} /> : <CircleCheck size={20} strokeWidth={2} />}
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

      <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 0.75 }}>
        <Badge label={count(summary.sheets, 'log sheet')} />
        {counts.rest > 0 && <Badge label={count(counts.rest, 'rest')} tone={color.sky} />}
        {counts.break > 0 && <Badge label={count(counts.break, 'break')} />}
        {counts.fuel > 0 && <Badge label={`${counts.fuel} fuel`} tone={color.orange} />}
        {counts.restart > 0 && (
          <Badge
            label={counts.restart === 1 ? '34-hr restart' : `${counts.restart} × 34-hr restarts`}
            tone={color.amber}
          />
        )}
      </Stack>
    </Card>
  )
}
