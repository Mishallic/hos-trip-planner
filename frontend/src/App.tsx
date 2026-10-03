import { Chip, Typography } from '@mui/material'
import { useState } from 'react'

import type { TripPlan } from './api/types'
import { AppShell, type View } from './components/AppShell'
import { DirectionsView } from './features/directions/DirectionsView'
import { LogsView } from './features/logs/LogsView'
import { PlanView } from './features/plan/PlanView'
import sample from './fixtures/plan-multi-day.json'
import { color } from './theme/tokens'

// Until the form talks to the API (chunk 15), the shell shows a real saved plan.
const plan = sample as TripPlan

function App() {
  const [view, setView] = useState<View>('plan')
  const { summary } = plan

  return (
    <AppShell
      view={view}
      onViewChange={setView}
      title={
        <Typography noWrap sx={{ fontSize: 14, fontWeight: 500, color: 'inherit' }}>
          {summary.from} → {summary.pickup} → {summary.dropoff}
        </Typography>
      }
      badge={
        <Chip
          label="Within HOS limits"
          size="small"
          sx={{
            color: color.mint,
            background: 'rgba(20, 210, 155, 0.10)',
            border: '1px solid rgba(20, 210, 155, 0.35)',
          }}
        />
      }
    >
      {view === 'plan' && <PlanView plan={plan} />}
      {view === 'logs' && <LogsView plan={plan} />}
      {view === 'directions' && <DirectionsView plan={plan} />}
    </AppShell>
  )
}

export default App
