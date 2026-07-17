import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright config for frontend end-to-end tests.
 *
 * e2e specs live in `tests/e2e/` (kept separate from the co-located Vitest unit
 * tests under `src/`). Playwright builds the app and serves it with `vite
 * preview`; the smoke suite checks the app shell renders and needs no backend.
 * Deeper flows (upload → confirm → results) that require a running backend come
 * in a later pass — start `uvicorn` alongside and point specs at real data.
 */
const PORT = 4173
const BASE_URL = `http://localhost:${PORT}`

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  // Build once, then serve the production bundle. Reused locally if already up.
  webServer: {
    command: `npm run build && npm run preview -- --port ${PORT} --strictPort`,
    url: BASE_URL,
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
  },
})
