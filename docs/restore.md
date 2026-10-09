# Restore SQLite from gzip backup

HomeLab Monitor does **not** restore automatically. Follow these steps on the
Docker host. Do not overwrite the live database while the API is writing to it.

## 1. Choose a verified backup

```bash
ls -lh /var/lib/docker/volumes/homelab-monitor_homelab-data/_data/backups/
# or, inside the API container:
docker compose exec api ls -lh /var/lib/homelab-monitor/backups
```

Use a `homelab-monitor-YYYY-MM-DD-HHMMSS.sqlite3.gz` file whose sidecar JSON
shows `"integrity": "PASS"`. Do not restore `*.failed` files.

## 2. Stop services that use the database

```bash
cd /path/to/homelab-monitor
docker compose stop api dashboard
```

Stopping the dashboard is optional. The API **must** be stopped.

## 3. Locate the live database

```bash
DATA="$(docker volume inspect homelab-monitor_homelab-data --format '{{.Mountpoint}}')"
echo "$DATA/homelab-monitor.db"
```

Inside Compose the path is `/var/lib/homelab-monitor/homelab-monitor.db`.

## 4. Restore the database file

```bash
BACKUP=homelab-monitor-2026-09-21-020000.sqlite3.gz
sudo gzip -t "$DATA/backups/$BACKUP"
sudo cp -a "$DATA/homelab-monitor.db" "$DATA/homelab-monitor.db.pre-restore"
sudo gzip -dc "$DATA/backups/$BACKUP" | sudo tee "$DATA/homelab-monitor.db" >/dev/null
```

If the host cannot see the volume, copy the gzip out, decompress locally, then
`docker cp` the `.db` into a stopped API container at
`/var/lib/homelab-monitor/homelab-monitor.db`.

Remove leftover WAL files so SQLite does not replay stale journals:

```bash
sudo rm -f "$DATA/homelab-monitor.db-wal" "$DATA/homelab-monitor.db-shm"
```

## 5. Permissions

The API container runs as the image user. Match ownership to the previous
database file:

```bash
sudo chown --reference="$DATA/homelab-monitor.db.pre-restore" "$DATA/homelab-monitor.db"
sudo chmod 640 "$DATA/homelab-monitor.db"
```

If `--reference` is unavailable, use the UID/GID from `ls -ln` on the old file.

## 6. Restart

```bash
docker compose start api dashboard
docker compose ps
```

The API entrypoint runs `alembic upgrade head` so schema revisions newer than
the backup are applied.

## 7. Verification

```bash
docker compose exec api python -c "import sqlite3; c=sqlite3.connect('/var/lib/homelab-monitor/homelab-monitor.db'); print(c.execute('PRAGMA integrity_check').fetchone())"
curl -fsS http://127.0.0.1:18081/api/v1/health
```

Sign in to the dashboard and confirm Agents, Backup (SQLite cards), and Photo
Monitor still load. Send a Telegram test only if you already use Telegram.

## Recovery checklist

- [ ] Selected a PASS gzip, not a `.failed` file
- [ ] API stopped before overwrite
- [ ] Pre-restore copy of the live `.db` exists
- [ ] `gzip -t` succeeded
- [ ] WAL/SHM removed
- [ ] Ownership matches the previous file
- [ ] API started and health is 200
- [ ] `PRAGMA integrity_check` is `ok`
- [ ] Dashboard pages load with expected agents and settings
