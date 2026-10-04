import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { type ApiError, type PlanRequest, planTrip } from '../api/client'
import type { TripPlan } from '../api/types'
import {
  formFromParams,
  paramsFromForm,
  requestFromForm,
  type TripForm,
  type View,
  viewFromParams,
  withView,
} from './urlState'

function readUrl(): URLSearchParams {
  return new URLSearchParams(window.location.search)
}

function writeUrl(params: URLSearchParams, replace = false) {
  const query = params.toString()
  const url = `${window.location.pathname}${query ? `?${query}` : ''}`
  if (replace) window.history.replaceState(null, '', url)
  else window.history.pushState(null, '', url)
}

const planKey = (request: PlanRequest | null) => ['plan', request] as const

/**
 * The form and the view as stored in the URL, and the plan for the form. Back and
 * forward move between trips and between views; a link opens the same trip and view.
 */
export function useTripPlan() {
  const queryClient = useQueryClient()
  const [params, setParams] = useState(readUrl)

  useEffect(() => {
    const onPop = () => setParams(readUrl())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const form = useMemo(() => formFromParams(params), [params])
  const view = viewFromParams(params)
  const request = useMemo(() => requestFromForm(form), [form])

  const query = useQuery<TripPlan, ApiError>({
    queryKey: planKey(request),
    queryFn: ({ signal }) => {
      if (!request) throw new Error('No trip to plan') // never: the query is off without one
      return planTrip(request, signal)
    },
    enabled: request !== null,
    staleTime: Infinity,
    gcTime: 30 * 60 * 1000,
    retry: false,
  })
  const plan = query.data

  // Pin "now" and the home time zone into the URL, so the link shows this same plan
  // later; the plan is cached under the pinned inputs, so opening it refetches nothing.
  // The form here keeps "now", so editing the trip starts from now again.
  useEffect(() => {
    if (!plan || (form.startTime && form.homeTz)) return
    const pinned: TripForm = {
      ...form,
      startTime: form.startTime || plan.summary.start.slice(0, 16),
      startAuto: form.startAuto || !form.startTime,
      homeTz: form.homeTz || plan.log_header.time_zone,
    }
    queryClient.setQueryData(planKey(requestFromForm(pinned)), plan)
    writeUrl(withView(paramsFromForm(pinned), view), true)
  }, [plan, form, view, queryClient])

  const submit = useCallback(
    (next: TripForm) => {
      const nextParams = paramsFromForm(next) // a new trip opens on the plan
      // Without a start the trip starts now, not when it was last planned from "now".
      if (!next.startTime) queryClient.removeQueries({ queryKey: planKey(requestFromForm(next)), exact: true })
      writeUrl(nextParams, nextParams.toString() === readUrl().toString())
      setParams(nextParams)
    },
    [queryClient],
  )

  const changeView = useCallback(
    (next: View) => {
      if (next === view) return
      const nextParams = withView(params, next)
      writeUrl(nextParams)
      setParams(nextParams)
    },
    [params, view],
  )

  return { form, view, changeView, plan, error: query.error, isPlanning: query.isFetching, submit }
}
