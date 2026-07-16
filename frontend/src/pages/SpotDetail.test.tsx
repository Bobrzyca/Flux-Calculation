import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SpotDetail } from './SpotDetail'
import { renderWithProviders } from '@/test/utils'

const ANALYSIS = 'an_kampinos_0702'

function renderDetail() {
  renderWithProviders(
    <SpotDetail
      analysisId={ANALYSIS}
      nr={1}
      spotNrs={[1, 2]}
      onClose={() => {}}
      onNavigate={() => {}}
    />,
  )
}

describe('SpotDetail', () => {
  it('shows how much the fit window was shifted and the spike count', async () => {
    renderDetail()
    expect(
      await screen.findByText(/Window shifted \+30 s after the recorded start/),
    ).toBeInTheDocument()
    expect(screen.getByText('Spikes dropped')).toBeInTheDocument()
  })

  it('switches to the whole-recording fit when toggled', async () => {
    renderDetail()
    await screen.findByText(/Window shifted/)

    await userEvent.click(screen.getByRole('tab', { name: 'Whole recording' }))

    expect(
      await screen.findByText(/Fitting the whole recording \(600 s\) as-is/),
    ).toBeInTheDocument()
  })
})
