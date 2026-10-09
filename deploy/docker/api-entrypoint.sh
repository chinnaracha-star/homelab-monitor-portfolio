#!/bin/sh
set -eu

mkdir -p "${HOMELAB_DATA_DIR:-/var/lib/homelab-monitor}" \
  "${HOMELAB_LOG_DIR:-/var/log/homelab-monitor}"

alembic upgrade head
exec uvicorn homelab_monitor.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --proxy-headers \
  --forwarded-allow-ips="${HOMELAB_FORWARDED_ALLOW_IPS:-*}"
