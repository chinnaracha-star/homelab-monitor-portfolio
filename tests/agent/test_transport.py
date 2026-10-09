import json

import httpx
import pytest

from homelab_agent.config import AgentSettings
from homelab_agent.transport import AgentTransport, AuthenticationError


def agent_settings(**overrides) -> AgentSettings:
    return AgentSettings(
        server_url="http://monitor.test",
        agent_name="monitor",
        agent_token="secret-agent-token",
        retry_initial_backoff=0,
        **overrides,
    )


def control_response() -> dict[str, object]:
    return {
        "next_report_in": 75,
        "config_revision": 2,
        "configuration": {"modules": {"system": {"cpu_warning_percent": 85}}},
        "minimum_agent_version": "0.1.0",
        "latest_agent_version": "0.1.0",
        "update_available": False,
        "commands": [],
    }


def test_check_in_uses_bearer_authentication_and_parses_control() -> None:
    captured_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(200, json=control_response())

    client = httpx.Client(
        base_url="http://monitor.test",
        transport=httpx.MockTransport(handler),
    )
    transport = AgentTransport(agent_settings(), client=client)

    control = transport.check_in(config_revision=1)

    assert captured_request is not None
    assert captured_request.url.path == "/api/v1/agent/check-ins"
    assert captured_request.headers["authorization"] == "Bearer secret-agent-token"
    assert json.loads(captured_request.content)["config_revision"] == 1
    assert control.next_report_in == 75
    assert control.config_revision == 2


def test_retries_server_errors_with_bounded_attempts() -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503)
        return httpx.Response(200, json=control_response())

    client = httpx.Client(
        base_url="http://monitor.test",
        transport=httpx.MockTransport(handler),
    )
    transport = AgentTransport(
        agent_settings(retry_attempts=3),
        client=client,
        sleeper=sleeps.append,
    )

    transport.check_in(config_revision=0)

    assert attempts == 3
    assert sleeps == [0, 0]


def test_authentication_failure_is_not_retried() -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(401)

    client = httpx.Client(
        base_url="http://monitor.test",
        transport=httpx.MockTransport(handler),
    )
    transport = AgentTransport(agent_settings(retry_attempts=5), client=client)

    with pytest.raises(AuthenticationError):
        transport.check_in(config_revision=0)

    assert attempts == 1
