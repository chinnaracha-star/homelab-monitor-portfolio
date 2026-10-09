/// <reference lib="webworker" />
import { clientsClaim } from 'workbox-core'
import { CacheableResponsePlugin } from 'workbox-cacheable-response'
import { ExpirationPlugin } from 'workbox-expiration'
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching'
import { NavigationRoute, registerRoute, setCatchHandler } from 'workbox-routing'
import { CacheFirst } from 'workbox-strategies'
import { isApiOrSocketPath, passThroughToNetwork } from './pwa/api-request-policy'

declare let self: ServiceWorkerGlobalScope

self.skipWaiting()
clientsClaim()

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    void self.skipWaiting()
  }
})

/**
 * Never respondWith /api or /ws. Android Chrome fails SW-replayed POST bodies
 * (login → Axios/fetch "Network Error"). Default browser networking works.
 */
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)
  if (url.origin !== self.location.origin) {
    return
  }
  if (isApiOrSocketPath(url.pathname)) {
    return
  }
})

precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()

registerRoute(
  ({ request }) =>
    request.destination === 'style' ||
    request.destination === 'script' ||
    request.destination === 'worker' ||
    request.destination === 'font' ||
    request.destination === 'image',
  new CacheFirst({
    cacheName: 'homelab-static',
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({ maxEntries: 80, maxAgeSeconds: 60 * 60 * 24 * 30 }),
    ],
  }),
)

registerRoute(
  new NavigationRoute(createHandlerBoundToURL('/index.html'), {
    denylist: [/^\/api\//, /^\/health$/, /^\/ws\//, /^\/docs/, /^\/redoc/, /^\/offline\.html$/],
  }),
)

setCatchHandler(async ({ request }) => {
  const url = new URL(request.url)
  if (isApiOrSocketPath(url.pathname)) {
    return passThroughToNetwork(request)
  }
  if (request.destination === 'document') {
    const offline = await caches.match('/offline.html', { ignoreSearch: true })
    if (offline) {
      return offline
    }
  }
  return Response.error()
})

self.addEventListener('sync', (event) => {
  const syncEvent = event as ExtendableEvent & { tag?: string }
  if (syncEvent.tag === 'homelab-refresh') {
    syncEvent.waitUntil(Promise.resolve())
  }
})

self.addEventListener('periodicsync', (event) => {
  const syncEvent = event as ExtendableEvent & { tag?: string }
  if (syncEvent.tag === 'homelab-health') {
    syncEvent.waitUntil(Promise.resolve())
  }
})
