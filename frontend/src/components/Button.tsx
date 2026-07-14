import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { Spinner } from './Spinner'

export type ButtonVariant = 'primary' | 'cta' | 'secondary' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  loadingText?: string
  leftIcon?: ReactNode
  rightIcon?: ReactNode
}

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    'bg-primary text-white hover:bg-primary-hover active:bg-primary-hover',
  // Amber CTA uses slate text (not white) to clear WCAG AA on #F59E0B.
  cta: 'bg-cta text-[#1e293b] hover:bg-cta-hover active:bg-cta-hover font-semibold',
  secondary:
    'border border-border bg-surface text-text hover:bg-surface-2 active:bg-surface-2',
  ghost: 'text-text hover:bg-surface-2 active:bg-surface-2',
  danger: 'bg-danger text-white hover:opacity-90 active:opacity-90',
}

const SIZES: Record<ButtonSize, string> = {
  sm: 'h-9 px-3 text-sm gap-1.5',
  md: 'h-11 px-4 text-base gap-2',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      variant = 'primary',
      size = 'md',
      loading = false,
      loadingText,
      leftIcon,
      rightIcon,
      className,
      children,
      disabled,
      ...rest
    },
    ref,
  ) {
    const isDisabled = disabled || loading
    return (
      <button
        ref={ref}
        disabled={isDisabled}
        aria-busy={loading || undefined}
        className={cn(
          'inline-flex items-center justify-center rounded-lg font-medium transition-colors',
          'disabled:cursor-not-allowed disabled:opacity-50',
          SIZES[size],
          VARIANTS[variant],
          className,
        )}
        {...rest}
      >
        {loading ? (
          <>
            <Spinner className="h-4 w-4" />
            {loadingText ?? children}
          </>
        ) : (
          <>
            {leftIcon}
            {children}
            {rightIcon}
          </>
        )}
      </button>
    )
  },
)
