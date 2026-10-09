# Photo Monitor QA report

**Date:** 10 Sep 2026  
**Scope:** Production-stability only (logging, diagnostics, automated tests).  
**Not in scope:** API changes, schema changes, watcher redesign, AI/OpenCV.

Automated suite: `tests/api/test_photo_monitor.py` + `tests/api/test_photo_monitor_reliability.py`  
**Result:** 33 passed.

## PASS

- **Qfile Upload** — nested phone path (`S22-Ultra/2026/09/`) inserts one event, sends Telegram, notifies dashboard ingest hub, no duplicate on next scan.
- **Windows Copy** — `jpg` / `png` / `heic` into all six watch-folder names; 18 events, 18 Telegram messages, no duplicates.
- **SMB Upload** — `.tmp` and `.part` ignored until rename; final files detected exactly once.
- **Multi Upload** — bursts of 10, 50, then 100 images; none lost, none duplicated; cycle logs include scan / database / Telegram elapsed ms (each burst under 30s).
- **Large Files** — sparse 10 / 20 / 50 / 100 MB images detected; Telegram still sent (text notification, file not uploaded); scan under 15s.
- **Docker Restart** — new `PhotoWatcherService` loads `photo_baseline.json`; file added while first instance was gone is reported once.
- **Ubuntu Restart** — same process-restart simulation as Docker (baseline file on data volume). Hardware reboot was not executed on the live server in this sprint.
- **NAS Restart** — missing folder is skipped; remaining folder still records photos; when the missing path appears, it is baselined then later new files are detected; watcher does not crash.
- **Telegram Recovery** — outage stores event with `telegram_sent=false` and increments fail count; next photo after “reconnect” sends Telegram; watcher continues.
- **No Lost Photos** — 1000 mixed extensions (root + nested); `events == 1000`; second scan inserts 0.

## Logging

Each completed cycle logs: `photo_watcher_tick`, folders scanned, files discovered, new files, skipped, inserted, Telegram sent, elapsed scan / database / Telegram / cycle ms, `cycle_complete`.

Startup: `photo_watcher_started`. Shutdown/cancel: `photo_watcher_cancelled` (if cancelled) and always `photo_watcher_stopped`.

## Health

After the first successful scan loop, then at most once per 60 seconds: Photo Monitor Health (Running, watching folders, queue `0` because processing is inline, events today, Telegram OK/Failed, baseline size, last successful scan, last successful Telegram).

## Remaining known limitations

- Live Ubuntu reboot and live QNAP reboot were **simulated** in pytest, not performed on production hardware in this sprint.
- Telegram does not attach the image; large-file tests only prove `stat` + text notify.
- Failed Telegram messages are **not retried** for that event (`telegram_sent` stays false). Future photos still notify.
- `max_events` prune (100/500/1000) can drop old history; it does not drop the on-disk baseline, so detections still happen.
- First scan of a folder that just became available is a baseline (files already there are not notified).
