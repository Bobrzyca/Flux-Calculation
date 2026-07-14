import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '@/api/client'
import type { LogSeverity } from '@/api/types'
import { useAsync } from '@/hooks/useAsync'
import {
  Card,
  Button,
  Skeleton,
  ErrorState,
  EmptyState,
  useToast,
} from '@/components'
import {
  InfoIcon,
  WarningIcon,
  ErrorIcon,
  ChevronLeftIcon,
  DownloadIcon,
  ListIcon,
} from '@/components/icons'
import { cn } from '@/lib/cn'
import { formatDateTime } from '@/lib/format'

const SEV_META: Record<
  LogSeverity,
  { icon: typeof InfoIcon; color: string; label: string }
> = {
  info: { icon: InfoIcon, color: 'text-primary', label: 'Info' },
  warning: { icon: WarningIcon, color: 'text-warning', label: 'Warning' },
  error: { icon: ErrorIcon, color: 'text-danger', label: 'Error' },
}

export function ProcessingLog() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const { data, loading, error, reload } = useAsync(() => api.getLog(id!), [id])
  const [filter, setFilter] = useState<'all' | LogSeverity>('all')

  const filtered = useMemo(
    () => (data ?? []).filter((e) => filter === 'all' || e.severity === filter),
    [data, filter],
  )

  function download() {
    if (!data) return
    const text = data
      .map((e) => `${e.ts}\t${e.severity.toUpperCase()}\t${e.message}`)
      .join('\n')
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'processing-log.txt'
    link.click()
    URL.revokeObjectURL(url)
    toast.show('Downloaded processing-log.txt')
  }

  return (
    <div className="flex flex-col gap-6">
      <Button
        variant="ghost"
        size="sm"
        className="self-start"
        leftIcon={<ChevronLeftIcon className="h-4 w-4" />}
        onClick={() => navigate(`/analyses/${id}/results`)}
      >
        Back to results
      </Button>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text">Processing log</h1>
          <p className="mt-1 text-sm text-muted">
            Every transformation, in order — rows dropped, offset applied,
            matches made, and spots skipped.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            aria-label="Filter by severity"
            value={filter}
            onChange={(e) => setFilter(e.target.value as 'all' | LogSeverity)}
            className="h-10 rounded-lg border border-border bg-surface px-3 text-sm text-text focus:border-primary"
          >
            <option value="all">All severities</option>
            <option value="info">Info</option>
            <option value="warning">Warnings</option>
            <option value="error">Errors</option>
          </select>
          <Button
            variant="secondary"
            size="sm"
            leftIcon={<DownloadIcon className="h-4 w-4" />}
            onClick={download}
            disabled={!data}
          >
            Download
          </Button>
        </div>
      </div>

      {loading && (
        <Card className="flex flex-col gap-3 p-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </Card>
      )}

      {error && (
        <ErrorState
          title="Couldn't load the log"
          description={error.message}
          onRetry={reload}
        />
      )}

      {data && filtered.length === 0 && (
        <EmptyState
          icon={<ListIcon className="h-6 w-6" />}
          title="No log entries"
          description={
            filter === 'all'
              ? 'This analysis produced no log entries.'
              : `No ${filter} entries in this log.`
          }
        />
      )}

      {data && filtered.length > 0 && (
        <Card className="overflow-hidden">
          <ul>
            {filtered.map((e, i) => {
              const meta = SEV_META[e.severity]
              const Icon = meta.icon
              return (
                <li
                  key={i}
                  className="flex items-start gap-3 border-b border-border px-4 py-3 last:border-b-0"
                >
                  <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', meta.color)} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-text">{e.message}</p>
                    <p className="mt-0.5 text-xs text-muted tabular-nums">
                      {formatDateTime(e.ts)}
                    </p>
                  </div>
                </li>
              )
            })}
          </ul>
        </Card>
      )}
    </div>
  )
}
