#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_ROOT="${HOMELAB_BACKUP_DIR:-$ROOT_DIR/backups}"
DEST="$BACKUP_ROOT/$STAMP"

DB_PATH="${HOMELAB_BACKUP_DB:-}"
LOG_DIR="${HOMELAB_BACKUP_LOG_DIR:-}"
CONFIG_PATHS="${HOMELAB_BACKUP_CONFIG:-}"

if [[ -z "$DB_PATH" ]]; then
  if [[ -f /var/lib/homelab-monitor/homelab-monitor.db ]]; then
    DB_PATH=/var/lib/homelab-monitor/homelab-monitor.db
  elif [[ -f "$ROOT_DIR/data/homelab-monitor.db" ]]; then
    DB_PATH="$ROOT_DIR/data/homelab-monitor.db"
  fi
fi

if [[ -z "$LOG_DIR" ]]; then
  if [[ -d /var/log/homelab-monitor ]]; then
    LOG_DIR=/var/log/homelab-monitor
  elif [[ -d "$ROOT_DIR/logs" ]]; then
    LOG_DIR="$ROOT_DIR/logs"
  fi
fi

if [[ -z "$CONFIG_PATHS" ]]; then
  CONFIG_PATHS=""
  for candidate in \
    /etc/homelab-monitor \
    "$ROOT_DIR/.env" \
    "$ROOT_DIR/.env.production.example" \
    "$ROOT_DIR/deploy/systemd" \
    "$ROOT_DIR/deploy/nginx"
  do
    if [[ -e "$candidate" ]]; then
      CONFIG_PATHS+="$candidate"$'\n'
    fi
  done
fi

mkdir -p "$DEST/sqlite" "$DEST/logs" "$DEST/config"

if [[ -n "$DB_PATH" && -f "$DB_PATH" ]]; then
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$DB_PATH" "PRAGMA wal_checkpoint(FULL);" >/dev/null || true
    sqlite3 "$DB_PATH" ".backup '$DEST/sqlite/homelab-monitor.db'"
  else
    cp -- "$DB_PATH" "$DEST/sqlite/homelab-monitor.db"
    [[ -f "$DB_PATH-wal" ]] && cp -- "$DB_PATH-wal" "$DEST/sqlite/homelab-monitor.db-wal"
    [[ -f "$DB_PATH-shm" ]] && cp -- "$DB_PATH-shm" "$DEST/sqlite/homelab-monitor.db-shm"
  fi
else
  echo "warning: SQLite database not found; skipping database backup" >&2
fi

if [[ -n "$LOG_DIR" && -d "$LOG_DIR" ]]; then
  tar -C "$(dirname "$LOG_DIR")" -czf "$DEST/logs/logs.tar.gz" "$(basename "$LOG_DIR")"
else
  echo "warning: log directory not found; skipping log backup" >&2
fi

CONFIG_LIST=()
while IFS= read -r line; do
  [[ -n "$line" ]] && CONFIG_LIST+=("$line")
done <<< "$CONFIG_PATHS"

if ((${#CONFIG_LIST[@]})); then
  tar -czf "$DEST/config/config.tar.gz" -- "${CONFIG_LIST[@]}"
else
  echo "warning: no configuration paths found; skipping config backup" >&2
fi

printf '%s\n' "$STAMP" > "$DEST/MANIFEST"
echo "$DEST"
