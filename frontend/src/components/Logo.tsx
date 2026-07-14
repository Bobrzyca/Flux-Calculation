import { Link } from 'react-router-dom'
import { BubbleIcon } from './icons'

/** App mark + wordmark; links home. Minimal, scientific gas-bubble motif. */
export function Logo({ withSlogan = false }: { withSlogan?: boolean }) {
  return (
    <Link
      to="/"
      className="flex items-center gap-2.5 rounded-lg"
      aria-label="Flux Calculation — home"
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-white">
        <BubbleIcon className="h-5 w-5" />
      </span>
      <span className="flex flex-col leading-tight">
        <span className="text-base font-semibold text-text">
          Flux Calculation
        </span>
        {withSlogan && (
          <span className="hidden text-xs text-muted sm:inline">
            From messy field notes to clean fluxes
          </span>
        )}
      </span>
    </Link>
  )
}
