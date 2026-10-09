# Plugin architecture guide

## Intent

Plugins are **in-process adapters** over existing modules. They exist so future integrations can share name, version, author, description, capabilities, status, health, and configuration without forking REST.

They are not sandboxed processes and not a package marketplace.

## Discovery

`plugin_manager.plugins_root()` checks `/app/plugins`, repo `plugins/`, then cwd. Folders named `examples` or `sdk` are skipped. Each plugin needs `manifest.json` plus optional `config.json`.

If the directory is missing (site-packages install without COPY), five built-in records are synthesized.

Dockerfile.api copies `plugins/` into `/app/plugins`.

## Metadata

Manifest keys: `id`, `name`, `version`, `author`, `description`, `capabilities`, `builtin`.  
Config JSON is returned as `configuration` (must not contain secrets).

## Lifecycle

Discover → Load → Start → Health Check → Stop → Unload.

`GET /api/v1/plugins` discovers and starts adapters if the registry is empty, then refreshes health for `started` plugins.

`POST /api/v1/plugins/{id}/lifecycle` with `action` in discover|load|start|health|stop|unload. Admin only for POST.

## Health mapping

| Plugin | Source |
| --- | --- |
| core-system | always healthy if loaded |
| telegram | enabled + token + chat id |
| photo-monitor | last successful scan |
| backup | sqlite integrity PASS |
| analytics | always healthy if loaded |

## Loading / dependency

Python `json.loads` of local files. No signature, no capability ACL, no inter-plugin depends graph. Registry is a process-global dict (`_registry`).

## Built-in production adapters

core-system, telegram, photo-monitor, backup, analytics.

## Samples (not production)

`plugins/examples/{ups,weather,mqtt}` — documentation only. See [plugin-sdk.md](plugin-sdk.md) and [plugins.md](plugins.md).

## Architecture violation (documented, not fixed)

**Root cause:** lifecycle mutates adapter records only.  
**Impact:** Stop/Unload does not cancel `run_photo_watcher`, `run_sqlite_backup`, or the notification worker. Operators may believe a plugin is stopped while scans and Telegram still run.  
**Recommended fix (Phase 13+):** bind lifecycle to `runtime_control.restart_background` / task cancel, or make lifecycle read-only for builtins.
