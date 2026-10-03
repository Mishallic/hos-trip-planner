// The parts of the paper form around the grid: the header, the remarks band with
// its brackets and 45-degree flags, and the recap. Drawn in SVG units like the grid.

import type { DailyLog, LogHeader, Remark } from '../../api/types'
import { hm } from '../../lib/format'
import { color } from '../../theme/tokens'
import { GRID, gridTicks, minuteX, remarkLayout, SHEET } from './logGeometry'

const INK = color.paperInk
const MUTED = color.paperMuted

export const HEADER_HEIGHT = 168
export const REMARKS_HEIGHT = 272
export const RECAP_HEIGHT = 112

/**
 * A value cut to what fits a blank of `width` units at `size`, so a long carrier name
 * never runs into the next field. The full value shows on hover when it is cut.
 */
function Fitted({ x, y, width, value, size, weight = 600, color: fill = INK }: { x: number; y: number; width: number; value?: string | null; size: number; weight?: number; color?: string }) {
  if (!value) return null
  const max = Math.floor((width - 4) / (size * (weight >= 700 ? 0.64 : 0.56)))
  const cut = value.length > max
  return (
    <text x={x} y={y} fontSize={size} fontWeight={weight} fill={fill}>
      {cut ? `${value.slice(0, max - 1).trimEnd()}…` : value}
      {cut && <title>{value}</title>}
    </text>
  )
}

/** One labelled blank of the form: the value written on the line, its caption under it. */
function Field({ x, y, width, label, value, size = 14 }: { x: number; y: number; width: number; label: string; value?: string | null; size?: number }) {
  return (
    <g>
      <Fitted x={x + 2} y={y - 5} width={width} value={value} size={size} />
      <line x1={x} x2={x + width} y1={y} y2={y} stroke={INK} strokeWidth={0.9} />
      <text x={x} y={y + 12} fontSize={9.5} fill={MUTED} letterSpacing="0.03em">
        {label}
      </text>
    </g>
  )
}

/** The top of the form (guide p. 19, the blank daily log): date, places, miles, vehicles, carrier. */
export function SheetHeader({ log, header, day, days }: { log: DailyLog; header: LogHeader; day: number; days: number }) {
  const [year, month, date] = log.date.split('-')
  const miles = log.miles_today.toLocaleString('en-US', { maximumFractionDigits: 0 })
  const vehicles = [header.truck, header.trailer].filter(Boolean).join(' / ')
  return (
    <g>
      <text x={0} y={22} fontSize={22} fontWeight={800} fill={INK} fontFamily="Manrope Variable, inherit">
        Driver's Daily Log
      </text>
      <text x={0} y={38} fontSize={10.5} fill={MUTED}>
        One calendar day, 24 hours · sheet {day} of {days}
      </text>

      <Field x={330} y={26} width={42} label="month" value={month} size={17} />
      <Field x={386} y={26} width={42} label="day" value={date} size={17} />
      <Field x={442} y={26} width={60} label="year" value={year} size={17} />

      <text x={SHEET.width} y={14} textAnchor="end" fontSize={9.5} fill={MUTED}>
        Original: file at the home terminal.
      </text>
      <text x={SHEET.width} y={27} textAnchor="end" fontSize={9.5} fill={MUTED}>
        Duplicate: the driver keeps it for 8 days.
      </text>
      <text x={SHEET.width} y={40} textAnchor="end" fontSize={9.5} fill={MUTED}>
        Times: home terminal, {header.time_zone} (UTC{header.utc_offset})
      </text>

      <Field x={0} y={70} width={470} label="From" value={log.from} />
      <Field x={500} y={70} width={500} label="To" value={log.to} />

      {/* Miles: in boxes, as on the form. All miles are driven loaded here, so both match. */}
      <rect x={0} y={96} width={112} height={26} fill="none" stroke={INK} strokeWidth={1} />
      <text x={56} y={114} textAnchor="middle" fontSize={15} fontWeight={700} fill={INK}>
        {miles}
      </text>
      <text x={0} y={134} fontSize={9.5} fill={MUTED}>
        Total miles driving today
      </text>
      <rect x={124} y={96} width={112} height={26} fill="none" stroke={INK} strokeWidth={1} />
      <text x={180} y={114} textAnchor="middle" fontSize={15} fontWeight={700} fill={INK}>
        {miles}
      </text>
      <text x={124} y={134} fontSize={9.5} fill={MUTED}>
        Total mileage today
      </text>
      <Field x={250} y={122} width={220} label="Truck / trailer numbers" value={vehicles} />

      <Field x={500} y={110} width={240} label="Name of carrier" value={header.carrier} />
      <Field x={760} y={110} width={240} label="Home terminal address" value={header.home_terminal} />
      <Field x={500} y={148} width={240} label="Driver's signature" value={header.driver} size={13} />
      <Field x={760} y={148} width={240} label="Co-driver" value="N/A" size={13} />
    </g>
  )
}

/**
 * Under the grid: a tick row like the grid's top edge, a bracket under each stretch
 * where the truck stood still, and a flag at 45 degrees naming the place (guide p. 18).
 */
export function RemarksBand({ log, top, carried }: { log: DailyLog; top: number; carried?: Remark }) {
  const { brackets, flags } = remarkLayout(log, carried)
  const ruler = top + 18
  const bracketDepth = 10
  return (
    <g>
      <text x={4} y={ruler + 4} fontSize={12.5} fontWeight={800} fill={INK} letterSpacing="0.06em">
        REMARKS
      </text>
      <line x1={GRID.left} x2={GRID.right} y1={ruler} y2={ruler} stroke={INK} strokeWidth={1.2} />
      {gridTicks()
        .filter((tick) => tick.kind !== 'quarter')
        .map((tick) => (
          <line
            key={tick.minute}
            x1={minuteX(tick.minute)}
            x2={minuteX(tick.minute)}
            y1={ruler}
            y2={ruler - (tick.kind === 'hour' ? 8 : 5)}
            stroke={INK}
            strokeWidth={0.9}
          />
        ))}
      <g stroke={color.paperLine} strokeWidth={1.8} fill="none">
        {brackets.map((b) => (
          <path key={b.start} d={`M ${b.x1} ${ruler + 3} V ${ruler + bracketDepth} H ${b.x2} V ${ruler + 3}`} />
        ))}
      </g>
      {flags.map((flag) => {
        const foot = ruler + bracketDepth
        const start = foot + 8
        return (
          <g key={flag.anchorX}>
            <path d={`M ${flag.anchorX} ${foot} L ${flag.x} ${start}`} stroke={color.paperLine} strokeWidth={1.2} fill="none" />
            <text
              x={flag.x + 2}
              y={start + 4}
              transform={`rotate(45 ${flag.x} ${start})`}
              fontSize={11.5}
              fontWeight={600}
              fill={INK}
            >
              {flag.text}
            </text>
          </g>
        )
      })}
      {log.brackets.length === 0 && (
        <text x={GRID.left + 4} y={ruler + 26} fontSize={11.5} fill={MUTED}>
          No stops today.
        </text>
      )}
    </g>
  )
}

/**
 * The end-of-day recap (the form's bottom strip): on-duty hours today circled, as
 * the video does, and the 70-hour / 8-day figures A and B. Approximate (D12).
 */
export function Recap({ log, header, top, sinceRestart }: { log: DailyLog; header: LogHeader; top: number; sinceRestart: boolean }) {
  const { recap } = log
  // After a 34-hour restart the count starts again from zero, so it is exact.
  const approximate = recap.approximate && !sinceRestart
  const col = (x: number, title: string, value: string, note: string) => (
    <g>
      <text x={x} y={top + 40} fontSize={10} fill={MUTED}>
        {title}
      </text>
      <text x={x} y={top + 64} fontSize={19} fontWeight={800} fill={INK}>
        {value}
      </text>
      <text x={x} y={top + 80} fontSize={9.5} fill={MUTED}>
        {note}
      </text>
    </g>
  )
  const circleX = 60
  return (
    <g>
      <line x1={0} x2={SHEET.width} y1={top} y2={top} stroke={INK} strokeWidth={1.2} />
      <text x={0} y={top + 20} fontSize={12.5} fontWeight={800} fill={INK} letterSpacing="0.06em">
        RECAP · 70 HOUR / 8 DAY
      </text>

      <circle cx={circleX} cy={top + 58} r={22} fill="none" stroke={INK} strokeWidth={1.4} />
      <text x={circleX} y={top + 63} textAnchor="middle" fontSize={14} fontWeight={800} fill={INK}>
        {log.on_duty_hours}
      </text>
      <text x={circleX + 32} y={top + 52} fontSize={10} fill={MUTED}>
        On duty hours today
      </text>
      <text x={circleX + 32} y={top + 65} fontSize={10} fill={MUTED}>
        (lines 3 + 4: {hm(recap.on_duty_today_min)})
      </text>

      {/* The form's A (last 7 days) needs day-by-day history the trip does not have.
          C is what the planner knows, and B from C errs on the safe side. */}
      {col(300, 'C. Total hours on duty, last 8 days incl. today', `${approximate ? '≈ ' : ''}${hm(recap.cycle_used_min)}`, sinceRestart ? 'since the 34-hour restart' : 'cycle hours entered + this trip')}
      {col(560, 'B. Total hours available tomorrow (70 − C)', `${approximate ? '≈ ' : ''}${hm(recap.available_tomorrow_min)}`, 'after 34 hours off: 70:00 again')}
      <text x={800} y={top + 40} fontSize={10} fill={MUTED}>
        Shipping documents
      </text>
      <Fitted x={800} y={top + 64} width={200} value={header.load_id || '—'} size={19} weight={800} />
      <Fitted x={800} y={top + 80} width={200} value={[header.shipper, header.commodity].filter(Boolean).join(' · ') || 'Shipper & commodity'} size={9.5} weight={400} color={MUTED} />

      {approximate && (
        <text x={0} y={top + 102} fontSize={9.5} fill={MUTED}>
          ≈ Approximate: the days before the trip are known only as the cycle hours entered, so C is counted from them (decision D12).
        </text>
      )}
    </g>
  )
}

// Sizes the sheet needs, in SVG units: header, grid (with its totals), remarks, recap.
export const GRID_BLOCK_HEIGHT = GRID.bottom + 40
