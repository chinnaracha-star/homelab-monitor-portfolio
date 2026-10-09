# Performance review

## Database access

Every authenticated page poll hits REST. Production Health, Assistant, and Topology each call `ProductionHealthService.health`, which samples query latency and **inserts** an `ops_snapshots` performance row.

Agent ingest writes `metric_reports` (full JSON) plus `metric_history` plus possible alerts.

Knowledge Center runs six `LIMIT 100` queries per request.

## Background jobs (`operations.factories`)

| Task | Work |
| --- | --- |
| offline_monitor | agent last_seen vs threshold |
| infrastructure_monitor | QNAP/Docker/Immich HTTP |
| telegram_reports | scheduled Thai reports |
| notification_worker | queue drain to Telegram |
| photo_watcher | directory scan interval (default 5s) |
| sqlite_backup | 02:00 Asia/Bangkok gzip |

All share the API event loop / threads. Photo scan of large CIFS trees is the dominant CPU/IO risk.

## Telegram

Synchronous Bot API from worker and photo path. Failures enqueue retries. Button URLs must be the public dashboard origin (historical 400s when Docker internal URLs leaked).

## Docker interaction

Production Health lists containers when the socket is reachable. Operations can restart containers (blocking subprocess, 30s timeout).

## Cache

- PWA CacheFirst for static assets; NetworkOnly for `/api` and `/ws`
- In-process deques for API latency samples
- No Redis

## History tables

`metric_reports` and `ops_snapshots` grow without application-level purge (backup retention is for gzip copies, not live tables).

## Bottlenecks

1. Photo watcher full-tree scan interval  
2. SQLite writer lock (ingest + backup + health snapshot)  
3. Eager frontend bundle (no route lazy load)  
4. `schemas.py` / `types/dashboard.ts` size (dev compile, not runtime)  
5. Knowledge Python-side merge/sort  

## Scalability

The architecture is **single-node SQLite**. Horizontal API replicas would split plugin registry RAM, notification queues, and WAL writers. Enterprise scale needs an explicit store decision (out of freeze scope).
