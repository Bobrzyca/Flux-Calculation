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
      await screen.findByText(/Window starts 30 s after the recorded start/),
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
    await screen.findByText(/Window starts/)

    const input = screen.getByLabelText(
      'Fit window start offset (seconds; negative shifts earlier)',
    )
    await userEvent.clear(input)
    await userEvent.type(input, '75')
    // Ensure the input committed before applying (avoids a userEvent flush race).
    expect(await screen.findByDisplayValue('75')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Apply' }))

    expect(
      await screen.findByText(
        /Manual fit: window starts 75 s after the recorded start/,
        {},
        { timeout: 4000 },
      ),
    ).toBeInTheDocument()
    expect(changed).toBeGreaterThan(0)
    // Reset-to-auto appears once a manual offset is active.
    expect(
      screen.getByRole('button', { name: 'Reset to auto' }),
    ).toBeInTheDocument()
  })

  it('crops both ends when "Crop the end too" is enabled', async () => {
    let changed = 0
    renderDetail('auto', () => {
      changed += 1
    })
    await screen.findByText(/Window starts/)

    // The start offset is prefilled to the current window start (30 s); leave it
    // and crop the far edge to 210 s → a 180 s window.
    await userEvent.click(
      screen.getByRole('checkbox', { name: /Crop the end too/ }),
    )
    const end = screen.getByLabelText(
      'Fit window end offset (seconds from the recorded start)',
    )
    await userEvent.clear(end)
    await userEvent.type(end, '210')
    // Ensure the input committed before applying (avoids a userEvent flush race).
    expect(await screen.findByDisplayValue('210')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Apply' }))

    // The manual crop took effect (window length = 210 − 30 = 180 s).
    expect(
      await screen.findByText(/length 180 s/, {}, { timeout: 4000 }),
    ).toBeInTheDocument()
    expect(changed).toBeGreaterThan(0)
  })

  it('disables Apply when the crop end is before the start', async () => {
    renderDetail('auto')
    await screen.findByText(/Window starts/)

    const start = screen.getByLabelText(
      'Fit window start offset (seconds; negative shifts earlier)',
    )
    await userEvent.clear(start)
    await userEvent.type(start, '200')
    await userEvent.click(
      screen.getByRole('checkbox', { name: /Crop the end too/ }),
    )
    const end = screen.getByLabelText(
      'Fit window end offset (seconds from the recorded start)',
    )
    await userEvent.clear(end)
    await userEvent.type(end, '100')

    expect(screen.getByText('End must be after the start.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled()
  })
})
