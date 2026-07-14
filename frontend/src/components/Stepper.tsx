import { cn } from '@/lib/cn'
import { STEPS, type StepName } from '@/lib/constants'
import { CheckIcon } from './icons'

interface StepperProps {
  current: StepName
  /** How far the user has progressed; steps up to here are clickable. */
  furthest?: StepName
  onNavigate?: (step: StepName) => void
}

/**
 * Upload -> Confirm -> Results. Completed steps are clickable (go back),
 * the current step is highlighted, future steps are disabled.
 */
export function Stepper({ current, furthest, onNavigate }: StepperProps) {
  const currentIdx = STEPS.indexOf(current)
  const furthestIdx = furthest ? STEPS.indexOf(furthest) : currentIdx

  return (
    <nav aria-label="Progress" className="w-full">
      <ol className="flex items-center gap-2 sm:gap-4">
        {STEPS.map((step, i) => {
          const state =
            i < currentIdx
              ? 'complete'
              : i === currentIdx
                ? 'current'
                : 'upcoming'
          const reachable = i <= furthestIdx && i !== currentIdx
          const clickable = reachable && !!onNavigate
          return (
            <li key={step} className="flex flex-1 items-center gap-2 sm:gap-4">
              <button
                type="button"
                disabled={!clickable}
                onClick={() => clickable && onNavigate?.(step)}
                aria-current={state === 'current' ? 'step' : undefined}
                className={cn(
                  'flex items-center gap-2 rounded-lg px-1 py-1 text-left',
                  clickable && 'hover:opacity-80',
                  !clickable && 'cursor-default',
                )}
              >
                <span
                  className={cn(
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold tabular-nums',
                    state === 'complete' && 'bg-primary text-white',
                    state === 'current' &&
                      'bg-primary-tint text-primary ring-2 ring-primary',
                    state === 'upcoming' &&
                      'border border-border bg-surface text-muted',
                  )}
                >
                  {state === 'complete' ? (
                    <CheckIcon className="h-4 w-4" />
                  ) : (
                    i + 1
                  )}
                </span>
                <span
                  className={cn(
                    'text-sm font-medium',
                    state === 'current' ? 'text-text' : 'text-muted',
                    // hide labels on the smallest screens except the current step
                    state === 'current' ? 'inline' : 'hidden sm:inline',
                  )}
                >
                  {step}
                </span>
              </button>
              {i < STEPS.length - 1 && (
                <span
                  aria-hidden
                  className={cn(
                    'h-px flex-1',
                    i < currentIdx ? 'bg-primary' : 'bg-border',
                  )}
                />
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
