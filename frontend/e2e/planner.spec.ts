import { expect, test } from '@playwright/test'

import { mockApi, PLANS, TRIP_LINK, TRIP_LINK_FROM_NOW } from './api.ts'

const arrival = /^Arrives /

test('a sample trip plans in one click and shows the arrival, the stops and the map', async ({ page }) => {
  const plans = await mockApi(page)
  await page.goto('/')

  await page.getByRole('button', { name: /Los Angeles → Phoenix → Atlanta/ }).click()

  await expect(page.getByRole('heading', { name: arrival })).toBeVisible()
  expect(plans).toHaveLength(1)
  expect(plans[0].postDataJSON()).toMatchObject({ cycle_used_hours: 52, current: { label: 'Los Angeles, CA' } })
  // Tomorrow at 07:00: the days on the sample's card hold whenever it is tried.
  expect(plans[0].postDataJSON().start_time).toMatch(/T07:00$/)
  await expect(page.getByRole('option')).toHaveCount(PLANS.restart.stops.length)
  await expect(page.getByRole('region', { name: 'Route map' })).toBeVisible()
})

test('a trip planned from "now" is pinned in the link, and planning it again starts from now', async ({ page }) => {
  const plans = await mockApi(page)
  await page.goto(TRIP_LINK_FROM_NOW)
  await expect(page.getByRole('heading', { name: arrival })).toBeVisible()
  // The link replans the same trip; "now=1" marks the start as "now" for editing.
  await expect(page).toHaveURL(/start=[^&]+&now=1/)
  const planned = plans.length

  await page.getByRole('button', { name: 'Edit' }).click()
  await expect(page.locator('input[type="datetime-local"]')).toHaveValue('') // "Empty = now"
  await page.getByRole('button', { name: 'Plan trip' }).click()

  await expect.poll(() => plans.length).toBe(planned + 1)
  expect(plans.at(-1)?.postDataJSON().start_time).toBeUndefined()
})

test('Enter in a place field picks the top suggestion and does not plan', async ({ page }) => {
  const plans = await mockApi(page)
  await page.goto('/')
  const dropoff = page.getByRole('combobox', { name: 'Drop-off' })

  await dropoff.fill('atla')
  await expect(page.getByRole('option', { name: 'Atlanta, GA' })).toBeVisible()
  await dropoff.press('Enter')

  await expect(dropoff).toHaveValue('Atlanta, GA')
  expect(plans).toHaveLength(0)
})

test('the logs have one sheet per day, each adding up to 24 hours', async ({ page }) => {
  await mockApi(page)
  await page.goto(`${TRIP_LINK}&view=logs`)
  const days = page.getByRole('tab')

  await expect(days).toHaveCount(PLANS.restart.logs.length)
  for (let day = 0; day < PLANS.restart.logs.length; day++) {
    await days.nth(day).click()
    const sheet = page.getByRole('tabpanel')
    await expect(sheet).toContainText(`sheet ${day + 1} of ${PLANS.restart.logs.length}`)
    await expect(sheet).toContainText('24:00')
  }
})

test('every day prints, each on its own page', async ({ page }) => {
  await mockApi(page)
  await page.goto(`${TRIP_LINK}&view=logs`)
  await expect(page.getByRole('tab')).toHaveCount(PLANS.restart.logs.length)

  await page.emulateMedia({ media: 'print' })

  const sheets = page.locator('section[id^="day-panel-"]')
  await expect(sheets).toHaveCount(PLANS.restart.logs.length)
  for (const sheet of await sheets.all()) await expect(sheet).toBeVisible()
  await expect(page.getByRole('button', { name: /Print/ })).toBeHidden()
})

test('Back returns from the logs to the plan of the same trip, without replanning', async ({ page }) => {
  const plans = await mockApi(page)
  await page.goto(TRIP_LINK)
  await expect(page.getByRole('heading', { name: arrival })).toBeVisible()
  const planned = plans.length // React's development mode may send the first one twice

  await page.getByRole('button', { name: 'Logs' }).click()
  await expect(page).toHaveURL(/view=logs/)
  await expect(page.getByRole('heading', { name: 'Daily logs' })).toBeVisible()
  await page.goBack()

  await expect(page.getByRole('heading', { name: arrival })).toBeVisible()
  expect(plans).toHaveLength(planned)
})

test('a place that cannot be found is reported on its field', async ({ page }) => {
  const message = 'No place in the US, Canada or Mexico matches "asdfgh".'
  await mockApi(page, { status: 422, body: { error: { code: 'not_found', field: 'dropoff', message } } })
  await page.goto('/')

  await page.getByRole('combobox', { name: 'Current location' }).fill('Dallas, TX')
  await page.getByRole('combobox', { name: 'Pickup' }).fill('Fort Worth, TX')
  await page.getByRole('combobox', { name: 'Drop-off' }).fill('asdfgh')
  await page.getByRole('button', { name: 'Plan trip' }).click()

  await expect(page.getByText(message)).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Drop-off' })).toHaveAttribute('aria-invalid', 'true')
})

test('on a phone, a marker that hides stops near it says so', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'only a small map hides markers on this trip')
  await mockApi(page)
  await page.goto(TRIP_LINK)
  await expect(page.locator('.route-marker').first()).toBeVisible()

  // Its name, which screen readers read, and its tooltip both count what is hidden.
  await expect(page.locator('.route-marker[title*="nearby: zoom in"]').first()).toBeAttached()
})

test('on a phone, a zoomed log sheet keeps its row labels in view', async ({ page, isMobile }) => {
  test.skip(!isMobile, 'only a phone needs to zoom the sheet')
  await mockApi(page)
  await page.goto(`${TRIP_LINK}&view=logs`)

  await page.getByRole('button', { name: 'Zoom in' }).click()
  const scroller = page.getByRole('tabpanel').getByLabel(/^Log sheet, /)
  await scroller.evaluate((element) => {
    element.scrollLeft = 400
  })

  const labels = scroller.locator('svg[aria-hidden="true"]').first()
  const [box, edge] = await Promise.all([labels.boundingBox(), scroller.boundingBox()])
  expect(Math.abs((box?.x ?? Infinity) - (edge?.x ?? 0))).toBeLessThan(2)
})
