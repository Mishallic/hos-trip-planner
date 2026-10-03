import { Box, Stack, Typography } from '@mui/material'
import { useEffect, useRef, useState } from 'react'

import type { DailyLog, TripPlan } from '../../api/types'
import type { StopSelection } from '../../state/selection'
import { color, layout, radius, shadow } from '../../theme/tokens'
import { LogSheet } from '../eld-log/LogSheet'
import { minuteX, SHEET, stopOnSheet } from '../eld-log/logGeometry'

const MOBILE = `@media (max-width: ${layout.mobile - 1}px)`
/** Narrower than this the labels get too small: the sheet scrolls sideways in its card instead. */
const SHEET_MIN_WIDTH = 820

/** Every day of the trip as a paper log sheet on the dark page. */
export function LogsView({ plan, selection }: { plan: TripPlan; selection: StopSelection }) {
  const stop = selection.selected === null ? undefined : plan.stops[selection.selected]
  const spans = plan.logs.map((log) => (stop ? stopOnSheet(stop, log) : null))

  const sheets = useRef<(HTMLElement | null)[]>([])
  const scrollers = useRef<(HTMLElement | null)[]>([])
  const scrolls = useOverflows(scrollers)

  // Opening the logs with a stop selected shows it: the first day it falls on, and
  // on a sheet too wide for the screen, the part of each day that holds it.
  useEffect(() => {
    if (!stop) return
    const onSheets = plan.logs.map((log) => stopOnSheet(stop, log))
    onSheets.forEach((span, index) => {
      const scroller = scrollers.current[index]
      const sheet = scroller?.firstElementChild as HTMLElement | null
      if (!span || !scroller || !sheet || scroller.scrollWidth <= scroller.clientWidth) return
      const x = sheet.offsetLeft + (minuteX(span.start) / SHEET.width) * sheet.clientWidth
      scroller.scrollLeft = Math.max(0, x - scroller.clientWidth / 4)
    })
    const first = onSheets.findIndex(Boolean)
    if (first > 0) sheets.current[first]?.scrollIntoView({ block: 'start' })
  }, [stop, plan.logs])

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
      <Stack spacing={3} sx={{ maxWidth: 1100, mx: 'auto', minWidth: 0 }}>
        {plan.logs.map((log, index) => (
          <Box
            key={log.date}
            component="section"
            aria-label={`Day ${index + 1}, ${longDate(log)}`}
            ref={(node: HTMLElement | null) => {
              sheets.current[index] = node
            }}
            sx={{
              position: 'relative', // holds the sheet's screen-reader list
              minWidth: 0,
              scrollMarginTop: 16,
              background: color.paper,
              color: color.paperInk,
              borderRadius: `${radius.button}px`,
              boxShadow: shadow.paper,
              p: 3,
              [MOBILE]: { p: 2 },
            }}
          >
            <Stack
              direction="row"
              sx={{ justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', columnGap: 2, mb: 1.5 }}
            >
              <Typography sx={{ fontWeight: 800, fontFamily: 'Manrope Variable', color: color.paperInk }}>
                Driver's Daily Log · Day {index + 1}
              </Typography>
              <Typography sx={{ fontWeight: 600, fontSize: 14, color: color.paperInk }}>{longDate(log)}</Typography>
            </Stack>
            <Box
              ref={(node: HTMLElement | null) => {
                scrollers.current[index] = node
              }}
              sx={{ overflowX: 'auto', mx: -1, px: 1, pb: 0.5 }}
            >
              <Box sx={{ minWidth: SHEET_MIN_WIDTH }}>
                <LogSheet log={log} selected={spans[index]} />
              </Box>
            </Box>
            {scrolls && (
              <Typography sx={{ mt: 1, fontSize: 12, color: color.paperMuted }}>Scroll sideways for the whole day.</Typography>
            )}
          </Box>
        ))}
      </Stack>
    </Box>
  )
}

/** Whether the sheets are wider than their cards, kept up to date as the window resizes. */
function useOverflows(scrollers: { current: (HTMLElement | null)[] }): boolean {
  const [overflows, setOverflows] = useState(false)
  useEffect(() => {
    const scroller = scrollers.current[0]
    if (!scroller || typeof ResizeObserver === 'undefined') return
    // Every sheet has the same width, so the first one speaks for all.
    const observer = new ResizeObserver(() => setOverflows(scroller.scrollWidth > scroller.clientWidth + 1))
    observer.observe(scroller)
    return () => observer.disconnect()
  }, [scrollers])
  return overflows
}

/** "Mon 5 Oct 2026": the sheet's own date, never shifted by the viewer's time zone. */
function longDate(log: DailyLog): string {
  return new Date(`${log.date}T12:00:00Z`).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  })
}
