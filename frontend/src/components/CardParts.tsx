import { Box, Stack, Typography } from '@mui/material'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { color, radius } from '../theme/tokens'

/** A tinted square behind an icon, as on the product's feature cards. */
export function IconChip({ children, tone = color.turquoise }: { children: ReactNode; tone?: string }) {
  return (
    <Box
      sx={{
        width: 40,
        height: 40,
        flexShrink: 0,
        borderRadius: `${radius.chip}px`,
        display: 'grid',
        placeItems: 'center',
        color: tone,
        background: `${tone}1A`,
        border: `1px solid ${tone}40`,
      }}
    >
      {children}
    </Box>
  )
}

/** Icon chip, title and turquoise subtitle at the top of a card. */
export function CardHeading({
  Icon,
  title,
  subtitle,
  hint,
}: {
  Icon: LucideIcon
  title: string
  subtitle: string
  hint?: string
}) {
  return (
    <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', mb: 2 }}>
      <IconChip>
        <Icon size={19} strokeWidth={1.9} />
      </IconChip>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="h6" component="h2" sx={{ lineHeight: 1.25 }}>
          {title}
        </Typography>
        <Typography variant="subtitle2" component="p" sx={{ fontSize: 12.5 }}>
          {subtitle}
        </Typography>
      </Box>
      {hint && <Typography variant="caption">{hint}</Typography>}
    </Stack>
  )
}

/** Small uppercase badge on a tinted pill, like the feature cards' "ESSENTIAL". */
export function Badge({ label, tone = color.turquoise }: { label: string; tone?: string }) {
  return (
    <Box
      component="span"
      sx={{
        px: 1,
        py: 0.25,
        borderRadius: `${radius.pill}px`,
        fontSize: 10.5,
        fontWeight: 700,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        color: tone,
        background: `${tone}1A`,
        border: `1px solid ${tone}33`,
      }}
    >
      {label}
    </Box>
  )
}
