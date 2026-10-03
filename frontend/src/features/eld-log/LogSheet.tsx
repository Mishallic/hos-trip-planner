import { Box, Tooltip, Typography } from '@mui/material'
import type { DailyLog } from '../../api/types'
import { hm } from '../../lib/format'
import { color } from '../../theme/tokens'
import {
  changeDots,
  DAY_MIN,
  dutyPath,
  dutyRuns,
  GRID,
  GRID_WIDTH,
  gridTicks,
  hourLabels,
  minuteX,
  ROWS,
  rowTop,
  type Run,
  type Segment,
  SHEET,
  statusY,
} from './logGeometry'

const INK = color.paperInk
const ROW_H = SHEET.rowHeight
/** The band reaches a little past the grid, so the midnight labels centre on its edges. */
const BAND_LEFT = GRID.left - 24
const TOTALS_X = SHEET.width - 10 // right edge of the totals text
const HEIGHT = GRID.bottom + 76

interface LogSheetProps {
  log: DailyLog
  /** The selected stop's stretch of this day, when it falls on this sheet. */
  selected: Segment | null
}

/**
 * One day of the driver's log, drawn like the paper form: the 24-hour grid, the duty
 * line at exact minutes with a dot at every change, and each line's total.
 */
export function LogSheet({ log, selected }: LogSheetProps) {
  const runs = dutyRuns(log.segments)
  const totals = ROWS.map((row) => `${row.title} ${log.totals_hm[row.status]}`).join(', ')

  return (
    <>
      <svg
        viewBox={`0 0 ${SHEET.width} ${HEIGHT}`}
        role="img"
        // A label, not an SVG <title>: browsers would show a title as a second tooltip.
        aria-label={`Duty status for ${log.date}: ${totals}.`}
        style={{ display: 'block', width: '100%', height: 'auto', fontFamily: 'inherit' }}
      >

        <HourBand />
        <RowLabels />

        {selected && <SelectedStretch selected={selected} runs={runs} />}

        <Grid />

        <path
          d={dutyPath(log.segments)}
          fill="none"
          stroke={color.paperLine}
          strokeWidth={3}
          strokeLinejoin="round"
        />
        {selected && <SelectedLine selected={selected} runs={runs} />}
        {changeDots(log.segments).map((dot, i) => (
          <circle key={i} cx={dot.x} cy={dot.y} r={3.6} fill={color.paperLine} />
        ))}

        <Totals log={log} />

        {/* On top of everything: one invisible target per stretch for the tooltip. */}
        {runs.map((run) => (
          <Tooltip
            key={run.start}
            title={<RunDetails run={run} log={log} />}
            placement="top"
            enterTouchDelay={0}
            leaveTouchDelay={4000}
            slotProps={{ tooltip: { sx: { maxWidth: 260 } } }}
          >
            <rect
              x={run.x1}
              y={rowTop(run.status)}
              width={run.x2 - run.x1}
              height={ROW_H}
              fill="transparent"
              style={{ cursor: 'default' }}
            />
          </Tooltip>
        ))}
      </svg>

      {/* The same day for screen readers, one line per stretch. */}
      <Box component="ol" sx={visuallyHidden}>
        {runs.map((run) => (
          <li key={run.start}>
            {clock(run.start)} to {clock(run.end)}, {rowTitle(run)}
            {placeOf(run, log) ? `, ${placeOf(run, log)}` : ''}
          </li>
        ))}
      </Box>
    </>
  )
}

/** The black band of hour labels over the grid, with the totals heading. */
function HourBand() {
  const textY = SHEET.headerHeight - 9
  return (
    <g>
      <rect x={BAND_LEFT} y={0} width={SHEET.width - BAND_LEFT} height={SHEET.headerHeight} fill={INK} />
      {hourLabels().map(({ minute, text }) => {
        const x = minuteX(minute)
        return (
          <text key={minute} x={x} y={textY} textAnchor="middle" fill={color.paper} fontSize={11.5} fontWeight={700}>
            {text.length === 1 ? (
              text[0]
            ) : (
              <>
                <tspan x={x} dy={-12}>
                  {text[0]}
                </tspan>
                <tspan x={x} dy={12}>
                  {text[1]}
                </tspan>
              </>
            )}
          </text>
        )
      })}
      <text x={GRID.right + SHEET.totalsWidth / 2} y={textY} textAnchor="middle" fill={color.paper} fontSize={11} fontWeight={700}>
        <tspan x={GRID.right + SHEET.totalsWidth / 2} dy={-12}>
          Total
        </tspan>
        <tspan x={GRID.right + SHEET.totalsWidth / 2} dy={12}>
          Hours
        </tspan>
      </text>
    </g>
  )
}

function RowLabels() {
  return (
    <g fill={INK} fontSize={12.5} fontWeight={700}>
      {ROWS.map((row) => {
        const y = statusY(row.status) + 4.5 - (row.label.length - 1) * 7.5
        return (
          <text key={row.status} x={4} y={y}>
            {row.label.map((line, i) => (
              <tspan key={line} x={4} dy={i ? 15 : 0} fontWeight={i ? 500 : 700}>
                {line}
              </tspan>
            ))}
          </text>
        )
      })}
    </g>
  )
}

/** Hour lines through all four rows; half-hour and quarter ticks hanging from each row's top. */
function Grid() {
  const ticks = gridTicks()
  return (
    <g stroke={INK} strokeLinecap="butt">
      {ROWS.slice(1).map((row) => (
        <line key={row.status} x1={GRID.left} x2={GRID.right} y1={rowTop(row.status)} y2={rowTop(row.status)} strokeWidth={1} />
      ))}
      {ticks
        .filter((tick) => tick.kind === 'hour')
        .map((tick) => (
          <line key={tick.minute} x1={minuteX(tick.minute)} x2={minuteX(tick.minute)} y1={GRID.top} y2={GRID.bottom} strokeWidth={1} />
        ))}
      {ROWS.map((row) =>
        ticks
          .filter((tick) => tick.kind !== 'hour')
          .map((tick) => {
            const x = minuteX(tick.minute)
            const top = rowTop(row.status)
            const length = (tick.kind === 'half' ? SHEET.halfTick : SHEET.quarterTick) * ROW_H
            return <line key={`${row.status}-${tick.minute}`} x1={x} x2={x} y1={top} y2={top + length} strokeWidth={0.9} />
          }),
      )}
      <rect x={GRID.left} y={GRID.top} width={GRID_WIDTH} height={GRID.bottom - GRID.top} fill="none" strokeWidth={1.6} />
    </g>
  )
}

/** The selected stop's part of its row, shaded under the grid. */
function SelectedStretch({ selected, runs }: { selected: Segment; runs: Run[] }) {
  return (
    <g fill={color.paperHighlight}>
      {overlaps(selected, runs).map(([start, end]) => (
        <rect key={start} x={minuteX(start)} y={rowTop(selected.status)} width={minuteX(end) - minuteX(start)} height={ROW_H} />
      ))}
    </g>
  )
}

/** ...and its stretch of the duty line, drawn heavier. */
function SelectedLine({ selected, runs }: { selected: Segment; runs: Run[] }) {
  const y = statusY(selected.status)
  return (
    <g stroke={color.paperLine} strokeWidth={6} strokeLinecap="butt">
      {overlaps(selected, runs).map(([start, end]) => (
        <line key={start} x1={minuteX(start)} x2={minuteX(end)} y1={y} y2={y} />
      ))}
    </g>
  )
}

/** Where the selected stop meets the duty line on its own row, so a highlight never floats off it. */
function overlaps(selected: Segment, runs: Run[]): [number, number][] {
  return runs
    .filter((run) => run.status === selected.status)
    .map((run): [number, number] => [Math.max(run.start, selected.start), Math.min(run.end, selected.end)])
    .filter(([start, end]) => end > start)
}

/** Each line's total on the right, their sum under them, and on-duty hours as the video circles them. */
function Totals({ log }: { log: DailyLog }) {
  const left = GRID.right + 14
  const sumY = GRID.bottom + 27
  const circleX = GRID.right + SHEET.totalsWidth / 2
  const circleY = GRID.bottom + 52
  return (
    <g fill={INK}>
      {ROWS.map((row) => (
        <g key={row.status}>
          <text x={TOTALS_X} y={statusY(row.status) + 5} textAnchor="end" fontSize={15} fontWeight={700}>
            {log.totals_hm[row.status]}
          </text>
          <line x1={left} x2={TOTALS_X} y1={rowTop(row.status) + ROW_H - 7} y2={rowTop(row.status) + ROW_H - 7} stroke={INK} strokeWidth={0.8} />
        </g>
      ))}
      <line x1={left} x2={TOTALS_X} y1={GRID.bottom + 6} y2={GRID.bottom + 6} stroke={INK} strokeWidth={0.9} />
      <line x1={left} x2={TOTALS_X} y1={GRID.bottom + 9} y2={GRID.bottom + 9} stroke={INK} strokeWidth={0.9} />
      <text x={TOTALS_X} y={sumY} textAnchor="end" fontSize={15} fontWeight={800}>
        {hm(Object.values(log.totals_min).reduce((sum, minutes) => sum + minutes, 0))}
      </text>
      <circle cx={circleX} cy={circleY} r={19} fill="none" stroke={INK} strokeWidth={1.2} />
      <text x={circleX} y={circleY + 4} textAnchor="middle" fontSize={11} fontWeight={800}>
        {log.on_duty_hours}
      </text>
      <text x={circleX - 26} y={circleY + 4} textAnchor="end" fontSize={11.5} fill={color.paperMuted}>
        On duty today, lines 3 + 4, in hours
      </text>
    </g>
  )
}

function RunDetails({ run, log }: { run: Run; log: DailyLog }) {
  const activities = log.remarks
    .filter((remark) => remark.status === run.status && remark.minute >= run.start && remark.minute < run.end)
    .map((remark) => remark.label)
    // The stretch's own name says it already: no "Driving" under Driving.
    .filter((label) => label.toLowerCase() !== rowTitle(run).toLowerCase() && label !== 'Driving')
  const place = placeOf(run, log)
  return (
    <Box>
      <Typography sx={{ fontWeight: 700, fontSize: 13 }}>{rowTitle(run)}</Typography>
      <Typography sx={{ fontSize: 12.5 }}>
        {clock(run.start)} – {clock(run.end)} · {hm(run.end - run.start)}
      </Typography>
      {place && <Typography sx={{ fontSize: 12.5 }}>{place}</Typography>}
      {activities.length > 0 && (
        <Typography sx={{ fontSize: 12, opacity: 0.8 }}>{activities.join(' · ')}</Typography>
      )}
    </Box>
  )
}

/** Where a stretch happened: where it began, and for driving also where it ended. */
function placeOf(run: Run, log: DailyLog): string | null {
  const at = (minute: number) => log.remarks.find((remark) => remark.minute === minute)?.place ?? null
  const from = at(run.start) ?? (run.start === 0 ? log.from : null)
  if (run.status !== 'driving') return from
  const to = at(run.end) ?? (run.end === DAY_MIN ? log.to : null)
  return from && to && from !== to ? `${from} → ${to}` : from ?? to
}

function rowTitle(run: Run): string {
  return ROWS.find((row) => row.status === run.status)?.title ?? run.status
}

/** Minutes from midnight as a clock time; the end of the day reads 24:00. */
function clock(minute: number): string {
  return `${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(Math.round(minute % 60)).padStart(2, '0')}`
}

// Positioned inside its sheet (LogsView's section is relative), so it never
// stretches the page.
const visuallyHidden = {
  position: 'absolute',
  width: '1px',
  height: '1px',
  m: '-1px',
  p: 0,
  border: 0,
  overflow: 'hidden',
  clip: 'rect(0 0 0 0)',
  whiteSpace: 'nowrap',
} as const
