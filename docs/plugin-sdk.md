# Plugin SDK

Documentation-only. Do not install sample plugins in production.

## Manifest

```json
{
  "id": "example-weather",
  "name": "Weather",
  "version": "0.1.0",
  "author": "HomeLab Monitor",
  "description": "Sample weather adapter",
  "capabilities": ["read"],
  "builtin": false,
  "production": false
}
```

Required fields: `id`, `name`, `version`, `author`, `description`, `capabilities`.

## Lifecycle

Discover → Load → Start → Health Check → Stop → Unload.

Adapters must be read-compatible with existing services. They must not replace `/api/v1/agents` or other frozen contracts.

## Developer guide

1. Copy `plugins/examples/weather/` as a template.
2. Fill `manifest.json` and `config.json`.
3. Document the runtime mapping in `runtime.md`.
4. Keep secrets in `.env`, never in the plugin folder.

## Testing guide

- Unit-test discovery against a temp `plugins/` tree.
- Assert the plugin is skipped if it lives under `examples/`.
- Do not start a second process.

## Sample plugins

| Sample | Path | Notes |
| --- | --- | --- |
| UPS | `plugins/examples/ups/` | Battery telemetry sketch |
| Weather | `plugins/examples/weather/` | Outdoor conditions sketch |
| MQTT | `plugins/examples/mqtt/` | Broker subscription sketch |

None of these are production plugins.
