from types import SimpleNamespace

from homelab_agent.collectors.system import SystemCollector
from homelab_agent.config import AgentSettings


def configure_core_metrics(monkeypatch) -> None:
    monkeypatch.setattr(
        "homelab_agent.collectors.system.psutil.cpu_percent",
        lambda interval: 25.5,
    )
    monkeypatch.setattr(
        "homelab_agent.collectors.system.psutil.cpu_count",
        lambda logical: 8 if logical else 4,
    )
    monkeypatch.setattr(
        "homelab_agent.collectors.system.psutil.virtual_memory",
        lambda: SimpleNamespace(
            total=16_000,
            used=8_000,
            available=8_000,
            percent=50.0,
        ),
    )
    monkeypatch.setattr(
        "homelab_agent.collectors.system.psutil.disk_partitions",
        lambda all: [
            SimpleNamespace(
                device="/dev/sda1",
                mountpoint="/",
                fstype="ext4",
            )
        ],
    )
    monkeypatch.setattr(
        "homelab_agent.collectors.system.psutil.disk_usage",
        lambda mount: SimpleNamespace(
            total=100_000,
            used=40_000,
            free=60_000,
            percent=40.0,
        ),
    )
    monkeypatch.setattr(
        "homelab_agent.collectors.system.os.getloadavg",
        lambda: (0.5, 0.4, 0.3),
    )
    monkeypatch.setattr(
        "homelab_agent.collectors.system.psutil.boot_time",
        lambda: 1_000.0,
    )
    monkeypatch.setattr(
        "homelab_agent.collectors.system.time.time",
        lambda: 4_600.0,
    )


def test_collects_cpu_memory_disk_load_and_uptime(monkeypatch) -> None:
    configure_core_metrics(monkeypatch)
    monkeypatch.setattr(
        "homelab_agent.collectors.system.psutil.sensors_temperatures",
        lambda fahrenheit: {
            "coretemp": [
                SimpleNamespace(
                    label="Package",
                    current=52.0,
                    high=90.0,
                    critical=100.0,
                )
            ]
        },
    )

    result = SystemCollector(AgentSettings()).collect()

    assert result.status == "healthy"
    assert result.metrics["cpu"]["usage_percent"] == 25.5
    assert result.metrics["memory"]["available_bytes"] == 8_000
    assert result.metrics["disks"][0]["mount_point"] == "/"
    assert result.metrics["load_average"]["15_minutes"] == 0.3
    assert result.metrics["uptime_seconds"] == 3_600
    assert result.metrics["temperatures"][0]["current_celsius"] == 52.0


def test_temperature_unavailable_does_not_crash(monkeypatch) -> None:
    configure_core_metrics(monkeypatch)
    monkeypatch.setattr(
        "homelab_agent.collectors.system.psutil.sensors_temperatures",
        lambda fahrenheit: {},
    )

    result = SystemCollector(AgentSettings()).collect()

    assert result.status == "healthy"
    assert result.metrics["temperatures"] == []
    assert result.diagnostics["temperature_status"] == "unavailable"


def test_thresholds_are_centralized_in_settings(monkeypatch) -> None:
    configure_core_metrics(monkeypatch)
    monkeypatch.setattr(
        "homelab_agent.collectors.system.psutil.cpu_percent",
        lambda interval: 95.0,
    )
    monkeypatch.setattr(
        "homelab_agent.collectors.system.psutil.sensors_temperatures",
        lambda fahrenheit: {},
    )

    result = SystemCollector(AgentSettings(cpu_warning_percent=90)).collect()

    assert result.status == "warning"
