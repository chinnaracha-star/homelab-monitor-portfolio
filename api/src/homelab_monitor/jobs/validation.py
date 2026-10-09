"""Compare the job registry with operations.factories.

The comparison only reads metadata. It does not call the factory lambdas.
"""

from dataclasses import dataclass

from homelab_monitor.jobs.engine import JobDefinition
from homelab_monitor.operations import factories
from homelab_monitor.settings import Settings

EXPECTED: dict[str, dict[str, str]] = {
    "offline_monitor": {
        "implementation": "homelab_monitor.offline_monitor.run_offline_monitor",
        "schedule": "alert_evaluation_interval_seconds (default 30s)",
        "enabled": "always started by operations.factories",
    },
    "infrastructure_monitor": {
        "implementation": "homelab_monitor.infrastructure_monitor.run_infrastructure_monitor",
        "schedule": "infrastructure_refresh_seconds (default 30s)",
        "enabled": "always started by operations.factories",
    },
    "telegram_reports": {
        "implementation": "homelab_monitor.telegram_reports.run_telegram_reports",
        "schedule": "tick every 60s",
        "enabled": "always started by operations.factories",
    },
    "notification_worker": {
        "implementation": "homelab_monitor.notification_worker.run_notification_worker",
        "schedule": "poll about every 0.25s",
        "enabled": "notification_worker_enabled",
    },
    "photo_watcher": {
        "implementation": "homelab_monitor.photo_watcher.run_photo_watcher",
        "schedule": "photo scan interval (default 5s)",
        "enabled": "photo_watcher_enabled",
    },
    "sqlite_backup": {
        "implementation": "homelab_monitor.sqlite_backup.run_sqlite_backup",
        "schedule": "next backup time, or 3600s while backup is disabled",
        "enabled": "backup_enabled",
    },
}


@dataclass(frozen=True)
class RegistryValidation:
    status: str
    validated: bool
    registered_jobs: int
    factory_jobs: int
    warnings: tuple[str, ...]
    missing_jobs: tuple[str, ...]
    duplicated_jobs: tuple[str, ...]
    registry_only: tuple[str, ...]
    factory_only: tuple[str, ...]


def factory_callables(settings: Settings) -> dict[str, str]:
    found: dict[str, str] = {}
    for name, factory in factories(settings).items():
        called = [item for item in factory.__code__.co_names if item.startswith("run_")]
        found[name] = called[-1] if called else ""
    return found


def validate_jobs(
    jobs: list[JobDefinition],
    factory_names: dict[str, str],
) -> RegistryValidation:
    duplicated = tuple(
        sorted({job.name for job in jobs if sum(item.name == job.name for item in jobs) > 1})
    )
    by_name: dict[str, JobDefinition] = {}
    for job in jobs:
        by_name.setdefault(job.name, job)
    registry_names = set(by_name)
    factory_set = set(factory_names)
    registry_only = tuple(sorted(registry_names - factory_set))
    factory_only = tuple(sorted(factory_set - registry_names))
    warnings: list[str] = []
    if duplicated:
        warnings.append(f"duplicated jobs: {', '.join(duplicated)}")
    if registry_only:
        warnings.append(f"registry-only jobs: {', '.join(registry_only)}")
    if factory_only:
        warnings.append(f"factory-only jobs: {', '.join(factory_only)}")
    missing = tuple(sorted(set(registry_only) | set(factory_only)))
    if missing:
        warnings.append(f"missing jobs: {', '.join(missing)}")
    for name in sorted(registry_names & factory_set):
        job = by_name[name]
        expected = EXPECTED.get(name)
        called = factory_names[name]
        if expected is None:
            warnings.append(f"{name}: no expected contract")
            continue
        if job.implementation != expected["implementation"]:
            warnings.append(f"{name}: implementation path mismatch")
        elif not job.implementation.endswith(f".{called}") or not called:
            warnings.append(f"{name}: factory callable mismatch")
        if job.schedule != expected["schedule"]:
            warnings.append(f"{name}: schedule description mismatch")
        if job.enabled != expected["enabled"]:
            warnings.append(f"{name}: enabled flag source mismatch")
    status = "pass" if not warnings else "warning"
    return RegistryValidation(
        status=status,
        validated=True,
        registered_jobs=len(registry_names),
        factory_jobs=len(factory_set),
        warnings=tuple(warnings),
        missing_jobs=missing,
        duplicated_jobs=duplicated,
        registry_only=registry_only,
        factory_only=factory_only,
    )


def validate_runtime(settings: Settings, jobs: list[JobDefinition]) -> RegistryValidation:
    return validate_jobs(jobs, factory_callables(settings))
