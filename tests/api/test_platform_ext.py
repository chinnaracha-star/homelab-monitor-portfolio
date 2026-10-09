from collections.abc import Callable

from fastapi.testclient import TestClient


def test_plugins_list_builtin(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    body = client.get("/api/v1/plugins", headers=auth_header()).json()
    names = {item["id"] for item in body}
    assert {"core-system", "telegram", "photo-monitor", "backup", "analytics"} <= names
    assert "example-ups" not in names
    sample = next(item for item in body if item["id"] == "core-system")
    assert sample["name"]
    assert sample["version"]
    assert sample["author"]
    assert sample["capabilities"]
    assert sample["status"]
    assert sample["health"]
    assert "configuration" in sample


def test_plugin_lifecycle(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    stopped = client.post(
        "/api/v1/plugins/telegram/lifecycle",
        headers=auth_header(),
        json={"action": "stop"},
    )
    assert stopped.status_code == 200
    assert stopped.json()["lifecycle"] == "stopped"
    started = client.post(
        "/api/v1/plugins/telegram/lifecycle",
        headers=auth_header(),
        json={"action": "start"},
    )
    assert started.status_code == 200
    assert started.json()["lifecycle"] == "started"


def test_assistant_briefing_is_read_only(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    body = client.get("/api/v1/assistant/briefing", headers=auth_header()).json()
    assert body["never_modifies_platform"] is True
    assert body["provider"] == "local-heuristic"
    assert "summary" in body
    assert "root_cause" in body
    assert "possible_impact" in body
    assert "recommended_checks" in body
    assert "recommended_actions" in body


def test_knowledge_and_topology(
    client: TestClient,
    auth_header: Callable[..., dict[str, str]],
) -> None:
    knowledge = client.get("/api/v1/knowledge", headers=auth_header())
    assert knowledge.status_code == 200
    assert "items" in knowledge.json()
    export = client.get("/api/v1/knowledge/export", headers=auth_header())
    assert export.status_code == 200
    assert "kind,timestamp,title" in export.text
    topology = client.get("/api/v1/system/topology", headers=auth_header())
    assert topology.status_code == 200
    ids = {node["id"] for node in topology.json()["nodes"]}
    assert ids == {"internet", "router", "ubuntu", "docker", "immich", "qnap", "photo", "telegram"}
    assert "flowchart LR" in topology.json()["mermaid"]
