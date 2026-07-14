import { cn } from '@/lib/cn'

/** Indeterminate spinner. Always paired with text so it is never the only cue. */
export function Spinner({
  className,
  label,
}: {
  className?: string
  label?: string
}) {
  return (
    <span
      className={cn(
        'inline-block animate-spin rounded-full border-2 border-current border-t-transparent',
        className ?? 'h-4 w-4',
      )}
      role={label ? 'status' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
    />
  )
}
