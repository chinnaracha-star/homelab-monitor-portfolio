# API development guide

## Start the API

Copy `.env.example` to `.env` and replace the registration key. Then install the
project, apply migrations, and start Uvicorn as described in the root README.

## Register an agent

With the API running, execute this from the repository root. The snippet reads
`HOMELAB_REGISTRATION_KEY` directly from `.env`; it does not require exporting
the key into the shell:

```bash
AGENT_TOKEN="$(
  .venv/bin/python - <<'PY'
import socket

import httpx
from dotenv import dotenv_values

config = dotenv_values(".env")
registration_key = config.get("HOMELAB_REGISTRATION_KEY")
if not registration_key:
    raise SystemExit("HOMELAB_REGISTRATION_KEY is missing from .env")

response = httpx.post(
    "http://127.0.0.1:8000/api/v1/agents/register",
    headers={"X-Registration-Key": registration_key},
    json={
        "name": socket.gethostname(),
        "hostname": socket.gethostname(),
        "version": "0.1.0",
        "capabilities": ["ubuntu"],
    },
)
response.raise_for_status()
print(response.json()["agent_token"])
PY
)"
```

The one-time token is now available as `AGENT_TOKEN` in the current shell
without being printed. Store it in the agent environment file with mode `0600`;
the server does not return it again.

## Upload a report

```bash
curl --request POST http://127.0.0.1:8000/api/v1/agent/reports \
  --header "Authorization: Bearer AGENT_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "report_id": "home-server-000001",
    "schema_version": "1.0",
    "observed_at": "2026-09-07T05:00:00Z",
    "config_revision": 1,
    "modules": [{
      "module": "system",
      "status": "healthy",
      "summary": "System resources are within thresholds",
      "metrics": {
        "cpu_percent": 12.5,
        "memory_percent": 44.0
      }
    }]
  }'
```

Retrying an identical `report_id` and payload is idempotent. Reusing the ID with
different content returns HTTP `409`.

Interactive OpenAPI documentation is available at `/docs`.

## Authentication

Dashboard APIs require a JWT issued by `POST /api/v1/auth/login`:

```bash
curl --request POST http://127.0.0.1:8000/api/v1/auth/login \
  --header "Content-Type: application/json" \
  --data '{"username":"admin","password":"<bootstrap-admin-password>"}'
```

The example uses the bootstrap administrator from `HOMELAB_BOOTSTRAP_ADMIN_PASSWORD`.
Operator and viewer accounts are documented in [authentication.md](authentication.md).

- `GET /api/v1/auth/me`
- `GET /api/v1/dashboard/overview`
- `GET /api/v1/agents`
- `GET /api/v1/agents/{agent_id}`
- `GET /api/v1/agents/{agent_id}/latest-report`
- `GET /api/v1/agents/{agent_id}/reports?limit=30`
- `GET /api/v1/alerts/active`
- `POST /api/v1/alerts/{alert_id}/acknowledge` (admin and operator)
- `GET /api/v1/groups`
- `GET /api/v1/groups/summary`
- `GET /api/v1/groups/{group_id}`
- `POST /api/v1/groups` (admin and operator)
- `PUT /api/v1/groups/{group_id}` (admin and operator)
- `DELETE /api/v1/groups/{group_id}` (admin and operator)
- `POST /api/v1/groups/{group_id}/agents` (admin and operator)
- `DELETE /api/v1/groups/{group_id}/agents/{agent_id}` (admin and operator)
- `GET /api/v1/users` (admin)
- `GET /api/v1/notifications`
- `GET /api/v1/notifications/{notification_id}`
- `POST /api/v1/notifications/test` (admin and operator)
- `POST /api/v1/notifications/{notification_id}/retry` (admin and operator)
- `GET /api/v1/settings/notifications`
- `PUT /api/v1/settings/notifications` (admin)
- `GET /api/v1/alert-rules`
- `GET /api/v1/alert-rules/{rule_id}`
- `POST /api/v1/alert-rules` (admin)
- `PUT /api/v1/alert-rules/{rule_id}` (admin)
- `PATCH /api/v1/alert-rules/{rule_id}/enable` (admin)
- `DELETE /api/v1/alert-rules/{rule_id}` (admin)
- `GET /api/v1/infrastructure`
- `GET /api/v1/infrastructure/qnap`
- `GET /api/v1/infrastructure/docker`
- `GET /api/v1/infrastructure/immich`
- `GET /api/v1/infrastructure/qumagie`
- `GET /api/v1/infrastructure/backup`
- `GET /api/v1/photo-services`
- `GET /api/v1/photos`
- `GET /api/v1/photos/latest`
- `GET /api/v1/photos/stats`
- `GET /api/v1/photos/settings`
- `PUT /api/v1/photos/settings` (admin)
- `GET /api/v1/backup`
- `POST /api/v1/users` (admin)
- `PUT /api/v1/users/{user_id}` (admin)
- `PATCH /api/v1/users/{user_id}/password` (admin)
- `PATCH /api/v1/users/{user_id}/status` (admin)
- `DELETE /api/v1/users/{user_id}` (admin)

- `GET /api/v1/ws/dashboard` (dashboard JWT, WebSocket)
- `GET /api/v1/history/agents/{agent_id}`
- `GET /api/v1/history/agents/{agent_id}/export`

`GET /health` and agent registration/check-in/report upload remain independent
of dashboard JWTs. Roles are documented in
[authentication.md](authentication.md) and [rbac.md](rbac.md).

## Dashboard API

The read-only Dashboard API uses the existing agent and report data and requires
a dashboard JWT:

- `GET /api/v1/dashboard/overview` returns agent status, report counts, total
  groups, and per-group agent/online stats. Existing `agents` and `reports`
  fields are unchanged.
- `GET /api/v1/agents` returns agents ordered by name.
- `GET /api/v1/agents/{agent_id}` returns agent details, capabilities, and the
  current configuration revision.
- `GET /api/v1/agents/{agent_id}/latest-report` returns the report with the
  newest observation timestamp.
- `GET /api/v1/agents/{agent_id}/reports?limit=30` returns 2–100 recent reports,
  ordered from newest to oldest, for dashboard trend rendering.
- `GET /api/v1/alerts/active` returns persisted active alerts with agent names
  for the dashboard alert banner.
- `POST /api/v1/alerts/{alert_id}/acknowledge` is available to admins and
  operators. It confirms the alert exists; persisted acknowledgement state can
  be added later without changing the route or role list.
- Group APIs list, create, update, delete, and assign agents. See
  [groups.md](groups.md).
- Notification APIs list delivery history, send tests, retry failures, and
  read/update channel settings. See [notifications.md](notifications.md).
- `GET /api/v1/users` lists dashboard accounts for administrators. Password
  hashes are never returned.
- `POST /api/v1/users`, `PUT /api/v1/users/{user_id}`,
  `PATCH /api/v1/users/{user_id}/password`,
  `PATCH /api/v1/users/{user_id}/status`, and `DELETE /api/v1/users/{user_id}`
  provide admin-only user management. See [user-management.md](user-management.md).
- `GET /api/v1/ws/dashboard` is a WebSocket for live dashboard updates. Pass the
  JWT as `token` or `Authorization: Bearer`. Event types are `connection`,
  `overview_updated`, `agent_updated`, and `alert_updated`. REST contracts are
  unchanged; see [realtime.md](realtime.md).
- `GET /api/v1/history/agents/{agent_id}?from=&to=&interval=` returns aggregated
  metric history ordered by timestamp. Supported intervals are `1m`, `5m`,
  `15m`, and `1h`.
- `GET /api/v1/history/agents/{agent_id}/export` returns the same series as CSV.
  See [history.md](history.md).

- `GET /api/v1/system/health` returns production health, optional observability,
  and optional performance scores. See [performance.md](performance.md).
- `GET /api/v1/operations`, `GET /api/v1/operations/history`, and
  `POST /api/v1/operations/{id}/run` (body `{ "confirm": true }`) are
  admin/operator maintenance actions. See [operations-center.md](operations-center.md).

Missing agents and missing reports use the API's standard structured `404`
responses. Complete response schemas and examples are available in OpenAPI.

## Ubuntu agent integration

The packaged agent implements check-in and report upload automatically. Configure
it with the one-time registration token and run:

```bash
.venv/bin/homelab-agent --env-file ./agent.env run
```

The current agent sends a full system report each cycle. Buffered retries retain
the original `report_id`, so the API's existing idempotency contract prevents
duplicate database rows.
