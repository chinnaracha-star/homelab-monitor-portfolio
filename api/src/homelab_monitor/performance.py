from __future__ import annotations

import statistics
import subprocess
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from homelab_monitor.models import OpsSnapshot
from homelab_monitor.photo_watcher import get_photo_watcher_service
from homelab_monitor.schemas import PerformanceSnapshot, PerformanceWindow
from homelab_monitor.settings import Settings
from homelab_monitor.sqlite_backup import load_state

_API_SAMPLES: deque[float] = deque(maxlen=200)


def record_api_duration(duration_ms: float) -> None:
    if duration_ms >= 0:
        _API_SAMPLES.append(float(duration_ms))


def api_latency_ms() -> float | None:
    if not _API_SAMPLES:
        return None
    return round(statistics.mean(_API_SAMPLES), 2)


def collect_and_store(
    db: Session, settings: Settings, *, query_ms: float | None
) -> PerformanceSnapshot:
    sample = _sample(settings, query_ms=query_ms)
    db.add(
        OpsSnapshot(
            kind="performance",
            observed_at=datetime.now(UTC),
            payload=sample,
        )
    )
    cutoff = datetime.now(UTC) - timedelta(days=31)
    stale = db.scalars(
        select(OpsSnapshot).where(
            OpsSnapshot.kind == "performance", OpsSnapshot.observed_at < cutoff
        )
    ).all()
    for row in stale:
        db.delete(row)
    db.commit()
    return snapshot_from_history(db, settings, current=sample)


def snapshot_from_history(
    db: Session, settings: Settings, *, current: dict | None = None
) -> PerformanceSnapshot:
    current = current or _sample(settings, query_ms=None)
    rows = list(
        db.scalars(
            select(OpsSnapshot)
            .where(OpsSnapshot.kind == "performance")
            .order_by(OpsSnapshot.observed_at.desc())
            .limit(2000)
        ).all()
    )
    now = datetime.now(UTC)
    return PerformanceSnapshot(
        generated_at=now,
        performance_score=_performance_score(current),
        reliability_score=_reliability_score(current),
        current=current,
        windows={
            "24h": _window(rows, now - timedelta(hours=24)),
            "7d": _window(rows, now - timedelta(days=7)),
            "30d": _window(rows, now - timedelta(days=30)),
        },
    )


def _sample(settings: Settings, *, query_ms: float | None) -> dict:
    db_path = _db_path(settings.database_url)
    size = db_path.stat().st_size if db_path and db_path.is_file() else 0
    backup = load_state(settings).get("latest") or {}
    watcher = get_photo_watcher_service(settings)
    docker = _docker_stats()
    return {
        "api_ms": api_latency_ms(),
        "query_ms": query_ms,
        "sqlite_bytes": size,
        "sqlite_growth_bytes": size - int(backup.get("uncompressed_bytes") or 0)
        if backup.get("uncompressed_bytes")
        else None,
        "docker_cpu_percent": docker.get("cpu"),
        "docker_memory_bytes": docker.get("memory"),
        "photo_scan_ms": getattr(watcher, "last_scan_duration_ms", None),
        "backup_seconds": backup.get("duration_seconds"),
        "telegram_ms": None,
        "scheduler_seconds": backup.get("duration_seconds"),
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _window(rows: list[OpsSnapshot], start: datetime) -> PerformanceWindow:
    start_utc = _as_utc(start)
    payloads = [row.payload for row in rows if _as_utc(row.observed_at) >= start_utc]

    def avg(key: str) -> float | None:
        values = [float(item[key]) for item in payloads if isinstance(item.get(key), (int, float))]
        if not values:
            return None
        return round(statistics.mean(values), 2)

    return PerformanceWindow(
        samples=len(payloads),
        api_ms=avg("api_ms"),
        query_ms=avg("query_ms"),
        photo_scan_ms=avg("photo_scan_ms"),
        backup_seconds=avg("backup_seconds"),
    )


def _performance_score(sample: dict) -> int:
    score = 100
    api = sample.get("api_ms")
    query = sample.get("query_ms")
    if isinstance(api, int | float):
        if api > 250:
            score -= 25
        elif api > 100:
            score -= 10
    if isinstance(query, int | float):
        if query > 50:
            score -= 20
        elif query > 15:
            score -= 8
    return max(0, min(100, score))


def _reliability_score(sample: dict) -> int:
    score = 100
    if sample.get("backup_seconds") is None:
        score -= 15
    if sample.get("photo_scan_ms") is None:
        score -= 10
    cpu = sample.get("docker_cpu_percent")
    if isinstance(cpu, int | float) and cpu > 90:
        score -= 20
    return max(0, min(100, score))


def _db_path(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite:///"):
        return None
    raw = database_url.removeprefix("sqlite:///")
    if not raw or raw == ":memory:":
        return None
    return Path(raw)


def _docker_stats() -> dict:
    try:
        result = subprocess.run(
            [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {}
    if result.returncode != 0:
        return {}
    cpu_total = 0.0
    mem_total = 0
    count = 0
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3 or "homelab-monitor" not in parts[0]:
            continue
        cpu_total += float(parts[1].replace("%", "") or 0)
        mem = parts[2].split("/")[0].strip()
        mem_total += _parse_bytes(mem)
        count += 1
    if not count:
        return {}
    return {"cpu": round(cpu_total, 2), "memory": mem_total}


def _parse_bytes(value: str) -> int:
    number = "".join(ch for ch in value if ch.isdigit() or ch == ".")
    try:
        amount = float(number or 0)
    except ValueError:
        return 0
    upper = value.upper()
    if "GI" in upper or "GB" in upper:
        return int(amount * 1024**3)
    if "MI" in upper or "MB" in upper:
        return int(amount * 1024**2)
    if "KI" in upper or "KB" in upper:
        return int(amount * 1024)
    return int(amount)


def time_query(db: Session) -> float:
    started = time.perf_counter()
    db.execute(text("SELECT 1"))
    return round((time.perf_counter() - started) * 1000, 2)
