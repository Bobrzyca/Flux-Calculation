import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from 'react'
import { cn } from '@/lib/cn'

interface FieldShellProps {
  id: string
  label: string
  helper?: ReactNode
  error?: string
  required?: boolean
  children: ReactNode
}

/** Label + helper + error scaffold shared by every form control. */
function FieldShell({
  id,
  label,
  helper,
  error,
  required,
  children,
}: FieldShellProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium text-text">
        {label}
        {required && (
          <span className="text-danger" aria-hidden>
            {' '}
            *
          </span>
        )}
      </label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-sm text-danger" role="alert">
          {error}
        </p>
      ) : helper ? (
        <p id={`${id}-helper`} className="text-sm text-muted">
          {helper}
        </p>
      ) : null}
    </div>
  )
}

const controlClass = (error?: boolean) =>
  cn(
    'h-11 w-full rounded-lg border bg-surface px-3 text-base text-text',
    'placeholder:text-muted transition-colors',
    'disabled:cursor-not-allowed disabled:opacity-50',
    error
      ? 'border-danger focus:border-danger'
      : 'border-border focus:border-primary',
  )

type BaseInputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string
  helper?: ReactNode
  error?: string
}

export const TextInput = forwardRef<HTMLInputElement, BaseInputProps>(
  function TextInput({ label, helper, error, id, required, ...rest }, ref) {
    const autoId = useId()
    const fieldId = id ?? autoId
    return (
      <FieldShell
        id={fieldId}
        label={label}
        helper={helper}
        error={error}
        required={required}
      >
        <input
          ref={ref}
          id={fieldId}
          type={rest.type ?? 'text'}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={
            error
              ? `${fieldId}-error`
              : helper
                ? `${fieldId}-helper`
                : undefined
          }
          className={controlClass(!!error)}
          {...rest}
        />
      </FieldShell>
    )
  },
)

export const NumberInput = forwardRef<HTMLInputElement, BaseInputProps>(
  function NumberInput(props, ref) {
    return (
      <TextInput
        ref={ref}
        inputMode="decimal"
        {...props}
        type="number"
        className={cn('tabular-nums', props.className)}
      />
    )
  },
)

export const DateInput = forwardRef<HTMLInputElement, BaseInputProps>(
  function DateInput(props, ref) {
    return <TextInput ref={ref} {...props} type="date" />
  },
)

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: string
  helper?: ReactNode
  error?: string
  options: { value: string; label: string }[]
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  function Select(
    { label, helper, error, options, id, required, ...rest },
    ref,
  ) {
    const autoId = useId()
    const fieldId = id ?? autoId
    return (
      <FieldShell
        id={fieldId}
        label={label}
        helper={helper}
        error={error}
        required={required}
      >
        <select
          ref={ref}
          id={fieldId}
          required={required}
          aria-invalid={error ? true : undefined}
          className={cn(controlClass(!!error), 'pr-8')}
          {...rest}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </FieldShell>
    )
  },
)
