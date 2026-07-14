import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Home } from './Home'
import { renderWithProviders } from '@/test/utils'

describe('Home', () => {
  it('shows a loading skeleton then the seeded analyses', async () => {
    renderWithProviders(<Home />)
    expect(screen.getByLabelText('Loading analyses')).toBeInTheDocument()
    expect(await screen.findByText('Kampinos — 2 July')).toBeInTheDocument()
    expect(screen.getByText('Biebrza fen — 20 June')).toBeInTheDocument()
  })

  it('opens a confirm dialog before deleting', async () => {
    renderWithProviders(<Home />)
    await screen.findByText('Kampinos — 2 July')
    await userEvent.click(screen.getByLabelText('Delete Kampinos — 2 July'))
    expect(
      await screen.findByRole('dialog', { name: 'Delete analysis?' }),
    ).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))
    await waitFor(() =>
      expect(screen.queryByText('Kampinos — 2 July')).not.toBeInTheDocument(),
    )
  })
})
