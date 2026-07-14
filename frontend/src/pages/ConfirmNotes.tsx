import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '@/api/client'
import type { LightDark, NoteRow } from '@/api/types'
import { useAsync } from '@/hooks/useAsync'
import {
  Stepper,
  Card,
  Button,
  Banner,
  SkeletonTable,
  ErrorState,
  IconButton,
  PipelineProgress,
  type PipelineStep,
} from '@/components'
import { PlusIcon, TrashIcon, WarningIcon } from '@/components/icons'

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** Seconds since midnight, or null if the string isn't a valid HH:MM[:SS]. */
function parseTime(value: string): number | null {
  const m = value.trim().match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/)
  if (!m) return null
  const h = Number(m[1])
  const min = Number(m[2])
  const s = m[3] ? Number(m[3]) : 0
  if (h > 23 || min > 59 || s > 59) return null
  return h * 3600 + min * 60 + s
}

interface RowError {
  startInvalid: boolean
  stopInvalid: boolean
  stopBeforeStart: boolean
  gpsMissing: boolean
}

function rowErrors(row: NoteRow): RowError {
  const start = parseTime(row.start_time)
  const stop = parseTime(row.stop_time)
  return {
    startInvalid: start === null,
    stopInvalid: stop === null,
    stopBeforeStart: start !== null && stop !== null && stop <= start,
    gpsMissing: !row.gps.trim() || row.gps.trim() === '?',
  }
}

/** Hard errors block Approve; a missing GPS is only a soft warning. */
function hasHardError(e: RowError): boolean {
  return e.startInvalid || e.stopInvalid || e.stopBeforeStart
}

export function ConfirmNotes() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data, loading, error, reload } = useAsync(
    () => api.getNotes(id!),
    [id],
  )

  const [rows, setRows] = useState<NoteRow[]>([])
  const [running, setRunning] = useState(false)
  const [steps, setSteps] = useState<PipelineStep[]>([])

  useEffect(() => {
    if (data) setRows(data.rows)
  }, [data])

  function updateRow(nr: number, patch: Partial<NoteRow>) {
    setRows((rs) => rs.map((r) => (r.nr === nr ? { ...r, ...patch } : r)))
  }
  function deleteRow(nr: number) {
    setRows((rs) => rs.filter((r) => r.nr !== nr))
  }
  function addRow() {
    const nextNr = rows.reduce((m, r) => Math.max(m, r.nr), 0) + 1
    setRows((rs) => [
      ...rs,
      {
        nr: nextNr,
        start_time: '',
        stop_time: '',
        gps: '',
        light_dark: 'light',
        location: '',
        flags: [],
      },
    ])
  }

  const errorsByNr = new Map(rows.map((r) => [r.nr, rowErrors(r)]))
  const hardErrorCount = rows.filter((r) =>
    hasHardError(errorsByNr.get(r.nr)!),
  ).length
  const warningCount = rows.filter((r) => {
    const e = errorsByNr.get(r.nr)!
    return !hasHardError(e) && e.gpsMissing
  }).length

  async function approve() {
    if (hardErrorCount > 0) return
    setRunning(true)
    setSteps([
      { label: 'Saving your confirmed notes', status: 'active' },
      {
        label: 'Matching temperature & pressure to each spot',
        status: 'pending',
      },
      { label: 'Fitting CO₂ and CH₄ slopes', status: 'pending' },
    ])
    await api.saveNotes(id!, rows)
    setSteps([
      { label: 'Saving your confirmed notes', status: 'done' },
      {
        label: 'Matching temperature & pressure to each spot',
        status: 'active',
      },
      { label: 'Fitting CO₂ and CH₄ slopes', status: 'pending' },
    ])
    await sleep(600)
    setSteps([
      { label: 'Saving your confirmed notes', status: 'done' },
      { label: 'Matching temperature & pressure to each spot', status: 'done' },
      { label: 'Fitting CO₂ and CH₄ slopes', status: 'active' },
    ])
    await api.matchAndCompute(id!)
    setSteps((s) => s.map((x) => ({ ...x, status: 'done' })))
    await sleep(300)
    navigate(`/analyses/${id}/results`)
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
        onNavigate={(s) => s === 'Upload' && navigate(`/analyses/${id}/upload`)}
      />

      <div>
        <h1 className="text-2xl font-bold text-text">Confirm parsed notes</h1>
        <p className="mt-1 text-sm text-muted">
          Review the cleaned field notes before we match the data.
        </p>
      </div>

      {data?.parse_failed ? (
        <Banner tone="warning" title="Automatic parsing failed">
          Please check the times below manually before continuing.
        </Banner>
      ) : (
        <Banner tone="info">
          We cleaned up your field notes. Please confirm the times and GPS
          before we match the data.
        </Banner>
      )}

      {loading && (
        <Card className="p-4">
          <SkeletonTable rows={6} cols={6} />
        </Card>
      )}

      {error && (
        <ErrorState
          title="Couldn't load the parsed notes"
          description={error.message}
          onRetry={reload}
        />
      )}

      {!loading && !error && (
        <>
          {(hardErrorCount > 0 || warningCount > 0) && (
            <div className="flex flex-wrap items-center gap-4 text-sm">
              {hardErrorCount > 0 && (
                <span className="inline-flex items-center gap-1.5 text-danger">
                  <WarningIcon className="h-4 w-4" />
                  {hardErrorCount} row{hardErrorCount > 1 ? 's' : ''} need
                  attention before you can continue
                </span>
              )}
              {warningCount > 0 && (
                <span className="inline-flex items-center gap-1.5 text-warning">
                  <WarningIcon className="h-4 w-4" />
                  {warningCount} row{warningCount > 1 ? 's' : ''} missing GPS
                  (allowed)
                </span>
              )}
            </div>
          )}

          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm">
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
                      Light/Dark
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Location
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const e = errorsByNr.get(row.nr)!
                    const hard = hasHardError(e)
                    return (
                      <tr
                        key={row.nr}
                        className={
                          hard
                            ? 'border-b border-border bg-danger-tint/40'
                            : e.gpsMissing
                              ? 'border-b border-border bg-warning-tint/30'
                              : 'border-b border-border'
                        }
                      >
                        <td className="px-3 py-2 tabular-nums text-muted">
                          <span className="inline-flex items-center gap-1">
                            {hard && (
                              <WarningIcon className="h-4 w-4 text-danger" />
                            )}
                            {row.nr}
                          </span>
                        </td>
                        <td className="px-2 py-1.5">
                          <CellInput
                            value={row.start_time}
                            invalid={e.startInvalid || e.stopBeforeStart}
                            ariaLabel={`Start time for spot ${row.nr}`}
                            placeholder="HH:MM:SS"
                            onChange={(v) =>
                              updateRow(row.nr, { start_time: v })
                            }
                          />
                        </td>
                        <td className="px-2 py-1.5">
                          <CellInput
                            value={row.stop_time}
                            invalid={e.stopInvalid || e.stopBeforeStart}
                            ariaLabel={`Stop time for spot ${row.nr}`}
                            placeholder="HH:MM:SS"
                            onChange={(v) =>
                              updateRow(row.nr, { stop_time: v })
                            }
                          />
                        </td>
                        <td className="px-2 py-1.5">
                          <CellInput
                            value={row.gps}
                            invalid={e.gpsMissing}
                            ariaLabel={`GPS for spot ${row.nr}`}
                            placeholder="lat, lon"
                            onChange={(v) => updateRow(row.nr, { gps: v })}
                          />
                        </td>
                        <td className="px-2 py-1.5">
                          <select
                            aria-label={`Light or dark for spot ${row.nr}`}
                            value={row.light_dark}
                            onChange={(ev) =>
                              updateRow(row.nr, {
                                light_dark: ev.target.value as LightDark,
                              })
                            }
                            className="h-9 rounded-lg border border-border bg-surface px-2 text-sm text-text focus:border-primary"
                          >
                            <option value="light">light</option>
                            <option value="dark">dark</option>
                          </select>
                        </td>
                        <td className="px-2 py-1.5">
                          <CellInput
                            value={row.location}
                            ariaLabel={`Location for spot ${row.nr}`}
                            placeholder="location"
                            onChange={(v) => updateRow(row.nr, { location: v })}
                          />
                        </td>
                        <td className="px-2 py-1.5 text-right">
                          <IconButton
                            label={`Delete spot ${row.nr}`}
                            className="h-9 w-9"
                            onClick={() => deleteRow(row.nr)}
                          >
                            <TrashIcon className="h-4 w-4" />
                          </IconButton>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="border-t border-border p-3">
              <Button
                variant="ghost"
                size="sm"
                leftIcon={<PlusIcon className="h-4 w-4" />}
                onClick={addRow}
              >
                Add row
              </Button>
            </div>
          </Card>

          <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6">
            <Button
              variant="secondary"
              onClick={() => navigate(`/analyses/${id}/upload`)}
            >
              Back
            </Button>
            <Button
              variant="cta"
              onClick={approve}
              disabled={hardErrorCount > 0 || rows.length === 0}
            >
              Approve &amp; match
            </Button>
          </div>
        </>
      )}
    </div>
  )
}

function CellInput({
  value,
  onChange,
  invalid,
  ariaLabel,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  invalid?: boolean
  ariaLabel: string
  placeholder?: string
}) {
  return (
    <input
      type="text"
      value={value}
      aria-label={ariaLabel}
      aria-invalid={invalid || undefined}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className={
        invalid
          ? 'h-9 w-full min-w-24 rounded-lg border border-danger bg-surface px-2 text-sm text-text tabular-nums'
          : 'h-9 w-full min-w-24 rounded-lg border border-border bg-surface px-2 text-sm text-text tabular-nums focus:border-primary'
      }
    />
  )
}
