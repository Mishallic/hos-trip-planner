import { Box, ButtonBase, Card, Stack, Tooltip, Typography } from '@mui/material'
import { Truck } from 'lucide-react'
import { type RefObject, useEffect, useMemo, useRef, useState } from 'react'

import type { TripPlan } from '../../api/types'
import { miles, STOP_LABEL, timeRange } from '../../lib/format'
import { clusterByPosition, timeScale } from '../../lib/timeScale'
import type { StopSelection } from '../../state/selection'
import { color, font, stopColor } from '../../theme/tokens'
import { mostSignificant } from '../route-map/stopGroups'

const DOT = 14
const LINE_Y = 30
/** Until the strip is measured: dots closer than this share of it merge. */
const MIN_DOT_GAP = 0.014
/** Day labels: their style, and how far right of the midnight line they start. */
const LABEL_FONT = { size: 10.5, weight: 700, spacingEm: 0.06 }
const LABEL_OFFSET = 5

// Below this width the truck icon goes, and the totals drop under the strip when
// the strip would get too short (a narrow desktop column, a small phone).
const NARROW = '@media (max-width: 1023px)'

/**
 * The whole trip on one line, spaced by TIME: each stop is a coloured segment as
 * long as it lasts, so a 10-hour rest or a 34-hour restart reads as long. Dots
 * mark where stops begin; day separators sit at midnight in the trip's time zone.
 */
export function TimelineStrip({ plan, selection }: { plan: TripPlan; selection: StopSelection }) {
  const { selected, select } = selection
  const { summary, stops } = plan
  const strip = useRef<HTMLDivElement>(null)
  const width = useWidth(strip)
  const scale = useMemo(() => timeScale(summary.start, summary.end), [summary.start, summary.end])
  const spans = useMemo(
    () => stops.map((stop, index) => ({ index, stop, left: scale.at(stop.start), right: scale.at(stop.end) })),
    [stops, scale],
  )
  // Dots that would touch at the strip's real width merge into one, so a phone
  // shows fewer, larger targets instead of a pile. Positions are taken as drawn:
  // a dot at either end is kept half a dot inside the strip.
  const dots = useMemo(() => {
    const edge = width > 0 ? DOT / 2 / width : 0
    const points = spans.map((s) => ({ position: Math.min(1 - edge, Math.max(edge, s.left)), value: s.index }))
    return clusterByPosition(points, width > 0 ? (DOT + 2) / width : MIN_DOT_GAP)
  }, [spans, width])

  const describe = (index: number) => {
    const stop = stops[index]
    return `${STOP_LABEL[stop.kind]} · ${stop.place ?? `mile ${stop.mile}`} · ${timeRange(stop.start, stop.end)}`
  }

  return (
    <Card sx={{ px: 2.5, pt: 1, pb: 1.25 }}>
      <Stack direction="row" sx={{ alignItems: 'center', flexWrap: 'wrap', columnGap: 2 }}>
        <Box sx={{ color: color.textSecondary, display: 'flex', mt: 1.5, [NARROW]: { display: 'none' } }}>
          <Truck size={22} strokeWidth={1.8} />
        </Box>

        <Box
          ref={strip}
          role="group"
          aria-label="Trip timeline, spaced by time"
          sx={{ position: 'relative', flex: '1 1 220px', height: 46, minWidth: 0 }}
        >
          {scale.days.map((day, i) => {
            // A label sits just right of its midnight line and is left out when the
            // day is too short on screen to hold it.
            const room = ((scale.days[i + 1]?.position ?? 1) - day.position) * width
            const fits = width === 0 || room >= (i > 0 ? LABEL_OFFSET : 0) + labelWidth(day.label)
            return (
              <Box key={day.date} sx={{ position: 'absolute', left: `${day.position * 100}%`, top: 0, bottom: 0 }}>
                {i > 0 && (
                  <Box sx={{ position: 'absolute', top: 2, bottom: 2, left: 0, width: '1px', background: color.border }} />
                )}
                {fits && (
                  <Typography
                    component="span"
                    sx={{
                      position: 'absolute',
                      top: 0,
                      left: i > 0 ? LABEL_OFFSET : 0,
                      fontSize: LABEL_FONT.size,
                      fontWeight: LABEL_FONT.weight,
                      letterSpacing: `${LABEL_FONT.spacingEm}em`,
                      textTransform: 'uppercase',
                      color: color.textMuted,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {day.label}
                  </Typography>
                )}
              </Box>
            )
          })}

          {/* Driving: the thin line underneath everything. */}
          <Box
            sx={{
              position: 'absolute',
              left: 0,
              right: 0,
              top: LINE_Y - 1,
              height: 2,
              borderRadius: 2,
              background: 'rgba(196, 208, 212, 0.22)',
            }}
          />

          {/* Stops: as long as they last. Mouse only; the dots carry the labels. */}
          {spans.map(({ index, stop, left, right }) => (
            <Box
              key={`${stop.kind}-${stop.start}`}
              aria-hidden
              onClick={() => select(index)}
              sx={{
                position: 'absolute',
                left: `${left * 100}%`,
                width: `max(${(right - left) * 100}%, 3px)`,
                top: LINE_Y - 4,
                height: 8,
                borderRadius: 4,
                cursor: 'pointer',
                background: stopColor[stop.kind],
                opacity: index === selected ? 1 : 0.7,
                boxShadow: index === selected ? `0 0 0 2px ${color.text}` : 'none',
                transition: 'opacity 120ms',
                '&:hover': { opacity: 1 },
              }}
            />
          ))}

          {dots.map((dot) => {
            const kind = mostSignificant(dot.values.map((i) => stops[i].kind))
            const isSelected = selected !== null && dot.values.includes(selected)
            const label = dot.values.map(describe).join('\n')
            // Like a map marker, a dot selects its first stop; clicking it again
            // steps through the others merged into it.
            const next = isSelected ? dot.values[(dot.values.indexOf(selected) + 1) % dot.values.length] : dot.values[0]
            return (
              <Tooltip
                key={dot.values[0]}
                title={<Box sx={{ whiteSpace: 'pre-line' }}>{label}</Box>}
                placement="top"
              >
                <ButtonBase
                  aria-label={label}
                  aria-pressed={isSelected}
                  onClick={() => select(next)}
                  sx={{
                    position: 'absolute',
                    top: LINE_Y - DOT / 2,
                    left: `clamp(0px, calc(${dot.position * 100}% - ${DOT / 2}px), calc(100% - ${DOT}px))`,
                    width: DOT,
                    height: DOT,
                    borderRadius: '50%',
                    background: stopColor[kind],
                    border: `2px solid ${color.bgMid}`,
                    boxShadow: isSelected ? `0 0 0 3px ${color.text}` : `0 0 0 3px ${stopColor[kind]}33`,
                    transform: isSelected ? 'scale(1.3)' : 'none',
                    transition: 'transform 120ms, box-shadow 120ms',
                    zIndex: isSelected ? 2 : 1,
                    '&:focus-visible': {
                      // The transparent outline only shows in forced colours, where shadows are dropped.
                      outline: '2px solid transparent',
                      outlineOffset: 2,
                      boxShadow: `0 0 0 3px ${color.turquoise}`,
                    },
                    '@media (forced-colors: active)': isSelected
                      ? { outline: '2px solid Highlight', outlineOffset: 2 }
                      : {},
                  }}
                />
              </Tooltip>
            )
          })}
        </Box>

        <Box sx={{ textAlign: 'right', flexShrink: 0, ml: 'auto', mt: 1.25 }}>
          <Typography sx={{ fontWeight: 700, whiteSpace: 'nowrap', lineHeight: 1.2 }}>
            {miles(summary.total_miles)}
          </Typography>
          <Typography variant="caption" sx={{ whiteSpace: 'nowrap' }}>
            {summary.elapsed} total
          </Typography>
        </Box>
      </Stack>
    </Card>
  )
}

/** The element's content width, kept up to date; 0 until it has been measured. */
function useWidth(ref: RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(0)
  useEffect(() => {
    const node = ref.current
    if (!node || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(node)
    return () => observer.disconnect()
  }, [ref])
  return width
}

const labelWidths = new Map<string, number>()
let measure: CanvasRenderingContext2D | null | undefined

/** The drawn width of an uppercase day label, measured once the font has loaded. */
function labelWidth(label: string): number {
  const text = label.toUpperCase()
  const known = labelWidths.get(text)
  if (known !== undefined) return known
  if (measure === undefined) measure = document.createElement('canvas').getContext('2d')
  const style = `${LABEL_FONT.weight} ${LABEL_FONT.size}px ${font.body}`
  const spacing = text.length * LABEL_FONT.spacingEm * LABEL_FONT.size
  if (!measure) return text.length * LABEL_FONT.size * 0.8 + spacing // a safe guess without a canvas
  measure.font = style
  const width = measure.measureText(text).width + spacing
  // A width taken with a fallback font is used once, not remembered.
  if (document.fonts?.check(style) !== false) labelWidths.set(text, width)
  return width
}
