# Technical debt register (Sprint 12.7)

No fixes were applied in this sprint except documentation.

## Critical

None for single-tenant homelab operation.

## High

| ID | Item | Notes |
| --- | --- | --- |
| H1 | Plugin lifecycle vs workers | Stop/Unload is cosmetic; photo/backup/telegram tasks continue |
| H2 | GET `/system/health` writes `ops_snapshots` | Assistant and topology trigger writes; poll amplification |
| H3 | Unbounded JSON history | `metric_reports.payload` and `ops_snapshots` lack purge |
| H4 | Knowledge/CSV visible to viewers | Operational filenames and alert text leave the admin circle |

## Medium

| ID | Item |
| --- | --- |
| M1 | Dual notification UIs (`/notifications` and `/monitoring/notifications`) |
| M2 | Overlapping analytics/trends/capacity/insights/predictions APIs |
| M3 | Large files: `schemas.py` (1262), `types/dashboard.ts` (1102), `telegram_reports.py` (791), `photo_watcher.py` (734), `production_health.py` (667) |
| M4 | No `React.lazy` route splitting |
| M5 | Telegram implementation split (`telegram.py`, `notifications/telegram.py`, `photo_telegram.py`, `telegram_reports.py`) |
| M6 | Operations history JSON off SQLite |
| M7 | Tests `create_all` vs Alembic (drift risk) |
| M8 | Naive/aware datetime mix in historical rows |
| M9 | Unsigned plugin JSON |
| M10 | `.env.example` bootstrap password filled |

## Low

| ID | Item |
| --- | --- |
| L1 | `ConnectionLost` vs `RealtimeDisconnectedBanner` similar UX |
| L2 | Developer Phase percent tuple manually maintained |
| L3 | PWA widget metadata is declarative only (not a native widget) |
| L4 | Sample plugins sit in-tree (`examples/`) |
| L5 | Duplicate freeze vs operator docs |
| L6 | `ruff format --check .` may fail on files never formatted as a batch |

## Dead / unused (review)

- No unused router modules found.
- `ForbiddenPage` is used by `PermissionRoute`.
- Discord/Slack/email senders exist but are not the live alert path (documented limitation, not dead code).

## Circular dependencies

No Python import cycle was required for startup. Plugin manager imports photo watcher and sqlite backup; those do not import plugin manager.

## Architecture violations

1. Lifecycle pretends to own runtimes it does not own (H1).  
2. Read APIs that persist (H2).  
3. Knowledge “platform” reads JSON files the ORM does not know (M6).
