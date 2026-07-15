import { lazy, Suspense, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '@/api/client'
import type { ExportFormat, Gas, SpotResult } from '@/api/types'
import { useAsync } from '@/hooks/useAsync'
import {
  Stepper,
  Card,
  Button,
  Banner,
  Skeleton,
  SkeletonTable,
  ErrorState,
  Chip,
  FlagChip,
  LightDarkTag,
  Tooltip,
  useToast,
} from '@/components'

// Code-split Plotly: only loads when results (with the graph) render.
const TimeSeriesPlot = lazy(() =>
  import('@/components/TimeSeriesPlot').then((m) => ({
    default: m.TimeSeriesPlot,
  })),
)
import {
  DownloadIcon,
  ListIcon,
  SearchIcon,
  ChevronDownIcon,
} from '@/components/icons'
import { EXPORT_FORMATS, LOW_R2_THRESHOLD } from '@/lib/constants'
import {
  formatFlux,
  formatR2,
  formatPressure,
  formatTemperature,
} from '@/lib/format'
import { SpotDetail } from './SpotDetail'

type SortKey = 'nr' | 'co2' | 'ch4' | 'r2co2' | 'r2ch4'

export function Results() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()

  const results = useAsync(() => api.getResults(id!), [id])
  const analysis = useAsync(() => api.getAnalysis(id!), [id])

  const [query, setQuery] = useState('')
  const [lightDark, setLightDark] = useState<'all' | 'light' | 'dark'>('all')
  const [flaggedOnly, setFlaggedOnly] = useState(false)
  const [sortKey, setSortKey] = useState<SortKey>('nr')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [openSpot, setOpenSpot] = useState<number | null>(null)

  const spots = results.data?.spots ?? []

  const filtered = useMemo(() => {
    const source = results.data?.spots ?? []
    const q = query.trim().toLowerCase()
    const rows = source.filter((s) => {
      if (lightDark !== 'all' && s.light_dark !== lightDark) return false
      if (flaggedOnly && s.flags.length === 0 && !s.skipped) return false
      if (!q) return true
      return (
        String(s.nr).includes(q) ||
        s.gps.toLowerCase().includes(q) ||
        s.location.toLowerCase().includes(q)
      )
    })
    const dir = sortDir === 'asc' ? 1 : -1
    const val = (s: SpotResult): number => {
      switch (sortKey) {
        case 'co2':
          return s.co2_flux_umol_m2_s ?? -Infinity
        case 'ch4':
          return s.ch4_flux_umol_m2_s ?? -Infinity
        case 'r2co2':
          return s.r2_co2 ?? -Infinity
        case 'r2ch4':
          return s.r2_ch4 ?? -Infinity
        default:
          return s.nr
      }
    }
    return [...rows].sort((a, b) => (val(a) - val(b)) * dir)
  }, [results.data, query, lightDark, flaggedOnly, sortKey, sortDir])

  const navigableNrs = spots.filter((s) => !s.skipped).map((s) => s.nr)

  async function onExport(format: ExportFormat) {
    try {
      const blob = await api.exportResults(id!, format)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${analysis.data?.name ?? 'flux-results'}.${format}`
      link.click()
      URL.revokeObjectURL(url)
      toast.show(`Exported ${link.download}`)
    } catch {
      toast.show('Export failed. Please try again.', 'error')
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Stepper
        current="Results"
        furthest="Results"
        onNavigate={(s) => {
          if (s === 'Upload') navigate(`/analyses/${id}/upload`)
          if (s === 'Confirm') navigate(`/analyses/${id}/confirm`)
        }}
      />

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-text">
            {analysis.data?.name ?? 'Results'}
          </h1>
          {analysis.data && (
            <p className="mt-1 text-sm text-muted">
              {analysis.data.spot_count} spots · {analysis.data.work_date}
            </p>
          )}
        </div>
        <Button
          variant="secondary"
          onClick={() => navigate(`/analyses/${id}/upload`)}
        >
          Re-run
        </Button>
      </div>

      {/* Quality check summary.
          TODO: n8n quality check (later seminar) — the backend returns
          available:false for now; this "unavailable" branch is the current path. */}
      {results.data &&
        (results.data.quality_check.available ? (
          <Banner tone="info" title="Quality check">
            {results.data.quality_check.summary}
            {results.data.quality_check.flags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {results.data.quality_check.flags.map((f, i) => (
                  <Chip
                    key={i}
                    tone={f.severity === 'high' ? 'danger' : 'warning'}
                  >
                    Spot {f.nr} · {f.gas === 'CO2' ? 'CO₂' : 'CH₄'}: {f.issue}
                  </Chip>
                ))}
              </div>
            )}
          </Banner>
        ) : (
          <Banner tone="warning" title="Quality check unavailable">
            The automatic quality check didn't run. Please review the R² values
            manually — the flux numbers below were computed regardless.
          </Banner>
        ))}

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 sm:max-w-xs">
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search Nr, GPS, comment"
            aria-label="Search results"
            className="h-10 w-full rounded-lg border border-border bg-surface pl-9 pr-3 text-sm text-text placeholder:text-muted focus:border-primary"
          />
        </div>

        <select
          aria-label="Filter by light or dark"
          value={lightDark}
          onChange={(e) =>
            setLightDark(e.target.value as 'all' | 'light' | 'dark')
          }
          className="h-10 rounded-lg border border-border bg-surface px-3 text-sm text-text focus:border-primary"
        >
          <option value="all">All</option>
          <option value="light">Light only</option>
          <option value="dark">Dark only</option>
        </select>

        <label className="inline-flex h-10 cursor-pointer items-center gap-2 rounded-lg border border-border bg-surface px-3 text-sm text-text">
          <input
            type="checkbox"
            checked={flaggedOnly}
            onChange={(e) => setFlaggedOnly(e.target.checked)}
            className="h-4 w-4 accent-[var(--primary)]"
          />
          Flagged only
        </label>

        <div className="ml-auto flex items-center gap-2">
          <select
            aria-label="Sort by"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
            className="h-10 rounded-lg border border-border bg-surface px-3 text-sm text-text focus:border-primary"
          >
            <option value="nr">Sort: Nr</option>
            <option value="co2">Sort: CO₂ flux</option>
            <option value="ch4">Sort: CH₄ flux</option>
            <option value="r2co2">Sort: R² CO₂</option>
            <option value="r2ch4">Sort: R² CH₄</option>
          </select>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))}
          >
            {sortDir === 'asc' ? 'Asc' : 'Desc'}
          </Button>

          <ExportMenu onExport={onExport} />

          <Button
            variant="ghost"
            size="sm"
            leftIcon={<ListIcon className="h-4 w-4" />}
            onClick={() => navigate(`/analyses/${id}/log`)}
          >
            <span className="hidden sm:inline">Processing log</span>
          </Button>
        </div>
      </div>

      {/* Regression graph: concentration time series + fitted flux line, with
          the chosen (best) window shaded, for a selected spot. */}
      {results.data && id && navigableNrs.length > 0 && (
        <SpotGraph analysisId={id} spotNrs={navigableNrs} />
      )}

      {/* Table / states */}
      {results.loading && (
        <Card className="p-4">
          <SkeletonTable rows={8} cols={7} />
        </Card>
      )}

      {results.error && (
        <ErrorState
          title="Couldn't load results"
          description={results.error.message}
          onRetry={results.reload}
        />
      )}

      {results.data && filtered.length === 0 && (
        <Card className="p-10 text-center text-sm text-muted">
          No spots match your filters.
        </Card>
      )}

      {results.data && filtered.length > 0 && (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                  <th scope="col" className="px-3 py-2 font-medium">
                    Nr
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Start
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Stop
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    GPS
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Type
                  </th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">
                    CO₂ flux
                  </th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">
                    CH₄ flux
                  </th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">
                    R² CO₂
                  </th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">
                    R² CH₄
                  </th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">
                    Temp
                  </th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">
                    Pressure
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Flags
                  </th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => (
                  <ResultRow
                    key={s.nr}
                    s={s}
                    onOpen={() => !s.skipped && setOpenSpot(s.nr)}
                  />
                ))}
              </tbody>
            </table>
          </div>
          <p className="border-t border-border px-3 py-2 text-xs text-muted">
            CO₂ / CH₄ flux in µmol · m⁻² · s⁻¹. Full unit ladder in each spot
            and the export. R² below {LOW_R2_THRESHOLD.toFixed(2)} is
            highlighted.
          </p>
        </Card>
      )}

      {openSpot !== null && id && (
        <SpotDetail
          analysisId={id}
          nr={openSpot}
          spotNrs={navigableNrs}
          onClose={() => setOpenSpot(null)}
          onNavigate={setOpenSpot}
        />
      )}
    </div>
  )
}

function ResultRow({ s, onOpen }: { s: SpotResult; onOpen: () => void }) {
  if (s.skipped) {
    return (
      <tr className="border-b border-border bg-surface-2/40 text-muted">
        <td className="px-3 py-2 tabular-nums">{s.nr}</td>
        <td className="px-3 py-2 tabular-nums">{s.start}</td>
        <td className="px-3 py-2 tabular-nums">{s.stop}</td>
        <td className="px-3 py-2">{s.gps || '—'}</td>
        <td className="px-3 py-2">
          <LightDarkTag value={s.light_dark} />
        </td>
        <td className="px-3 py-2 text-right" colSpan={6}>
          <Tooltip content={s.skip_reason ?? 'Skipped'}>
            <span className="cursor-help italic underline decoration-dotted">
              Skipped — {s.skip_reason}
            </span>
          </Tooltip>
        </td>
      </tr>
    )
  }
  const lowCo2 = (s.r2_co2 ?? 1) < LOW_R2_THRESHOLD
  const lowCh4 = (s.r2_ch4 ?? 1) < LOW_R2_THRESHOLD
  return (
    <tr
      onClick={onOpen}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onOpen()
        }
      }}
      className="cursor-pointer border-b border-border hover:bg-primary-subtle focus:bg-primary-subtle focus:outline-none"
    >
      <td className="px-3 py-2 tabular-nums font-medium text-text">{s.nr}</td>
      <td className="px-3 py-2 tabular-nums text-muted">{s.start}</td>
      <td className="px-3 py-2 tabular-nums text-muted">{s.stop}</td>
      <td className="px-3 py-2 text-muted">{s.gps || '—'}</td>
      <td className="px-3 py-2">
        <LightDarkTag value={s.light_dark} />
      </td>
      <td className="px-3 py-2 text-right tabular-nums text-text">
        {formatFlux(s.co2_flux_umol_m2_s)}
      </td>
      <td className="px-3 py-2 text-right tabular-nums text-text">
        {formatFlux(s.ch4_flux_umol_m2_s)}
      </td>
      <td
        className={
          lowCo2
            ? 'rounded bg-warning-tint px-3 py-2 text-right font-medium tabular-nums text-warning'
            : 'px-3 py-2 text-right tabular-nums text-text'
        }
      >
        {formatR2(s.r2_co2)}
      </td>
      <td
        className={
          lowCh4
            ? 'bg-warning-tint px-3 py-2 text-right font-medium tabular-nums text-warning'
            : 'px-3 py-2 text-right tabular-nums text-text'
        }
      >
        {formatR2(s.r2_ch4)}
      </td>
      <td className="px-3 py-2 text-right tabular-nums text-muted">
        {s.temperature_min_c != null && s.temperature_max_c != null ? (
          <Tooltip
            content={`Range over the window: ${formatTemperature(
              s.temperature_min_c,
            )} – ${formatTemperature(s.temperature_max_c)} (mean used in the flux)`}
          >
            <span className="cursor-help underline decoration-dotted">
              {formatTemperature(s.temperature_used_c)}
            </span>
          </Tooltip>
        ) : (
          formatTemperature(s.temperature_used_c)
        )}
      </td>
      <td className="px-3 py-2 text-right tabular-nums text-muted">
        {formatPressure(s.pressure_used_hpa)}
      </td>
      <td className="px-3 py-2">
        <div className="flex flex-wrap gap-1">
          {s.flags.map((f) => (
            <FlagChip key={f} flag={f} />
          ))}
        </div>
      </td>
    </tr>
  )
}

/** Inline concentration-vs-time graph with the fitted flux line and shaded fit
 *  window, for a spot the user selects. Lets you verify the match/fit visually
 *  on the results page without opening each spot. */
function SpotGraph({
  analysisId,
  spotNrs,
}: {
  analysisId: string
  spotNrs: number[]
}) {
  const [mode, setMode] = useState<'single' | 'all'>('single')
  const [nr, setNr] = useState(spotNrs[0])
  const [gas, setGas] = useState<Gas>('CO2')
  const { data, loading } = useAsync(
    () => api.getTimeseries(analysisId),
    [analysisId],
  )
  // If the selected spot vanished from the list (re-run), fall back to the first.
  const selected = spotNrs.includes(nr) ? nr : spotNrs[0]
  const gasData = data ? (gas === 'CO2' ? data.co2 : data.ch4) : null

  return (
    <Card className="p-4">
      <div className="mb-1 flex flex-wrap items-center gap-3">
        <h2 className="text-sm font-semibold text-text">
          Concentration &amp; flux fit
        </h2>
        <div
          role="tablist"
          aria-label="Which spots"
          className="inline-flex rounded-lg border border-border p-1"
        >
          {(['single', 'all'] as const).map((m) => (
            <button
              key={m}
              role="tab"
              aria-selected={mode === m}
              onClick={() => setMode(m)}
              className={
                mode === m
                  ? 'rounded-md bg-primary px-3 py-1 text-sm font-medium text-white'
                  : 'rounded-md px-3 py-1 text-sm font-medium text-muted hover:text-text'
              }
            >
              {m === 'single' ? 'This spot' : 'All spots'}
            </button>
          ))}
        </div>
        {mode === 'single' && (
          <label className="flex items-center gap-2 text-sm text-muted">
            Spot
            <select
              aria-label="Graph spot"
              value={selected}
              onChange={(e) => setNr(Number(e.target.value))}
              className="h-9 rounded-lg border border-border bg-surface px-2 text-sm text-text focus:border-primary"
            >
              {spotNrs.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        )}
        <div
          role="tablist"
          aria-label="Gas"
          className="ml-auto inline-flex rounded-lg border border-border p-1"
        >
          {(['CO2', 'CH4'] as Gas[]).map((g) => (
            <button
              key={g}
              role="tab"
              aria-selected={gas === g}
              onClick={() => setGas(g)}
              className={
                gas === g
                  ? 'rounded-md bg-primary px-3 py-1 text-sm font-medium text-white'
                  : 'rounded-md px-3 py-1 text-sm font-medium text-muted hover:text-text'
              }
            >
              {g === 'CO2' ? 'CO₂' : 'CH₄'}
            </button>
          ))}
        </div>
      </div>
      <p className="mb-2 text-xs text-muted">
        Real clock time on the x-axis. Highlighted points + line = the fitted
        window; drag to zoom and check individual points.
      </p>
      {loading || !gasData ? (
        <Skeleton className="h-[380px] w-full" />
      ) : (
        <Suspense fallback={<Skeleton className="h-[380px] w-full" />}>
          <TimeSeriesPlot
            gas={gas}
            data={gasData}
            mode={mode}
            selectedNr={selected}
          />
        </Suspense>
      )}
    </Card>
  )
}

function ExportMenu({
  onExport,
}: {
  onExport: (format: ExportFormat) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  return (
    <div
      ref={ref}
      className="relative"
      onBlur={(e) => {
        if (!ref.current?.contains(e.relatedTarget as Node)) setOpen(false)
      }}
    >
      <Button
        variant="primary"
        size="sm"
        leftIcon={<DownloadIcon className="h-4 w-4" />}
        rightIcon={<ChevronDownIcon className="h-4 w-4" />}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        Export
      </Button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-30 mt-1 w-56 rounded-lg border border-border bg-surface p-1 shadow-md"
        >
          {EXPORT_FORMATS.map((f) => (
            <button
              key={f.format}
              role="menuitem"
              onClick={() => {
                setOpen(false)
                onExport(f.format)
              }}
              className="block w-full rounded-md px-3 py-2 text-left text-sm text-text hover:bg-surface-2"
            >
              {f.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
