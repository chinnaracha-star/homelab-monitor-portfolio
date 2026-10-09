# Architecture freeze

**Product:** HomeLab Monitor  
**Version:** 1.0.0-rc3  
**Sprint:** 12.7  
**Status:** Architecture frozen for Phase 12. Phase 13 (Enterprise) is not started.

This freeze documents the platform as implemented after Sprints 12.1–12.6. It is not a redesign. The status line above is the Sprint 12.7 snapshot. Later work follows [RFC-0001](rfc/RFC-0001-architecture-governance.md). [RFC-0002](rfc/RFC-0002-job-engine-execution-wrapper.md) is implemented: Phase 13.12 owns background-task start and stop through `JobExecutionWrapper` and does not change the frozen contracts. [RFC-0003](rfc/RFC-0003-backup-clock-ownership.md) is implemented: Phase 13.13 splits the backup wait into `run_backup_clock` inside the existing `sqlite_backup` lifecycle and does not change the frozen contracts. [RFC-0004](rfc/RFC-0004-report-clock-ownership.md) is implemented: Phase 13.14 splits the report wait into `run_report_clock` inside the existing `telegram_reports` lifecycle and does not change the frozen contracts. [RFC-0005](rfc/RFC-0005-photo-watcher-interval-ownership.md) is implemented: Phase 13.15 keeps `photo_watcher` and `run_photo_watcher` as the job/lifecycle, while internal `run_photo_watcher_interval` performs one scan/flush, dynamic sleep, and return. The first scan remains immediate, registry/factories remain six, and frozen baseline and notification boundaries do not change.

## Frozen contracts

Do not change without an explicit Phase 13 RFC:

- REST shapes for existing routes (especially `GET /api/v1/agents` agent summaries)
- Agent protocol (`POST /api/v1/agents/register`, `/api/v1/agent/check-ins`, `/api/v1/agent/reports`) at protocol version `0.1.0`
- Dashboard JWT + RBAC roles `admin` | `operator` | `viewer`
- SQLite as the system of record (WAL, `PRAGMA foreign_keys=ON`)
- In-process plugin adapters (no second runtime)

## Additive surface (Phase 12)

These routes are additive and remain read-mostly except plugin lifecycle and operations:

- `/api/v1/plugins`
- `/api/v1/assistant/briefing`
- `/api/v1/knowledge` and `/export`
- `/api/v1/system/topology`
- `/api/v1/operations`

## Freeze rules

1. No new business features in this sprint (satisfied).
2. No new dashboard pages or production plugins in this sprint (satisfied).
3. Documentation in this freeze set is authoritative for architecture intent.
4. Technical debt listed in [technical-debt.md](technical-debt.md) is **not** auto-fixed.

## Related freeze docs

| Doc | Topic |
| --- | --- |
| [platform-architecture.md](platform-architecture.md) | Layers and diagrams |
| [module-map.md](module-map.md) | Python and dashboard modules |
| [api-catalog.md](api-catalog.md) | REST catalog |
| [database.md](database.md) | SQLite ER and JSON usage |
| [plugin-architecture.md](plugin-architecture.md) | Plugin manager |
| [event-flow.md](event-flow.md) | Events, knowledge, AI |
| [security-review.md](security-review.md) | JWT, secrets, export |
| [performance-review.md](performance-review.md) | Jobs, SQLite, scans |
| [repository-health.md](repository-health.md) | Repo structure |
| [technical-debt.md](technical-debt.md) | Debt register |
