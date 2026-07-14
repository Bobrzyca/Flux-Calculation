import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border bg-surface px-6 py-16 text-center',
        className,
      )}
    >
      {icon && (
        <div
          className="flex h-14 w-14 items-center justify-center rounded-full bg-primary-subtle text-primary"
          aria-hidden
        >
          {icon}
        </div>
      )}
      <h2 className="text-lg font-semibold text-text">{title}</h2>
      {description && (
        <p className="max-w-md text-sm text-muted">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
