import { cn } from '@/lib/cn'
import { CheckIcon } from './icons'
import { Spinner } from './Spinner'

export interface PipelineStep {
  label: string
  status: 'pending' | 'active' | 'done'
}

/**
 * The live step indicator shown while the pipeline runs, e.g.
 * "Parsing notes… matching temperature… fitting CO₂ and CH₄… done".
 * aria-live so progress is announced; never a frozen blank screen.
 */
export function PipelineProgress({
  steps,
  title = 'Working…',
}: {
  steps: PipelineStep[]
  title?: string
}) {
  return (
    <div
      className="mx-auto flex max-w-md flex-col gap-4 rounded-xl border border-border bg-surface p-6"
      role="status"
      aria-live="polite"
    >
      <h2 className="text-base font-semibold text-text">{title}</h2>
      <ol className="flex flex-col gap-3">
        {steps.map((step, i) => (
          <li key={i} className="flex items-center gap-3">
            <span
              className={cn(
                'flex h-6 w-6 shrink-0 items-center justify-center rounded-full',
                step.status === 'done' && 'bg-primary text-white',
                step.status === 'active' && 'text-primary',
                step.status === 'pending' && 'border border-border text-muted',
              )}
            >
              {step.status === 'done' ? (
                <CheckIcon className="h-4 w-4" />
              ) : step.status === 'active' ? (
                <Spinner className="h-4 w-4" />
              ) : (
                <span className="h-2 w-2 rounded-full bg-current" />
              )}
            </span>
            <span
              className={cn(
                'text-sm',
                step.status === 'pending' ? 'text-muted' : 'text-text',
                step.status === 'active' && 'font-medium',
              )}
            >
              {step.label}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}
