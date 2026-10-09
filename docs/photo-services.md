# Photo services

The dashboard is a **read-only** observer of the existing photo workflow. It
never uploads, moves, indexes, or deletes photos, and it never writes to the
NAS.

```text
Phone → Qfile Pro → QNAP TS-453Be → Shared Folder → Immich → QuMagie → Dashboard
```

```text
Dashboard → InfrastructureService → Photo connectors (Immich, QuMagie, QNAP)
         → REST `/api/v1/photo-services` → Realtime dashboard
```

Existing infrastructure APIs stay in place. Photo Services reuses the same
connector layer and snapshot cache.

## Connectors

Mock mode remains the default (`HOMELAB_INFRASTRUCTURE_MOCK=true`). Live mode
issues **GET** requests only.

### Immich

When `HOMELAB_IMMICH_URL` and `HOMELAB_IMMICH_API_KEY` are set, the connector
reads:

- `/api/server/ping`
- `/api/server/version`
- `/api/server/statistics`
- `/api/jobs`
- `/api/users`
- `/api/albums`

It never calls upload, delete, or job-start endpoints.

### QNAP

Read-only sysinfo and share list. Optional GET `authLogin.cgi` obtains a
session id; prefer `HOMELAB_QNAP_SID` so the password is unused. Collected
fields include hostname, model, firmware, uptime, online status, capacity,
used, free, usage percent, shared folders, and temperature when the NAS
returns it.

### QuMagie

QNAP QuMagie has no stable public API. The connector probes GET
`/api/status` and then `/cgi-bin/qphoto/qphoto.cgi?func=get_info`. If neither
responds, the snapshot is isolated as unhealthy and other connectors still
return.

## APIs

- `GET /api/v1/photo-services` — Immich, QuMagie, and QNAP snapshots plus
  flattened photo statistics
- Existing `GET /api/v1/infrastructure*` unchanged

JWT required. Roles: admin, operator, viewer. `read_only` is always `true`.

Statistics (and later alert metrics, not evaluated in this sprint):

- `indexed_photos`, `indexed_videos`, `albums`, `users`
- `storage_used`, `storage_free`, `storage_percent`, `capacity_bytes`
- `thumbnail_queue`, `face_queue`, `last_scan`
- `immich_health`, `qumagie_health`
- `storage_percent_metric`, `thumbnail_queue_metric`, `face_queue_metric`
- `storage_history` (`today`, `yesterday`, `last_week` used bytes)
- `photo_growth` (`today`, `yesterday`, `this_week` photo deltas)

Background refresh stores `ops_snapshots` so live mode can compute those
windows. Mock mode returns demo Storage History and Photo Growth values.

Storage health for display: healthy below 80%, warning at 80%, critical at 90%.

## Realtime

Background refresh publishes existing `overview_updated` once with
`reason=photo_services_updated`. No new WebSocket event type. Polling remains
the fallback.
