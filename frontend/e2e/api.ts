import { readFileSync } from 'node:fs'

import type { Page, Request } from '@playwright/test'

// Plans recorded from the API, the same ones the unit tests use.
const fixture = (name: string) =>
  JSON.parse(readFileSync(new URL(`../src/fixtures/${name}.json`, import.meta.url), 'utf-8'))

export const PLANS = {
  restart: fixture('plan-restart'), // Los Angeles -> Phoenix -> Atlanta, 5 sheets, a 34-hour restart
  multiDay: fixture('plan-multi-day'), // Chicago -> Indianapolis -> Denver, 3 sheets
  short: fixture('plan-short'), // Dallas -> Fort Worth -> Houston, 1 sheet
}

const SUGGESTIONS: Record<string, { label: string; lat: number; lon: number }[]> = {
  atla: [
    { label: 'Atlanta, GA', lat: 33.75447, lon: -84.38982 },
    { label: 'Atlas, IL', lat: 39.51394, lon: -90.96958 },
    { label: 'Atlantic City, NJ', lat: 39.36429, lon: -74.42294 },
  ],
}

/** Answers the app's API calls; returns the plan requests it saw. */
export async function mockApi(
  page: Page,
  plan: object | { status: number; body: object } = PLANS.restart,
): Promise<Request[]> {
  const planRequests: Request[] = []
  await page.route('**/api/trips/plan', async (route) => {
    planRequests.push(route.request())
    const answer = 'status' in plan ? plan : { status: 200, body: plan }
    await route.fulfill({ status: answer.status, json: answer.body })
  })
  await page.route('**/api/places?**', async (route) => {
    const query = new URL(route.request().url()).searchParams.get('q')?.toLowerCase() ?? ''
    await route.fulfill({ json: { places: SUGGESTIONS[query] ?? [] } })
  })
  return planRequests
}

/** The link the app writes for a trip of picked places: it plans on load. */
export const TRIP_LINK =
  '/?from=Los+Angeles%2C+CA&from_at=34.05369%2C-118.24277&pickup=Phoenix%2C+AZ&pickup_at=33.44844%2C-112.07414' +
  '&dropoff=Atlanta%2C+GA&dropoff_at=33.75447%2C-84.38982&cycle=52&start=2026-10-05T07%3A00&tz=America%2FLos_Angeles'

/** The same trip without a start: it plans from now, and the app pins the start into the link. */
export const TRIP_LINK_FROM_NOW = TRIP_LINK.replace('&start=2026-10-05T07%3A00&tz=America%2FLos_Angeles', '')
