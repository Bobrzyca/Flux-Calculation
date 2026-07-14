import { cn } from '@/lib/cn'

/** Shimmer placeholder. Matches final layout so there is no shift on load. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn('animate-pulse rounded-md bg-surface-2', className)}
    />
  )
}

/** Skeleton rows for a data table. */
export function SkeletonTable({
  rows = 6,
  cols = 5,
}: {
  rows?: number
  cols?: number
}) {
  return (
    <div
      className="flex flex-col gap-2"
      role="status"
      aria-label="Loading data"
    >
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-3">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton
              key={c}
              className={cn('h-10 flex-1', c === 0 && 'max-w-16')}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

export function SkeletonCards({ count = 3 }: { count?: number }) {
  return (
    <div
      className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
      role="status"
      aria-label="Loading analyses"
    >
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-32 w-full rounded-xl" />
      ))}
    </div>
  )
}
