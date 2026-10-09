#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "" ]]; then
  echo "usage: $0 /path/to/backup-directory" >&2
  exit 1
fi

SOURCE="$(cd "$1" && pwd)"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_DEST="${HOMELAB_BACKUP_DB:-}"
LOG_DEST="${HOMELAB_BACKUP_LOG_DIR:-}"
CONFIG_DEST="${HOMELAB_RESTORE_CONFIG_DIR:-}"

if [[ ! -f "$SOURCE/MANIFEST" ]]; then
  echo "error: $SOURCE is not a HomeLab Monitor backup directory" >&2
  exit 1
fi

if [[ -z "$DB_DEST" ]]; then
  if [[ -d /var/lib/homelab-monitor ]]; then
    DB_DEST=/var/lib/homelab-monitor/homelab-monitor.db
  else
    mkdir -p "$ROOT_DIR/data"
    DB_DEST="$ROOT_DIR/data/homelab-monitor.db"
  fi
fi

if [[ -z "$LOG_DEST" ]]; then
  if [[ -d /var/log/homelab-monitor ]]; then
    LOG_DEST=/var/log/homelab-monitor
  else
    LOG_DEST="$ROOT_DIR/logs"
  fi
fi

if [[ -f "$SOURCE/sqlite/homelab-monitor.db" ]]; then
  mkdir -p "$(dirname "$DB_DEST")"
  cp -- "$SOURCE/sqlite/homelab-monitor.db" "$DB_DEST"
  echo "restored database to $DB_DEST"
else
  echo "warning: backup has no SQLite database" >&2
fi

if [[ -f "$SOURCE/logs/logs.tar.gz" ]]; then
  mkdir -p "$LOG_DEST"
  tar -xzf "$SOURCE/logs/logs.tar.gz" -C "$(dirname "$LOG_DEST")"
  echo "restored logs toward $(dirname "$LOG_DEST")"
else
  echo "warning: backup has no logs archive" >&2
fi

if [[ -n "$CONFIG_DEST" && -f "$SOURCE/config/config.tar.gz" ]]; then
  mkdir -p "$CONFIG_DEST"
  tar -xzf "$SOURCE/config/config.tar.gz" -C "$CONFIG_DEST"
  echo "extracted configuration archive into $CONFIG_DEST"
elif [[ -f "$SOURCE/config/config.tar.gz" ]]; then
  echo "configuration archive: $SOURCE/config/config.tar.gz"
  echo "set HOMELAB_RESTORE_CONFIG_DIR to extract it automatically"
fi

echo "stop the API before replacing a live database, then start it and run alembic upgrade head"
