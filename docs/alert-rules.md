# Alert rules

Hard-coded thresholds are replaced by rows in `alert_rules`. Alert event kinds
remain `cpu_high`, `memory_high`, `disk_high`, `temperature_high`, and
`agent_offline`. The `alerts` table is unchanged.

## Pipeline

```text
Agent Report
  → Metric Evaluator
  → Alert Rules Engine
  → Alert Engine (open / update / resolve)
  → Notification Dispatcher
  → Telegram / Discord / Slack / Email
```

Enabled rules are loaded on each report and offline evaluation. If the table is
empty, the engine falls back to the existing environment thresholds so current
behavior is preserved until rules are created.

`applies_to` may be `all`, `group` (requires `group_id`), or `agent` (requires
`agent_id`). Disabled rules are skipped. `cooldown_seconds` delays reopening a
resolved alert of the same kind and resource. Identical active alerts are still
updated in place rather than duplicated.

When several rules match the same metric and resource, the highest severity
wins; `>=` outranks `>` at the same severity when its threshold is higher.

## APIs

| Method | Path | Roles |
| --- | --- | --- |
| `GET` | `/api/v1/alert-rules` | admin, operator, viewer |
| `GET` | `/api/v1/alert-rules/{id}` | admin, operator, viewer |
| `POST` | `/api/v1/alert-rules` | admin |
| `PUT` | `/api/v1/alert-rules/{id}` | admin |
| `PATCH` | `/api/v1/alert-rules/{id}/enable` | admin |
| `DELETE` | `/api/v1/alert-rules/{id}` | admin |

Rule mutations publish existing WebSocket events `overview_updated` and
`alert_updated` with `reason=rule_updated`.
