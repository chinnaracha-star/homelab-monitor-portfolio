# Metric repository

**Sprint:** 13.4  
**Status:** Repository added. Analytics, trends, capacity, insights, and predictions still query `metric_history` themselves.

## Current architecture

`AnalyticsService` loads `MetricHistory` rows for a time window and keeps those ORM instances inside the request. Trends call analytics for one field. Capacity, insights, and predictions call that family again. HTTP handlers return the existing Pydantic models. A process-wide cache of ORM rows was tried and removed because a later session saw detached instances and wrong aggregates.

## Repository responsibilities

`MetricRepository` in `metrics/repository.py` only reads. It supports:

- `latest` — newest samples, optionally for one agent
- `between` — samples in a time range, oldest first
- `aggregation_input` — the same window, for averages and buckets
- `trend_input` — `(timestamp, value)` pairs for one history field

It does not write, classify direction, forecast capacity, or choose insight text.

## Data ownership

`metric_history` stays owned by the history writer in `history.py`. The repository does not insert or update rows. Each sample is a frozen `MetricSample` copied while the session is open. The copy holds strings, datetimes, and floats.

## Session lifetime

The repository keeps the `Session` it was constructed with and uses it only for the call in progress. Callers close the session when their unit of work ends. Samples remain usable after `close` because they are not bound to the session.

## Why ORM objects stay inside the repository

SQLAlchemy instances expire or detach when the session commits or closes. A later request, a second database, or a cache that stores those instances reads empty or stale attributes. Copying fields at the query boundary makes that class of bug impossible for this type.

## Caching policy

This sprint does not add a cache.

If a cache is added later:

- Store plain numbers and timestamps only. Never store `MetricHistory` or any other ORM instance.
- Drop the cache when the session that filled it closes. A cache must not outlive that session.
- Key entries by database URL and agent so one SQLite file cannot satisfy another.
- Invalidate on the next metric insert for that agent, or by not caching across requests until a test proves a second database does not see the first database's rows.

## Analytics engine

```text
Metric Repository
        ↓
Analytics Engine
        ↓
     Trend
        ↓
    Capacity
        ↓
    Insight
        ↓
   Prediction
```

The engine is not implemented in this sprint. Existing services keep their current queries and JSON.

## Future migration

1. Point `AnalyticsService._history_window` at `between` and adapt the existing math to `MetricSample`. Response JSON must match current tests.
2. Move average and series math into an engine that still returns today's models.
3. Point trends, then capacity, insights, and predictions at that engine.
4. Only then consider a session-scoped cache of plain numbers.
