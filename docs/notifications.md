# Notification center

Alert activate and recover events are enqueued for **Telegram** delivery. The
worker batches jobs for 10 seconds, retries failed sends up to three times
(5s apart), and records attempts in an **in-memory** history buffer.

Discord, Slack, and email are **not** on the live alert path in v1.0.0-rc1.
See [known-limitations.md](known-limitations.md).

Environment Telegram settings (`TELEGRAM_*` / `HOMELAB_TELEGRAM_*`) control
the worker. Dashboard Settings may still show other channel fields; those
do not send live alerts in this RC. Telegram buttons use public URLs only
(`HOMELAB_DASHBOARD_PUBLIC_URL`, Tailnet HTTPS, Immich/QNAP public URLs).
Docker health URLs are never attached; see [telegram.md](telegram.md).

## Delivery

Statuses recorded on successful or dropped attempts: `sent`, `failed`.

Queue and history are process-local. An API restart drops pending jobs and
clears Notification Center delivery history and metrics.

## APIs

| Method | Path | Roles |
| --- | --- | --- |
| `GET` | `/api/v1/notifications` | admin, operator, viewer |
| `GET` | `/api/v1/notifications/{id}` | admin, operator, viewer |
| `POST` | `/api/v1/notifications/test` | admin, operator |
| `POST` | `/api/v1/notifications/{id}/retry` | admin, operator |
| `GET` | `/api/v1/notifications/delivery-history` | admin, operator, viewer |
| `GET` | `/api/v1/notifications/metrics` | admin, operator, viewer |
| `GET` | `/api/v1/settings/notifications` | admin, operator, viewer |
| `PUT` | `/api/v1/settings/notifications` | admin |

Error codes: `notification_not_found`, `notification_channel_unconfigured`,
`permission_denied`, `auth_required`.

## Dashboard

- Notification Center (`/monitoring/notifications`): delivery metric cards,
  search/filter history (max 100 rows), and the existing timeline.
- Settings (admin): Telegram test controls, Public URL validation, and button
  preview. The bot token is never displayed. Health URLs are not edited here.
- Notifications page: persisted `notifications` rows for tests/retries.
