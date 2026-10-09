# Operations Center

Operators run maintenance from **Production Health** (admin and operator). There is no extra page.

## Actions

| Action | Effect |
| --- | --- |
| Run Backup Now | Immediate gzip SQLite backup |
| Run Telegram Test | Sends a test message via existing TelegramNotifier |
| Run Photo Scan | One Photo Monitor cycle |
| Run Health Check | Recomputes Production Health |
| Run System Audit | Health check plus a silent backup |
| Restart API | Exits the API process after 1s (Compose `restart: unless-stopped`) |
| Restart Dashboard | `docker restart` on the dashboard container if Docker CLI is visible |
| Restart Photo Monitor | Cancels and recreates the watcher task |
| Restart Scheduler | Recreates the backup scheduler task |
| Reload Configuration | Clears `get_settings` LRU cache |
| Clear Cache | Resets Photo Monitor in-memory baseline service |

Every action requires `confirm=true`. The UI asks for confirmation, shows in-progress text, then success or failure. History is stored next to the database as `operations-history.json` (last 200 rows).

Restart API/Dashboard from inside a locked-down API container often fails until Docker socket/CLI is provided. That is expected.

API: `GET /api/v1/operations`, `GET /api/v1/operations/history`, `POST /api/v1/operations/{id}/run`.
