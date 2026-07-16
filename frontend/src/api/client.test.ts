import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, REQUEST_ID_HEADER } from './client'
import type { CreateAnalysisInput } from './types'

function makeInput(overrides: Partial<CreateAnalysisInput> = {}) {
  const file = (name: string) => new File(['x'], name)
  const input: CreateAnalysisInput = {
    name: 'Test campaign',
    work_date: '2026-07-14',
    chamber_area_m2: 0.0625,
    chamber_volume_l: 15.625,
    time_offset_seconds: 0,
    files: {
      concentration: file('li7810.txt'),
      notes: file('notes.docx'),
      temperature: file('temp.xlsx'),
      pressure: file('pressure.csv'),
    },
    ...overrides,
  }
  return input
}

describe('api.listAnalyses', () => {
  it('returns the seed analyses newest-first', async () => {
    const list = await api.listAnalyses()
    expect(list.length).toBeGreaterThanOrEqual(3)
    // sorted by created_at desc
    for (let i = 1; i < list.length; i++) {
      expect(
        list[i - 1].created_at.localeCompare(list[i].created_at),
      ).toBeGreaterThanOrEqual(0)
    }
  })
})

describe('api.createAnalysis', () => {
  it('creates an analysis and adds it to the list', async () => {
    const before = await api.listAnalyses()
    const created = await api.createAnalysis(makeInput({ name: 'Fresh run' }))
    expect(created.name).toBe('Fresh run')
    expect(created.status).toBe('needs_review')
    const after = await api.listAnalyses()
    expect(after.length).toBe(before.length + 1)
  })

  it('rejects a duplicate-looking name with a field error', async () => {
    await expect(
      api.createAnalysis(makeInput({ name: 'dup campaign' })),
    ).rejects.toMatchObject({
      name: 'ApiError',
      code: 'duplicate_name',
      field: 'name',
    })
  })

  it('rejects a bad LI-7810 file with a concentration-field error', async () => {
    const input = makeInput()
    input.files.concentration = new File(['x'], 'bad-export.txt')
    await expect(api.createAnalysis(input)).rejects.toBeInstanceOf(ApiError)
    await expect(api.createAnalysis(input)).rejects.toHaveProperty(
      'field',
      'concentration',
    )
  })
})

describe('api.deleteAnalysis', () => {
  it('removes an analysis from the list', async () => {
    const created = await api.createAnalysis(makeInput({ name: 'To delete' }))
    await api.deleteAnalysis(created.id)
    const list = await api.listAnalyses()
    expect(list.find((a) => a.id === created.id)).toBeUndefined()
  })
})

describe('api.getResults', () => {
  beforeEach(() => {})
  it('returns 18 spots including one skipped and low-R² spots', async () => {
    const { spots, quality_check } = await api.getResults('an_kampinos_0702')
    expect(spots).toHaveLength(18)
    expect(spots.some((s) => s.skipped)).toBe(true)
    expect(spots.some((s) => s.flags.includes('low_r2'))).toBe(true)
    expect(quality_check.available).toBe(true)
  })
})

describe('api.exportResults', () => {
  it('produces a tab-delimited blob for txt', async () => {
    const blob = await api.exportResults('an_kampinos_0702', 'txt')
    const text = await blob.text()
    expect(text.split('\n')[0]).toContain('\t')
    expect(text).toContain('Nr')
  })
  it('produces a comma-delimited blob for csv', async () => {
    const blob = await api.exportResults('an_kampinos_0702', 'csv')
    const text = await blob.text()
    expect(text.split('\n')[0]).toContain(',')
  })
})

describe('correlation id', () => {
  function lastRequestId(): string | null {
    const mock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>
    const init = mock.mock.calls.at(-1)![1] as RequestInit
    return new Headers(init.headers).get(REQUEST_ID_HEADER)
  }

  it('attaches an X-Request-ID header to every request', async () => {
    await api.listAnalyses()
    const id = lastRequestId()
    expect(id).toBeTruthy()
    expect(id!.length).toBeGreaterThan(8)
  })

  it('uses a fresh id per request', async () => {
    await api.listAnalyses()
    const first = lastRequestId()
    await api.listAnalyses()
    const second = lastRequestId()
    expect(first).not.toBe(second)
  })

  it('sets the header on the direct-fetch getSpotDetail path too', async () => {
    await api.getSpotDetail('an_kampinos_0702', 1)
    expect(lastRequestId()).toBeTruthy()
  })
})
