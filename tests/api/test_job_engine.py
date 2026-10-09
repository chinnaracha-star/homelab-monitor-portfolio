from homelab_monitor.jobs.engine import CATEGORIES, JobEngine, default_engine


def test_job_engine_registers_metadata_only() -> None:
    engine = default_engine()
    names = {job.name for job in engine.jobs()}
    assert names == {
        "offline_monitor",
        "infrastructure_monitor",
        "telegram_reports",
        "notification_worker",
        "photo_watcher",
        "sqlite_backup",
    }
    photo = engine.describe("photo_watcher")
    assert photo.category == "Monitoring"
    assert photo.implementation.endswith("run_photo_watcher")
    assert not hasattr(engine, "run")
    assert set(CATEGORIES) >= {job.category for job in engine.jobs()}


def test_job_engine_rejects_unknown_category() -> None:
    from homelab_monitor.jobs.engine import JobDefinition

    engine = JobEngine()
    try:
        engine.register(
            JobDefinition(
                name="custom",
                description="n/a",
                category="Other",
                implementation="unused",
                schedule="unused",
                enabled="unused",
                owner="unused",
            )
        )
    except ValueError as error:
        assert "unknown job category" in str(error)
    else:
        raise AssertionError("expected ValueError")
