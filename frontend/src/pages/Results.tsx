import { useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '@/api/client'
import type { ExportFormat, SpotResult } from '@/api/types'
import { useAsync } from '@/hooks/useAsync'
import {
  Stepper,
  Card,
  Button,
  Banner,
  SkeletonTable,
  ErrorState,
  Chip,
  FlagChip,
  LightDarkTag,
  Tooltip,
  useToast,
} from '@/components'
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
            placeholder="Search Nr, GPS, location"
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
        {formatTemperature(s.temperature_used_c)}
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
