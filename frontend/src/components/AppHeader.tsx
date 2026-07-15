import { useLocation, useNavigate } from 'react-router-dom'
import { Logo } from './Logo'
import { ThemeToggle } from './ThemeToggle'
import { Button } from './Button'
import { PlusIcon } from './icons'

/** Persistent top bar: logo + wordmark, theme toggle. The New-analysis button
 *  only appears on the home page — the other screens are steps within an
 *  analysis, where starting a new one would be a distraction. */
export function AppHeader() {
  const navigate = useNavigate()
  const isHome = useLocation().pathname === '/'
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-surface/95 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
        <Logo withSlogan />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          {isHome && (
            <Button
              variant="primary"
              size="sm"
              leftIcon={<PlusIcon className="h-4 w-4" />}
              onClick={() => navigate('/analyses/new')}
            >
              <span className="hidden sm:inline">New analysis</span>
              <span className="sm:hidden">New</span>
            </Button>
          )}
        </div>
      </div>
    </header>
  )
}
