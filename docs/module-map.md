# Module map

## API (`api/src/homelab_monitor`)

| Area | Modules |
| --- | --- |
| App | `main.py`, `settings.py`, `database.py`, `errors.py`, `logging.py` |
| Auth | `auth/tokens.py`, `auth/dependencies.py`, `auth/bootstrap.py`, `security.py` (agent tokens) |
| Agents | `routers/agents.py`, `control.py`, `agent_presence.py`, `history.py`, `alert_engine.py` |
| Dashboard REST | `routers/dashboard.py`, `groups.py`, `users.py`, `alert_rules.py` |
| Analytics family | `analytics.py`, `trends.py`, `capacity_planning.py`, `insights.py`, `predictions.py` |
| Notifications | `telegram.py`, `notifications/*`, `notification_worker.py`, `telegram_reports.py`, `photo_telegram.py` |
| Photos | `photo_watcher.py`, `photo_events.py`, `routers/photos.py` |
| Backup | `sqlite_backup.py`, `backup_status.py`, `routers` via dashboard backup |
| Ops / health | `production_health.py`, `performance.py`, `operations.py`, `runtime_control.py` |
| Phase 12 | `plugin_manager.py`, `assistant.py`, `knowledge.py`, `topology.py` |
| Realtime | `realtime/manager.py`, `routers/realtime.py` |
| Connectors | `connectors/{qnap,docker,immich,qumagie,backup,http}` |

Routers live under `routers/` and are included only from `main.create_app()`.

## Dashboard (`dashboard/src`)

| Area | Path |
| --- | --- |
| Routes | `App.tsx` (eager imports, no `React.lazy`) |
| Auth | `auth/*` JWT in `storage.ts`, RBAC `permissions.ts` |
| API client | `api/client.ts`, `api/dashboard.ts`, `api/users.ts` |
| Pages | `pages/*Page.tsx` |
| Layout | `components/Layout.tsx`, `Navbar`, `Sidebar` |
| PWA | `pwa/PwaProvider.tsx`, `manifest.ts`, `sw.ts` |
| Types | `types/dashboard.ts` (~1100 lines) |

## Plugins

Production adapters: `plugins/{core-system,telegram,photo-monitor,backup,analytics}/`.  
Samples (not loaded): `plugins/examples/{ups,weather,mqtt}/`.

## Agent

`agent/src/homelab_agent` — outbound HTTPS only, protocol `0.1.0`.

## Deploy

`Dockerfile.api`, `Dockerfile.dashboard`, `docker-compose.yml`, `deploy/docker/api-entrypoint.sh` (`alembic upgrade head`).

## Tests

`tests/api/` pytest; `dashboard` Vitest + Testing Library.
