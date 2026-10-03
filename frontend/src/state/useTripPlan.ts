import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { type ApiError, type PlanRequest, planTrip } from '../api/client'
import type { TripPlan } from '../api/types'
import { formFromParams, paramsFromForm, requestFromForm, type TripForm } from './urlState'

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

/** The form as stored in the URL, and the plan for it. Back and forward work. */
export function useTripPlan() {
  const queryClient = useQueryClient()
  const [params, setParams] = useState(readUrl)

  useEffect(() => {
    const onPop = () => setParams(readUrl())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const form = useMemo(() => formFromParams(params), [params])
  const request = useMemo(() => requestFromForm(form), [form])

  const query = useQuery<TripPlan, ApiError>({
    queryKey: planKey(request),
    queryFn: async ({ signal }) => {
      const plan = await planTrip(request!, signal)
      // Pin "now" and the home time zone into the URL, so the link shows this same
      // plan later. The result is cached under the pinned inputs too: no refetch.
      if (!form.startTime || !form.homeTz) {
        const pinned: TripForm = {
          ...form,
          startTime: form.startTime || plan.summary.start.slice(0, 16),
          homeTz: form.homeTz || plan.log_header.time_zone,
        }
        const pinnedParams = paramsFromForm(pinned)
        queryClient.setQueryData(planKey(requestFromForm(pinned)), plan)
        writeUrl(pinnedParams, true)
        setParams(pinnedParams)
      }
      return plan
    },
    enabled: request !== null,
    staleTime: Infinity,
    gcTime: 30 * 60 * 1000,
    retry: false,
  })

  const submit = useCallback((next: TripForm) => {
    const nextParams = paramsFromForm(next)
    writeUrl(nextParams)
    setParams(nextParams)
  }, [])

  return { form, request, plan: query.data, error: query.error, isPlanning: query.isFetching, submit }
}
