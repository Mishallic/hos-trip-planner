import { Box, Button, Typography } from '@mui/material'
import { FileText } from 'lucide-react'
import { useState } from 'react'

import { AppShell, type View } from './components/AppShell'
import { DirectionsView } from './features/directions/DirectionsView'
import { LogsView } from './features/logs/LogsView'
import { PlanView } from './features/plan/PlanView'
import { TripForm } from './features/trip-form/TripForm'
import { VerdictBadge } from './features/trip-summary/VerdictBadge'
import { useStopSelection } from './state/selection'
import { useTripPlan } from './state/useTripPlan'
import { color } from './theme/tokens'

function App() {
  const [view, setView] = useState<View>('plan')
  const [editing, setEditing] = useState(false)
  const { form, plan, error, isPlanning, submit } = useTripPlan()
  // One selected stop for the map, timeline, list and clocks. A new plan clears it.
  const selection = useStopSelection(plan)

  const tripForm = (
    <TripForm
      initial={form}
      collapsed={Boolean(plan) && !editing && !isPlanning}
      onExpand={() => setEditing(true)}
      planning={isPlanning}
      error={error}
      onSubmit={(next) => {
        submit(next)
        setEditing(false)
      }}
    />
  )

  return (
    <AppShell
      view={view}
      onViewChange={setView}
      title={
        plan && (
          <Typography noWrap sx={{ fontSize: 14, fontWeight: 500, color: 'inherit' }}>
            {plan.summary.from} → {plan.summary.pickup} → {plan.summary.dropoff}
          </Typography>
        )
      }
      badge={plan && <VerdictBadge plan={plan} />}
    >
      {view === 'plan' && (
        <PlanView
          plan={plan}
          form={tripForm}
          planning={isPlanning}
          selection={selection}
        />
      )}
      {view === 'logs' && (plan ? <LogsView plan={plan} /> : <NoPlanYet onPlan={() => setView('plan')} />)}
      {view === 'directions' &&
        (plan ? <DirectionsView plan={plan} /> : <NoPlanYet onPlan={() => setView('plan')} />)}
    </AppShell>
  )
}

function NoPlanYet({ onPlan }: { onPlan: () => void }) {
  return (
    <Box sx={{ height: '100%', display: 'grid', placeItems: 'center', p: 3, textAlign: 'center' }}>
      <Box>
        <Box sx={{ color: color.turquoise, display: 'flex', justifyContent: 'center', mb: 1.5 }}>
          <FileText size={34} strokeWidth={1.6} />
        </Box>
        <Typography variant="h6" component="p">
          Plan a trip first
        </Typography>
        <Typography variant="body2" sx={{ mt: 0.75, mb: 2 }}>
          Logs and directions appear once the trip is planned.
        </Typography>
        <Button variant="contained" onClick={onPlan}>
          Go to the trip form
        </Button>
      </Box>
    </Box>
  )
}

export default App
