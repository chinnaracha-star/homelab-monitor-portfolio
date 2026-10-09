# Disaster recovery

This runbook covers loss of the HomeLab Monitor API container, host disk, or
SQLite file. SQLite remains the primary database. There is no PostgreSQL
failover path.

## What is protected

| Asset | Location | How it is copied |
| --- | --- | --- |
| Application database | `/var/lib/homelab-monitor/homelab-monitor.db` | Daily gzip at 02:00 Asia/Bangkok |
| Backup archives | `/var/lib/homelab-monitor/backups` | Same Docker volume `homelab-data` |
| Logs | `/var/log/homelab-monitor` | Volume `homelab-logs` (not in gzip DB backups) |
| Compose + `.env` | Git checkout / host | Operator copies; never commit `.env` |

Photo files live on CIFS mounts and are **not** in the SQLite backup.

## RPO / RTO (homelab)

- Recovery point: last verified daily gzip (up to ~24 hours plus the 02:00 window)
- Recovery time: stop API, restore gzip, start API — typically minutes on the same host

## Host still healthy

Follow `docs/restore.md`. Keep the last good gzip on another disk if the data
volume is the only copy.

## Docker volume lost

1. Recreate the stack: `docker compose up -d`
2. Copy a gzip from off-host storage into
   `/var/lib/homelab-monitor/backups`
3. Restore as in `docs/restore.md`
4. Re-enter Telegram, JWT, and bootstrap secrets from a printed/offline `.env`

## Entire host lost

1. Install Docker and clone this repository
2. Restore `.env` (registration key, JWT secret, Telegram, photo folders)
3. `docker compose up -d`
4. Restore the newest PASS gzip into `homelab-data`
5. Register agents again only if agent tokens were not in the restored database

## What not to do

- Do not point `HOMELAB_DATABASE_URL` at PostgreSQL
- Do not restore while the API is running
- Do not treat TS-253 Pro observer status as an application-database backup
- Do not delete remaining gzip files after a failed backup

## Operator checklist after a disaster

- [ ] API `/health` returns 200
- [ ] Dashboard login works with restored users
- [ ] Agents check in (or re-register)
- [ ] Photo Monitor folders mount
- [ ] Next 02:00 backup completes with integrity PASS
- [ ] Telegram Backup Complete arrives if enabled
