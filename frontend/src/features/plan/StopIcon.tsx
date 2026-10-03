import { Box } from '@mui/material'
import { BedDouble, ClipboardCheck, Coffee, Flag, Fuel, MapPin, RotateCcw } from 'lucide-react'

import type { StopKind } from '../../api/types'
import { stopColor } from '../../theme/tokens'

const ICONS: Record<StopKind, typeof Fuel> = {
  pre_trip: ClipboardCheck,
  pickup: MapPin,
  dropoff: Flag,
  fuel: Fuel,
  break: Coffee,
  rest: BedDouble,
  restart: RotateCcw,
}

/** A round, filled icon per stop kind, as in the driver app's stop list. */
export function StopIcon({ kind, size = 34 }: { kind: StopKind; size?: number }) {
  const Icon = ICONS[kind]
  return (
    <Box
      sx={{
        width: size,
        height: size,
        flexShrink: 0,
        borderRadius: '50%',
        display: 'grid',
        placeItems: 'center',
        color: '#05060F',
        background: stopColor[kind],
        boxShadow: `0 0 0 4px ${stopColor[kind]}22`,
      }}
    >
      <Icon size={size * 0.5} strokeWidth={2.2} />
    </Box>
  )
}
