import { Box, Stack, Typography } from '@mui/material'

import type { TripPlan } from '../../api/types'
import { color, layout, radius, shadow } from '../../theme/tokens'

const MOBILE = `@media (max-width: ${layout.mobile - 1}px)`
const LINES = ['Off duty', 'Sleeper berth', 'Driving', 'On duty']

/** Placeholder: each day as a light "paper" sheet on the dark page (chunks 18-20 draw them). */
export function LogsView({ plan }: { plan: TripPlan }) {
  return (
    <Box sx={{ height: '100%', overflowY: 'auto', p: 3, [MOBILE]: { p: 2 } }}>
      <Stack
        direction="row"
        sx={{ alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', columnGap: 2, rowGap: 0.5, mb: 2.5 }}
      >
        <Typography variant="h5" component="h2" sx={{ whiteSpace: 'nowrap' }}>
          Daily logs
        </Typography>
        <Typography variant="body2">
          {plan.logs.length} sheets · times in {plan.log_header.time_zone} (UTC{plan.log_header.utc_offset})
        </Typography>
      </Stack>
      <Stack spacing={3} sx={{ maxWidth: 1100, mx: 'auto' }}>
        {plan.logs.map((log, index) => (
          <Box
            key={log.date}
            sx={{
              background: color.paper,
              color: color.paperInk,
              borderRadius: `${radius.button}px`,
              boxShadow: shadow.paper,
              p: 3,
              [MOBILE]: { p: 2 },
            }}
          >
            <Stack direction="row" sx={{ justifyContent: 'space-between', mb: 2 }}>
              <Typography sx={{ fontWeight: 800, fontFamily: 'Manrope Variable', color: color.paperInk }}>
                Driver's Daily Log · Day {index + 1}
              </Typography>
              <Typography sx={{ fontWeight: 600, color: color.paperInk }}>{log.date}</Typography>
            </Stack>
            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: '110px 1fr 56px',
                rowGap: 0,
                border: `1px solid ${color.paperInk}`,
                [MOBILE]: { gridTemplateColumns: '78px 1fr 44px' },
              }}
            >
              {LINES.map((line, i) => (
                <Box key={line} sx={{ display: 'contents' }}>
                  <Typography sx={{ fontSize: 12, fontWeight: 600, p: 1, color: color.paperInk, borderTop: i ? `1px solid ${color.paperInk}` : 0 }}>
                    {line}
                  </Typography>
                  <Box
                    sx={{
                      borderTop: i ? `1px solid ${color.paperInk}` : 0,
                      borderLeft: `1px solid ${color.paperInk}`,
                      backgroundImage: `repeating-linear-gradient(90deg, rgba(20,32,43,0.35) 0 1px, transparent 1px calc(100% / 24))`,
                    }}
                  />
                  <Typography sx={{ fontSize: 12, fontWeight: 700, p: 1, textAlign: 'right', color: color.paperInk, borderTop: i ? `1px solid ${color.paperInk}` : 0, borderLeft: `1px solid ${color.paperInk}` }}>
                    {Object.values(log.totals_hm)[i]}
                  </Typography>
                </Box>
              ))}
            </Box>
            <Typography sx={{ mt: 1.5, fontSize: 12, color: '#55606A' }}>
              Grid, duty line, remarks and recap are drawn here in a later step.
            </Typography>
          </Box>
        ))}
      </Stack>
    </Box>
  )
}
