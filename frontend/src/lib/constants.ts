/**
 * App-wide constants. Values marked (assumption) come from the project brief's
 * open questions and are surfaced here rather than hard-coded silently, so they
 * are easy to change once confirmed with the researcher.
 */

/** Chamber defaults, pre-filled on the Upload screen. (assumption — confirm) */
export const DEFAULT_CHAMBER_AREA_M2 = 0.0625
export const DEFAULT_CHAMBER_VOLUME_L = 15.625
export const DEFAULT_TIME_OFFSET_S = 0

/** R² below this is flagged "low R²". (assumption — confirm, brief default 0.80) */
export const LOW_R2_THRESHOLD = 0.8

/** Max upload size per file, from the brief (~50 MB). */
export const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

export const STEPS = ['Upload', 'Confirm', 'Results'] as const
export type StepName = (typeof STEPS)[number]

/** Accepted file types per Upload dropzone. */
export const FILE_ACCEPT = {
  concentration: '.txt',
  notes: '.docx,.xlsx,.csv,.txt,.tsv',
  temperature: '.xlsx,.csv,.txt',
  pressure: '', // format varies — accept anything
} as const

/**
 * The full unit ladder, in display order, keyed to FluxLadder fields.
 * label is what the user sees; short units use middots to avoid ambiguity.
 */
export const UNIT_LADDER: { key: string; label: string }[] = [
  { key: 'umol_m2_s', label: 'µmol · m⁻² · s⁻¹' },
  { key: 'umol_m2_h', label: 'µmol · m⁻² · h⁻¹' },
  { key: 'mol_m2_h', label: 'mol · m⁻² · h⁻¹' },
  { key: 'gC_m2_day', label: 'g C · m⁻² · day⁻¹' },
  { key: 'kg_m2_h', label: 'kg · m⁻² · h⁻¹' },
  { key: 'kg_ha_h', label: 'kg · ha⁻¹ · h⁻¹' },
  { key: 'kg_ha_day', label: 'kg · ha⁻¹ · day⁻¹' },
  { key: 'kg_ha_year', label: 'kg · ha⁻¹ · year⁻¹' },
  { key: 'Mg_ha_year', label: 'Mg · ha⁻¹ · year⁻¹' },
  { key: 'Mg_ha_year_co2equiv', label: 'Mg · ha⁻¹ · year⁻¹ (CO₂-eq)' },
]

/** Data-viz colours (mirror the CSS vars; Plotly needs literal values). */
export const VIZ = {
  co2: '#0f766e',
  ch4: '#92400e',
  muted: '#94a3b8',
} as const

export const EXPORT_FORMATS: {
  format: 'xlsx' | 'txt' | 'csv'
  label: string
}[] = [
  { format: 'xlsx', label: 'Excel (.xlsx)' },
  { format: 'txt', label: 'Tab-delimited (.txt)' },
  { format: 'csv', label: 'CSV (.csv)' }, // (assumption — confirm before building)
]
