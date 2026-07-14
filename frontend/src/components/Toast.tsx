import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { cn } from '@/lib/cn'
import { CheckIcon, ErrorIcon, InfoIcon, CloseIcon } from './icons'

type ToastTone = 'success' | 'error' | 'info'
interface Toast {
  id: number
  tone: ToastTone
  message: string
}

interface ToastContextValue {
  show: (message: string, tone?: ToastTone) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const ICON: Record<ToastTone, typeof CheckIcon> = {
  success: CheckIcon,
  error: ErrorIcon,
  info: InfoIcon,
}
const ICON_COLOR: Record<ToastTone, string> = {
  success: 'text-success',
  error: 'text-danger',
  info: 'text-primary',
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const counter = useRef(0)

  const dismiss = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id))
  }, [])

  const show = useCallback(
    (message: string, tone: ToastTone = 'success') => {
      const id = ++counter.current
      setToasts((t) => [...t, { id, tone, message }])
      setTimeout(() => dismiss(id), 4000)
    },
    [dismiss],
  )

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      {/* Live region so screen readers announce confirmations. */}
      <div
        className="pointer-events-none fixed inset-x-0 bottom-4 z-[100] flex flex-col items-center gap-2 px-4"
        role="region"
        aria-live="polite"
        aria-label="Notifications"
      >
        {toasts.map((t) => {
          const Icon = ICON[t.tone]
          return (
            <div
              key={t.id}
              className="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border border-border bg-surface p-3 shadow-lg"
            >
              <Icon
                className={cn('mt-0.5 h-5 w-5 shrink-0', ICON_COLOR[t.tone])}
              />
              <p className="flex-1 text-sm text-text">{t.message}</p>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss notification"
                className="shrink-0 rounded p-0.5 text-muted hover:text-text"
              >
                <CloseIcon className="h-4 w-4" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
