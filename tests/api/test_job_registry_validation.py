import logging

from homelab_monitor.jobs.engine import JobDefinition, default_engine
from homelab_monitor.jobs.startup import log_job_registry_validation
from homelab_monitor.jobs.validation import factory_callables, validate_jobs
from homelab_monitor.settings import get_settings


def _job(name: str, **overrides: str) -> JobDefinition:
    current = default_engine().describe(name)
    data = {
        "name": current.name,
        "description": current.description,
        "category": current.category,
        "implementation": current.implementation,
        "schedule": current.schedule,
        "enabled": current.enabled,
        "owner": current.owner,
    }
    data.update(overrides)
    return JobDefinition(**data)


def test_identical_registry_and_factories() -> None:
    settings = get_settings()
    jobs = list(default_engine().jobs())
    result = validate_jobs(jobs, factory_callables(settings))
    assert result.status == "pass"
    assert result.validated is True
    assert result.registered_jobs == 6
    assert result.factory_jobs == 6
    assert result.warnings == ()


def test_missing_registry_job_is_factory_only() -> None:
    jobs = [job for job in default_engine().jobs() if job.name != "sqlite_backup"]
    found = factory_callables(get_settings())
    result = validate_jobs(jobs, found)
    assert result.status == "warning"
    assert "sqlite_backup" in result.factory_only
    assert "sqlite_backup" in result.missing_jobs


def test_missing_factory_job_is_registry_only() -> None:
    jobs = list(default_engine().jobs())
    found = factory_callables(get_settings())
    del found["photo_watcher"]
    result = validate_jobs(jobs, found)
    assert "photo_watcher" in result.registry_only
    assert "photo_watcher" in result.missing_jobs


def test_duplicate_registry_names() -> None:
    jobs = list(default_engine().jobs())
    jobs.append(_job("offline_monitor"))
    result = validate_jobs(jobs, factory_callables(get_settings()))
    assert "offline_monitor" in result.duplicated_jobs
    assert any(item.startswith("duplicated jobs:") for item in result.warnings)


def test_validation_warning_for_schedule_drift(caplog) -> None:
    jobs = [
        _job("offline_monitor", schedule="every hour") if job.name == "offline_monitor" else job
        for job in default_engine().jobs()
    ]
    result = validate_jobs(jobs, factory_callables(get_settings()))
    assert any("schedule description mismatch" in item for item in result.warnings)
    with caplog.at_level(logging.INFO, logger="homelab_monitor.jobs"):
        log_job_registry_validation(get_settings())
    assert "Job registry validation: PASS" in caplog.text
