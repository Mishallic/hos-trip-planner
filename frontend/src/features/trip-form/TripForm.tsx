import {
  Alert,
  Box,
  Button,
  Card,
  Collapse,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { ChevronDown, Route } from 'lucide-react'
import { type FormEvent, useState } from 'react'

import type { ApiError } from '../../api/client'
import { HEADER_FIELDS, type HeaderField, type TripForm as Form, validateForm } from '../../state/urlState'
import { color, radius } from '../../theme/tokens'
import { PlaceInput } from './PlaceInput'

// Home terminal zones across the US, Canada and Mexico. Empty = the current location's.
const TIME_ZONES: [string, string][] = [
  ['', 'Same as current location'],
  ['America/New_York', 'Eastern (New York)'],
  ['America/Chicago', 'Central (Chicago)'],
  ['America/Denver', 'Mountain (Denver)'],
  ['America/Phoenix', 'Mountain, no DST (Phoenix)'],
  ['America/Los_Angeles', 'Pacific (Los Angeles)'],
  ['America/Anchorage', 'Alaska (Anchorage)'],
  ['Pacific/Honolulu', 'Hawaii (Honolulu)'],
  ['America/Halifax', 'Atlantic (Halifax)'],
  ['America/St_Johns', 'Newfoundland (St. John’s)'],
  ['America/Regina', 'Central, no DST (Regina)'],
  ['America/Mexico_City', 'Central Mexico (Mexico City)'],
  ['America/Tijuana', 'Pacific Mexico (Tijuana)'],
]

const HEADER_LABELS: Record<HeaderField, string> = {
  driver: 'Driver',
  carrier: 'Carrier',
  truck: 'Truck no.',
  trailer: 'Trailer no.',
  shipper: 'Shipper',
  commodity: 'Commodity',
  load_id: 'Load no.',
  home_terminal: 'Home terminal',
}

interface TripFormProps {
  initial: Form
  onSubmit: (form: Form) => void
  planning: boolean
  error?: ApiError | null
  collapsed: boolean
  onExpand: () => void
}

/** The trip inputs. After a plan is shown it shrinks to one line with Edit. */
export function TripForm({ initial, onSubmit, planning, error, collapsed, onExpand }: TripFormProps) {
  if (collapsed) return <CollapsedTrip form={initial} onExpand={onExpand} />
  return <ExpandedTrip key={JSON.stringify(initial)} {...{ initial, onSubmit, planning, error }} />
}

function CollapsedTrip({ form, onExpand }: { form: Form; onExpand: () => void }) {
  const short = (label: string) => label.split(',')[0]
  return (
    <Card sx={{ pl: 1.75, pr: 0.5, py: 0.75 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', minWidth: 0 }}>
        <Typography noWrap sx={{ minWidth: 0, fontSize: 13, fontWeight: 600, letterSpacing: '-0.01em' }}>
          {short(form.current.label)} → {short(form.pickup.label)} → {short(form.dropoff.label)}
        </Typography>
        <Typography sx={{ flexShrink: 0, fontSize: 13, color: color.textMuted, whiteSpace: 'nowrap' }}>
          · {Number(form.cycleUsedHours)} h used
        </Typography>
        <Box sx={{ flex: 1 }} />
        <Button size="small" onClick={onExpand} sx={{ flexShrink: 0, minWidth: 0, px: 1, color: color.turquoise }}>
          Edit
        </Button>
      </Stack>
    </Card>
  )
}

function ExpandedTrip({
  initial,
  onSubmit,
  planning,
  error,
}: Pick<TripFormProps, 'initial' | 'onSubmit' | 'planning' | 'error'>) {
  const [form, setForm] = useState<Form>(initial)
  const [touched, setTouched] = useState(false)
  const hasExtras = Boolean(initial.homeTz || HEADER_FIELDS.some((f) => initial.header[f]))
  const [showMore, setShowMore] = useState(hasExtras)

  const local = touched ? validateForm(form) : {}
  const errors = { ...serverErrors(error), ...local }
  const update = (patch: Partial<Form>) => setForm((previous) => ({ ...previous, ...patch }))

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setTouched(true)
    if (Object.keys(validateForm(form)).length === 0) onSubmit(form)
  }

  return (
    <Card component="form" onSubmit={submit} noValidate sx={{ p: 2.5 }}>
      <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', mb: 2 }}>
        <Box
          sx={{
            width: 40,
            height: 40,
            borderRadius: `${radius.chip}px`,
            display: 'grid',
            placeItems: 'center',
            color: color.turquoise,
            background: color.chip,
            border: `1px solid ${color.border}`,
          }}
        >
          <Route size={19} />
        </Box>
        <Box>
          <Typography variant="h6" component="h2" sx={{ lineHeight: 1.25 }}>
            Plan a trip
          </Typography>
          <Typography variant="subtitle2" sx={{ fontSize: 12.5 }}>
            Every stop placed under the HOS rules
          </Typography>
        </Box>
      </Stack>

      <Stack spacing={1.75}>
        {/* First, where it is seen at once, even on a phone. Field errors sit on their field. */}
        {error && !Object.keys(serverErrors(error)).length && (
          <Alert severity={error.status === 422 ? 'warning' : 'error'} variant="outlined" role="alert">
            {error.message}
          </Alert>
        )}
        <PlaceInput label="Current location" value={form.current} onChange={(current) => update({ current })} error={errors.current} autoFocus={!initial.current.label} />
        <PlaceInput label="Pickup" value={form.pickup} onChange={(pickup) => update({ pickup })} error={errors.pickup} />
        <PlaceInput label="Drop-off" value={form.dropoff} onChange={(dropoff) => update({ dropoff })} error={errors.dropoff} />

        <Stack direction="row" spacing={1.5}>
          <TextField
            size="small"
            label="Cycle used (hours)"
            value={form.cycleUsedHours}
            onChange={(e) => update({ cycleUsedHours: e.target.value })}
            error={Boolean(errors.cycle_used_hours)}
            helperText={errors.cycle_used_hours ?? 'Of 70, last 8 days'}
            slotProps={{ htmlInput: { inputMode: 'decimal', pattern: '[0-9]*[.]?[0-9]*' } }}
            sx={{ flex: 1 }}
          />
          <TextField
            size="small"
            label="Start"
            type="datetime-local"
            value={form.startTime}
            onChange={(e) => update({ startTime: e.target.value })}
            error={Boolean(errors.start_time)}
            helperText={errors.start_time ?? (form.startTime ? 'Home terminal time' : 'Empty = now')}
            slotProps={{ inputLabel: { shrink: true } }}
            sx={{ flex: 1.35 }}
          />
        </Stack>

        <Button
          size="small"
          onClick={() => setShowMore((v) => !v)}
          endIcon={<ChevronDown size={16} style={{ transform: showMore ? 'rotate(180deg)' : undefined, transition: 'transform 150ms' }} />}
          sx={{ alignSelf: 'flex-start', color: color.textSecondary, px: 1 }}
        >
          Time zone and log header (optional)
        </Button>
        <Collapse in={showMore} unmountOnExit>
          <Stack spacing={1.5}>
            <TextField
              select
              size="small"
              label="Home terminal time zone"
              value={form.homeTz}
              onChange={(e) => update({ homeTz: e.target.value })}
              error={Boolean(errors.home_tz)}
              helperText={errors.home_tz ?? 'All log times use this zone (guide p. 16)'}
            >
              {zoneOptions(form.homeTz).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </TextField>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
              {HEADER_FIELDS.map((field) => (
                <TextField
                  key={field}
                  size="small"
                  label={HEADER_LABELS[field]}
                  value={form.header[field]}
                  onChange={(e) => update({ header: { ...form.header, [field]: e.target.value } })}
                  slotProps={{ htmlInput: { maxLength: field === 'home_terminal' ? 200 : 100 } }}
                />
              ))}
            </Box>
          </Stack>
        </Collapse>

        <Button type="submit" variant="contained" size="large" disabled={planning} sx={{ py: 1.25 }}>
          {planning ? 'Planning…' : 'Plan trip'}
        </Button>
      </Stack>
    </Card>
  )
}

/** Keep a zone from a shared link selectable even if it is not in the short list. */
function zoneOptions(current: string): [string, string][] {
  if (!current || TIME_ZONES.some(([value]) => value === current)) return TIME_ZONES
  return [...TIME_ZONES, [current, current]]
}

/** The API's field errors, keyed like the form. */
function serverErrors(error?: ApiError | null): Record<string, string> {
  if (!error) return {}
  if (error.field && error.field !== 'route') return { [error.field]: error.message }
  if (!error.fields) return {}
  return Object.fromEntries(
    Object.entries(error.fields).map(([field, detail]) => [field, flatten(detail)]),
  )
}

function flatten(detail: unknown): string {
  if (Array.isArray(detail)) return detail.map(flatten).join(' ')
  if (detail && typeof detail === 'object') return Object.values(detail).map(flatten).join(' ')
  return String(detail)
}
