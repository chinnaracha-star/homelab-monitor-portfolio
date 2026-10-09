# Photo Monitor

Photo Monitor polls one or more configured NAS folders for **new image files**,
stores an event in SQLite, and sends a Telegram **photo** for **each** new file
(caption includes folder, filename, and time). If `sendPhoto` fails, that file
falls back to a text caption only. It does not analyze images, talk to CCTV, or
use OpenCV.

## Watch rules

Supported extensions: `jpg`, `jpeg`, `png`, `heic`, `gif`, `bmp`, `webp`.

Ignored:

- hidden files (names starting with `.`)
- incomplete copies ending in `.tmp` or `.part`

The first scan of each watch folder (after process start, or after that folder
is added) is a baseline. Existing files are not notified. Later scans persist
only files that are new relative to that folder’s baseline and not already in
`photo_events`. Removing a folder drops its in-memory baseline; other folders
are unchanged.

Polling is used instead of inotify so CIFS/NFS mounts work.

## Settings

Configure from the dashboard **Settings** page (admin):

- Enable / Disable
- Watch Folders (one or more paths; legacy `watch_folder` is migrated into this list)
- Recursive Scan
- Scan Interval: 5 / 10 / 30 / 60 seconds
- Maximum Events: 100 / 500 / 1000
- Auto Delete History: Never / 30 days / 90 days

Default watch folders (new installs): `/data/photos`, `/data/photos/library-a`,
`/data/photos/library-b`, `/data/photos/library-c`, `/data/photos/library-d`,
`/data/photos/library-e`. Override with `HOMELAB_PHOTO_WATCH_FOLDERS` (JSON list)
or the legacy `HOMELAB_PHOTO_WATCH_FOLDER`. Existing `watch_folder` rows are
migrated into `watch_folders` and are not overwritten.

## Docker

The API container does not bind-mount the NAS path by default (the compose
file must stay valid when the host path is missing). To watch a host folder:

```yaml
# docker-compose.yml api.volumes
- ${HOMELAB_PHOTO_WATCH_FOLDER:-/data/photos}:/data/photos:ro
```

Then set Watch Folder in Settings to `/data/photos`.

## API

- `GET /api/v1/photos` — latest events (`limit` 1–100, default 20)
- `GET /api/v1/photos/latest` — newest event, or `404 latest_photo_not_found`
- `GET /api/v1/photos/stats` — includes legacy `watch_folder` plus `watch_folders`,
  `watch_folder_labels`, `indexed_files`, `last_folder`, and `status`
- `GET /api/v1/photos/settings`
- `PUT /api/v1/photos/settings` (admin) — accepts `watch_folders` and/or legacy `watch_folder`

Read endpoints: admin, operator, viewer.
