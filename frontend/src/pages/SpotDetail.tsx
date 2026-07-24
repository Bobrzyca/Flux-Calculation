import { lazy, Suspense, useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { FitMode, Gas } from '@/api/types'
import { useAsync } from '@/hooks/useAsync'
import {
  Overlay,
  Button,
  Skeleton,
  ErrorState,
  FlagChip,
  LightDarkTag,
} from '@/components'

// Code-split Plotly: it only loads when a spot detail is opened.
const RegressionPlot = lazy(() =>
  import('@/components/RegressionPlot').then((m) => ({
    default: m.RegressionPlot,
  })),
)
import { ChevronLeftIcon, ChevronRightIcon } from '@/components/icons'
import { UNIT_LADDER } from '@/lib/constants'
import { formatR2 } from '@/lib/format'

/** Human phrase for a fit-window offset relative to the recorded start. */
function describeOffset(seconds: number): string {
  const s = Math.round(seconds)
  if (s === 0) return 'starts at the recorded start'
  if (s > 0) return `starts ${s} s after the recorded start`
  return `starts ${Math.abs(s)} s before the recorded start`
}

interface SpotDetailProps {
  analysisId: string
  nr: number
  /** Ordered list of navigable (non-skipped) spot numbers. */
  spotNrs: number[]
  /** Global fit mode from Results — "full" blocks the automatic best-window fit. */
  fitMode: FitMode
  onClose: () => void
  onNavigate: (nr: number) => void
  /** Called after a manual shift is saved, so Results can refresh table + graph. */
  onFitChanged?: () => void
}

export function SpotDetail({
  analysisId,
  nr,
  spotNrs,
  fitMode,
  onClose,
  onNavigate,
  onFitChanged,
}: SpotDetailProps) {
  const { data, loading, error, reload } = useAsync(
    () => api.getSpotDetail(analysisId, nr, fitMode),
    [analysisId, nr, fitMode],
  )
  const [gas, setGas] = useState<Gas>('CO2')

  // Manual per-spot window shift. The input tracks the current effective offset
  // (reset when the spot / mode / applied value changes) so the user nudges from
  // where the fit actually sits.
  const [offsetInput, setOffsetInput] = useState('')
  // Optional END-crop: when on, the far edge is hand-picked too (both ends
  // trimmed), for spots where the start AND the end of the measurement are
  // disturbed. When off, the window keeps its full length (a plain shift).
  const [cropEnd, setCropEnd] = useState(false)
  const [endInput, setEndInput] = useState('')
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    if (!data) return
    setOffsetInput(String(Math.round(data.fit_offset_s)))
    setEndInput(String(Math.round(data.fit_end_s)))
    setCropEnd(data.manual_end_offset_s !== null)
  }, [
    data?.nr,
    data?.mode,
    data?.fit_offset_s,
    data?.fit_end_s,
    data?.manual_end_offset_s,
  ])

  const startVal = Number(offsetInput)
  const endVal = Number(endInput)
  const endInvalid =
    cropEnd &&
    (endInput.trim() === '' || Number.isNaN(endVal) || endVal <= startVal)

  async function saveOffset(
    value: number | null,
    endValue: number | null = null,
  ) {
    setSaving(true)
    try {
      await api.setSpotFit(analysisId, nr, value, endValue)
      reload()
      onFitChanged?.()
    } finally {
      setSaving(false)
    }
  }

  function applyOffset() {
    // Negative is allowed: it shifts the window EARLIER than the recorded start.
    if (offsetInput.trim() === '' || Number.isNaN(startVal)) return
    if (cropEnd && endInvalid) return
    const end = cropEnd ? Math.round(endVal) : null
    void saveOffset(Math.round(startVal), end)
  }

  function nudge(delta: number) {
    const base = Number(offsetInput)
    setOffsetInput(String((Number.isNaN(base) ? 0 : base) + delta))
  }

  function nudgeEnd(delta: number) {
    const base = Number(endInput)
    setEndInput(String((Number.isNaN(base) ? 0 : base) + delta))
  }

  const idx = spotNrs.indexOf(nr)
  const prev = idx > 0 ? spotNrs[idx - 1] : null
  const next = idx >= 0 && idx < spotNrs.length - 1 ? spotNrs[idx + 1] : null

  return (
    <Overlay
      open
      onClose={onClose}
      variant="drawer"
      title={`Spot ${nr}`}
      footer={
        <div className="flex w-full items-center justify-between">
          <Button
            variant="secondary"
            size="sm"
            disabled={prev === null}
            onClick={() => prev !== null && onNavigate(prev)}
            leftIcon={<ChevronLeftIcon className="h-4 w-4" />}
          >
            Previous
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={next === null}
            onClick={() => next !== null && onNavigate(next)}
            rightIcon={<ChevronRightIcon className="h-4 w-4" />}
          >
            Next
          </Button>
        </div>
      }
    >
      {loading && (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-[340px] w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      )}

      {error && (
        <ErrorState
          title="Couldn't load this spot"
          description={error.message}
          onRetry={reload}
        />
      )}

      {!loading && !error && !data && (
        <ErrorState
          title="No readings in this spot's window"
          description="This spot was skipped, so there is no regression to show."
        />
      )}

      {data && (
        <div className="flex flex-col gap-5">
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
            <LightDarkTag value={data.light_dark} />
            <span>GPS {data.gps || '—'}</span>
            <span aria-hidden>·</span>
            <span>
              Fit window {data.fit_window.start} → {data.fit_window.stop}
            </span>
          </div>

          {/* How much the fit window moved / was cut (visible supervision). */}
          <p className="text-sm text-muted">
            {data.mode === 'full'
              ? `Fitting the whole recording (${Math.round(
                  data.fit_window_s,
                )} s) as-is — no window selection.`
              : data.mode === 'manual'
                ? `Manual fit: window ${describeOffset(
                    data.fit_offset_s,
                  )} · length ${Math.round(data.fit_window_s)} s.`
                : `Window ${describeOffset(
                    data.fit_offset_s,
                  )} · length ${Math.round(data.fit_window_s)} s${
                    data.window_shortened ? ' · shortened to improve R²' : ''
                  }`}
          </p>

          {/* Manual per-spot window shift: correct a mis-placed automatic fit. */}
          <div className="rounded-lg border border-border p-3">
            <div className="mb-2 flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted">
                Manual fit window
              </span>
              {data.mode === 'manual' && (
                <span className="rounded bg-primary-subtle px-2 py-0.5 text-xs font-medium text-primary">
                  active
                </span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => nudge(-30)}
                aria-label="Shift 30 seconds earlier"
              >
                −30 s
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => nudge(-5)}
                aria-label="Shift 5 seconds earlier"
              >
                −5 s
              </Button>
              <input
                type="number"
                value={offsetInput}
                onChange={(e) => setOffsetInput(e.target.value)}
                aria-label="Fit window start offset (seconds; negative shifts earlier)"
                className="h-9 w-24 rounded-lg border border-border bg-surface px-2 text-sm tabular-nums text-text focus:border-primary"
              />
              <span className="text-sm text-muted">s</span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => nudge(5)}
                aria-label="Shift 5 seconds later"
              >
                +5 s
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => nudge(30)}
                aria-label="Shift 30 seconds later"
              >
                +30 s
              </Button>
              <Button
                size="sm"
                onClick={applyOffset}
                disabled={saving || (cropEnd && endInvalid)}
              >
                Apply
              </Button>
              {data.manual_offset_s !== null && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => void saveOffset(null, null)}
                  disabled={saving}
                >
                  Reset to auto
                </Button>
              )}
            </div>

            {/* Optional crop of the far edge, for spots disturbed at BOTH ends. */}
            <label className="mt-3 flex items-center gap-2 text-sm text-text">
              <input
                type="checkbox"
                checked={cropEnd}
                onChange={(e) => setCropEnd(e.target.checked)}
                className="h-4 w-4 rounded border-border"
              />
              Crop the end too (both ends disturbed)
            </label>
            {cropEnd && (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="text-xs text-muted">End at</span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => nudgeEnd(-30)}
                  aria-label="Move window end 30 seconds earlier"
                >
                  −30 s
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => nudgeEnd(-5)}
                  aria-label="Move window end 5 seconds earlier"
                >
                  −5 s
                </Button>
                <input
                  type="number"
                  value={endInput}
                  onChange={(e) => setEndInput(e.target.value)}
                  aria-label="Fit window end offset (seconds from the recorded start)"
                  className="h-9 w-24 rounded-lg border border-border bg-surface px-2 text-sm tabular-nums text-text focus:border-primary"
                />
                <span className="text-sm text-muted">s</span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => nudgeEnd(5)}
                  aria-label="Move window end 5 seconds later"
                >
                  +5 s
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => nudgeEnd(30)}
                  aria-label="Move window end 30 seconds later"
                >
                  +30 s
                </Button>
                {/* Commit the window from here too, so the end crop can be applied
                    without scrolling back up to the start row's Apply. */}
                <Button
                  size="sm"
                  onClick={applyOffset}
                  disabled={saving || endInvalid}
                  aria-label="Apply the cropped fit window"
                >
                  Apply
                </Button>
                {endInvalid && (
                  <span className="text-xs text-danger">
                    End must be after the start.
                  </span>
                )}
              </div>
            )}

            <p className="mt-2 text-xs text-muted">
              Move where the {Math.round(data.fit_window_s)}-second window
              starts, relative to the recorded start — use a negative value to
              shift it earlier. Tick <em>Crop the end too</em> to also trim the
              far edge when both ends of the measurement are disturbed;
              otherwise the window keeps its length, so a shift never cuts your
              measurement. For this spot only; saved — the results table and
              export follow.
            </p>
          </div>

          {data.flags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {data.flags.map((f) => (
                <FlagChip key={f} flag={f} />
              ))}
            </div>
          )}

          {/* Gas toggle */}
          <div
            role="tablist"
            aria-label="Gas"
            className="inline-flex rounded-lg border border-border p-1"
          >
            {(['CO2', 'CH4'] as Gas[]).map((g) => (
              <button
                key={g}
                role="tab"
                aria-selected={gas === g}
                onClick={() => setGas(g)}
                className={
                  gas === g
                    ? 'rounded-md bg-primary px-4 py-1.5 text-sm font-medium text-white'
                    : 'rounded-md px-4 py-1.5 text-sm font-medium text-muted hover:text-text'
                }
              >
                {g === 'CO2' ? 'CO₂' : 'CH₄'}
              </button>
            ))}
          </div>

          <Suspense fallback={<Skeleton className="h-[340px] w-full" />}>
            <RegressionPlot gas={gas} detail={data.gases[gas]} />
          </Suspense>

          {/* Fit facts */}
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 rounded-lg border border-border p-4 text-sm sm:grid-cols-3">
            <Fact label="Slope" value={String(data.gases[gas].fit.slope)} />
            <Fact label="R²" value={formatR2(data.gases[gas].fit.r2)} />
            <Fact
              label="Points used"
              value={String(data.gases[gas].fit.n_points)}
            />
            <Fact
              label="nan dropped"
              value={String(data.gases[gas].fit.n_dropped_nan)}
            />
            <Fact
              label="Spikes dropped"
              value={String(data.gases[gas].fit.n_spikes)}
            />
            <Fact label="Unit" value={data.gases[gas].unit} />
            <Fact
              label="Intercept"
              value={String(data.gases[gas].fit.intercept)}
            />
          </dl>

          {/* Full unit ladder */}
          <div>
            <h3 className="mb-2 text-sm font-semibold text-text">
              Flux — full unit ladder
            </h3>
            <div className="overflow-hidden rounded-lg border border-border">
              <table className="w-full text-sm">
                <tbody>
                  {UNIT_LADDER.map((u, i) => (
                    <tr
                      key={u.key}
                      className={i % 2 ? 'bg-surface-2/50' : undefined}
                    >
                      <th
                        scope="row"
                        className="px-3 py-1.5 text-left font-normal text-muted"
                      >
                        {u.label}
                      </th>
                      <td className="px-3 py-1.5 text-right tabular-nums text-text">
                        {String(
                          (
                            data.gases[gas].flux_ladder as unknown as Record<
                              string,
                              number
                            >
                          )[u.key],
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </Overlay>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-0.5 tabular-nums text-text">{value}</dd>
    </div>
  )
}
