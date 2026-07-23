import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Routes, Route } from 'react-router-dom'
import { ConfirmTemperature } from './ConfirmTemperature'
import { renderWithProviders } from '@/test/utils'

function renderPage() {
  renderWithProviders(
    <Routes>
      <Route
        path="/analyses/:id/confirm-temperature"
        element={<ConfirmTemperature />}
      />
      <Route path="/analyses/:id/results" element={<div>Results page</div>} />
    </Routes>,
    { route: '/analyses/an_kampinos_0702/confirm-temperature' },
  )
}

describe('ConfirmTemperature', () => {
  it('shows the parsed temperature summary for review', async () => {
    renderPage()
    expect(
      await screen.findByRole('heading', {
        name: /Confirm parsed temperature/,
      }),
    ).toBeInTheDocument()
    // Stats from the parsed file are surfaced (readings count + °C values).
    expect(screen.getByText('Readings')).toBeInTheDocument()
    expect(screen.getByText('Mean')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Confirm & compute/ }),
    ).toBeEnabled()
  })

  it('runs the match and navigates to results on confirm', async () => {
    renderPage()
    await screen.findByRole('heading', { name: /Confirm parsed temperature/ })
    await userEvent.click(
      screen.getByRole('button', { name: /Confirm & compute/ }),
    )
    expect(
      await screen.findByText('Results page', {}, { timeout: 4000 }),
    ).toBeInTheDocument()
  })
})
