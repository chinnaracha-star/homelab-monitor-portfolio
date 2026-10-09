# Performance and reliability

Production Health records a performance sample when `/api/v1/system/health` is read.

## Metrics

| Metric | Source |
| --- | --- |
| API response time | HTTP middleware rolling mean |
| Database query time | `SELECT 1` latency |
| SQLite size / growth | DB file vs last backup uncompressed size |
| Docker CPU / memory | `docker stats` when the CLI is available |
| Photo scan duration | Last Photo Monitor cycle |
| Backup duration | Last sqlite gzip job |
| Scheduler time | Same as last backup duration (scheduler work) |
| Telegram latency | Filled when an operations Telegram test runs; otherwise unset |

## History

Samples are stored as `ops_snapshots` with `kind=performance` and pruned after 31 days. The dashboard shows **24h / 7d / 30d** averages for API and query times.

## Scores

- **Performance Score** (0–100): penalizes slow API (>100 ms / >250 ms) and slow queries (>15 ms / >50 ms).
- **Reliability Score** (0–100): penalizes missing backup/photo samples and very high Docker CPU.

No new dashboard page. Cards live on Production Health.
