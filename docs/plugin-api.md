# Plugin API

**Sprint:** 13.1  
**Plugin API version:** v1

This document governs the in-process plugin adapter surface. Sprint 13.1 does not change `plugin_manager.py` or any manifest.

## Current version

v1 is the surface already loaded at runtime:

- Discovery from `/app/plugins`, the repo `plugins/` directory, or the process working directory
- `manifest.json` keys `id`, `name`, `version`, `author`, `description`, `capabilities`, `builtin`
- Optional `config.json` returned as `configuration` with no secrets
- Lifecycle actions `discover`, `load`, `start`, `health`, `stop`, `unload`
- Record fields returned by `GET /api/v1/plugins`: `id`, `name`, `version`, `author`, `description`, `capabilities`, `status`, `health`, `configuration`, `lifecycle`, `builtin`

Folders named `examples` and `sdk` are not loaded. Built-in ids are `core-system`, `telegram`, `photo-monitor`, `backup`, and `analytics`.

## Rules

- v1 is backward compatible.
- Changes are additive only: a new optional manifest field, a new optional response field, or a new lifecycle action that old clients can ignore.
- Removing a field, renaming an action, or changing the meaning of `stop` is a breaking change and needs an accepted RFC before code changes.
- The product version (`1.0.0-rc3`) and the Plugin API version (v1) are different. A release may bump the product version without bumping the Plugin API.

## Non-goals of v1

Plugins do not run in a second process, do not receive a signed package, and do not replace Photo Monitor, Telegram, or backup workers. Those workers keep running when an adapter is stopped. That gap is recorded in `docs/technical-debt.md` as H1 and is not fixed here.
