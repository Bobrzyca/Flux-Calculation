import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { FitMode } from '@/api/types'
import { SpotDetail } from './SpotDetail'
import { renderWithProviders } from '@/test/utils'

const ANALYSIS = 'an_kampinos_0702'

function renderDetail(fitMode: FitMode = 'auto', onFitChanged = () => {}) {
  renderWithProviders(
    <SpotDetail
      analysisId={ANALYSIS}
      nr={1}
      spotNrs={[1, 2]}
      fitMode={fitMode}
      onClose={() => {}}
      onNavigate={() => {}}
      onFitChanged={onFitChanged}
    />,
  )
}

describe('SpotDetail', () => {
  it('shows how much the fit window was shifted and the spike count', async () => {
    renderDetail('auto')
    expect(
      await screen.findByText(/Window shifted \+30 s after the recorded start/),
    ).toBeInTheDocument()
    expect(screen.getByText('Spikes dropped')).toBeInTheDocument()
  })

  it('reflects the whole-recording fit mode from Results', async () => {
    renderDetail('full')
    expect(
      await screen.findByText(/Fitting the whole recording \(600 s\) as-is/),
    ).toBeInTheDocument()
  })

  it('applies a manual window shift and notifies the parent', async () => {
    let changed = 0
    renderDetail('auto', () => {
      changed += 1
    })
    await screen.findByText(/Window shifted/)

    const input = screen.getByLabelText('Fit window start offset (seconds)')
    await userEvent.clear(input)
    await userEvent.type(input, '75')
    await userEvent.click(screen.getByRole('button', { name: 'Apply' }))

    expect(
      await screen.findByText(/Manual fit: window starts \+75 s/),
    ).toBeInTheDocument()
    expect(changed).toBeGreaterThan(0)
    // Reset-to-auto appears once a manual offset is active.
    expect(
      screen.getByRole('button', { name: 'Reset to auto' }),
    ).toBeInTheDocument()
  })
})
