import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Stepper } from './Stepper'

describe('Stepper', () => {
  it('renders all three steps', () => {
    render(<Stepper current="Upload" />)
    expect(screen.getByText('Upload')).toBeInTheDocument()
    expect(screen.getByText('Confirm')).toBeInTheDocument()
    expect(screen.getByText('Results')).toBeInTheDocument()
  })

  it('marks the current step with aria-current', () => {
    render(<Stepper current="Confirm" furthest="Confirm" />)
    const current = screen.getByRole('button', { current: 'step' })
    expect(current).toHaveTextContent('Confirm')
  })

  it('lets the user click back to a completed step', async () => {
    const onNavigate = vi.fn()
    render(
      <Stepper current="Results" furthest="Results" onNavigate={onNavigate} />,
    )
    await userEvent.click(screen.getByRole('button', { name: /Upload/ }))
    expect(onNavigate).toHaveBeenCalledWith('Upload')
  })

  it('does not allow navigating to a future step', async () => {
    const onNavigate = vi.fn()
    render(
      <Stepper current="Upload" furthest="Upload" onNavigate={onNavigate} />,
    )
    const results = screen.getByRole('button', { name: /Results/ })
    expect(results).toBeDisabled()
  })
})
