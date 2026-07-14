import { useId, useState, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

/**
 * Minimal tooltip shown on hover AND focus (keyboard-reachable). The trigger is
 * described by the tip via aria-describedby. For flag explanations, truncated
 * cells and skipped-row reasons.
 */
export function Tooltip({
  content,
  children,
  className,
}: {
  content: ReactNode
  children: ReactNode
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const id = useId()
  return (
    <span
      className={cn('relative inline-flex', className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span aria-describedby={open ? id : undefined}>{children}</span>
      {open && (
        <span
          role="tooltip"
          id={id}
          className="absolute bottom-full left-1/2 z-50 mb-2 w-max max-w-xs -translate-x-1/2 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs text-text shadow-md"
        >
          {content}
        </span>
      )}
    </span>
  )
}
