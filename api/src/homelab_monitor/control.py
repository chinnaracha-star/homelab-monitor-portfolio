from homelab_monitor.models import Agent
from homelab_monitor.schemas import AgentControlResponse
from homelab_monitor.settings import Settings


def _version_key(value: str) -> tuple[int, ...]:
    numeric = value.split("-", maxsplit=1)[0]
    try:
        return tuple(int(part) for part in numeric.split("."))
    except ValueError:
        return (0,)


def build_agent_control(
    agent: Agent,
    settings: Settings,
    current_config_revision: int,
) -> AgentControlResponse:
    configuration = agent.configuration
    include_configuration = (
        configuration is not None and current_config_revision < configuration.revision
    )

    return AgentControlResponse(
        next_report_in=settings.agent_report_interval_seconds,
        config_revision=configuration.revision if configuration else 0,
        configuration=configuration.settings if include_configuration else None,
        minimum_agent_version=settings.minimum_agent_version,
        latest_agent_version=settings.latest_agent_version,
        update_available=_version_key(agent.version) < _version_key(settings.latest_agent_version),
        commands=[],
    )
