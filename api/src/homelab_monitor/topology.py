from __future__ import annotations

from homelab_monitor.schemas import (
    ProductionHealthResponse,
    ProductionNetworkResponse,
    ProductionRuntimeResponse,
)


def topology(
    health: ProductionHealthResponse,
    runtime: ProductionRuntimeResponse,
    network: ProductionNetworkResponse,
) -> dict:
    by_name = {item.component: item.status for item in health.checks}

    def node(
        node_id: str, label: str, kind: str, status: str, latency: float | None = None
    ) -> dict:
        return {
            "id": node_id,
            "label": label,
            "kind": kind,
            "status": status,
            "online": status in {"healthy", "excellent", "good"},
            "latency_ms": latency,
        }

    nodes = [
        node("internet", "Internet", "edge", network.internet),
        node("router", "Router / Gateway", "network", "healthy" if network.gateway else "unknown"),
        node("ubuntu", "Ubuntu host", "host", by_name.get("API") or "unknown"),
        node("docker", "Docker", "runtime", by_name.get("Docker") or "unknown"),
        node("immich", "Immich", "app", "healthy" if runtime.docker_available else "unknown"),
        node("qnap", "QNAP", "nas", by_name.get("Storage") or "unknown"),
        node("photo", "Photo Monitor", "app", by_name.get("Photo Monitor") or "unknown"),
        node("telegram", "Telegram", "notify", by_name.get("Telegram") or "unknown"),
    ]
    edges = [
        {"from": "internet", "to": "router"},
        {"from": "router", "to": "ubuntu"},
        {"from": "ubuntu", "to": "docker"},
        {"from": "docker", "to": "immich"},
        {"from": "router", "to": "qnap"},
        {"from": "qnap", "to": "photo"},
        {"from": "ubuntu", "to": "telegram"},
    ]
    return {
        "generated_at": health.generated_at.isoformat(),
        "nodes": nodes,
        "edges": edges,
        "mermaid": _mermaid(nodes, edges),
    }


def _mermaid(nodes: list[dict], edges: list[dict]) -> str:
    lines = ["flowchart LR"]
    for item in nodes:
        lines.append(f'  {item["id"]}["{item["label"]} ({item["status"]})"]')
    for edge in edges:
        lines.append(f"  {edge['from']} --> {edge['to']}")
    return "\n".join(lines)
