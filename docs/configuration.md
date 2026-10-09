# Configuration standard

**Sprint:** 13.1

Configuration stays where it is. This sprint does not move files or change how settings load.

## Lifecycle

1. **Configuration.** Values start in the process environment, `.env` (see `.env.example`), and `docker-compose.yml` variable defaults. Plugin adapters may also have a `config.json` next to `manifest.json`.
2. **Validation.** `homelab_monitor.settings.Settings` loads and checks environment values at process start. Invalid values fail startup rather than being half-applied. Public URL rules use `shared/public-url-rules.json`.
3. **Persistence.** Operator-edited notification settings, photo monitor settings, and user passwords are stored in SQLite. The photo baseline is a JSON file beside the database (`photo_baseline.json`). Plugin `config.json` files stay on disk and are not written by the API.
4. **Runtime.** Background jobs and request handlers read the `Settings` object and the SQLite rows. A change in `.env` applies on process restart. A change in SQLite settings applies on the next read.

## Where configuration lives today

| Concern | Source |
| --- | --- |
| Database URL, JWT, bootstrap users, log level | Environment / `.env` via `Settings` |
| Telegram bot token and chat id | Environment via `Settings` |
| Public dashboard URL rules | `shared/public-url-rules.json` plus environment URL fields |
| Photo watch folders and scan interval | Environment defaults, then `photo_monitor_settings` in SQLite |
| Photo baseline | `photo_baseline.json` under the data directory |
| Scheduled report switches and last-sent times | `notification_settings.payload` in SQLite |
| Plugin display configuration | `plugins/*/config.json` |
| Compose service wiring | `docker-compose.yml` |

Secrets stay in the environment. They are not written into plugin JSON or the capability docs.
