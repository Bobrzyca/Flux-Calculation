import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import type { FitMode } from '@/api/types'
import { SpotDetail } from './SpotDetail'
import { renderWithProviders } from '@/test/utils'

const ANALYSIS = 'an_kampinos_0702'

function renderDetail(fitMode: FitMode = 'auto') {
  renderWithProviders(
    <SpotDetail
      analysisId={ANALYSIS}
      nr={1}
      spotNrs={[1, 2]}
      fitMode={fitMode}
      onClose={() => {}}
      onNavigate={() => {}}
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
})
