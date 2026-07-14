/** Display formatters. Kept pure and framework-free for easy unit testing. */

/** Flux values: compact but precise. Uses exponent for very small magnitudes. */
export function formatFlux(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  const abs = Math.abs(value)
  if (abs !== 0 && abs < 0.001) return value.toExponential(2)
  if (abs < 1) return value.toFixed(4)
  if (abs < 1000) return value.toFixed(3)
  return value.toLocaleString('en-US', { maximumFractionDigits: 1 })
}

/** R²: three decimals, or an em dash when absent. */
export function formatR2(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toFixed(3)
}

export function formatNumber(
  value: number | null | undefined,
  digits = 1,
): string {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

/** "1004.2 hPa" or an em dash. */
export function formatPressure(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${value.toFixed(1)} hPa`
}

export function formatTemperature(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${value.toFixed(1)} °C`
}

/** Signed seconds offset: "+5 s", "0 s", "−3 s". */
export function formatOffset(seconds: number): string {
  const sign = seconds > 0 ? '+' : seconds < 0 ? '−' : ''
  return `${sign}${Math.abs(seconds)} s`
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** ISO date -> "2 Jul 2026". */
export function formatDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

/** ISO datetime -> "2 Jul 2026, 09:12". */
export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
