import { Box, ButtonBase, Card, Stack, Typography } from '@mui/material'
import { Navigation } from 'lucide-react'
import { useMemo } from 'react'

import type { TripPlan } from '../../api/types'
import { IconChip } from '../../components/CardParts'
import { hm, miles, STOP_LABEL, timeRange, zoneOf } from '../../lib/format'
import type { StopSelection } from '../../state/selection'
import { color, layout, radius, stopColor, stopTextColor } from '../../theme/tokens'
import { StopIcon } from '../itinerary/StopIcon'
import { directionRows } from './directionRows'

const MOBILE = `@media (max-width: ${layout.mobile - 1}px)`

/** "0.4 mi", or feet for the short hops between turns. */
function distance(value: number): string {
  if (value >= 0.1) return `${value.toLocaleString('en-US', { maximumFractionDigits: 1 })} mi`
  return value > 0 ? `${Math.max(50, Math.round((value * 5280) / 50) * 50)} ft` : ''
}

/** Turn-by-turn directions for each leg, with every planned stop where it happens. */
export function DirectionsView({ plan, selection }: { plan: TripPlan; selection: StopSelection }) {
  const legs = useMemo(() => directionRows(plan.route.legs, plan.stops), [plan.route.legs, plan.stops])

  return (
    <Box
      data-print-light
      sx={{ height: '100%', overflowY: 'auto', p: 3, [MOBILE]: { p: 2 }, '@media print': { height: 'auto', overflow: 'visible', p: 0 } }}
    >
      <Box sx={{ maxWidth: 760, mx: 'auto' }}>
        <Typography variant="h5" component="h2">
          Directions
        </Typography>
        <Typography variant="body2" sx={{ mb: 2.5 }}>
          {miles(plan.summary.total_miles)} · {plan.summary.driving} of driving · stops in the order you reach
          them · times in {zoneOf(plan)}
        </Typography>
        <Stack spacing={2}>
          {legs.map(({ leg, startMile, rows }) => (
            <Card key={leg.to} component="section" aria-label={`To ${leg.to === 'pickup' ? plan.summary.pickup : plan.summary.dropoff}`} sx={{ p: 2.5, [MOBILE]: { p: 2 } }}>
              <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', mb: 1.5 }}>
                <IconChip>
                  <Navigation size={19} strokeWidth={1.9} />
                </IconChip>
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="h6" component="h3">
                    To {leg.to === 'pickup' ? plan.summary.pickup : plan.summary.dropoff}
                  </Typography>
                  <Typography variant="body2">
                    {miles(leg.miles)} · {hm(leg.planned_min)} planned driving · from mile {startMile.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </Typography>
                </Box>
              </Stack>
              <Box component="ol" sx={{ listStyle: 'none', m: 0, p: 0 }}>
                {rows.map((row) =>
                  row.kind === 'step' ? (
                    <Box
                      component="li"
                      key={`step-${row.index}`}
                      sx={{
                        display: 'grid',
                        gridTemplateColumns: '28px 1fr auto',
                        columnGap: 1.5,
                        py: 0.9,
                        borderTop: `1px solid ${color.borderSoft}`,
                        alignItems: 'baseline',
                      }}
                    >
                      <Typography variant="caption" sx={{ textAlign: 'right' }}>
                        {row.index + 1}
                      </Typography>
                      <Typography sx={{ fontSize: 14 }}>{row.step.instruction}</Typography>
                      <Typography variant="caption" sx={{ whiteSpace: 'nowrap' }}>
                        {distance(row.step.miles)}
                      </Typography>
                    </Box>
                  ) : (
                    <Box component="li" key={`stop-${row.index}`} sx={{ borderTop: `1px solid ${color.borderSoft}`, py: 0.75 }}>
                      <ButtonBase
                        onClick={() => selection.select(row.index)}
                        aria-pressed={selection.selected === row.index}
                        sx={{
                          width: '100%',
                          justifyContent: 'flex-start',
                          textAlign: 'left',
                          gap: 1.5,
                          p: 1,
                          borderRadius: `${radius.button}px`,
                          background: selection.selected === row.index ? 'rgba(64, 224, 208, 0.08)' : `${stopColor[row.stop.kind]}0F`,
                          boxShadow: `inset 3px 0 0 ${stopColor[row.stop.kind]}`,
                          '&:focus-visible': { outline: `2px solid ${color.turquoise}`, outlineOffset: 1 },
                        }}
                      >
                        <StopIcon kind={row.stop.kind} />
                        <Box sx={{ minWidth: 0 }}>
                          <Typography sx={{ fontWeight: 700, fontSize: 14, color: stopTextColor[row.stop.kind] }}>
                            {STOP_LABEL[row.stop.kind]}
                            <Box component="span" sx={{ color: color.textMuted, fontWeight: 500 }}>
                              {' '}
                              · {row.stop.place ?? `mile ${row.stop.mile}`} · {timeRange(row.stop.start, row.stop.end)}
                            </Box>
                          </Typography>
                          <Typography variant="body2" sx={{ fontSize: 12.5 }}>
                            {row.stop.explanation}
                          </Typography>
                        </Box>
                      </ButtonBase>
                    </Box>
                  ),
                )}
              </Box>
            </Card>
          ))}
        </Stack>
      </Box>
    </Box>
  )
}
