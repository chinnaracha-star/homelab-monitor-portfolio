# Architecture principles

**Sprint:** 13.2

These principles apply to Phase 13 work after this plan. They do not change the running system by themselves.

1. **Backward compatibility first.** A change that alters current REST, agent protocol `0.1.0`, SQLite rows, JWT, RBAC, dashboard behavior, Telegram text, Photo Monitor delivery, or Plugin API v1 does not ship.
2. **Additive APIs only.** New fields and new routes are allowed when old clients still work. Removing or renaming a field needs an accepted RFC.
3. **One notification provider.** New Telegram sends go through the future notification facade. Existing callers move one at a time and keep today's message.
4. **One scheduler.** New periodic work registers with the future job engine. Until that engine exists, new loops are not added beside the six in `operations.factories`.
5. **RFC before architecture changes.** `docs/rfc/RFC-0001-architecture-governance.md` is the gate. Planning documents are not approval to implement.
6. **Regression before merge.** `ruff check`, `ruff format --check`, `pytest`, `npm run lint`, `npm run test`, `npm run build`, and `docker compose config` pass on the change.
7. **Health-first design.** A page that only records history still returns its status when the history write fails. Liveness stays `GET /health`.
8. **Observable systems.** A consolidation step logs the same job names and does not drop the current self-check or delivery error log.
9. **One responsibility per service.** The notification facade sends. The job engine sleeps and starts jobs. The metric repository reads. The backup service does not also format analytics.
