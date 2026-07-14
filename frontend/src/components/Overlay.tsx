import { useEffect, useRef, type ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { IconButton } from './IconButton'
import { Button } from './Button'
import { CloseIcon } from './icons'

type Variant = 'modal' | 'drawer'

interface OverlayProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  variant?: Variant
  /** Extra width control for the panel. */
  className?: string
}

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'

/**
 * Accessible dialog. `modal` centers; `drawer` slides from the right (used for
 * per-spot detail on wide screens). Focus is trapped, Esc closes, backdrop
 * click closes, and focus returns to the trigger on close.
 */
export function Overlay({
  open,
  onClose,
  title,
  children,
  footer,
  variant = 'modal',
  className,
}: OverlayProps) {
  const panelRef = useRef<HTMLDivElement>(null)
  const previouslyFocused = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!open) return
    previouslyFocused.current = document.activeElement as HTMLElement
    const panel = panelRef.current
    // Move focus into the dialog.
    const first = panel?.querySelector<HTMLElement>(FOCUSABLE)
    ;(first ?? panel)?.focus()

    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
        return
      }
      if (e.key === 'Tab' && panel) {
        const items = Array.from(
          panel.querySelectorAll<HTMLElement>(FOCUSABLE),
        ).filter((el) => el.offsetParent !== null)
        if (items.length === 0) return
        const firstEl = items[0]
        const lastEl = items[items.length - 1]
        if (e.shiftKey && document.activeElement === firstEl) {
          e.preventDefault()
          lastEl.focus()
        } else if (!e.shiftKey && document.activeElement === lastEl) {
          e.preventDefault()
          firstEl.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
      previouslyFocused.current?.focus?.()
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[90] flex"
      style={{ backgroundColor: 'rgba(15,23,42,0.4)' }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={cn(
          'flex flex-col bg-surface shadow-lg outline-none',
          variant === 'modal'
            ? 'm-auto max-h-[90vh] w-full max-w-lg rounded-xl'
            : 'ml-auto h-full w-full max-w-xl',
          className,
        )}
      >
        <header className="flex items-center justify-between gap-3 border-b border-border p-4">
          <h2 className="text-lg font-semibold text-text">{title}</h2>
          <IconButton label="Close" onClick={onClose}>
            <CloseIcon className="h-5 w-5" />
          </IconButton>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div>
        {footer && (
          <footer className="flex items-center justify-end gap-3 border-t border-border p-4">
            {footer}
          </footer>
        )}
      </div>
    </div>
  )
}

/** Confirm dialog for destructive / overwrite actions. */
export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Confirm',
  danger = false,
}: {
  open: boolean
  onClose: () => void
  onConfirm: () => void
  title: string
  message: ReactNode
  confirmLabel?: string
  danger?: boolean
}) {
  return (
    <Overlay
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant={danger ? 'danger' : 'primary'}
            onClick={() => {
              onConfirm()
              onClose()
            }}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-sm text-text">{message}</p>
    </Overlay>
  )
}
