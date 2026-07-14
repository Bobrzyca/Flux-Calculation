/**
 * Typed API client for the Flux Calculation backend.
 *
 * PHASE 1: every method is backed by in-memory mocks (src/api/mocks). Each is
 * annotated `TODO: connect to API` with the real endpoint it will call. Swap the
 * bodies for fetch() calls later; the signatures and return types are the
 * contract and should not need to change.
 */
import type {
  Analysis,
  AnalysisSummary,
  CreateAnalysisInput,
  ExportFormat,
  LogEntry,
  ParsedNotes,
  NoteRow,
  ResultsPayload,
  SpotDetail,
} from '@/api/types'
import {
  SEED_ANALYSES,
  buildLog,
  buildNotes,
  buildResults,
  buildSpotDetail,
} from '@/api/mocks/data'

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

/** Simulated network latency (ms). Kept short so the UI feels responsive. */
const LATENCY = 450
function delay<T>(value: T, ms = LATENCY): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms))
}

/** Mutable session store, seeded from the fixtures. */
let analyses: Analysis[] = [...SEED_ANALYSES]
/** Per-analysis edited notes (persist within a session). */
const notesStore = new Map<string, ParsedNotes>()

let idCounter = 1
function nextId(): string {
  // Deterministic-ish id without Date.now(); fine for a local mock.
  return `an_new_${idCounter++}`
}

export const api = {
  /** TODO: connect to API — GET /analyses */
  async listAnalyses(): Promise<AnalysisSummary[]> {
    return delay(
      [...analyses].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    )
  },

  /** TODO: connect to API — GET /analyses/{id} */
  async getAnalysis(id: string): Promise<Analysis> {
    const found = analyses.find((a) => a.id === id)
    if (!found) throw new ApiError('not_found', `Analysis ${id} not found`)
    return delay(found)
  },

  /** TODO: connect to API — DELETE /analyses/{id} */
  async deleteAnalysis(id: string): Promise<void> {
    analyses = analyses.filter((a) => a.id !== id)
    notesStore.delete(id)
    return delay(undefined)
  },

  /**
   * TODO: connect to API — POST /analyses (multipart: 4 files + fields).
   * Mock error injection (so the UI error states are reachable):
   *   - name containing "dup" -> duplicate-name error
   *   - concentration filename containing "bad" -> LI-7810 format error
   */
  async createAnalysis(input: CreateAnalysisInput): Promise<Analysis> {
    await delay(undefined, 900)

    if (/dup/i.test(input.name)) {
      throw new ApiError(
        'duplicate_name',
        `An analysis named "${input.name}" already exists.`,
        'name',
      )
    }
    const conc = input.files.concentration
    if (conc && /bad/i.test(conc.name)) {
      throw new ApiError(
        'bad_li7810',
        "This doesn't look like a LI-7810 export — expected columns SECONDS, CO2, CH4.",
        'concentration',
      )
    }

    const analysis: Analysis = {
      id: nextId(),
      name: input.name,
      work_date: input.work_date,
      spot_count: 18,
      status: 'needs_review',
      created_at: '2026-07-14T12:00:00Z',
      chamber_area_m2: input.chamber_area_m2,
      chamber_volume_l: input.chamber_volume_l,
      time_offset_seconds: input.time_offset_seconds,
    }
    analyses = [analysis, ...analyses]
    return analysis
  },

  /** TODO: connect to API — GET /analyses/{id}/notes */
  async getNotes(id: string): Promise<ParsedNotes> {
    const stored = notesStore.get(id)
    if (stored) return delay(stored)
    return delay(buildNotes())
  },

  /** TODO: connect to API — PUT /analyses/{id}/notes */
  async saveNotes(id: string, rows: NoteRow[]): Promise<ParsedNotes> {
    const payload: ParsedNotes = { parse_failed: false, rows }
    notesStore.set(id, payload)
    return delay(payload)
  },

  /** TODO: connect to API — POST /analyses/{id}/match (approve -> match + fit) */
  async matchAndCompute(id: string): Promise<void> {
    const idx = analyses.findIndex((a) => a.id === id)
    if (idx >= 0) analyses[idx] = { ...analyses[idx], status: 'complete' }
    return delay(undefined, 900)
  },

  /** TODO: connect to API — GET /analyses/{id}/results */
  async getResults(_id: string): Promise<ResultsPayload> {
    return delay(buildResults())
  },

  /** TODO: connect to API — GET /analyses/{id}/spots/{nr} */
  async getSpotDetail(_id: string, nr: number): Promise<SpotDetail | null> {
    return delay(buildSpotDetail(nr))
  },

  /** TODO: connect to API — GET /analyses/{id}/log */
  async getLog(_id: string): Promise<LogEntry[]> {
    return delay(buildLog())
  },

  /**
   * TODO: connect to API — GET /analyses/{id}/export?format=xlsx|txt|csv
   * Mock: build a tab/comma-delimited file client-side from the results so the
   * export button + toast are exercisable. (xlsx served as a .txt stand-in.)
   */
  async exportResults(_id: string, format: ExportFormat): Promise<Blob> {
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
    await delay(undefined, 300)
    return new Blob([content], {
      type: format === 'csv' ? 'text/csv' : 'text/plain',
    })
  },
}
