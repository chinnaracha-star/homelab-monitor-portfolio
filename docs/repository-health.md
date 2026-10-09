# Repository health

## Layout

Python toolkit (API + agent) + Vite dashboard + Compose + `docs/` + `plugins/` + `tests/api`.

## Strengths

- Clear freeze of agent protocol and JWT RBAC
- Alembic chain 0001–0010
- Dashboard tests (170) plus API pytest
- Operator docs for backup, Telegram, PWA, RBAC
- Phase 12 adapters isolated in new modules

## Weaknesses

- `docs/` already had overlapping architecture, plugins, and performance notes; freeze set adds a second cluster of docs (intentional snapshot)
- Notifications, Telegram, and health are split across many similarly named modules
- Dashboard `App.tsx` imports every page eagerly
- `alembic.ini` default URL is local `./data/`; Compose uses volume path via env
- Global plugin registry is not multiprocess-safe (Compose runs one API replica)

## Hygiene

- `.venv/` gitignored
- `.env` gitignored
- Do not commit `.env`

## Duplicate documentation (non-blocking)

`docs/architecture.md` vs `docs/platform-architecture.md`; `docs/plugins.md` vs `docs/plugin-architecture.md`; `docs/performance.md` vs `docs/performance-review.md`. Freeze docs are the 12.7 snapshot; earlier docs remain operator-facing.
