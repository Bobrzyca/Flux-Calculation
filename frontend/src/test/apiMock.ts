/**
 * Test-only fetch mock for the backend API.
 *
 * Installs a `global.fetch` stub that serves the deterministic fixtures in
 * `mockData.ts`, so component/integration tests run without a live backend. This
 * replaces the old in-memory client and is imported ONLY from tests — the app's
 * runtime `api` client makes real fetch calls.
 */
import { vi } from 'vitest'

import type { Analysis, ParsedNotes } from '@/api/types'
import {
  SEED_ANALYSES,
  buildLog,
  buildNotes,
  buildResults,
  buildSpotDetail,
  buildTimeseries,
} from '@/test/mockData'

let analyses: Analysis[] = []
let notesStore = new Map<string, ParsedNotes>()
let idCounter = 1

export function resetApiMock(): void {
  analyses = SEED_ANALYSES.map((a) => ({ ...a }))
  notesStore = new Map()
  idCounter = 1
}

function json(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

function errorResponse(
  status: number,
  code: string,
  message: string,
  field?: string,
): Response {
  const detail: Record<string, string> = { code, message }
  if (field) detail.field = field
  return json({ detail }, status)
}

function exportBlob(format: string): Response {
  const { spots } = buildResults()
  const sep = format === 'csv' ? ',' : '\t'
  const headers = [
    'Nr',
    'date',
    'start',
    'stop',
    'GPS',
    'light/dark',
    'location',
    'CO2 flux (umol/m2/s)',
    'CH4 flux (umol/m2/s)',
    'R2_CO2',
    'R2_CH4',
    'temperature_used',
    'pressure_used',
    'time_offset_applied',
  ]
  const lines = spots.map((s) =>
    [
      s.nr,
      s.date,
      s.start,
      s.stop,
      s.gps,
      s.light_dark,
      s.location,
      s.co2_flux_umol_m2_s ?? '',
      s.ch4_flux_umol_m2_s ?? '',
      s.r2_co2 ?? '',
      s.r2_ch4 ?? '',
      s.temperature_used_c ?? '',
      s.pressure_used_hpa ?? '',
      s.time_offset_applied_s,
    ].join(sep),
  )
  const content = [headers.join(sep), ...lines].join('\n')
  return new Response(content, {
    status: 200,
    headers: { 'content-type': format === 'csv' ? 'text/csv' : 'text/plain' },
  })
}

async function handle(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const url = new URL(String(input instanceof Request ? input.url : input))
  const path = url.pathname.replace(/^\/api/, '')
  const method = (init?.method ?? 'GET').toUpperCase()

  // POST /analyses (multipart create).
  if (path === '/analyses' && method === 'POST') {
    const form = init?.body as FormData
    const name = String(form.get('name') ?? '')
    if (/dup/i.test(name)) {
      return errorResponse(
        409,
        'duplicate_name',
        `"${name}" already exists.`,
        'name',
      )
    }
    const conc = form.get('concentration')
    if (conc instanceof File && /bad/i.test(conc.name)) {
      return errorResponse(
        422,
        'bad_li7810',
        "This doesn't look like a LI-7810 export — expected columns SECONDS, CO2, CH4.",
        'concentration',
      )
    }
    const analysis: Analysis = {
      id: `an_new_${idCounter++}`,
      name,
      work_date: String(form.get('work_date') ?? ''),
      spot_count: 18,
      status: 'needs_review',
      created_at: '2026-07-14T12:00:00Z',
      chamber_area_m2: Number(form.get('chamber_area_m2')),
      chamber_volume_l: Number(form.get('chamber_volume_l')),
      time_offset_seconds: Number(form.get('time_offset_seconds')),
    }
    analyses = [analysis, ...analyses]
    return json(analysis, 201)
  }

  // GET /analyses (list).
  if (path === '/analyses' && method === 'GET') {
    const sorted = [...analyses].sort((a, b) =>
      b.created_at.localeCompare(a.created_at),
    )
    return json(sorted)
  }

  const idMatch = path.match(/^\/analyses\/([^/]+)$/)
  if (idMatch) {
    const id = idMatch[1]
    if (method === 'DELETE') {
      analyses = analyses.filter((a) => a.id !== id)
      notesStore.delete(id)
      return json(null, 204)
    }
    const found = analyses.find((a) => a.id === id)
    if (!found)
      return errorResponse(404, 'not_found', `Analysis ${id} not found.`)
    return json(found)
  }

  const notesMatch = path.match(/^\/analyses\/([^/]+)\/notes$/)
  if (notesMatch) {
    const id = notesMatch[1]
    if (method === 'PUT') {
      const rows = JSON.parse(String(init?.body ?? '[]'))
      const payload: ParsedNotes = { parse_failed: false, rows }
      notesStore.set(id, payload)
      return json(payload)
    }
    return json(notesStore.get(id) ?? buildNotes())
  }

  const matchMatch = path.match(/^\/analyses\/([^/]+)\/match$/)
  if (matchMatch && method === 'POST') {
    const id = matchMatch[1]
    analyses = analyses.map((a) =>
      a.id === id ? { ...a, status: 'complete' as const } : a,
    )
    return json({ status: 'complete' })
  }

  const resultsMatch = path.match(/^\/analyses\/([^/]+)\/results$/)
  if (resultsMatch) return json(buildResults())

  const spotMatch = path.match(/^\/analyses\/([^/]+)\/spots\/(\d+)$/)
  if (spotMatch) return json(buildSpotDetail(Number(spotMatch[2])))

  const tsMatch = path.match(/^\/analyses\/([^/]+)\/timeseries$/)
  if (tsMatch) return json(buildTimeseries())

  const logMatch = path.match(/^\/analyses\/([^/]+)\/log$/)
  if (logMatch) return json(buildLog())

  const exportMatch = path.match(/^\/analyses\/([^/]+)\/export$/)
  if (exportMatch) return exportBlob(url.searchParams.get('format') ?? 'xlsx')

  return errorResponse(404, 'not_found', `No mock route for ${method} ${path}`)
}

export function installApiMock(): void {
  globalThis.fetch = vi.fn(handle) as unknown as typeof fetch
}
