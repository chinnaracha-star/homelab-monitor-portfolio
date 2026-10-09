# Ubuntu agent guide

The `homelab-agent` Python package collects one host's system health and sends
authenticated reports to the central HomeLab Monitor API.

## Install

Ubuntu requires Python 3.12 or newer and the virtual-environment package:

```bash
sudo apt install python3-venv
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Configuration

Copy `deploy/systemd/agent.env.example` to a private location and set:

- `HOMELAB_SERVER_URL`: central API URL
- `HOMELAB_AGENT_NAME`: unique agent name
- `HOMELAB_AGENT_TOKEN`: token returned once during registration
- `HOMELAB_REPORT_INTERVAL`: fallback interval before server control is received
- `HOMELAB_REQUEST_TIMEOUT`: timeout for each HTTP request
- `HOMELAB_RETRY_ATTEMPTS`: bounded attempts for network errors and HTTP 5xx
- `HOMELAB_BUFFER_PATH`: persistent local SQLite queue
- `HOMELAB_BUFFER_MAX_REPORTS`: maximum queued reports
- CPU, memory, and disk warning thresholds

Protect the environment file:

```bash
sudo chmod 600 /etc/homelab-monitor/agent.env
```

The token is represented as a secret value internally and is never included in
structured logs.

## Register the agent

Start the API, then use the copy-paste registration example in
[`docs/api.md`](api.md#register-an-agent). It loads the registration key directly
from the repository's `.env` file using `python-dotenv`, so no
`REGISTRATION_KEY` shell export is required.

The example stores the one-time credential in the current shell as
`AGENT_TOKEN`. Write that value to the protected agent environment file before
closing the shell.

## Collect once

The collect command does not require server credentials:

```bash
.venv/bin/homelab-agent collect
```

It prints formatted JSON containing hostname, OS and kernel, CPU, memory, disks,
load averages, uptime, and temperatures. Missing hardware sensor support returns
`temperature_status: unavailable` and does not fail the system check.

## Run manually

```bash
.venv/bin/homelab-agent --env-file ./agent.env run
```

The agent checks in, applies the server's `next_report_in` and configuration
revision, retries older buffered reports, collects a full snapshot, and uploads
the current report.

Use `Ctrl+C` or send `SIGTERM` to stop cleanly. The HTTP client and local queue
are closed before exit.

## Run with systemd

The unit file is `deploy/systemd/homelab-agent.service`. It:

- starts `homelab-agent run`
- reads `EnvironmentFile=/opt/homelab-monitor/state/agent.env` (no tokens in the unit)
- uses `Restart=always` and `RestartSec=5`
- starts after `network-online.target`
- is enabled with `WantedBy=multi-user.target`

Copy `deploy/systemd/agent.env.example` to `state/agent.env` in the checkout, then
install and enable the service:

```bash
sudo cp deploy/systemd/homelab-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable homelab-agent
sudo systemctl start homelab-agent
sudo systemctl status homelab-agent
journalctl -u homelab-agent -f
```

If the checkout is not `/opt/homelab-monitor`, edit `WorkingDirectory`,
`EnvironmentFile`, `ExecStart`, and `ReadWritePaths` in the installed unit
before `daemon-reload`.

The unit assumes:

- application checkout at `/opt/homelab-monitor`
- virtual environment at `/opt/homelab-monitor/.venv`
- dedicated `homelab-monitor` user and group
- environment file at `/opt/homelab-monitor/state/agent.env`
- writable state under `/opt/homelab-monitor/state` and `/var/lib/homelab-monitor`

## Offline buffer and retries

Connection refusal, DNS failure, timeout, and HTTP 5xx use bounded exponential
backoff. If delivery still fails, the complete report is written transactionally
to SQLite. On recovery, reports are retried oldest first with the same report ID,
using server-side idempotency to prevent duplicates.

HTTP 401 and 403 are not rapidly retried. They emit `authentication_failed` and
increase the next loop delay to at least five minutes. Replace the invalid token
instead of restarting repeatedly.

When the queue reaches its configured limit, the oldest report is removed and
the structured `report_buffered` event records `dropped_oldest`.

## Troubleshooting

- `Configuration error`: verify server URL and agent token are present for `run`.
- HTTP 401/403: register or rotate the agent credential and update the protected
  environment file.
- Reports remain buffered: check DNS, routing, API health, and HTTPS trust.
- No temperature values: install/configure hardware sensor support if available;
  this is not fatal.
- Permission denied for buffer: ensure the service user owns its state directory.
