import { useNavigate } from 'react-router-dom'
import { Logo } from './Logo'
import { ThemeToggle } from './ThemeToggle'
import { Button } from './Button'
import { PlusIcon } from './icons'

/** Persistent top bar: logo + wordmark, theme toggle, New-analysis button. */
export function AppHeader() {
  const navigate = useNavigate()
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-surface/95 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
        <Logo withSlogan />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button
            variant="primary"
            size="sm"
            leftIcon={<PlusIcon className="h-4 w-4" />}
            onClick={() => navigate('/analyses/new')}
          >
            <span className="hidden sm:inline">New analysis</span>
            <span className="sm:hidden">New</span>
          </Button>
        </div>
      </div>
    </header>
  )
}
