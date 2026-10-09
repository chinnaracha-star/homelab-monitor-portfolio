export const MUTATING_HTTP_METHODS = ['POST', 'PUT', 'PATCH', 'DELETE'] as const

export type MutatingHttpMethod = (typeof MUTATING_HTTP_METHODS)[number]

export type ApiRuntimeStrategy = 'network-only' | 'network-pass-through' | 'none'

export function isMutatingHttpMethod(method: string): method is MutatingHttpMethod {
  return (MUTATING_HTTP_METHODS as readonly string[]).includes(method.toUpperCase())
}

export function isApiOrSocketPath(pathname: string): boolean {
  return pathname.startsWith('/api/') || pathname.startsWith('/ws/')
}

/** Mutating /api and /ws requests must never be served from CacheFirst or precache. */
export function mutatingApiBypassesRuntimeCache(method: string, pathname: string): boolean {
  return isApiOrSocketPath(pathname) && isMutatingHttpMethod(method)
}

export function apiRuntimeStrategy(method: string, pathname: string): ApiRuntimeStrategy {
  if (!isApiOrSocketPath(pathname)) {
    return 'none'
  }
  if (isMutatingHttpMethod(method)) {
    return 'network-pass-through'
  }
  if (method.toUpperCase() === 'GET' || method.toUpperCase() === 'HEAD') {
    return 'network-only'
  }
  return 'network-pass-through'
}

const BLOCKED_HEADERS = new Set(['host', 'content-length', 'connection', 'keep-alive', 'transfer-encoding'])

export async function passThroughToNetwork(
  request: Request,
  fetchImpl: typeof fetch = fetch,
): Promise<Response> {
  try {
    return await fetchImpl(request)
  } catch {
    const headers = new Headers()
    request.headers.forEach((value, key) => {
      if (!BLOCKED_HEADERS.has(key.toLowerCase())) {
        headers.set(key, value)
      }
    })
    const init: RequestInit & { duplex?: string } = {
      method: request.method,
      headers,
      credentials: 'same-origin',
      cache: 'no-store',
      redirect: 'follow',
      mode: 'same-origin',
      duplex: 'half',
    }
    if (request.method !== 'GET' && request.method !== 'HEAD' && !request.bodyUsed) {
      init.body = await request.clone().arrayBuffer()
    }
    return fetchImpl(request.url, init)
  }
}
