# Knowledge Center

Collects existing history into a searchable timeline. No replacement of Alert Timeline, Backup, or Photo Monitor pages.

## Sources

| Kind | Source |
| --- | --- |
| incident | Alerts |
| telegram | Notification rows |
| photo | Photo events |
| system | Ops snapshots |
| backup | Latest SQLite backup state |
| maintenance | Operations Center history |

## HTTP

- `GET /api/v1/knowledge?q=&kind=`
- `GET /api/v1/knowledge/export` (CSV)

Dashboard route `/knowledge` with search, kind filter, and export.
