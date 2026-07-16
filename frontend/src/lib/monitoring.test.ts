import { describe, expect, it } from 'vitest'

import { REDACTED } from './logger'
import { scrubEvent } from './monitoring'

describe('scrubEvent', () => {
  it('redacts request headers, cookies and body', () => {
    const event = {
      request: {
        headers: {
          Authorization: 'Bearer secret',
          'Content-Type': 'application/json',
        },
        cookies: { session_id: 'abc' },
        data: { password: 'hunter2', note: 'ok' },
        query_string: 'token=leak',
      },
    }
    const out = scrubEvent(structuredClone(event))
    const req = out.request as {
      headers: Record<string, unknown>
      cookies: Record<string, unknown>
      data: Record<string, unknown>
    }
    expect(req.headers.Authorization).toBe(REDACTED)
    expect(req.headers['Content-Type']).toBe('application/json')
    expect(req.cookies.session_id).toBe(REDACTED)
    expect(req.data.password).toBe(REDACTED)
    expect(req.data.note).toBe('ok')
    // Raw query string is dropped entirely.
    expect('query_string' in (out.request as object)).toBe(false)
  })

  it('redacts extra and drops user PII', () => {
    const out = scrubEvent({
      extra: { api_key: 'sk-live', count: 2 },
      user: { ip_address: '1.2.3.4' },
    })
    expect(out.extra?.api_key).toBe(REDACTED)
    expect(out.extra?.count).toBe(2)
    expect('user' in out).toBe(false)
  })
})
