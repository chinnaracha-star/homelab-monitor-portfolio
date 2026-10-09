import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { login } from './api'

describe('login client', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ access_token: 'jwt', token_type: 'bearer', expires_in: 3600 }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('POSTs credentials to /auth/login with fetch (never a cached GET)', async () => {
    await login('admin', 'secret')
    expect(fetch).toHaveBeenCalledTimes(1)
    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/v1/auth/login')
    expect(init.method).toBe('POST')
    expect(init.cache).toBe('no-store')
    expect(init.body).toBe(JSON.stringify({ username: 'admin', password: 'secret' }))
  })
})
