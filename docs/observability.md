# Observability

HomeLab Monitor reuses Production Health, Analytics, Capacity, Insights, and
Developer pages. Sprint 11.2 adds self-monitoring fields on
`GET /api/v1/system/health` without new dashboard routes.

## Overall Health Score (0–100)

Weighted from API, Database, Agent, CPU, Memory, Storage, SQLite Backup,
Telegram, and Photo Monitor. Active alerts subtract up to 10 points.

## Metrics on Production Health

| Signal | Source |
| --- | --- |
| Service dependency status | Existing component checks |
| API latency | Health probe |
| Database size / growth | SQLite file vs last backup uncompressed size |
| Container uptime | Docker runtime table |
| CPU / memory / disk history | Last agent `metric_history` samples |
| Network latency | Existing network probe |
| Telegram delivery success rate | `notifications` rows with channel `telegram` |
| Photo Monitor latency | Configured scan interval (CIFS poll) |
| Backup success rate | Verified gzip vs `.failed` archives |

## Last events

Production Health shows Last Self Check, Last Backup, Last Telegram, Last Photo
Scan, and Last Agent Check-in. These are additive JSON fields with defaults so
older clients keep working.

No new business features were added. Authentication, Telegram report text, and
REST paths are unchanged.
