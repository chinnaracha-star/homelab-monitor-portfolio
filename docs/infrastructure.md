# Infrastructure connectors

The dashboard can read snapshots from external infrastructure without changing
the agent protocol, alert engine, or notification dispatcher. Connectors only
collect information. They never control QNAP, Docker, Immich, QuMagie, or
backup systems.

```text
Dashboard → InfrastructureService → Connectors → Snapshot → REST → Realtime
```

Mock mode is on by default (`HOMELAB_INFRASTRUCTURE_MOCK=true`). No NAS or
Docker socket is required. One connector failure is isolated; the remaining
snapshots still return, and the last successful snapshot is cached.

## APIs

All require a dashboard JWT. Roles: admin, operator, viewer. Read-only.

- `GET /api/v1/infrastructure`
- `GET /api/v1/infrastructure/qnap`
- `GET /api/v1/infrastructure/docker`
- `GET /api/v1/infrastructure/immich`
- `GET /api/v1/infrastructure/qumagie`
- `GET /api/v1/infrastructure/backup`

Normalized item:

```json
{
  "service": "qnap",
  "status": "healthy",
  "version": "5.2.1",
  "updated_at": "2026-09-08T01:00:00+00:00",
  "summary": {}
}
```

Summary fields are flat metrics so a later sprint can feed them into the
existing Alert Rules engine. This sprint does not evaluate infrastructure
alerts.

## Realtime

A background refresh publishes existing `overview_updated` once with
`reason=photo_services_updated` (the same snapshot cycle feeds Infrastructure
and Photo Services). A second `infrastructure_updated` publish is not sent, so
clients do not refetch twice. No new WebSocket event type. The dashboard falls
back to polling when the socket is disconnected.

Photo-specific snapshots and statistics are documented in
[photo-services.md](photo-services.md).
