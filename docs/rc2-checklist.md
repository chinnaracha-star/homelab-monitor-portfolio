# Release candidate checklist — RC2

Version: **1.0.0-rc2**  
Date: 2026-09-21

## Baseline

- [ ] `git status` reviewed; no secrets staged
- [ ] Version strings are `1.0.0-rc2` (pyproject, API, dashboard)
- [ ] `PROJECT_STATUS.md` and `CHANGELOG.md` match this tree
- [ ] Known limitations updated (SQLite backup exists; queue still in-memory)

## Quality gates

- [ ] `ruff check .` and `ruff format --check .`
- [ ] `pytest`
- [ ] `npm test` and `npm run build` in `dashboard/`
- [ ] `docker compose config`

## Operations

- [ ] `.env` has bootstrap admin password (production)
- [ ] `HOMELAB_BACKUP_ENABLED=true` and backup path on `homelab-data`
- [ ] One gzip backup verified (integrity PASS)
- [ ] Restore steps in `docs/restore.md` understood by the operator
- [ ] Telegram token/chat ID only if delivery is required
- [ ] Images rebuilt so 11.1–11.5 code is what Compose runs

## Sign-off

- [ ] No commit until the operator requests it
- [ ] Tag `v1.0.0-rc2` only after commit
