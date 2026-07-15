/**
 * Domain types for the Flux Calculation UI.
 *
 * These mirror the data shapes in assignment/frontend.md "Backend touchpoints".
 * They are the contract the frontend builds against; every field is served by
 * the mock client today and is the shape to confirm with the backend later.
 */

export type AnalysisStatus = 'complete' | 'draft' | 'needs_review'

export interface AnalysisSummary {
  id: string
  name: string
  work_date: string // ISO date, e.g. "2026-07-02"
  spot_count: number
  status: AnalysisStatus
  created_at: string // ISO datetime
}

export interface ChamberConstants {
  chamber_area_m2: number
  chamber_volume_l: number
  time_offset_seconds: number
}

export interface Analysis extends AnalysisSummary, ChamberConstants {}

export type LightDark = 'light' | 'dark'

/** Machine-flags surfaced on a parsed-notes row. */
export type NoteFlag =
  'stop_before_start' | 'gps_missing' | 'unparseable_time' | 'location_missing'

export interface NoteRow {
  nr: number
  start_time: string // "HH:MM:SS"
  stop_time: string // "HH:MM:SS"
  gps: string
  light_dark: LightDark
  location: string
  flags: NoteFlag[]
}

export interface ParsedNotes {
  parse_failed: boolean
  rows: NoteRow[]
}

export type Gas = 'CO2' | 'CH4'

/** Per-spot warning flags shown on results + detail. */
export type SpotFlag =
  | 'low_r2'
  | 'short_window'
  | 'time_shifted'
  | 'no_pressure'
  | 'dropped_nan'
  | 'anomalous'

export interface SpotResult {
  nr: number
  date: string
  start: string
  stop: string
  gps: string
  light_dark: LightDark
  location: string
  co2_flux_umol_m2_s: number | null
  ch4_flux_umol_m2_s: number | null
  r2_co2: number | null
  r2_ch4: number | null
  temperature_used_c: number | null
  temperature_min_c: number | null
  temperature_max_c: number | null
  pressure_used_hpa: number | null
  time_offset_applied_s: number
  /** Seconds the fit window was shifted after the recorded start. */
  fit_offset_s: number
  n_points_co2: number
  n_points_ch4: number
  flags: SpotFlag[]
  skipped: boolean
  skip_reason: string | null
}

export type Severity = 'low' | 'medium' | 'high'

export interface QualityFlag {
  nr: number
  gps: string
  gas: Gas
  issue: string
  severity: Severity
}

export interface QualityCheck {
  available: boolean
  summary: string | null
  flags: QualityFlag[]
}

export interface ResultsPayload {
  quality_check: QualityCheck
  spots: SpotResult[]
}

/** The full unit ladder for one gas at one spot. */
export interface FluxLadder {
  umol_m2_s: number
  umol_m2_h: number
  mol_m2_h: number
  gC_m2_day: number
  kg_m2_h: number
  kg_ha_h: number
  kg_ha_day: number
  kg_ha_year: number
  Mg_ha_year: number
  Mg_ha_year_co2equiv: number
}

export interface GasPoint {
  t_s: number
  value: number
  in_window: boolean
}

export interface GasFit {
  slope: number
  intercept: number
  r2: number
  n_points: number
  n_dropped_nan: number
}

export interface GasDetail {
  unit: string // "ppm" | "ppb"
  points: GasPoint[]
  fit: GasFit
  flux_ladder: FluxLadder
}

export interface SpotDetail {
  nr: number
  gps: string
  light_dark: LightDark
  fit_window: { start: string; stop: string }
  flags: SpotFlag[]
  gases: Record<Gas, GasDetail>
}

/** Whole-campaign time series for the overview graph (absolute time axis). */
export interface TSPoint {
  t_unix: number
  value: number
  in_window: boolean
}

export interface TSSpot {
  nr: number
  light_dark: LightDark
  points: TSPoint[]
  line: { t_unix: number; y: number }[]
}

export interface TSGas {
  unit: string
  spots: TSSpot[]
}

export interface Timeseries {
  co2: TSGas
  ch4: TSGas
}

export type LogSeverity = 'info' | 'warning' | 'error'

export interface LogEntry {
  ts: string
  severity: LogSeverity
  message: string
}

export type ExportFormat = 'xlsx' | 'txt' | 'csv'

/** Payload for creating a new analysis (Upload screen). */
export interface CreateAnalysisInput {
  name: string
  work_date: string
  chamber_area_m2: number
  chamber_volume_l: number
  time_offset_seconds: number
  files: {
    concentration: File | null
    notes: File | null
    temperature: File | null
    pressure: File | null
  }
}
