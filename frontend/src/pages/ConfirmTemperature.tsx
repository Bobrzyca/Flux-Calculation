import { lazy, Suspense, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '@/api/client'
import { useAsync } from '@/hooks/useAsync'
import {
  Stepper,
  Card,
  Button,
  Banner,
  Skeleton,
  ErrorState,
  PipelineProgress,
  type PipelineStep,
} from '@/components'

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

const TemperaturePlot = lazy(() =>
  import('@/components/TemperaturePlot').then((m) => ({
    default: m.TemperaturePlot,
  })),
)

/** Format an absolute unix-seconds stamp as a local HH:MM:SS wall-clock time. */
function clock(unix: number | null): string {
  if (unix === null) return '—'
  const d = new Date(unix * 1000)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())}`
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-0.5 text-sm font-medium tabular-nums text-text">
        {value}
      </dd>
    </div>
  )
}

/**
 * Second half of the Confirm step: review the PARSED temperature series before
 * we match it to each spot and fit fluxes. Lets the researcher catch a
 * mis-parsed temperature file (wrong column, comma decimals, bad dates) before
 * it silently affects the flux. "Confirm & compute" runs the match + fit.
 */
export function ConfirmTemperature() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data, loading, error, reload } = useAsync(
    () => api.getTemperature(id!),
    [id],
  )

  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [steps, setSteps] = useState<PipelineStep[]>([])

  async function compute() {
    setRunError(null)
    setRunning(true)
    const labels = [
      'Matching temperature & pressure to each spot',
      'Fitting CO₂ and CH₄ slopes',
    ]
    const at = (active: number): PipelineStep[] =>
      labels.map((label, i) => ({
        label,
        status: i < active ? 'done' : i === active ? 'active' : 'pending',
      }))
    try {
      setSteps(at(0))
      await sleep(400)
      setSteps(at(1))
      await api.matchAndCompute(id!)
      setSteps((s) => s.map((x) => ({ ...x, status: 'done' })))
      await sleep(300)
      navigate(`/analyses/${id}/results`)
    } catch (err) {
      setRunning(false)
      setRunError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Matching failed. Please try again.',
      )
    }
  }

  if (running) {
    return (
      <div className="flex flex-col gap-8">
        <Stepper current="Confirm" furthest="Confirm" />
        <div className="py-8">
          <PipelineProgress steps={steps} title="Matching and fitting…" />
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <Stepper
        current="Confirm"
        furthest="Confirm"
        onNavigate={(s) => {
          if (s === 'Upload') navigate(`/analyses/${id}/upload`)
        }}
      />

      <div>
        <h1 className="text-2xl font-bold text-text">
          Confirm parsed temperature
        </h1>
        <p className="mt-1 text-sm text-muted">
          Check the temperature log we read before matching it to each spot — a
          mis-read column or decimal would otherwise quietly skew the flux.
        </p>
      </div>

      {runError && (
        <Banner
          tone="error"
          title="Matching couldn't finish"
          onDismiss={() => setRunError(null)}
        >
          {runError}
        </Banner>
      )}

      {loading && <Skeleton className="h-[360px] w-full" />}

      {error && (
        <ErrorState
          title="Couldn't load the temperature"
          description={error.message}
          onRetry={reload}
        />
      )}

      {data && !data.available && (
        <Banner tone="error" title="Temperature file couldn't be read">
          {data.message ??
            'The temperature file is missing or unreadable. Go back to Upload and provide a readable .csv/.xlsx with a date/time column and a temperature (°C) column.'}
        </Banner>
      )}

      {data && data.available && (
        <>
          <Card>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
              <Fact label="Readings" value={String(data.count)} />
              <Fact
                label="From → to"
                value={`${clock(data.start_unix)} → ${clock(data.end_unix)}`}
              />
              <Fact
                label="Mean"
                value={
                  data.mean_c !== null ? `${data.mean_c.toFixed(2)} °C` : '—'
                }
              />
              <Fact
                label="Min"
                value={
                  data.min_c !== null ? `${data.min_c.toFixed(2)} °C` : '—'
                }
              />
              <Fact
                label="Max"
                value={
                  data.max_c !== null ? `${data.max_c.toFixed(2)} °C` : '—'
                }
              />
            </dl>
          </Card>

          <Card>
            <Suspense fallback={<Skeleton className="h-[300px] w-full" />}>
              <TemperaturePlot points={data.points} />
            </Suspense>
          </Card>
        </>
      )}

      <div className="flex items-center justify-between">
        <Button
          variant="secondary"
          onClick={() => navigate(`/analyses/${id}/confirm`)}
        >
          Back
        </Button>
        <Button
          variant="cta"
          onClick={compute}
          disabled={loading || !data?.available}
        >
          Confirm &amp; compute
        </Button>
      </div>
    </div>
  )
}
