import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '@/App'
import { renderWithProviders } from '@/test/utils'

const ROUTE = '/analyses/an_kampinos_0702/results'

describe('Results screen', () => {
  it('renders the quality-check summary and the results table', async () => {
    renderWithProviders(<App />, { route: ROUTE })
    expect(await screen.findByText('Quality check')).toBeInTheDocument()
    // Column headers present
    expect(screen.getByText('CO₂ flux')).toBeInTheDocument()
    expect(screen.getByText('CH₄ flux')).toBeInTheDocument()
    // A skipped spot is shown with its reason
    expect(screen.getByText(/Skipped —/)).toBeInTheDocument()
  })

  it('filters to flagged spots only', async () => {
    renderWithProviders(<App />, { route: ROUTE })
    await screen.findByText('Quality check')
    const table = screen.getByRole('table')

    // Spots 1 & 2 (unflagged, GPS 52.3012…) visible before filtering.
    expect(
      within(table).getAllByText('52.3012, 20.7891').length,
    ).toBeGreaterThan(0)

    await userEvent.click(screen.getByLabelText('Flagged only'))
    // Unflagged rows drop out; the anomalous spot 7 (GPS 52.3042…) stays.
    expect(
      within(table).queryByText('52.3012, 20.7891'),
    ).not.toBeInTheDocument()
    expect(
      within(table).getAllByText('52.3042, 20.7938').length,
    ).toBeGreaterThan(0)
  })
})
