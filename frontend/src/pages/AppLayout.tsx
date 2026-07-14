import { Outlet } from 'react-router-dom'
import { AppHeader } from '@/components'

/** App shell: persistent header + a centered content column. */
export function AppLayout() {
  return (
    <div className="flex min-h-svh flex-col bg-bg">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>
      <AppHeader />
      <main
        id="main"
        className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8"
      >
        <Outlet />
      </main>
    </div>
  )
}
