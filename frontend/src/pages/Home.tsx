import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { AnalysisSummary } from '@/api/types'
import { api } from '@/api/client'
import { useAsync } from '@/hooks/useAsync'
import {
  Button,
  Card,
  StatusChip,
  EmptyState,
  ErrorState,
  SkeletonCards,
  IconButton,
  ConfirmDialog,
  useToast,
} from '@/components'
import { PlusIcon, TrashIcon, UploadIcon } from '@/components/icons'
import { formatDate, formatDateTime } from '@/lib/format'

/** Where a card opens, based on how far the analysis progressed. */
function routeFor(a: AnalysisSummary): string {
  if (a.status === 'draft') return '/analyses/new'
  if (a.status === 'needs_review') return `/analyses/${a.id}/confirm`
  return `/analyses/${a.id}/results`
}

export function Home() {
  const navigate = useNavigate()
  const toast = useToast()
  const { data, loading, error, reload } = useAsync(() => api.listAnalyses())
  const [toDelete, setToDelete] = useState<AnalysisSummary | null>(null)

  async function confirmDelete() {
    if (!toDelete) return
    await api.deleteAnalysis(toDelete.id)
    toast.show(`Deleted "${toDelete.name}"`)
    reload()
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text">Your analyses</h1>
          <p className="mt-1 text-sm text-muted">
            From messy field notes to clean fluxes.
          </p>
        </div>
        <Button
          leftIcon={<PlusIcon className="h-4 w-4" />}
          onClick={() => navigate('/analyses/new')}
        >
          New analysis
        </Button>
      </div>

      {loading && <SkeletonCards count={3} />}

      {error && (
        <ErrorState
          title="Couldn't load your analyses"
          description={error.message}
          onRetry={reload}
        />
      )}

      {data && data.length === 0 && (
        <EmptyState
          icon={<UploadIcon className="h-6 w-6" />}
          title="No analyses yet"
          description="Upload your LI-7810, time notes, temperature and pressure files to calculate your first fluxes."
          action={
            <Button
              leftIcon={<PlusIcon className="h-4 w-4" />}
              onClick={() => navigate('/analyses/new')}
            >
              New analysis
            </Button>
          }
        />
      )}

      {data && data.length > 0 && (
        <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((a) => (
            <li key={a.id}>
              <Card className="group relative h-full p-5">
                <button
                  type="button"
                  onClick={() => navigate(routeFor(a))}
                  className="flex w-full flex-col gap-3 text-left"
                >
                  <div className="flex items-start justify-between gap-2">
                    <h2 className="font-semibold text-text group-hover:text-primary">
                      {a.name}
                    </h2>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
                    <span>{formatDate(a.work_date)}</span>
                    <span aria-hidden>·</span>
                    <span className="tabular-nums">
                      {a.spot_count} {a.spot_count === 1 ? 'spot' : 'spots'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <StatusChip status={a.status} />
                    <span className="text-xs text-muted">
                      {formatDateTime(a.created_at)}
                    </span>
                  </div>
                </button>
                <div className="absolute right-3 top-3">
                  <IconButton
                    label={`Delete ${a.name}`}
                    className="h-9 w-9 opacity-0 focus:opacity-100 group-hover:opacity-100"
                    onClick={() => setToDelete(a)}
                  >
                    <TrashIcon className="h-4 w-4" />
                  </IconButton>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        onConfirm={confirmDelete}
        title="Delete analysis?"
        message={
          <>
            This permanently removes <strong>{toDelete?.name}</strong> and its
            results. This cannot be undone.
          </>
        }
        confirmLabel="Delete"
        danger
      />
    </div>
  )
}
