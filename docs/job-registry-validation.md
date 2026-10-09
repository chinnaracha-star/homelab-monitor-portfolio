# Job registry validation

**Sprint:** 13.5.1  
**Status:** Validation runs at startup and on `GET /health`. It does not start or stop jobs.

## Purpose

`JobEngine` lists background jobs, and `operations.factories` still starts them. This check reports when those two lists disagree. Startup continues either way.

## Validation rules

For the registry and the factory map:

- Every factory name exists in the registry, and every registry name exists in the factory map.
- Names are not repeated in the registry list.
- The registry implementation path matches the expected path, and the factory lambda calls that function.
- The registry schedule description and enabled-flag source match the expected contract.

The validator does not call the lambdas and does not write settings or the database.

## Failure scenarios

| Case | Result |
| --- | --- |
| Lists and contracts match | `pass`, warnings empty |
| A factory job has no registry entry | `warning`, factory-only and missing |
| A registry job has no factory entry | `warning`, registry-only and missing |
| The same registry name appears twice | `warning`, duplicated |
| Implementation, schedule, or enabled text differs | `warning` for that job |

An unexpected exception becomes a warning. It is not raised.

## Startup behavior

`lifespan` logs the result, then registers the same six background tasks as before.

- Success: `Job registry validation: PASS`
- Failure: `Job registry validation: WARNING` plus missing, duplicated, registry-only, and factory-only names

The process is not stopped.

## Health reporting

`GET /health` adds `job_registry`:

```json
{
  "status": "pass",
  "validated": true,
  "registered_jobs": 6,
  "factory_jobs": 6,
  "warnings": []
}
```

Existing health fields stay in place. `status` here is the registry check, not the API status.

## Future migration

When startup later reads the registry to launch jobs, this warning is the gate that the registry and factories still name the same coroutines. Replacing the loops comes after that parity stays green.
