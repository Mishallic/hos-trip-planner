import { Box, ButtonBase, Stack, Tooltip, Typography } from '@mui/material'
import { FileText, Map, Navigation } from 'lucide-react'
import type { ReactNode } from 'react'

import { color, layout, radius } from '../theme/tokens'
import { BrandMark } from './BrandMark'

export type View = 'plan' | 'logs' | 'directions'

const NAV: { view: View; label: string; Icon: typeof Map }[] = [
  { view: 'plan', label: 'Plan', Icon: Map },
  { view: 'logs', label: 'Logs', Icon: FileText },
  { view: 'directions', label: 'Directions', Icon: Navigation },
]

interface AppShellProps {
  view: View
  onViewChange: (view: View) => void
  title?: ReactNode
  badge?: ReactNode
  children: ReactNode
}

const MOBILE = `@media (max-width: ${layout.mobile - 1}px)`

const visuallyHidden = {
  position: 'absolute',
  width: '1px',
  height: '1px',
  overflow: 'hidden',
  clip: 'rect(0 0 0 0)',
  whiteSpace: 'nowrap',
} as const

export function AppShell({ view, onViewChange, title, badge, children }: AppShellProps) {
  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: `${layout.rail}px 1fr`,
        gridTemplateRows: `${layout.topBar}px 1fr auto`,
        height: '100dvh',
        [MOBILE]: {
          gridTemplateColumns: '1fr',
          gridTemplateRows: `${layout.topBarMobile}px 1fr auto ${layout.bottomNav}px`,
          height: 'auto',
          minHeight: '100dvh',
        },
      }}
    >
      <Rail view={view} onViewChange={onViewChange} />

      <Box
        component="header"
        sx={{
          gridColumn: 2,
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          px: 3,
          borderBottom: `1px solid ${color.borderSoft}`,
          background: 'rgba(5, 6, 15, 0.55)',
          backdropFilter: 'blur(12px)',
          minWidth: 0,
          // On a phone the page scrolls under it, light log sheets included: less see-through.
          [MOBILE]: { gridColumn: 1, px: 2, position: 'sticky', top: 0, zIndex: 10, background: 'rgba(5, 6, 15, 0.9)' },
        }}
      >
        <Box sx={{ display: 'none', [MOBILE]: { display: 'flex' } }}>
          <BrandMark size={28} />
        </Box>
        {/* On a phone the plan's badge needs the room; the name stays for screen readers. */}
        <Typography
          variant="h6"
          component="h1"
          sx={{ whiteSpace: 'nowrap', ...(badge ? { [MOBILE]: visuallyHidden } : {}) }}
        >
          HOS Trip Planner
        </Typography>
        {title && (
          <Box
            sx={{
              minWidth: 0,
              color: color.textSecondary,
              borderLeft: `1px solid ${color.borderSoft}`,
              pl: 2,
              overflow: 'hidden',
              [MOBILE]: { display: 'none' },
            }}
          >
            {title}
          </Box>
        )}
        <Box sx={{ ml: 'auto', flexShrink: 0, minWidth: 0, [MOBILE]: { flexShrink: 1 } }}>{badge}</Box>
      </Box>

      <Box
        component="main"
        sx={{ gridColumn: 2, minHeight: 0, minWidth: 0, [MOBILE]: { gridColumn: 1 } }}
      >
        {children}
      </Box>

      <Box
        component="footer"
        sx={{
          gridColumn: 2,
          px: 3,
          py: 0.75,
          borderTop: `1px solid ${color.borderSoft}`,
          [MOBILE]: { gridColumn: 1, px: 2, py: 1.5 },
        }}
      >
        <Typography variant="caption" component="p">
          Place names © GeoNames (CC BY 4.0) · Map data © OpenStreetMap contributors · Routing OSRM ·
          Search Photon
        </Typography>
      </Box>

      <BottomNav view={view} onViewChange={onViewChange} />
    </Box>
  )
}

function Rail({ view, onViewChange }: Pick<AppShellProps, 'view' | 'onViewChange'>) {
  return (
    <Box
      component="nav"
      aria-label="Main"
      sx={{
        gridRow: '1 / 4',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 1,
        py: 2,
        background: color.bgDeep,
        borderRight: `1px solid ${color.borderSoft}`,
        [MOBILE]: { display: 'none' },
      }}
    >
      <Box sx={{ mb: 2 }}>
        <BrandMark />
      </Box>
      <Stack
        spacing={1}
        sx={{
          p: 0.75,
          borderRadius: radius.chip + 2,
          background: 'rgba(255, 255, 255, 0.03)',
          border: `1px solid ${color.borderSoft}`,
        }}
      >
        {NAV.map(({ view: item, label, Icon }) => {
          const active = item === view
          return (
            <Tooltip key={item} title={label} placement="right">
              <ButtonBase
                aria-label={label}
                aria-current={active ? 'page' : undefined}
                onClick={() => onViewChange(item)}
                sx={{
                  width: 40,
                  height: 40,
                  borderRadius: `${radius.button}px`,
                  color: active ? color.text : color.textMuted,
                  background: active ? color.teal : 'transparent',
                  boxShadow: active ? '0 4px 16px rgba(0, 139, 139, 0.45)' : 'none',
                  transition: 'background 120ms, color 120ms',
                  '&:hover': { color: color.text, background: active ? color.teal : color.chip },
                }}
              >
                <Icon size={19} strokeWidth={1.9} />
              </ButtonBase>
            </Tooltip>
          )
        })}
      </Stack>
    </Box>
  )
}

function BottomNav({ view, onViewChange }: Pick<AppShellProps, 'view' | 'onViewChange'>) {
  return (
    <Box
      component="nav"
      aria-label="Main"
      sx={{
        display: 'none',
        [MOBILE]: {
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          position: 'sticky',
          bottom: 0,
          zIndex: 10,
          background: 'rgba(5, 6, 15, 0.92)',
          backdropFilter: 'blur(12px)',
          borderTop: `1px solid ${color.borderSoft}`,
        },
      }}
    >
      {NAV.map(({ view: item, label, Icon }) => {
        const active = item === view
        return (
          <ButtonBase
            key={item}
            aria-current={active ? 'page' : undefined}
            onClick={() => onViewChange(item)}
            sx={{ flexDirection: 'column', gap: 0.5, color: active ? color.turquoise : color.textMuted }}
          >
            <Box
              sx={{
                px: 2,
                py: 0.25,
                borderRadius: radius.pill,
                background: active ? 'rgba(0, 139, 139, 0.35)' : 'transparent',
                display: 'flex',
              }}
            >
              <Icon size={20} strokeWidth={1.9} />
            </Box>
            <Typography variant="caption" sx={{ color: 'inherit', fontWeight: 600 }}>
              {label}
            </Typography>
          </ButtonBase>
        )
      })}
    </Box>
  )
}
