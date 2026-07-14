import { EmptyState } from './EmptyState'
import { Button } from './Button'
import { ErrorIcon } from './icons'

/** Generic error panel with a retry action for failed data loads. */
export function ErrorState({
  title = 'Something went wrong',
  description,
  onRetry,
}: {
  title?: string
  description?: string
  onRetry?: () => void
}) {
  return (
    <EmptyState
      icon={<ErrorIcon className="h-6 w-6" />}
      title={title}
      description={description}
      action={
        onRetry ? (
          <Button variant="secondary" onClick={onRetry}>
            Try again
          </Button>
        ) : undefined
      }
    />
  )
}
