import { afterEach, describe, expect, it, vi } from 'vitest'

import { REDACTED, createLogger, isSensitiveKey, redact } from './logger'

describe('isSensitiveKey', () => {
  it.each([
    'Authorization',
    'authorization',
    'Cookie',
    'Set-Cookie',
    'password',
    'user_password',
    'api_key',
    'X-API-Key',
    'access_token',
    'refresh_token',
    'session_id',
  ])('flags %s as sensitive', (key) => {
    expect(isSensitiveKey(key)).toBe(true)
  })

  it.each(['method', 'path', 'status', 'durationMs', 'requestId'])(
    'leaves %s alone',
    (key) => {
      expect(isSensitiveKey(key)).toBe(false)
    },
  )
})

describe('redact', () => {
  it('masks sensitive values recursively without mutating the input', () => {
    const input = {
      method: 'POST',
      headers: {
        Authorization: 'Bearer secret',
        Cookie: 'session=abc',
        'Content-Type': 'application/json',
      },
      items: [{ token: 't0p' }, { safe: 'ok' }],
    }
    const out = redact(input) as typeof input

    expect(out.method).toBe('POST')
    expect(out.headers.Authorization).toBe(REDACTED)
    expect(out.headers.Cookie).toBe(REDACTED)
    expect(out.headers['Content-Type']).toBe('application/json')
    expect(out.items[0].token).toBe(REDACTED)
    expect(out.items[1].safe).toBe('ok')
    // input untouched
    expect(input.headers.Authorization).toBe('Bearer secret')
  })

  it('redacts Headers objects', () => {
    const h = new Headers({ Authorization: 'Bearer x', 'X-Ok': 'yes' })
    const out = redact(h) as Record<string, string>
    expect(out['authorization']).toBe(REDACTED)
    expect(out['x-ok']).toBe('yes')
  })
})

describe('level gating', () => {
  afterEach(() => vi.restoreAllMocks())

  it('suppresses lines below the configured level', () => {
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {})
    const log = createLogger('warn')

    log.info('should be dropped')
    log.warn('should print')

    expect(infoSpy).not.toHaveBeenCalled()
    expect(warnSpy).toHaveBeenCalledTimes(1)
  })

  it('silent drops everything', () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    createLogger('silent').error('nope')
    expect(errSpy).not.toHaveBeenCalled()
  })

  it('emits a structured record and redacts fields', () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    createLogger('debug').error('api.response', {
      status: 500,
      authorization: 'Bearer nope',
    })
    expect(errSpy).toHaveBeenCalledTimes(1)
    const record = JSON.parse(errSpy.mock.calls[0][0] as string)
    expect(record.level).toBe('error')
    expect(record.msg).toBe('api.response')
    expect(record.status).toBe(500)
    expect(record.authorization).toBe(REDACTED)
    expect(record.ts).toBeTruthy()
  })

  it('child loggers carry base fields', () => {
    const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {})
    createLogger('debug').child({ requestId: 'rid-1' }).info('hi')
    const record = JSON.parse(infoSpy.mock.calls[0][0] as string)
    expect(record.requestId).toBe('rid-1')
  })
})
