import { expect, test } from '@playwright/test'

/**
 * Smoke test: the app shell loads and does not white-screen.
 *
 * Intentionally backend-independent — it asserts the persistent header and the
 * document title, which render regardless of API state. This guards against
 * build/routing regressions that break the whole app. Backend-dependent flows
 * (upload → confirm → results) are added later with a live API.
 */
test('app shell renders on the home page', async ({ page }) => {
  await page.goto('/')

  await expect(page).toHaveTitle(/Flux Calculation/)
  // The persistent top bar (role="banner") is always present.
  await expect(page.getByRole('banner')).toBeVisible()
})

test('unknown route still renders the app shell', async ({ page }) => {
  await page.goto('/this-route-does-not-exist')
  await expect(page.getByRole('banner')).toBeVisible()
})
