# Event, knowledge, and AI flows

## Event flow (realtime)

```mermaid
sequenceDiagram
  participant Agent
  participant API
  participant Hub
  participant PWA
  Agent->>API: check-in or report
  API->>Hub: notify_ingest
  Hub->>PWA: overview_updated / agent_updated / alert_updated
  PWA->>API: REST refetch
```

Alert engine, photo events, and backups do not all emit the same hub events; the PWA also polls (~30s).

## Platform data flow

```mermaid
flowchart LR
  AgentReports --> MetricReport
  MetricReport --> MetricHistory
  MetricReport --> Alerts
  Alerts --> NotificationRows
  NotificationRows --> Telegram
  PhotoScan --> PhotoEvents
  PhotoEvents --> Telegram
  HealthGET --> OpsSnapshots
  BackupJob --> GzipFiles
  OpsJSON[operations-history.json] --> Knowledge
  Alerts --> Knowledge
  PhotoEvents --> Knowledge
  NotificationRows --> Knowledge
  OpsSnapshots --> Knowledge
```

## Knowledge flow

`knowledge.collect` concatenates last 100 alerts (kind `incident`), notifications (`telegram`), photo events, ops snapshots (`system`), latest backup state (`backup`), operations JSON (`maintenance`). Query string filters title/details; `kind` filters. Export is CSV `kind,timestamp,title`.

## AI read-only flow

```mermaid
flowchart TB
  Briefing[GET /assistant/briefing]
  Briefing --> Health[ProductionHealthService.health]
  Briefing --> AlertCount
  Briefing --> TelegramFailed
  Briefing --> BackupIntegrity
  Briefing --> PhotoLastScan
  Briefing --> Text[summary / root_cause / impact / checks / actions]
```

`LocalHeuristicProvider` never writes. `never_modifies_platform` is always true. No external LLM.

**Side effect caveat:** `ProductionHealthService.health` records a performance snapshot. Assistant and topology inherit that GET-write. Root cause: health aggregator reused for reads. Impact: extra `ops_snapshots` rows. Recommended fix: split read snapshot from collect_and_store (do not change in freeze).
