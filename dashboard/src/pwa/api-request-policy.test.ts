import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it, vi } from 'vitest'
import {
  apiRuntimeStrategy,
  isApiOrSocketPath,
  MUTATING_HTTP_METHODS,
  mutatingApiBypassesRuntimeCache,
  passThroughToNetwork,
} from './api-request-policy'

const root = join(dirname(fileURLToPath(import.meta.url)), '../..')
const swSource = readFileSync(join(root, 'src/sw.ts'), 'utf8')

const API_SAMPLES = [
  '/api/v1/auth/login',
  '/api/v1/auth/me',
  '/api/v1/agents',
  '/api/v1/alerts/ack-1',
  '/api/v1/photos/settings',
  '/api/v1/notifications/settings',
  '/api/v1/plugins/telegram/lifecycle',
  '/ws/dashboard',
]

describe('mutating /api requests never use runtime cache', () => {
  it.each(MUTATING_HTTP_METHODS)('marks %s /api/* as network pass-through, not CacheFirst', (method) => {
    for (const pathname of API_SAMPLES) {
      expect(mutatingApiBypassesRuntimeCache(method, pathname)).toBe(true)
      expect(apiRuntimeStrategy(method, pathname)).toBe('network-pass-through')
    }
  })

  it('does not treat GET /api as a mutating cache bypass', () => {
    expect(mutatingApiBypassesRuntimeCache('GET', '/api/v1/auth/login')).toBe(false)
    expect(apiRuntimeStrategy('GET', '/api/v1/dashboard/overview')).toBe('network-only')
  })

  it('does not apply API pass-through to static assets', () => {
    expect(isApiOrSocketPath('/assets/index.js')).toBe(false)
    expect(apiRuntimeStrategy('GET', '/assets/index.js')).toBe('none')
    expect(mutatingApiBypassesRuntimeCache('POST', '/assets/index.js')).toBe(false)
  })
})

describe('POST /api/v1/auth/login always reaches the network', () => {
  it('uses network-pass-through and fetch()s the original Request first', async () => {
    expect(apiRuntimeStrategy('POST', '/api/v1/auth/login')).toBe('network-pass-through')
    const fetchImpl = vi.fn().mockResolvedValue(new Response('{"access_token":"t"}', { status: 200 }))
    const request = new Request('https://homelab.example/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'admin', password: 'secret' }),
    })
    const response = await passThroughToNetwork(request, fetchImpl)
    expect(response.status).toBe(200)
    expect(fetchImpl).toHaveBeenCalledTimes(1)
    expect(fetchImpl.mock.calls[0]?.[0]).toBe(request)
  })

  it('retries with a buffered body when the first fetch throws', async () => {
    const fetchImpl = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(new Response('{"ok":true}', { status: 200 }))
    const request = new Request('https://homelab.example/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'admin', password: 'secret' }),
    })
    const response = await passThroughToNetwork(request, fetchImpl)
    expect(response.status).toBe(200)
    expect(fetchImpl).toHaveBeenCalledTimes(2)
    const retryInit = fetchImpl.mock.calls[1]?.[1] as RequestInit
    expect(retryInit.method).toBe('POST')
    expect(retryInit.cache).toBe('no-store')
    expect(retryInit.mode).toBe('same-origin')
  })
})

describe('GET /api/* runtime strategy', () => {
  it('keeps GET /api on NetworkOnly, not CacheFirst', () => {
    expect(apiRuntimeStrategy('GET', '/api/v1/agents')).toBe('network-only')
    expect(apiRuntimeStrategy('HEAD', '/api/v1/system/health')).toBe('network-only')
    expect(swSource).toContain("cacheName: 'homelab-static'")
    expect(swSource).not.toContain('new NetworkOnly()')
    expect(swSource).not.toContain('event.respondWith')
  })
})

describe('service worker wiring', () => {
  it('claims clients and does not intercept /api fetch (Android POST login)', () => {
    expect(swSource).toContain('clientsClaim()')
    expect(swSource).toContain('self.skipWaiting()')
    expect(swSource).toContain("addEventListener('fetch'")
    expect(swSource).toContain('isApiOrSocketPath(url.pathname)')
    expect(swSource).toContain('return')
    expect(swSource).not.toContain('event.respondWith')
    expect(MUTATING_HTTP_METHODS).toEqual(['POST', 'PUT', 'PATCH', 'DELETE'])
  })
})

describe('offline mode', () => {
  it('still ships the offline document and uses it as the document catch handler', () => {
    const html = readFileSync(join(root, 'public/offline.html'), 'utf8')
    expect(html).toContain('<h1>HomeLab Monitor</h1>')
    expect(html).toContain('Server Offline')
    expect(html).toContain('/offline.css')
    expect(swSource).toContain("caches.match('/offline.html'")
    expect(swSource).toContain('denylist:')
    expect(swSource).toContain('/^\\/api\\//')
  })
})
