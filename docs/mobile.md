# Mobile experience

The dashboard remains a Vite PWA (`injectManifest`, `src/sw.ts`). No API or backend redesign.

## Install UX

- `beforeinstallprompt` still drives **Install HomeLab Monitor**.
- Manifest version is `1.0.0-rc3`.
- Shortcuts: Overview, Alerts, Photo Monitor, Backup (Chrome / Edge / Android long-press).
- Widget metadata: `widgets[]` with tag `homelab-status` (home-screen widget hint; not a native Android widget APK).

## Offline and sync

- `/api` and `/ws` stay `NetworkOnly`.
- Navigation fallback is `/offline.html`.
- Service worker registers Background Sync tag `homelab-refresh` and Periodic Sync tag `homelab-health` when the browser allows it.

## Touch

- Nav, logout, and plugin actions keep 2.75rem minimum targets.
- Mobile quick actions: Overview, Alerts, Photos, Backup.
- Pull down at the top of `main` to dispatch `homelab-pull-refresh` (reloads live polls).

## Verification targets

Android Chrome, desktop Chrome, and Edge: install from the address bar or Install button, then confirm shortcuts and standalone display-mode.
