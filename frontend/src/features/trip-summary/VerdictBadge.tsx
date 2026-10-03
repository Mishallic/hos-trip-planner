import { Chip, Tooltip } from '@mui/material'

import type { TripPlan } from '../../api/types'
import { color } from '../../theme/tokens'
import { verdictFor } from './verdict'

/** The header's one-line answer: when it delivers, or the restart in the way. */
export function VerdictBadge({ plan }: { plan: TripPlan }) {
  const verdict = verdictFor(plan.summary, plan.stops)
  const tone = verdict.tone === 'warn' ? color.amber : color.mint
  return (
    // describeChild: the badge keeps its visible text as its name and the detail
    // becomes its description. Focusable, so the detail is not for mice only.
    <Tooltip title={verdict.detail} describeChild>
      <Chip
        label={verdict.text}
        size="small"
        tabIndex={0}
        sx={{
          color: tone,
          background: `${tone}1A`,
          border: `1px solid ${tone}59`,
          maxWidth: '100%',
          '&:focus-visible': { outline: `2px solid ${color.turquoise}`, outlineOffset: 2 },
        }}
      />
    </Tooltip>
  )
}
