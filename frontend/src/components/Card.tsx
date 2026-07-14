import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  /** Adds hover affordance for clickable cards. */
  interactive?: boolean
}

/** Flat, border-first surface (elevation via border, not shadow). */
export function Card({ children, interactive, className, ...rest }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-surface',
        interactive &&
          'cursor-pointer transition-colors hover:border-primary hover:bg-primary-subtle',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  )
}

export function CardSection({
  title,
  description,
  children,
  className,
}: {
  title?: string
  description?: string
  children: ReactNode
  className?: string
}) {
  return (
    <Card className={cn('p-6', className)}>
      {title && (
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-text">{title}</h2>
          {description && (
            <p className="mt-1 text-sm text-muted">{description}</p>
          )}
        </div>
      )}
      {children}
    </Card>
  )
}
