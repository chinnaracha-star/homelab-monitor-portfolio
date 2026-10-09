# Platform architecture (freeze)

HomeLab Monitor is a single-host agent-server monitor: Python agents POST metrics; FastAPI persists SQLite, evaluates alerts, notifies Telegram, and serves a React PWA.

## Layer diagram

```mermaid
flowchart TB
  subgraph clients [Clients]
    PWA[React PWA]
    Agent[Python agent 0.1.0]
  end
  subgraph edge [Edge]
    Nginx[nginx / dashboard container]
  end
  subgraph api [API process]
    REST[FastAPI REST]
    WS[Dashboard WebSocket]
    Auth[JWT RBAC + agent bearer]
    Plugins[Plugin Manager adapters]
    Jobs[Background asyncio tasks]
  end
  subgraph data [Data]
    SQLite[(SQLite WAL)]
    Files[gzip backups + JSON history]
  end
  subgraph ext [External]
    TG[Telegram Bot API]
    Docker[Docker socket]
    NAS[QNAP / CIFS photo mounts]
  end
  PWA --> Nginx --> REST
  PWA --> WS
  Agent --> REST
  REST --> Auth
  REST --> SQLite
  REST --> Plugins
  Jobs --> SQLite
  Jobs --> TG
  Jobs --> NAS
  Jobs --> Docker
  Jobs --> Files
```

## Module diagram

```mermaid
flowchart LR
  agents[agents + alert_engine]
  dash[dashboard routers]
  photo[photo_watcher]
  backup[sqlite_backup]
  notify[notification_worker + telegram]
  ops[operations + production_health]
  plat[plugins + assistant + knowledge + topology]
  agents --> dash
  photo --> notify
  backup --> ops
  agents --> notify
  ops --> plat
  dash --> plat
```

## Dependency graph (runtime)

```mermaid
flowchart TB
  FastAPI --> Settings
  FastAPI --> SQLAlchemy
  FastAPI --> PluginManager
  PluginManager --> PhotoWatcher
  PluginManager --> SqliteBackup
  PluginManager --> Settings
  Assistant --> ProductionHealth
  Knowledge --> Models
  Knowledge --> OperationsHistoryJSON
  Topology --> ProductionHealth
  AlertEngine --> Notifications
  PhotoWatcher --> PhotoTelegram
```

## Service interaction

| Actor | Talks to | How |
| --- | --- | --- |
| Agent | API | HTTPS bearer token, 60s default |
| Dashboard | API | JWT REST + `GET /api/v1/ws/dashboard` |
| API | SQLite | SQLAlchemy sessions |
| Notification worker | Telegram | Bot API |
| Photo watcher | CIFS mounts | filesystem scan |
| Backup scheduler | data volume | gzip copy + integrity |
| Operations Center | Docker CLI | restart named containers (admin) |

## Plugin lifecycle

```mermaid
flowchart LR
  Discover --> Load --> Start --> HealthCheck[Health Check]
  HealthCheck --> Stop --> Unload
```

Adapters record lifecycle in process memory. Stopping a plugin does **not** cancel the corresponding asyncio worker. See [plugin-architecture.md](plugin-architecture.md).

## Request flow (dashboard)

```mermaid
sequenceDiagram
  participant UI as PWA
  participant API as FastAPI
  participant DB as SQLite
  UI->>API: JWT GET /api/v1/...
  API->>API: require_roles
  API->>DB: Session query
  DB-->>API: rows
  API-->>UI: JSON
  UI->>API: WS /api/v1/ws/dashboard
  API-->>UI: compact events
  UI->>API: refetch REST
```

## Request flow (agent)

```mermaid
sequenceDiagram
  participant A as Agent
  participant API as FastAPI
  participant DB as SQLite
  A->>API: POST /agent/reports Bearer
  API->>API: hash token, idempotent report_id
  API->>DB: MetricReport + MetricHistory
  API->>API: AlertEngine
  API-->>A: control (interval, config revision)
```

## Component relationship

Browser PWA → nginx static + `/api` proxy → FastAPI → SQLite.  
Background tasks share the API process: offline monitor, infrastructure monitor, Telegram reports, notification worker, photo watcher, SQLite backup.  
Plugin Manager, AI assistant, topology, and knowledge **read** those same stores.

Existing architecture narrative: [architecture.md](architecture.md).
