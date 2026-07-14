import type { ReactElement, ReactNode } from 'react'
import { render, type RenderOptions } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '@/theme/ThemeProvider'
import { ToastProvider } from '@/components'

/** Wraps a UI tree in the same providers the app uses (router, theme, toasts). */
export function renderWithProviders(
  ui: ReactElement,
  { route = '/', ...options }: { route?: string } & RenderOptions = {},
) {
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <ThemeProvider>
        <ToastProvider>
          <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
        </ToastProvider>
      </ThemeProvider>
    )
  }
  return render(ui, { wrapper: Wrapper, ...options })
}
