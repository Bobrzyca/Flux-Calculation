import { useId, useRef, useState, type DragEvent } from 'react'
import { cn } from '@/lib/cn'
import { formatBytes } from '@/lib/format'
import { MAX_FILE_SIZE_BYTES } from '@/lib/constants'
import { FileIcon, UploadIcon, CloseIcon } from './icons'

interface DropzoneProps {
  label: string
  /** Human hint of accepted formats, e.g. ".docx, .xlsx, .csv" or "any format". */
  acceptHint: string
  /** `accept` attribute for the file input; empty string accepts anything. */
  accept?: string
  file: File | null
  onChange: (file: File | null) => void
  /** External error (e.g. from the backend format check) to display. */
  error?: string
  required?: boolean
}

export function Dropzone({
  label,
  acceptHint,
  accept,
  file,
  onChange,
  error,
  required,
}: DropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const id = useId()
  const shownError = error ?? localError

  function accept_(f: File | undefined | null) {
    if (!f) return
    if (f.size > MAX_FILE_SIZE_BYTES) {
      setLocalError(
        `File is too large (max ${formatBytes(MAX_FILE_SIZE_BYTES)}).`,
      )
      return
    }
    setLocalError(null)
    onChange(f)
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragOver(false)
    accept_(e.dataTransfer.files?.[0])
  }

  const open = () => inputRef.current?.click()

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium text-text">
        {label}
        {required && (
          <span className="text-danger" aria-hidden>
            {' '}
            *
          </span>
        )}
      </span>

      {file ? (
        // Attached state
        <div className="flex items-center gap-3 rounded-lg border border-border bg-surface p-3">
          <FileIcon className="h-6 w-6 shrink-0 text-primary" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-text">
              {file.name}
            </p>
            <p className="text-xs text-muted tabular-nums">
              {formatBytes(file.size)}
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              onChange(null)
              setLocalError(null)
              if (inputRef.current) inputRef.current.value = ''
            }}
            aria-label={`Remove ${label} file`}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-muted hover:bg-surface-2 hover:text-text"
          >
            <CloseIcon className="h-4 w-4" />
          </button>
        </div>
      ) : (
        // Idle / drag-over state — button so it is keyboard operable.
        <button
          type="button"
          onClick={open}
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          aria-describedby={shownError ? `${id}-error` : undefined}
          className={cn(
            'flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 text-center transition-colors',
            dragOver
              ? 'border-primary bg-primary-subtle'
              : shownError
                ? 'border-danger bg-surface'
                : 'border-border bg-surface hover:border-primary hover:bg-primary-subtle',
          )}
        >
          <UploadIcon className="h-6 w-6 text-muted" />
          <span className="text-sm text-text">
            <span className="font-medium text-primary">Choose a file</span> or
            drag it here
          </span>
          <span className="text-xs text-muted">
            {acceptHint || 'any format'}
          </span>
        </button>
      )}

      <input
        ref={inputRef}
        id={id}
        type="file"
        accept={accept || undefined}
        className="sr-only"
        onChange={(e) => accept_(e.target.files?.[0])}
      />

      {shownError && (
        <p id={`${id}-error`} className="text-sm text-danger" role="alert">
          {shownError}
        </p>
      )}
    </div>
  )
}
