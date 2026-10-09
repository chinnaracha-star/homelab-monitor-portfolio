# Module lifecycle

**Sprint:** 13.1  
Documentation only. No module is installed, stopped, or removed by this sprint.

## States

```text
Installed → Enabled → Running → Stopped → Disabled → Removed
```

| State | Meaning |
| --- | --- |
| Installed | Code and configuration are present |
| Enabled | Configuration allows the module to start |
| Running | A worker or request path is active |
| Stopped | The worker is not in its loop, configuration remains |
| Disabled | Configuration forbids start on the next process boot |
| Removed | Code and configuration are gone. Not used for built-ins |

## Current modules

### Plugins

Installed as directories under `plugins/`. Enabled when the manifest loads. `GET /api/v1/plugins` moves an empty registry to running. `stop` and `unload` change the adapter record only. Photo, backup, and Telegram workers are separate and keep running. There is no Removed state for the five built-ins.

### Assistant

Installed with the API. Enabled for any authenticated role that can read it. Running means `GET /api/v1/assistant/briefing` answers. There is no stop switch. It does not run a background job.

### Photo Monitor

Installed with the API. Enabled by `photo_watcher_enabled` and the SQLite photo settings row. Running is the `photo_watcher` task from `operations.factories`. Stopped only when that task is cancelled or the process exits. Disabled when the setting is turned off; the baseline file remains.

### Background jobs

`operations.factories` registers one asyncio task per job: `offline_monitor`, `infrastructure_monitor`, `telegram_reports`, `notification_worker`, `photo_watcher`, `sqlite_backup`. They start in the API lifespan and stop when the process shuts down. There is no per-job Removed state.

### Future modules

A new module uses the same six states and needs an accepted RFC if it changes REST, the agent protocol, SQLite, auth, or an existing worker. Planned names are listed in `docs/capability-matrix.md` under Enterprise and are not installed.
