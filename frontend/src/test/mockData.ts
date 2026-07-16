/**
 * In-memory mock fixtures. Everything the UI renders this phase comes from here.
 * Data is generated deterministically (seeded RNG) so tests and the visible plot
 * are stable across reloads. Replace this module with real API calls later; the
 * shapes match src/api/types.ts exactly.
 */
import type {
  Analysis,
  AnalysisSummary,
  GasDetail,
  GasPoint,
  LogEntry,
  NoteRow,
  ParsedNotes,
  ResultsPayload,
  SpotDetail,
  SpotResult,
} from '@/api/types'
import { LOW_R2_THRESHOLD } from '@/lib/constants'

/** Deterministic PRNG (mulberry32) so mock points don't reshuffle each render. */
function makeRng(seed: number) {
  let a = seed
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** Compact spec for one measurement spot; details are derived from it. */
interface SpotSpec {
  nr: number
  start: string
  stop: string
  gps: string
  light_dark: 'light' | 'dark'
  location: string
  co2Slope: number // ppm/s
  ch4Slope: number // ppb/s
  r2co2: number
  r2ch4: number
  temp: number
  pressure: number
  droppedNan?: number
  skip?: string // skip reason -> skipped spot
}

const SPOT_SPECS: SpotSpec[] = [
  {
    nr: 1,
    start: '09:38:00',
    stop: '09:44:30',
    gps: '52.3012, 20.7891',
    light_dark: 'light',
    location: 'dam edge',
    co2Slope: 0.118,
    ch4Slope: 4.2,
    r2co2: 0.997,
    r2ch4: 0.981,
    temp: 21.4,
    pressure: 1004.2,
  },
  {
    nr: 2,
    start: '09:46:00',
    stop: '09:52:30',
    gps: '52.3012, 20.7891',
    light_dark: 'dark',
    location: 'dam edge',
    co2Slope: 0.201,
    ch4Slope: 6.8,
    r2co2: 0.994,
    r2ch4: 0.972,
    temp: 21.6,
    pressure: 1004.1,
  },
  {
    nr: 3,
    start: '09:58:00',
    stop: '10:04:30',
    gps: '52.3020, 20.7903',
    light_dark: 'light',
    location: 'reed bed',
    co2Slope: 0.087,
    ch4Slope: 12.1,
    r2co2: 0.989,
    r2ch4: 0.965,
    temp: 22.1,
    pressure: 1004.0,
  },
  {
    nr: 4,
    start: '10:07:00',
    stop: '10:13:30',
    gps: '52.3020, 20.7903',
    light_dark: 'dark',
    location: 'reed bed',
    co2Slope: 0.156,
    ch4Slope: 15.4,
    r2co2: 0.991,
    r2ch4: 0.958,
    temp: 22.4,
    pressure: 1003.9,
  },
  {
    nr: 5,
    start: '10:16:00',
    stop: '10:22:30',
    gps: '52.3031, 20.7920',
    light_dark: 'light',
    location: 'open water margin',
    co2Slope: 0.064,
    ch4Slope: 8.9,
    r2co2: 0.985,
    r2ch4: 0.942,
    temp: 22.8,
    pressure: 1003.8,
  },
  {
    nr: 6,
    start: '10:25:00',
    stop: '10:31:30',
    gps: '52.3031, 20.7920',
    light_dark: 'dark',
    location: 'open water margin',
    co2Slope: 0.132,
    ch4Slope: 11.2,
    r2co2: 0.988,
    r2ch4: 0.951,
    temp: 23.0,
    pressure: 1003.7,
  },
  {
    nr: 7,
    start: '10:34:00',
    stop: '10:40:30',
    gps: '52.3042, 20.7938',
    light_dark: 'light',
    location: 'sedge tussock',
    co2Slope: 0.098,
    ch4Slope: 38.6,
    r2co2: 0.996,
    r2ch4: 0.812,
    temp: 23.3,
    pressure: 1003.6,
    droppedNan: 12,
  },
  {
    nr: 8,
    start: '10:43:00',
    stop: '10:49:30',
    gps: '52.3042, 20.7938',
    light_dark: 'dark',
    location: 'sedge tussock',
    co2Slope: 0.178,
    ch4Slope: 42.1,
    r2co2: 0.993,
    r2ch4: 0.889,
    temp: 23.5,
    pressure: 1003.5,
  },
  {
    nr: 9,
    start: '10:52:00',
    stop: '10:58:30',
    gps: '52.3055, 20.7951',
    light_dark: 'light',
    location: 'alder carr',
    co2Slope: 0.045,
    ch4Slope: 2.1,
    r2co2: 0.978,
    r2ch4: 0.734,
    temp: 23.1,
    pressure: 1003.5,
    droppedNan: 3,
  },
  {
    nr: 10,
    start: '11:01:00',
    stop: '11:07:30',
    gps: '52.3055, 20.7951',
    light_dark: 'dark',
    location: 'alder carr',
    co2Slope: 0.121,
    ch4Slope: 3.8,
    r2co2: 0.986,
    r2ch4: 0.901,
    temp: 23.4,
    pressure: 1003.4,
  },
  {
    nr: 11,
    start: '11:10:00',
    stop: '11:16:30',
    gps: '52.3068, 20.7969',
    light_dark: 'light',
    location: 'peat hollow',
    co2Slope: 0.073,
    ch4Slope: 21.5,
    r2co2: 0.992,
    r2ch4: 0.947,
    temp: 23.9,
    pressure: 1003.3,
  },
  {
    nr: 12,
    start: '11:19:00',
    stop: '11:25:30',
    gps: '52.3068, 20.7969',
    light_dark: 'dark',
    location: 'peat hollow',
    co2Slope: 0.149,
    ch4Slope: 25.9,
    r2co2: 0.99,
    r2ch4: 0.938,
    temp: 24.2,
    pressure: 1003.2,
  },
  {
    nr: 13,
    start: '11:28:00',
    stop: '11:34:30',
    gps: '',
    light_dark: 'light',
    location: 'unmarked',
    co2Slope: 0.061,
    ch4Slope: 5.4,
    r2co2: 0.981,
    r2ch4: 0.823,
    temp: 24.0,
    pressure: 1003.2,
  },
  {
    nr: 14,
    start: '13:33:00',
    stop: '13:27:00',
    gps: '52.3081, 20.7988',
    light_dark: 'dark',
    location: 'ditch',
    co2Slope: 0,
    ch4Slope: 0,
    r2co2: 0,
    r2ch4: 0,
    temp: 24.5,
    pressure: 1003.0,
    skip: 'stop 13:27 is before start 13:33 (time notes row 14)',
  },
  {
    nr: 15,
    start: '13:40:00',
    stop: '13:46:30',
    gps: '52.3094, 20.8001',
    light_dark: 'light',
    location: 'willow scrub',
    co2Slope: 0.055,
    ch4Slope: 3.1,
    r2co2: 0.983,
    r2ch4: 0.856,
    temp: 25.1,
    pressure: 1002.9,
  },
  {
    nr: 16,
    start: '13:49:00',
    stop: '13:55:30',
    gps: '52.3094, 20.8001',
    light_dark: 'dark',
    location: 'willow scrub',
    co2Slope: 0.113,
    ch4Slope: 4.6,
    r2co2: 0.987,
    r2ch4: 0.912,
    temp: 25.4,
    pressure: 1002.8,
  },
  {
    nr: 17,
    start: '13:58:00',
    stop: '14:04:30',
    gps: '52.3107, 20.8019',
    light_dark: 'light',
    location: 'moss lawn',
    co2Slope: 0.038,
    ch4Slope: 1.4,
    r2co2: 0.975,
    r2ch4: 0.688,
    temp: 25.8,
    pressure: 1002.7,
    droppedNan: 5,
  },
  {
    nr: 18,
    start: '14:07:00',
    stop: '14:13:30',
    gps: '52.3107, 20.8019',
    light_dark: 'dark',
    location: 'moss lawn',
    co2Slope: 0.104,
    ch4Slope: 2.9,
    r2co2: 0.984,
    r2ch4: 0.877,
    temp: 26.0,
    pressure: 1002.6,
  },
]

/** Rough closed-chamber conversion for plausible mock flux magnitudes only. */
function slopeToFluxUmol(
  slopePpmPerS: number,
  area: number,
  volumeL: number,
  tempC: number,
  pressureHpa: number,
): number {
  const volM3 = volumeL / 1000
  const R = 8.314
  const T = tempC + 273.15
  const P = pressureHpa * 100
  // n = PV/RT (mol of air); flux = slope[ppm/s]*1e-6 * n / area -> µmol/m²/s
  const molAir = (P * volM3) / (R * T)
  return (slopePpmPerS * 1e-6 * molAir * 1e6) / area
}

const AREA = 0.0625
const VOLUME = 15.625

function ladderFrom(fluxUmolM2S: number, co2Equiv = false) {
  const s = fluxUmolM2S
  const h = s * 3600
  const mol_m2_h = h / 1e6
  // crude but internally-consistent conversions for display
  const gC_m2_day = mol_m2_h * 24 * 12.011
  const kg_m2_h = mol_m2_h * 0.044
  const kg_ha_h = kg_m2_h * 10000
  return {
    umol_m2_s: round(s, 4),
    umol_m2_h: round(h, 1),
    mol_m2_h: round(mol_m2_h, 6),
    gC_m2_day: round(gC_m2_day, 3),
    kg_m2_h: round(kg_m2_h, 6),
    kg_ha_h: round(kg_ha_h, 3),
    kg_ha_day: round(kg_ha_h * 24, 2),
    kg_ha_year: round(kg_ha_h * 24 * 365, 0),
    Mg_ha_year: round((kg_ha_h * 24 * 365) / 1000, 2),
    Mg_ha_year_co2equiv: round(
      ((kg_ha_h * 24 * 365) / 1000) * (co2Equiv ? 27 : 1),
      2,
    ),
  }
}

function round(n: number, d: number) {
  const f = 10 ** d
  return Math.round(n * f) / f
}

/** Seconds since midnight for an "HH:MM:SS" string. */
function toSeconds(hms: string): number {
  const [h, m, s] = hms.split(':').map(Number)
  return h * 3600 + m * 60 + (s || 0)
}

function co2Flux(spec: SpotSpec): number {
  return slopeToFluxUmol(spec.co2Slope, AREA, VOLUME, spec.temp, spec.pressure)
}
function ch4Flux(spec: SpotSpec): number {
  // CH4 slope is ppb/s -> convert to ppm/s (÷1000) before flux math
  return slopeToFluxUmol(
    spec.ch4Slope / 1000,
    AREA,
    VOLUME,
    spec.temp,
    spec.pressure,
  )
}

export function buildResults(): ResultsPayload {
  const spots: SpotResult[] = SPOT_SPECS.map((spec) => {
    if (spec.skip) {
      return {
        nr: spec.nr,
        date: '2026-07-02',
        start: spec.start,
        stop: spec.stop,
        gps: spec.gps,
        light_dark: spec.light_dark,
        location: spec.location,
        co2_flux_umol_m2_s: null,
        ch4_flux_umol_m2_s: null,
        r2_co2: null,
        r2_ch4: null,
        temperature_used_c: null,
        temperature_min_c: null,
        temperature_max_c: null,
        pressure_used_hpa: null,
        time_offset_applied_s: 0,
        fit_offset_s: 0,
        n_points_co2: 0,
        n_points_ch4: 0,
        flags: [],
        skipped: true,
        skip_reason: spec.skip,
      }
    }
    const flags: SpotResult['flags'] = []
    if (spec.r2co2 < LOW_R2_THRESHOLD || spec.r2ch4 < LOW_R2_THRESHOLD)
      flags.push('low_r2')
    if (spec.droppedNan) flags.push('dropped_nan')
    if (spec.nr === 7) flags.push('anomalous')
    return {
      nr: spec.nr,
      date: '2026-07-02',
      start: spec.start,
      stop: spec.stop,
      gps: spec.gps,
      light_dark: spec.light_dark,
      location: spec.location,
      co2_flux_umol_m2_s: round(co2Flux(spec), 4),
      ch4_flux_umol_m2_s: round(ch4Flux(spec), 5),
      r2_co2: spec.r2co2,
      r2_ch4: spec.r2ch4,
      temperature_used_c: spec.temp,
      temperature_min_c: spec.temp !== null ? spec.temp - 0.4 : null,
      temperature_max_c: spec.temp !== null ? spec.temp + 0.4 : null,
      pressure_used_hpa: spec.pressure,
      time_offset_applied_s: 0,
      fit_offset_s: 0,
      n_points_co2: 300 - (spec.droppedNan ?? 0),
      n_points_ch4: 300 - (spec.droppedNan ?? 0),
      flags,
      skipped: false,
      skip_reason: null,
    }
  })

  return {
    quality_check: {
      available: true,
      summary:
        'Reviewed 18 spots. Spot 7 shows anomalous CH₄ flux (~4× the campaign median) and low CH₄ R². Spots 9 and 17 have low CH₄ R² and should be treated with caution.',
      flags: [
        {
          nr: 7,
          gps: '52.3042, 20.7938',
          gas: 'CH4',
          issue: 'CH₄ flux ~4× the campaign median; R² 0.81',
          severity: 'high',
        },
        {
          nr: 9,
          gps: '52.3055, 20.7951',
          gas: 'CH4',
          issue: 'CH₄ R² 0.73 — below 0.80 threshold',
          severity: 'medium',
        },
        {
          nr: 17,
          gps: '52.3107, 20.8019',
          gas: 'CH4',
          issue: 'CH₄ R² 0.69 — below 0.80 threshold',
          severity: 'medium',
        },
      ],
    },
    spots,
  }
}

/** Generate the concentration points + fit for one gas of one spot. */
function buildGasDetail(
  spec: SpotSpec,
  gas: 'CO2' | 'CH4',
  seed: number,
): GasDetail {
  const rng = makeRng(seed)
  const durationS = toSeconds(spec.stop) - toSeconds(spec.start)
  const totalPoints = Math.max(60, durationS) // 1 Hz
  const fitStart = 30
  const fitEnd = 30 + 300 // start+30s -> start+5min30s
  const slope = gas === 'CO2' ? spec.co2Slope : spec.ch4Slope / 1000
  const base = gas === 'CO2' ? 412 : 2.05 // ppm; CH4 shown in ppm here
  const r2 = gas === 'CO2' ? spec.r2co2 : spec.r2ch4
  const noise = (1 - r2) * (gas === 'CO2' ? 6 : 0.06)

  const points: GasPoint[] = []
  for (let t = 0; t < totalPoints; t++) {
    const inWindow = t >= fitStart && t < fitEnd
    const drift = t < fitStart ? -0.02 * (fitStart - t) : 0 // warm-up wobble
    const value = base + slope * t + drift + (rng() - 0.5) * 2 * noise
    points.push({
      t_s: t,
      value: round(value, gas === 'CO2' ? 2 : 4),
      in_window: inWindow,
    })
  }

  const nDropped = spec.droppedNan ?? 0
  const nPoints = Math.min(300, fitEnd - fitStart) - nDropped
  // Intercept reported at t = 0 s, so the plotted line is y = intercept + slope·t.
  const intercept = base

  return {
    unit: gas === 'CO2' ? 'ppm' : 'ppb',
    points,
    fit: {
      slope: round(slope, 6),
      intercept: round(intercept, 3),
      r2,
      n_points: nPoints,
      n_dropped_nan: nDropped,
      n_spikes: 0,
    },
    flux_ladder: ladderFrom(
      gas === 'CO2' ? co2Flux(spec) : ch4Flux(spec),
      gas === 'CH4',
    ),
  }
}

export function buildSpotDetail(nr: number): SpotDetail | null {
  const spec = SPOT_SPECS.find((s) => s.nr === nr)
  if (!spec || spec.skip) return null
  const flags: SpotDetail['flags'] = []
  if (spec.r2co2 < LOW_R2_THRESHOLD || spec.r2ch4 < LOW_R2_THRESHOLD)
    flags.push('low_r2')
  if (spec.droppedNan) flags.push('dropped_nan')
  if (spec.nr === 7) flags.push('anomalous')
  return {
    nr: spec.nr,
    gps: spec.gps,
    light_dark: spec.light_dark,
    fit_window: { start: spec.start, stop: spec.stop },
    mode: 'auto',
    fit_offset_s: 30,
    fit_window_s: 300,
    window_shortened: false,
    flags,
    gases: {
      CO2: buildGasDetail(spec, 'CO2', nr * 101 + 1),
      CH4: buildGasDetail(spec, 'CH4', nr * 101 + 2),
    },
  }
}

export function buildNotes(): ParsedNotes {
  const rows: NoteRow[] = SPOT_SPECS.map((spec) => {
    const flags: NoteRow['flags'] = []
    if (!spec.gps) flags.push('gps_missing')
    if (toSeconds(spec.stop) <= toSeconds(spec.start))
      flags.push('stop_before_start')
    if (!spec.location || spec.location === 'unmarked')
      flags.push('location_missing')
    return {
      nr: spec.nr,
      start_time: spec.start,
      stop_time: spec.stop,
      gps: spec.gps,
      light_dark: spec.light_dark,
      location: spec.location,
      flags,
    }
  })
  return { parse_failed: false, rows }
}

export function buildLog(): LogEntry[] {
  return [
    {
      ts: '2026-07-02T15:00:01Z',
      severity: 'info',
      message:
        'Loaded LI-7810 export: 21,604 rows (2 header rows, DATA rows following).',
    },
    {
      ts: '2026-07-02T15:00:01Z',
      severity: 'info',
      message: 'Applied time-offset +0 s to 21,604 LI-7810 timestamps.',
    },
    {
      ts: '2026-07-02T15:00:01Z',
      severity: 'info',
      message:
        'Warm-up period detected: first 47 rows all nan (laser stabilising) — skipped silently.',
    },
    {
      ts: '2026-07-02T15:00:02Z',
      severity: 'info',
      message:
        'Parsed 18 time-note rows; matched temperature (nearest ≤30 s) and pressure (nearest-in-time) to each spot.',
    },
    {
      ts: '2026-07-02T15:00:02Z',
      severity: 'warning',
      message:
        'Spot 7: 12 of 300 readings dropped (nan) inside the fit window.',
    },
    {
      ts: '2026-07-02T15:00:02Z',
      severity: 'warning',
      message: 'Spot 9: 3 of 300 readings dropped (nan) inside the fit window.',
    },
    {
      ts: '2026-07-02T15:00:02Z',
      severity: 'warning',
      message:
        'Spot 13: GPS blank in field notes — flux computed, spot flagged "no GPS".',
    },
    {
      ts: '2026-07-02T15:00:03Z',
      severity: 'error',
      message:
        'Spot 14 skipped: stop 13:27 is before start 13:33 (time notes row 14).',
    },
    {
      ts: '2026-07-02T15:00:03Z',
      severity: 'warning',
      message:
        'Spot 17: 5 of 300 readings dropped (nan) inside the fit window.',
    },
    {
      ts: '2026-07-02T15:00:03Z',
      severity: 'info',
      message:
        'Fitted CO₂ and CH₄ slopes for 17 spots (linear, start+30 s → start+5 min 30 s). Flux computed across the unit ladder.',
    },
    {
      ts: '2026-07-02T15:00:04Z',
      severity: 'info',
      message:
        'Quality check returned: 3 spots flagged (1 anomalous, 2 low R²).',
    },
  ]
}

/** Seed list of saved analyses shown on Home. */
export const SEED_ANALYSES: Analysis[] = [
  {
    id: 'an_kampinos_0702',
    name: 'Kampinos — 2 July',
    work_date: '2026-07-02',
    spot_count: 18,
    status: 'complete',
    created_at: '2026-07-02T15:00:04Z',
    chamber_area_m2: 0.0625,
    chamber_volume_l: 15.625,
    time_offset_seconds: 0,
  },
  {
    id: 'an_biebrza_0620',
    name: 'Biebrza fen — 20 June',
    work_date: '2026-06-20',
    spot_count: 12,
    status: 'complete',
    created_at: '2026-06-20T17:22:10Z',
    chamber_area_m2: 0.0625,
    chamber_volume_l: 15.625,
    time_offset_seconds: -3,
  },
  {
    id: 'an_draft_0710',
    name: 'Wetland A — 10 July',
    work_date: '2026-07-10',
    spot_count: 0,
    status: 'draft',
    created_at: '2026-07-10T08:40:00Z',
    chamber_area_m2: 0.0625,
    chamber_volume_l: 15.625,
    time_offset_seconds: 0,
  },
]

export type { AnalysisSummary }

/** Minimal whole-campaign time series for the overview graph (tests only). */
export function buildTimeseries(): import('@/api/types').Timeseries {
  const base = 1782980000
  const mk = (nr: number, offset: number) => ({
    nr,
    light_dark: 'light' as const,
    points: Array.from({ length: 20 }, (_, i) => ({
      t_unix: base + offset + i,
      value: 400 + i * 0.1,
      in_window: i >= 5,
    })),
    line: [
      { t_unix: base + offset + 5, y: 400.5 },
      { t_unix: base + offset + 19, y: 401.9 },
    ],
  })
  return {
    co2: { unit: 'ppm', spots: [mk(1, 0), mk(2, 100)] },
    ch4: { unit: 'ppb', spots: [mk(1, 0), mk(2, 100)] },
  }
}
