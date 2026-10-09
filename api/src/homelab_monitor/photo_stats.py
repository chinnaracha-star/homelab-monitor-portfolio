from homelab_monitor.connectors.base import ConnectorSnapshot
from homelab_monitor.connectors.http import as_float, as_int, as_str
from homelab_monitor.connectors.qnap import storage_health

PHOTO_SERVICE_NAMES = ("immich", "qumagie", "qnap")


def build_photo_stats(services: dict[str, ConnectorSnapshot]) -> dict[str, object]:
    immich = _summary(services.get("immich"))
    qumagie = _summary(services.get("qumagie"))
    qnap = _summary(services.get("qnap"))
    used = as_int(qnap.get("used_bytes"))
    free = as_int(qnap.get("free_bytes"))
    capacity = as_int(qnap.get("capacity_bytes"))
    percent = as_float(qnap.get("storage_percent") or qnap.get("storage_used_percent"))
    thumbnail_queue = as_int(immich.get("thumbnail_queue"))
    face_queue = as_int(immich.get("face_queue") or immich.get("face_jobs"))
    last_scan = as_str(immich.get("last_scan") or qumagie.get("last_scan"))
    return {
        "indexed_photos": as_int(immich.get("indexed_photos") or qumagie.get("indexed_photos")),
        "indexed_videos": as_int(immich.get("indexed_videos")),
        "albums": as_int(immich.get("albums")),
        "users": as_int(immich.get("users")),
        "storage_used": used,
        "storage_free": free,
        "storage_percent": percent,
        "thumbnail_queue": thumbnail_queue,
        "face_queue": face_queue,
        "last_scan": last_scan,
        "capacity_bytes": capacity,
        "storage_health": as_str(qnap.get("storage_health"), storage_health(percent)),
        "storage_percent_metric": percent,
        "thumbnail_queue_metric": thumbnail_queue,
        "face_queue_metric": face_queue,
        "immich_health": as_int(immich.get("immich_health")),
        "qumagie_health": as_int(qumagie.get("qumagie_health")),
    }


def _summary(snapshot: ConnectorSnapshot | None) -> dict:
    if snapshot is None:
        return {}
    return snapshot.summary
