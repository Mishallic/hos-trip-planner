import { Box, Button, GlobalStyles, Stack, Tab, Tabs, Typography } from '@mui/material'
import { Printer } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import type { DailyLog, TripPlan } from '../../api/types'
import type { StopSelection } from '../../state/selection'
import { color, layout, radius, shadow } from '../../theme/tokens'
import { LogSheet } from '../eld-log/LogSheet'
import { minuteX, SHEET, stopOnSheet } from '../eld-log/logGeometry'

const MOBILE = `@media (max-width: ${layout.mobile - 1}px)`
const PRINT = '@media print'
/** Narrower than this the labels get too small: the sheet scrolls sideways in its card instead. */
const SHEET_MIN_WIDTH = 820

/**
 * The trip's daily logs: one tab per day on screen, every day on its own page in print.
 * A selected stop opens its day, scrolled to it.
 */
export function LogsView({ plan, selection }: { plan: TripPlan; selection: StopSelection }) {
  const stop = selection.selected === null ? undefined : plan.stops[selection.selected]
  const spans = plan.logs.map((log) => (stop ? stopOnSheet(stop, log) : null))
  // A day whose cycle count dropped below yesterday's plus today's work had a 34-hour
  // restart; from then on the recap counts from zero, not from the hours entered.
  const restartBy = plan.logs.map((log, i) => {
    const before = plan.logs[i - 1]?.recap.cycle_used_min
    return before !== undefined && log.recap.cycle_used_min < before + log.recap.on_duty_today_min
  })
  const sinceRestart = restartBy.map((_, i) => restartBy.slice(0, i + 1).some(Boolean))

  const [chosen, setDay] = useState(() => Math.max(0, spans.findIndex(Boolean)))
  // App remounts this view for a new plan; the clamp only guards a shorter one.
  const day = Math.min(chosen, plan.logs.length - 1)
  const scrollers = useRef<(HTMLElement | null)[]>([])
  const scrolls = useOverflows(scrollers, day)

  // On a sheet too wide for the screen, show the part of the day that holds the stop.
  useEffect(() => {
    const span = stop && stopOnSheet(stop, plan.logs[day])
    const scroller = scrollers.current[day]
    const sheet = scroller?.firstElementChild as HTMLElement | null
    if (!span || !scroller || !sheet || scroller.scrollWidth <= scroller.clientWidth) return
    const x = sheet.offsetLeft + (minuteX(span.start) / SHEET.width) * sheet.clientWidth
    scroller.scrollLeft = Math.max(0, x - scroller.clientWidth / 4)
  }, [stop, plan.logs, day])

  return (
    <Box
      sx={{
        height: '100%',
        overflowY: 'auto',
        p: 3,
        [MOBILE]: { p: 2 },
        [PRINT]: { height: 'auto', overflow: 'visible', p: 0 },
      }}
    >
      {/* The printed sheets sit on white paper, not on the app's dark page. */}
      <GlobalStyles styles={{ '@media print': { 'html, body': { background: '#fff !important' } } }} />
      <Stack
        data-no-print
        direction="row"
        sx={{ alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', columnGap: 2, rowGap: 1, mb: 1.5, maxWidth: 1100, mx: 'auto' }}
      >
        <Box>
          <Typography variant="h5" component="h2" sx={{ whiteSpace: 'nowrap' }}>
            Daily logs
          </Typography>
          <Typography variant="body2">
            {plan.logs.length} {plan.logs.length === 1 ? 'sheet' : 'sheets'} · times in {plan.log_header.time_zone} (UTC
            {plan.log_header.utc_offset})
          </Typography>
        </Box>
        <Button variant="outlined" startIcon={<Printer size={17} />} onClick={() => window.print()}>
          {plan.logs.length === 1 ? 'Print / save as PDF' : 'Print all days / save as PDF'}
        </Button>
      </Stack>

      {plan.logs.length > 1 && (
        <Tabs
          data-no-print
          value={day}
          onChange={(_, next: number) => setDay(next)}
          variant="scrollable"
          scrollButtons="auto"
          allowScrollButtonsMobile
          aria-label="Day of the trip"
          sx={{ maxWidth: 1100, mx: 'auto', mb: 2, minHeight: 0, '& .MuiTab-root': { minHeight: 40, py: 1 } }}
        >
          {plan.logs.map((log, index) => (
            <Tab
              key={log.date}
              id={`day-tab-${index}`}
              aria-controls={`day-panel-${index}`}
              label={
                <span>
                  Day {index + 1} · {shortDate(log)}
                  {spans[index] && (
                    <Box component="span" aria-label=", has the selected stop" sx={{ ml: 0.75, color: color.turquoise }}>
                      ●
                    </Box>
                  )}
                </span>
              }
            />
          ))}
        </Tabs>
      )}

      <Box sx={{ maxWidth: 1100, mx: 'auto', minWidth: 0 }}>
        {plan.logs.map((log, index) => (
          <Box
            key={log.date}
            component="section"
            role={plan.logs.length > 1 ? 'tabpanel' : undefined}
            id={`day-panel-${index}`}
            aria-labelledby={plan.logs.length > 1 ? `day-tab-${index}` : undefined}
            aria-label={plan.logs.length > 1 ? undefined : `Day 1, ${longDate(log)}`}
            sx={{
              display: index === day ? 'block' : 'none',
              position: 'relative', // holds the sheet's screen-reader list
              minWidth: 0,
              background: color.paper,
              color: color.paperInk,
              borderRadius: `${radius.button}px`,
              boxShadow: shadow.paper,
              p: 3,
              [MOBILE]: { p: 2 },
              // Every day prints, each on its own page, without the screen's card.
              [PRINT]: {
                display: 'block',
                boxShadow: 'none',
                borderRadius: 0,
                p: 0,
                background: '#fff',
                '& + &': { breakBefore: 'page' },
              },
            }}
          >
            <Box
              ref={(node: HTMLElement | null) => {
                scrollers.current[index] = node
              }}
              // Focusable, so the keyboard can scroll a sheet wider than the screen.
              tabIndex={scrolls && index === day ? 0 : -1}
              aria-label={`Log sheet, ${longDate(log)}`}
              sx={{ overflowX: 'auto', mx: -1, px: 1, pb: 0.5, [PRINT]: { overflow: 'visible', m: 0, p: 0 } }}
            >
              <Box
                sx={{
                  minWidth: SHEET_MIN_WIDTH,
                  // One sheet per landscape page: sized by the page's height, which binds first.
                  [PRINT]: { minWidth: 0, breakInside: 'avoid', '& svg': { width: 'auto !important', height: '186mm !important', maxWidth: '100%', mx: 'auto' } },
                }}
              >
                <LogSheet
                  log={log}
                  selected={spans[index]}
                  header={plan.log_header}
                  day={index + 1}
                  days={plan.logs.length}
                  carried={plan.logs.slice(0, index).flatMap((d) => d.remarks).at(-1)}
                  sinceRestart={sinceRestart[index]}
                />
              </Box>
            </Box>
            {scrolls && (
              <Typography data-no-print sx={{ mt: 1, fontSize: 12, color: color.paperMuted }}>
                Scroll sideways for the whole day.
              </Typography>
            )}
          </Box>
        ))}
      </Box>
    </Box>
  )
}

/** Whether the shown sheet is wider than its card, kept up to date as the window resizes. */
function useOverflows(scrollers: { current: (HTMLElement | null)[] }, day: number): boolean {
  const [overflows, setOverflows] = useState(false)
  useEffect(() => {
    const scroller = scrollers.current[day]
    if (!scroller || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(() => setOverflows(scroller.scrollWidth > scroller.clientWidth + 1))
    observer.observe(scroller)
    return () => observer.disconnect()
  }, [scrollers, day])
  return overflows
}

const dateOf = (log: DailyLog) => new Date(`${log.date}T12:00:00Z`)

/** "Mon 5 Oct": the sheet's own date, never shifted by the viewer's time zone. */
function shortDate(log: DailyLog): string {
  return dateOf(log).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' })
}

function longDate(log: DailyLog): string {
  return dateOf(log).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
}
