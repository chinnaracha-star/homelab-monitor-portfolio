import json
import logging
from pathlib import Path

from homelab_monitor.settings import Settings

logger = logging.getLogger("homelab_monitor.photo_watcher")

SCHEMA_VERSION = 1


def baseline_file_path(settings: Settings) -> Path:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        db_path = Path(url.removeprefix("sqlite:///")).expanduser()
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        return db_path.resolve().parent / "photo_baseline.json"
    return Path("/var/lib/homelab-monitor/photo_baseline.json")


def load_baseline(path: Path) -> dict[str, set[tuple[str, str]]]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("photo_baseline_load_failed path=%s", path)
        return {}
    if not isinstance(payload, dict) or int(payload.get("version") or 0) != SCHEMA_VERSION:
        logger.warning("photo_baseline_ignored path=%s", path)
        return {}
    folders = payload.get("folders")
    if not isinstance(folders, dict):
        return {}
    restored: dict[str, set[tuple[str, str]]] = {}
    for watch_root, rows in folders.items():
        if not isinstance(watch_root, str) or not isinstance(rows, list):
            continue
        keys: set[tuple[str, str]] = set()
        for row in rows:
            if (
                isinstance(row, list)
                and len(row) == 2
                and isinstance(row[0], str)
                and isinstance(row[1], str)
            ):
                keys.add((row[0], row[1]))
        restored[watch_root] = keys
    logger.info("photo_baseline_loaded path=%s folders=%s", path, len(restored))
    return restored


def save_baseline(path: Path, seen: dict[str, set[tuple[str, str]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": SCHEMA_VERSION,
        "folders": {
            watch_root: [list(item) for item in sorted(keys)]
            for watch_root, keys in sorted(seen.items())
        },
    }
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=True, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
    logger.info("photo_baseline_saved path=%s folders=%s", path, len(seen))
