# Capability matrix

**Sprint:** 13.1  
**Status:** Documentation only. This file does not enable or disable any subsystem.

Marks:

- **Core** — required for the product to run
- **Stable** — shipped and covered by the current contracts
- **Experimental** — present, but lifecycle or scope is still thin
- **Planned** — named for Phase 13, not a running product surface

## Core

| Subsystem | Mark | Where it lives |
| --- | --- | --- |
| Agent | Core | `agent/`, `POST /api/v1/agents/register`, check-ins, reports. Protocol `0.1.0` |
| Dashboard | Core | `dashboard/`, JWT session, RBAC |
| Authentication | Core | `api/src/homelab_monitor/auth/` |
| Health | Core | `GET /health` plus production health under `/api/v1/system` |

## Platform

| Subsystem | Mark | Where it lives |
| --- | --- | --- |
| Telegram | Stable | Alerts, photo messages, and scheduled reports. Several modules call the bot |
| Photo Monitor | Stable | `photo_watcher.py`, `photo_events`, baseline file |
| Knowledge | Experimental | `GET /api/v1/knowledge` and CSV export. Read model over existing tables |
| Assistant | Experimental | `GET /api/v1/assistant/briefing`. Local heuristic, no external model |
| Plugins | Experimental | In-process adapters in `plugins/` and `plugin_manager.py`. Stop does not stop workers |
| Topology | Experimental | `GET /api/v1/system/topology` |

## Enterprise

| Subsystem | Mark | Notes |
| --- | --- | --- |
| Audit | Planned | No audit log beyond HTTP request logs and notification rows |
| Backup | Stable | SQLite gzip scheduler is running. The Backup page connector is a separate read-only status path |
| Event Bus | Planned | In-process dashboard hub only. No durable bus |
| Scheduler | Stable | One asyncio loop starts the workers in `operations.factories`. There is no shared scheduler service |
| Public API | Planned | The dashboard API is the operator API. No separate public API |
| Multi Node | Planned | One API, one SQLite file, one agent host in the current deployment |
