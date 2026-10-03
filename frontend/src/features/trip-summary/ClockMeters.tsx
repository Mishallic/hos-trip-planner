import { Box, Stack, Typography } from '@mui/material'

import type { Clocks } from '../../api/types'
import { hm } from '../../lib/format'
import { color, radius } from '../../theme/tokens'
import { clockTone } from './clockTone'

const METERS: { key: keyof Clocks; label: string; total: number }[] = [
  { key: 'driving_left_min', label: '11-hr drive', total: 660 },
  { key: 'window_left_min', label: '14-hr window', total: 840 },
  { key: 'break_left_min', label: '8-hr to break', total: 480 },
  { key: 'cycle_left_min', label: '70-hr cycle', total: 4200 },
]

/** What is left of each limit at one moment of the trip. */
export function ClockMeters({ clocks }: { clocks: Clocks }) {
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5, mt: 1 }}>
      {METERS.map(({ key, label, total }) => {
        const left = clocks[key]
        const tone = clockTone(left)
        const share = Math.max(0, Math.min(1, left / total))
        return (
          <Box
            key={key}
            role="meter"
            aria-label={label}
            aria-valuemin={0}
            aria-valuemax={total}
            aria-valuenow={left}
            aria-valuetext={`${hm(left)} left`}
            sx={{
              // A column, so the bars of two meters side by side line up at the
              // bottom even when one label has to wrap on a narrow phone.
              display: 'flex',
              flexDirection: 'column',
              p: 1.25,
              borderRadius: `${radius.button}px`,
              background: 'rgba(255, 255, 255, 0.025)',
              border: `1px solid ${tone === color.turquoise ? color.borderSoft : `${tone}66`}`,
              transition: 'border-color 150ms',
            }}
          >
            <Stack
              direction="row"
              sx={{ alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', columnGap: 1 }}
            >
              <Typography variant="caption">{label}</Typography>
              <Typography
                sx={{
                  fontWeight: 700,
                  fontSize: 15,
                  color: tone === color.turquoise ? color.text : tone === color.coral ? color.coralText : tone,
                }}
              >
                {hm(left)}
              </Typography>
            </Stack>
            <Box sx={{ mt: 'auto', pt: 1 }}>
              <Box sx={{ height: 4, borderRadius: 4, background: 'rgba(255,255,255,0.08)' }}>
                <Box
                  sx={{
                    width: `${share * 100}%`,
                    height: '100%',
                    borderRadius: 4,
                    background: tone,
                    transition: 'width 200ms, background 150ms',
                  }}
                />
              </Box>
            </Box>
          </Box>
        )
      })}
    </Box>
  )
}
