"""Metadata for background work.

Sprint 13.5 registers today's jobs and does not start, stop, or replace
the asyncio loops in operations.factories.
"""

from dataclasses import dataclass

CATEGORIES = (
    "Monitoring",
    "Notification",
    "Backup",
    "Reporting",
    "Maintenance",
    "Infrastructure",
)


@dataclass(frozen=True)
class JobDefinition:
    name: str
    description: str
    category: str
    implementation: str
    schedule: str
    enabled: str
    owner: str


class JobEngine:
    """Registers and describes jobs. It does not execute them."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobDefinition] = {}

    def register(self, job: JobDefinition) -> None:
        if job.category not in CATEGORIES:
            raise ValueError(f"unknown job category: {job.category}")
        if job.name in self._jobs:
            raise ValueError(f"job already registered: {job.name}")
        self._jobs[job.name] = job

    def describe(self, name: str) -> JobDefinition:
        return self._jobs[name]

    def jobs(self) -> tuple[JobDefinition, ...]:
        return tuple(self._jobs[name] for name in sorted(self._jobs))


def builtin_jobs() -> tuple[JobDefinition, ...]:
    return (
        JobDefinition(
            name="offline_monitor",
            description="Marks agents offline and raises alerts.",
            category="Monitoring",
            implementation="homelab_monitor.offline_monitor.run_offline_monitor",
            schedule="alert_evaluation_interval_seconds (default 30s)",
            enabled="always started by operations.factories",
            owner="offline_monitor",
        ),
        JobDefinition(
            name="infrastructure_monitor",
            description="Refreshes infrastructure snapshots.",
            category="Infrastructure",
            implementation="homelab_monitor.infrastructure_monitor.run_infrastructure_monitor",
            schedule="infrastructure_refresh_seconds (default 30s)",
            enabled="always started by operations.factories",
            owner="infrastructure_monitor",
        ),
        JobDefinition(
            name="telegram_reports",
            description="Sends scheduled Telegram reports when they are due.",
            category="Reporting",
            implementation="homelab_monitor.telegram_reports.run_telegram_reports",
            schedule="tick every 60s",
            enabled="always started by operations.factories",
            owner="telegram_reports",
        ),
        JobDefinition(
            name="notification_worker",
            description="Delivers queued alert notifications.",
            category="Notification",
            implementation="homelab_monitor.notification_worker.run_notification_worker",
            schedule="poll about every 0.25s",
            enabled="notification_worker_enabled",
            owner="notification_worker",
        ),
        JobDefinition(
            name="photo_watcher",
            description="Scans photo folders and sends new-photo notices.",
            category="Monitoring",
            implementation="homelab_monitor.photo_watcher.run_photo_watcher",
            schedule="photo scan interval (default 5s)",
            enabled="photo_watcher_enabled",
            owner="photo_watcher",
        ),
        JobDefinition(
            name="sqlite_backup",
            description="Copies the SQLite database on its backup schedule.",
            category="Backup",
            implementation="homelab_monitor.sqlite_backup.run_sqlite_backup",
            schedule="next backup time, or 3600s while backup is disabled",
            enabled="backup_enabled",
            owner="sqlite_backup",
        ),
    )


def default_engine() -> JobEngine:
    engine = JobEngine()
    for job in builtin_jobs():
        engine.register(job)
    return engine
