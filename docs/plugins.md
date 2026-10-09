# Plugin Manager

HomeLab Monitor v1.0.0-rc3 wraps existing modules as **adapters**. Plugins do not spawn a second runtime and do not change existing REST contracts.

## Layout

Each production plugin lives under `plugins/<id>/`:

- `manifest.json` — name, version, author, description, capabilities
- `config.json` — non-secret configuration
- `runtime.md` — how the adapter maps onto the existing service

Sample-only plugins (UPS, Weather, MQTT) live in `plugins/examples/` and are never loaded.

## Lifecycle

```mermaid
flowchart LR
  Discover --> Load --> Start --> HealthCheck[Health Check]
  HealthCheck --> Stop --> Unload
```

| Action | Effect |
| --- | --- |
| Discover | Read manifests from `plugins/` |
| Load | Register adapters in memory |
| Start | Mark running and run a health check |
| Health Check | Map existing health sources |
| Stop | Mark stopped; underlying workers keep their own settings |
| Unload | Drop adapter state from the registry |

## Built-in adapters

| Plugin | Existing module |
| --- | --- |
| Core System | API, SQLite, agents |
| Telegram | Notification worker |
| Photo Monitor | Photo watcher |
| Backup | SQLite backup scheduler |
| Analytics | Analytics APIs |

## HTTP (additive)

- `GET /api/v1/plugins`
- `POST /api/v1/plugins/{id}/lifecycle` with `{ "action": "load|start|health|stop|unload|discover" }`

Dashboard: **Mission Control → Plugin Manager** (Developer page). No extra page.

See [plugin-sdk.md](plugin-sdk.md) for authoring.
