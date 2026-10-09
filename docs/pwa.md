# Progressive Web App

HomeLab Monitor installs as a browser PWA. There is no Electron, Capacitor, or
native wrapper. The existing React + Vite dashboard, REST API, JWT login, and
SQLite backend stay the same.

```text
Browser
    │
    ▼
Service Worker
    │
    ▼
React + Vite
    │
    ▼
REST API
    │
    ▼
SQLite
```

## Installation

Build the dashboard (`npm run build` in `dashboard/`) so Vite PWA emits
`manifest.webmanifest` and `sw.js`. Serve the site over HTTPS (Tailscale Serve
or localhost). HTTP localhost is allowed for install in Chromium.

### Android

1. Open the dashboard in Chrome.
2. Use **Install app** in the browser menu, or **Install HomeLab Monitor** on
   Overview / Settings if the prompt is available.
3. The icon uses the HomeLab Monitor mark. The app opens in standalone mode.

### Windows

1. Open the dashboard in Chrome or Edge.
2. Use the install icon in the address bar, or **Install HomeLab Monitor**.
3. The app appears in the Start menu.

### Desktop Chrome

Same as Windows. After install, `display: standalone` hides browser chrome.

### Edge

Edge uses the same Chromium install flow. **Apps** > HomeLab Monitor.

### Safari limitations

Safari on iOS/macOS does not implement `beforeinstallprompt`. Use Share >
**Add to Home Screen**. The in-app Install button stays hidden until a
Chromium prompt exists. Service worker support is more limited; offline cache
may be colder than on Chrome.

## Offline behavior

Static assets (HTML, CSS, JS, icons, fonts, images) use **cache-first** after
the first visit.

`GET /api/*` uses **network-only** (Workbox default method is GET).

Mutating `/api/*` and `/ws/*` (`POST`, `PUT`, `PATCH`, `DELETE`) are registered explicitly and replayed with a buffered body. Android Chrome does not fall back to the network when a controlling service worker leaves those methods unmatched — Axios then shows **Network Error** and the API never sees `POST /api/v1/auth/login`.

The worker calls `skipWaiting()` and `clientsClaim()`. The catch handler must not synthesize `Response.error()` for `/api` or `/ws`.

When offline, Overview shows **Offline**, **Last Updated**, and **Cached Data**.
Mission Control shows **Offline Mode**. JWT tokens stay in `localStorage`; they
are not stored in the Cache API.

## Update flow

A new deploy updates `sw.js`. The waiting worker sets **Update Available**.

- **Reload** applies the waiting worker.
- **Dismiss** hides the banner. The page is not force-refreshed.

Settings → Application → **Check for Update** calls `registration.update()`.

## Cache strategy

| Resource | Strategy |
| --- | --- |
| Precached build assets | Cache first (Workbox precache) |
| Images, fonts, extra scripts | Cache first |
| API GET | Network only |
| Auth and mutations | Network pass-through, never CacheFirst |

**Clear Cache** in Settings deletes Cache Storage entries only. It does not
log you out.

## Troubleshooting

- **No install button:** Chromium only shows `beforeinstallprompt` after
  engagement, HTTPS, a valid manifest, and a registered service worker. Safari
  never fires that event.
- **Install works but offline is blank:** Visit the dashboard online once so
  the shell and a GET snapshot can be cached.
- **Stale UI after deploy:** Use **Update Available → Reload** or **Check for
  Update**. `sw.js` is served with `Cache-Control: no-cache`.
- **Auth failed while offline:** Expected. Login is network-only.
- **Icons missing:** Confirm `/icons/icon-192.png` and `icon-512.png` are in
  the dashboard `public/` tree and the Docker image rebuild copied `dist`.
