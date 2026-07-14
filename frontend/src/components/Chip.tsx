import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'
import type { AnalysisStatus, LightDark, SpotFlag } from '@/api/types'

type Tone = 'neutral' | 'primary' | 'success' | 'warning' | 'danger' | 'brown'

const TONES: Record<Tone, string> = {
  neutral: 'bg-surface-2 text-muted',
  primary: 'bg-primary-tint text-primary',
  success: 'bg-success-tint text-success',
  warning: 'bg-warning-tint text-warning',
  danger: 'bg-danger-tint text-danger',
  brown: 'bg-[#f5ebe0] text-secondary dark:bg-[#3a2a18]',
}

export function Chip({
  tone = 'neutral',
  icon,
  children,
  className,
}: {
  tone?: Tone
  icon?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium',
        TONES[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  )
}

const STATUS_META: Record<AnalysisStatus, { tone: Tone; label: string }> = {
  complete: { tone: 'success', label: 'Complete' },
  draft: { tone: 'neutral', label: 'Draft' },
  needs_review: { tone: 'warning', label: 'Needs review' },
}

export function StatusChip({ status }: { status: AnalysisStatus }) {
  const meta = STATUS_META[status]
  return <Chip tone={meta.tone}>{meta.label}</Chip>
}

/** light = teal tint, dark = brown tint — never colour alone, always the word. */
export function LightDarkTag({ value }: { value: LightDark }) {
  return (
    <Chip tone={value === 'light' ? 'primary' : 'brown'}>
      {value === 'light' ? 'Light' : 'Dark'}
    </Chip>
  )
}

const FLAG_META: Record<SpotFlag, { tone: Tone; label: string }> = {
  low_r2: { tone: 'warning', label: 'Low R²' },
  short_window: { tone: 'warning', label: 'Short window' },
  no_pressure: { tone: 'warning', label: 'No pressure' },
  dropped_nan: { tone: 'neutral', label: 'nan dropped' },
  anomalous: { tone: 'danger', label: 'Anomalous' },
}

export function FlagChip({ flag }: { flag: SpotFlag }) {
  const meta = FLAG_META[flag]
  return <Chip tone={meta.tone}>{meta.label}</Chip>
}
