import { Box, Card, Stack, Typography } from '@mui/material'
import { ListChecks } from 'lucide-react'
import { type KeyboardEvent, useEffect, useRef } from 'react'

import type { Stop } from '../../api/types'
import { CardHeading } from '../../components/CardParts'
import { clockTime, STOP_LABEL } from '../../lib/format'
import { type StopSelection, stepStop } from '../../state/selection'
import { color, layout, radius, stopColor, stopTextColor } from '../../theme/tokens'
import { StopIcon } from './StopIcon'

const MOBILE = `@media (max-width: ${layout.mobile - 1}px)`

/**
 * Every stop in time order, as a listbox: arrow keys move the selection, Home and
 * End jump to the ends, Enter centres the map on the stop, Space selects it.
 */
export function StopList({ stops, selection }: { stops: Stop[]; selection: StopSelection }) {
  const { selected, request, select, centre } = selection
  const rows = useRef<(HTMLDivElement | null)[]>([])

  // Keep the selected stop in view inside the sidebar only, on every request, even
  // for the stop already selected. On mobile the page itself scrolls, and jumping
  // away from the map the user just tapped would be wrong.
  useEffect(() => {
    const row = selected === null ? null : rows.current[selected]
    const sidebar = row && scrollingSidebar(row)
    if (!row || !sidebar) return
    const view = sidebar.getBoundingClientRect()
    // Rows only ever sit below the clocks card, so anything above its bottom edge
    // is hidden: scrolled out of the sidebar or under the card while it is pinned.
    const clocks = sidebar.querySelector('[data-sticky]')?.getBoundingClientRect()
    const top = Math.max(view.top, clocks?.bottom ?? view.top)
    const box = row.getBoundingClientRect()
    if (box.top < top) sidebar.scrollBy({ top: box.top - top - 12, behavior: 'smooth' })
    else if (box.bottom > view.bottom) sidebar.scrollBy({ top: box.bottom - view.bottom + 12, behavior: 'smooth' })
  }, [selected, request])

  const moveTo = (index: number | null) => {
    const row = index === null ? null : rows.current[index]
    if (index === null || !row) return
    select(index)
    // The sidebar effect above scrolls smoothly and knows about the pinned clocks.
    // Without a scrolling sidebar (phones, zoomed-in desktops) the browser brings
    // the focused row into view itself, so focus never walks off screen.
    row.focus({ preventScroll: Boolean(scrollingSidebar(row)) })
  }

  const onKeyDown = (event: KeyboardEvent, index: number) => {
    const keys: Record<string, () => void> = {
      ArrowDown: () => moveTo(stepStop(index, 1, stops.length)),
      ArrowUp: () => moveTo(stepStop(index, -1, stops.length)),
      Home: () => moveTo(0),
      End: () => moveTo(stops.length - 1),
      Enter: () => centre(index),
      ' ': () => select(index),
    }
    const action = keys[event.key]
    if (action) {
      event.preventDefault()
      action()
    }
  }

  // Roving focus: one row is in the tab order, the selected one or else the first.
  const tabStop = selected ?? 0

  return (
    <Card sx={{ p: 2.5 }}>
      <CardHeading Icon={ListChecks} title="Stops" subtitle="Every stop and the rule behind it" hint={`${stops.length}`} />
      <Box role="listbox" aria-label="Stops, in time order">
        {stops.map((stop, index) => {
          const isSelected = index === selected
          return (
            <Stack
              key={`${stop.kind}-${stop.start}`}
              id={`stop-${index}`}
              ref={(row: HTMLDivElement | null) => {
                rows.current[index] = row
              }}
              role="option"
              aria-selected={isSelected}
              tabIndex={index === tabStop ? 0 : -1}
              direction="row"
              spacing={1.5}
              onClick={() => select(index)}
              onKeyDown={(event) => onKeyDown(event, index)}
              sx={{
                py: 1.25,
                px: 1,
                mx: -1,
                borderRadius: `${radius.button}px`,
                borderTop: index ? `1px solid ${color.borderSoft}` : 'none',
                cursor: 'pointer',
                outline: 'none',
                background: isSelected ? 'rgba(64, 224, 208, 0.05)' : 'transparent',
                boxShadow: isSelected ? `inset 3px 0 0 ${stopColor[stop.kind]}` : 'none',
                '&:hover': { background: isSelected ? 'rgba(64, 224, 208, 0.07)' : 'rgba(255, 255, 255, 0.03)' },
                '&:focus-visible': {
                  // The transparent outline only shows in forced colours, where shadows are dropped.
                  outline: '2px solid transparent',
                  outlineOffset: -2,
                  boxShadow: [isSelected && `inset 3px 0 0 ${stopColor[stop.kind]}`, `inset 0 0 0 2px ${color.turquoise}`]
                    .filter(Boolean)
                    .join(', '),
                },
                '@media (forced-colors: active)': isSelected
                  ? { outline: '2px solid Highlight', outlineOffset: -2 }
                  : {},
              }}
            >
              <StopIcon kind={stop.kind} />
              <Box sx={{ minWidth: 0, flex: 1 }}>
                <Stack direction="row" spacing={1} sx={{ justifyContent: 'space-between' }}>
                  <Typography sx={{ fontWeight: 600, fontSize: 14 }} noWrap>
                    <Box component="span" sx={{ color: stopTextColor[stop.kind] }}>
                      {STOP_LABEL[stop.kind]}
                    </Box>{' '}
                    <Box component="span" sx={{ color: color.textMuted, fontWeight: 500 }}>
                      ({stop.place ?? `mile ${stop.mile}`})
                    </Box>
                  </Typography>
                  <Typography sx={{ fontSize: 13, color: color.textSecondary, whiteSpace: 'nowrap' }}>
                    {clockTime(stop.start)}
                  </Typography>
                </Stack>
                <Typography variant="body2" sx={{ fontSize: 12.5, mt: 0.25 }}>
                  {stop.explanation}
                </Typography>
              </Box>
            </Stack>
          )
        })}
      </Box>
      <Typography variant="caption" component="p" sx={{ mt: 1.5, [MOBILE]: { display: 'none' } }}>
        ↑ ↓ move between stops · Enter centres the map
      </Typography>
    </Card>
  )
}

/** The sidebar around a row, if it is the thing that scrolls (the desktop layout). */
function scrollingSidebar(row: HTMLElement): HTMLElement | null {
  const sidebar = row.closest<HTMLElement>('[data-scroll-container]')
  return sidebar && sidebar.scrollHeight > sidebar.clientHeight ? sidebar : null
}
