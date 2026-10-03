import { Box, Button, Typography } from '@mui/material'
import { FileText } from 'lucide-react'
import { useState } from 'react'

import type { ApiError } from './api/client'
import { AppShell, type View } from './components/AppShell'
import { ErrorBoundary } from './components/ErrorBoundary'
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
  const planKey = plan ? `${plan.summary.start}|${plan.summary.dropoff_arrival}|${plan.logs.length}` : 'none'

  // On a phone the page itself scrolls: a new view starts at its top, not halfway
  // down where the last one was left.
  const changeView = (next: View) => {
    setView(next)
    window.scrollTo(0, 0)
  }

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
      onViewChange={changeView}
      title={
        plan && (
          <Typography noWrap sx={{ fontSize: 14, fontWeight: 500, color: 'inherit' }}>
            {plan.summary.from} → {plan.summary.pickup} → {plan.summary.dropoff}
          </Typography>
        )
      }
      badge={plan && <VerdictBadge plan={plan} />}
      busy={isPlanning}
    >
      {view === 'plan' && <PlanView plan={plan} form={tripForm} planning={isPlanning} selection={selection} />}
      {view !== 'plan' && (
        // A new plan (Back, Forward, a new trip) starts the view afresh, error or not.
        <ErrorBoundary key={`${view}|${planKey}`}>
          {!plan ? (
            <NoPlanYet planning={isPlanning} error={error} onPlan={() => changeView('plan')} />
          ) : view === 'logs' ? (
            <LogsView plan={plan} selection={selection} />
          ) : (
            <DirectionsView plan={plan} selection={selection} />
          )}
        </ErrorBoundary>
      )}
    </AppShell>
  )
}

/** Logs and directions before there is a plan to show: why, and the way to the form. */
function NoPlanYet({ planning, error, onPlan }: { planning: boolean; error: ApiError | null; onPlan: () => void }) {
  const [title, text] = planning
    ? ['Planning the trip…', 'Logs and directions appear as soon as the plan is ready.']
    : error
      ? ['The trip could not be planned', error.message]
      : ['Plan a trip first', 'Logs and directions appear once the trip is planned.']
  return (
    <Box sx={{ height: '100%', display: 'grid', placeItems: 'center', p: 3, textAlign: 'center' }}>
      <Box sx={{ maxWidth: 420 }} role={error && !planning ? 'alert' : undefined}>
        <Box sx={{ color: error && !planning ? color.amber : color.turquoise, display: 'flex', justifyContent: 'center', mb: 1.5 }}>
          <FileText size={34} strokeWidth={1.6} />
        </Box>
        <Typography variant="h6" component="p">
          {title}
        </Typography>
        <Typography variant="body2" sx={{ mt: 0.75, mb: 2 }}>
          {text}
        </Typography>
        {!planning && (
          <Button variant="contained" onClick={onPlan}>
            Go to the trip form
          </Button>
        )}
      </Box>
    </Box>
  )
}

export default App
