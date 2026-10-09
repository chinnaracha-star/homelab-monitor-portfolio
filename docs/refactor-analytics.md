# Analytics consolidation plan

**Sprint:** 13.2  
**Status:** Plan only. Responses stay the same.

## Current pipeline

These services all read `metric_history` and related tables, then shape a different response:

| Consumer | Reads |
| --- | --- |
| `AnalyticsService` | Windows of `metric_history`, photo ops snapshots, backup ops snapshots |
| `TrendService` | Calls analytics, then classifies direction |
| `CapacityPlanningService` | Calls analytics and trends for storage, photos, and backup runway |
| Insights | Calls the same family for warning and healthy copy |
| `PredictionService` | Calls capacity and trends again for 7, 30, and 90 day text |

A dashboard page can request overview plus storage, system, photos, and backup. Each request walks overlapping windows. `TrendService._metric_trend` loads only the metric it needs. A process-wide cache of ORM rows was tried and removed: cached instances detached from the next session and broke aggregates.

## Target design

```text
Metric Repository
    ↓
Analytics Engine
    ↓
Consumers: analytics, trends, capacity, insights, predictions
```

**Metric Repository** is the only reader of `metric_history` for a time window. It returns plain values, not live ORM objects, so a later cache cannot leak across sessions.

**Analytics Engine** computes current, average, min, max, and hourly or daily buckets once per window. It does not choose risk words.

**Consumers** keep today's response models. They ask the engine for a window and apply the labels they already use (`rising`, `stable`, days to full, prediction horizons).

## Migration steps

1. Add the repository as a private helper used only by `AnalyticsService._history_window`. Return the same rows to existing functions.
2. Move average and series math into the engine. Analytics endpoints must match current JSON on the existing tests.
3. Point trends at the engine. Direction labels stay.
4. Point capacity, insights, then predictions. Do not merge the HTTP routes.
5. Cache plain numbers inside one process only after tests prove a second database does not see the first database's rows.

## Compatibility strategy

`/api/v1/analytics/*`, `/trends/*`, `/capacity/*`, `/insights/*`, and `/predictions/*` keep their paths and fields. No SQLite migration. No new index in the first step. If a query plan needs an index later, that is a schema RFC, not part of this plan's first code.

## Risk

Sharing a cached window across requests can mark a healthy series as unknown when the cache belongs to another SQLite file. The repository must key any cache by the engine URL and must store detached numbers only.
