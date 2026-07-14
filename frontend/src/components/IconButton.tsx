import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Required: icon-only buttons must be labelled for screen readers. */
  label: string
  children: ReactNode
}

/** Icon-only button with a >=44px hit area and a mandatory aria-label. */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  function IconButton({ label, className, children, ...rest }, ref) {
    return (
      <button
        ref={ref}
        type="button"
        aria-label={label}
        title={label}
        className={cn(
          'inline-flex h-11 w-11 items-center justify-center rounded-lg text-muted',
          'transition-colors hover:bg-surface-2 hover:text-text',
          'disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        {...rest}
      >
        {children}
      </button>
    )
  },
)
