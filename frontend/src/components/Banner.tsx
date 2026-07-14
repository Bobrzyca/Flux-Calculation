import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { InfoIcon, WarningIcon, ErrorIcon, CheckIcon, CloseIcon } from './icons'

export type BannerTone = 'info' | 'warning' | 'error' | 'success'

const META: Record<
  BannerTone,
  { icon: typeof InfoIcon; classes: string; role: 'status' | 'alert' }
> = {
  info: {
    icon: InfoIcon,
    classes: 'border-primary/30 bg-info-tint text-text',
    role: 'status',
  },
  success: {
    icon: CheckIcon,
    classes: 'border-success/30 bg-success-tint text-text',
    role: 'status',
  },
  warning: {
    icon: WarningIcon,
    classes: 'border-warning/40 bg-warning-tint text-text',
    role: 'alert',
  },
  error: {
    icon: ErrorIcon,
    classes: 'border-danger/40 bg-danger-tint text-text',
    role: 'alert',
  },
}

const ICON_COLOR: Record<BannerTone, string> = {
  info: 'text-primary',
  success: 'text-success',
  warning: 'text-warning',
  error: 'text-danger',
}

export function Banner({
  tone = 'info',
  title,
  children,
  onDismiss,
  className,
}: {
  tone?: BannerTone
  title?: string
  children?: ReactNode
  onDismiss?: () => void
  className?: string
}) {
  const meta = META[tone]
  const Icon = meta.icon
  return (
    <div
      role={meta.role}
      className={cn(
        'flex items-start gap-3 rounded-lg border p-4',
        meta.classes,
        className,
      )}
    >
      <Icon className={cn('mt-0.5 h-5 w-5 shrink-0', ICON_COLOR[tone])} />
      <div className="min-w-0 flex-1 text-sm">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cn(title && 'mt-1')}>{children}</div>}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="shrink-0 rounded p-1 text-muted hover:text-text"
        >
          <CloseIcon className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}
