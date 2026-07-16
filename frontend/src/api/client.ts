/**
 * Typed API client for the Flux Calculation backend.
 *
 * Real HTTP calls to the FastAPI backend (base URL from VITE_API_BASE_URL). The
 * function signatures and return types are the contract the rest of the app
 * depends on and are unchanged from the earlier mock phase.
 *
 * Deferred features keep their placeholders end-to-end: the backend returns
 * `quality_check.available === false` (n8n — later seminar) and
 * `parse_failed === false` (LLM notes parser — seminar 6); the UI already handles
 * both, so nothing is built here.
 */
import type {
  Analysis,
  AnalysisSummary,
  CreateAnalysisInput,
  ExportFormat,
  FitMode,
  LogEntry,
  NoteRow,
  ParsedNotes,
  ResultsPayload,
  SpotDetail,
  Timeseries,
} from '@/api/types'

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api'

/** Error the UI can branch on (missing file, bad format, duplicate name). */
export class ApiError extends Error {
  code: string
  field?: string
  constructor(code: string, message: string, field?: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.field = field
  }
}

/** Turn a non-OK response into an ApiError, preserving the backend's code/field. */
async function toApiError(res: Response): Promise<ApiError> {
  let detail: unknown
  try {
    detail = (await res.json())?.detail
  } catch {
    detail = undefined
  }
  if (detail && typeof detail === 'object') {
    const d = detail as { code?: string; message?: string; field?: string }
    return new ApiError(
      d.code ?? 'error',
      d.message ?? `Request failed (${res.status})`,
      d.field,
    )
  }
  return new ApiError('http_error', `Request failed (${res.status})`)
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(`${BASE_URL}${path}`, init)
  if (!res.ok) throw await toApiError(res)
  return res
}

async function getJson<T>(path: string): Promise<T> {
  const res = await request(path)
  return (await res.json()) as T
}

/** Build the multipart body for create/update. Only non-null files are sent. */
function analysisForm(input: CreateAnalysisInput): FormData {
  const form = new FormData()
  form.append('name', input.name)
  form.append('work_date', input.work_date)
  form.append('chamber_area_m2', String(input.chamber_area_m2))
  form.append('chamber_volume_l', String(input.chamber_volume_l))
  form.append('time_offset_seconds', String(input.time_offset_seconds))
  const roles = ['concentration', 'notes', 'temperature', 'pressure'] as const
  for (const role of roles) {
    const file = input.files[role]
    if (file) form.append(role, file)
  }
  return form
}

export const api = {
  /** GET /analyses */
  listAnalyses(): Promise<AnalysisSummary[]> {
    return getJson<AnalysisSummary[]>('/analyses')
  },

  /** GET /analyses/{id} */
  getAnalysis(id: string): Promise<Analysis> {
    return getJson<Analysis>(`/analyses/${id}`)
  },

  /** DELETE /analyses/{id} */
  async deleteAnalysis(id: string): Promise<void> {
    await request(`/analyses/${id}`, { method: 'DELETE' })
  },

  /** POST /analyses (multipart: files + fields; pressure optional). */
  async createAnalysis(input: CreateAnalysisInput): Promise<Analysis> {
    const res = await request('/analyses', {
      method: 'POST',
      body: analysisForm(input),
    })
    return (await res.json()) as Analysis
  },

  /**
   * PUT /analyses/{id} — edit an existing analysis and replace any files.
   * Only files present in `input.files` are replaced; the rest are kept. The
   * backend resets the analysis to `needs_review` (re-confirm + re-match).
   */
  async updateAnalysis(
    id: string,
    input: CreateAnalysisInput,
  ): Promise<Analysis> {
    const res = await request(`/analyses/${id}`, {
      method: 'PUT',
      body: analysisForm(input),
    })
    return (await res.json()) as Analysis
  },

  /** GET /analyses/{id}/notes */
  getNotes(id: string): Promise<ParsedNotes> {
    return getJson<ParsedNotes>(`/analyses/${id}/notes`)
  },

  /** PUT /analyses/{id}/notes */
  async saveNotes(id: string, rows: NoteRow[]): Promise<ParsedNotes> {
    const res = await request(`/analyses/${id}/notes`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rows),
    })
    return (await res.json()) as ParsedNotes
  },

  /** POST /analyses/{id}/match (approve -> match + fit) */
  async matchAndCompute(id: string): Promise<void> {
    await request(`/analyses/${id}/match`, { method: 'POST' })
  },

  /** GET /analyses/{id}/results */
  getResults(id: string): Promise<ResultsPayload> {
    return getJson<ResultsPayload>(`/analyses/${id}/results`)
  },

  /**
   * GET /analyses/{id}/spots/{nr} — null for a skipped spot.
   * `fitMode` "full" fits the whole recorded window (no window search).
   */
  async getSpotDetail(
    id: string,
    nr: number,
    fitMode: FitMode = 'auto',
  ): Promise<SpotDetail | null> {
    const query = fitMode === 'auto' ? '' : `?fit_mode=${fitMode}`
    const res = await fetch(`${BASE_URL}/analyses/${id}/spots/${nr}${query}`)
    if (res.status === 404) return null
    if (!res.ok) throw await toApiError(res)
    return (await res.json()) as SpotDetail | null
  },

  /** GET /analyses/{id}/log */
  getLog(id: string): Promise<LogEntry[]> {
    return getJson<LogEntry[]>(`/analyses/${id}/log`)
  },

  /** GET /analyses/{id}/timeseries — all spots' points on the absolute time axis. */
  getTimeseries(id: string): Promise<Timeseries> {
    return getJson<Timeseries>(`/analyses/${id}/timeseries`)
  },

  /** GET /analyses/{id}/export?format=xlsx|txt|csv — the file blob. */
  async exportResults(id: string, format: ExportFormat): Promise<Blob> {
    const res = await request(`/analyses/${id}/export?format=${format}`)
    return res.blob()
  },
}
