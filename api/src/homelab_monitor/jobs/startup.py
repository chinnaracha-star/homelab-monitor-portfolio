import logging

from homelab_monitor.jobs.engine import default_engine
from homelab_monitor.jobs.validation import validate_runtime
from homelab_monitor.settings import Settings

logger = logging.getLogger("homelab_monitor.jobs")

_WARNING = (
    "Job registry validation: WARNING missing=%s duplicated=%s registry_only=%s factory_only=%s"
)


def log_job_registry_validation(settings: Settings) -> None:
    try:
        result = validate_runtime(settings, list(default_engine().jobs()))
    except Exception:
        logger.warning(_WARNING, ["validation_failed"], [], [], [])
        return
    if result.status == "pass":
        logger.info("Job registry validation: PASS")
        return
    logger.warning(
        _WARNING,
        list(result.missing_jobs),
        list(result.duplicated_jobs),
        list(result.registry_only),
        list(result.factory_only),
    )
