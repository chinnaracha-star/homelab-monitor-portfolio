# AI Operations Assistant

Read-only explainer. It is **not** an autonomous agent and never mutates the platform.

## Provider abstraction

`LocalHeuristicProvider` (`local-heuristic`) is the default. A future LLM provider can implement the same `briefing(db, settings) -> dict` shape. No external AI dependency is required.

## Inputs (existing data)

Alerts, Production Health, capacity/health scores, SQLite backup integrity, Telegram failure counts, Photo Monitor last scan.

## Outputs

| Field | Meaning |
| --- | --- |
| summary | One-line health + alert + backup status |
| root_cause | Inferred causes |
| possible_impact | Operator-facing impact |
| recommended_checks | Where to look |
| recommended_actions | Human steps only |
| never_modifies_platform | Always `true` |

## HTTP

`GET /api/v1/assistant/briefing`

Dashboard: **Mission Control → AI Operations**.
