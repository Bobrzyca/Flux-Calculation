import { describe, expect, it } from 'vitest'
import {
  formatFlux,
  formatR2,
  formatOffset,
  formatPressure,
  formatTemperature,
  formatBytes,
  formatDate,
} from './format'

describe('formatFlux', () => {
  it('shows an em dash for null/NaN', () => {
    expect(formatFlux(null)).toBe('—')
    expect(formatFlux(undefined)).toBe('—')
    expect(formatFlux(NaN)).toBe('—')
  })
  it('uses exponent for very small magnitudes', () => {
    expect(formatFlux(0.00004)).toBe('4.00e-5')
  })
  it('uses fixed decimals for sub-1 values', () => {
    expect(formatFlux(0.812)).toBe('0.8120')
  })
  it('formats mid-range with three decimals', () => {
    expect(formatFlux(1.83456)).toBe('1.835')
  })
})

describe('formatR2', () => {
  it('renders three decimals', () => {
    expect(formatR2(0.9)).toBe('0.900')
    expect(formatR2(0.812)).toBe('0.812')
  })
  it('handles missing values', () => {
    expect(formatR2(null)).toBe('—')
  })
})

describe('formatOffset', () => {
  it('signs positive, negative and zero offsets', () => {
    expect(formatOffset(5)).toBe('+5 s')
    expect(formatOffset(-3)).toBe('−3 s')
    expect(formatOffset(0)).toBe('0 s')
  })
})

describe('unit-suffixed formatters', () => {
  it('formats pressure and temperature with units', () => {
    expect(formatPressure(1004.23)).toBe('1004.2 hPa')
    expect(formatTemperature(21.44)).toBe('21.4 °C')
    expect(formatPressure(null)).toBe('—')
  })
  it('formats byte sizes', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2048)).toBe('2 KB')
    expect(formatBytes(3 * 1024 * 1024)).toBe('3.0 MB')
  })
})

describe('formatDate', () => {
  it('formats an ISO date', () => {
    expect(formatDate('2026-07-02')).toBe('2 Jul 2026')
  })
  it('returns the input when unparseable', () => {
    expect(formatDate('not-a-date')).toBe('not-a-date')
  })
})
