# Metric history

HomeLab Monitor stores a compact time-series row for every newly accepted agent
report. Full JSON reports remain in `metric_reports`. History is an additive
index for charts and CSV export.

## Storage

Table `metric_history` (Alembic revision `0004`):

- `agent_id`, `timestamp`
- `cpu_percent`, `memory_percent`, `disk_percent`
- `temperature_celsius`
- `network_rx_bytes`, `network_tx_bytes`

Indexes exist on `agent_id` and `timestamp`. Duplicate report uploads do not
insert a second history row.

CPU and memory come from `modules[].metrics.cpu.usage_percent` and
`memory.usage_percent`. Disk is the `/` mount when present, otherwise the highest
disk usage. Temperature is the highest `current_celsius`. Network counters are
stored when the payload includes them; the current Ubuntu collector does not
yet report network bytes.

## API

`GET /api/v1/history/agents/{agent_id}`

Query parameters:

- `from` and `to` — ISO-8601 timestamps. Defaults to the last 24 hours.
- `interval` — required: `1m`, `5m`, `15m`, or `1h`

The response is ordered by timestamp ascending. Points in the same interval
bucket are averaged.

`GET /api/v1/history/agents/{agent_id}/export` returns the same series as CSV.
Dashboard JWT required (`admin`, `operator`, `viewer`).

## Dashboard

Agent Detail shows a History section with CPU, memory, disk, and temperature
charts. Range buttons request only that window:

| Range | Interval |
| --- | --- |
| 1h | 1m |
| 6h | 5m |
| 24h (default) | 15m |
| 7d | 1h |
| 30d | 1h |

Export CSV uses the currently loaded points and the filename
`agent-name-yyyyMMdd-HHmm.csv`.
