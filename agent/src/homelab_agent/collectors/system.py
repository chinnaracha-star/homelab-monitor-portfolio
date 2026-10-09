import os
import platform
import socket
import time
from typing import Any

import psutil

from homelab_agent.config import AgentSettings
from homelab_agent.models import ModuleResult


class SystemCollector:
    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings

    def collect(self) -> ModuleResult:
        errors: list[str] = []
        metrics: dict[str, Any] = {
            "hostname": socket.gethostname(),
            "os": self._os_information(),
        }

        try:
            metrics["cpu"] = self._cpu()
            metrics["memory"] = self._memory()
            metrics["disks"] = self._disks()
            metrics["load_average"] = self._load_average()
            metrics["uptime_seconds"] = self._uptime()
        except (OSError, RuntimeError) as error:
            errors.append(f"core_metrics: {type(error).__name__}")

        temperatures, temperature_status = self._temperatures()
        metrics["temperatures"] = temperatures

        status = self._status(metrics, errors)
        summary = {
            "healthy": "System operating normally",
            "warning": "One or more system metrics exceeded warning thresholds",
            "critical": "System metrics are in a critical state",
            "unknown": "System metrics could not be collected completely",
        }[status]

        return ModuleResult(
            module="system",
            status=status,
            summary=summary,
            metrics=metrics,
            diagnostics={
                "temperature_status": temperature_status,
                "collection_errors": errors,
                "thresholds": {
                    "cpu_warning_percent": self.settings.cpu_warning_percent,
                    "memory_warning_percent": self.settings.memory_warning_percent,
                    "disk_warning_percent": self.settings.disk_warning_percent,
                },
            },
        )

    @staticmethod
    def _cpu() -> dict[str, float | int]:
        return {
            "usage_percent": round(psutil.cpu_percent(interval=0.1), 2),
            "logical_count": psutil.cpu_count(logical=True) or 0,
            "physical_count": psutil.cpu_count(logical=False) or 0,
        }

    @staticmethod
    def _memory() -> dict[str, float | int]:
        memory = psutil.virtual_memory()
        return {
            "total_bytes": memory.total,
            "used_bytes": memory.used,
            "available_bytes": memory.available,
            "usage_percent": round(memory.percent, 2),
        }

    @staticmethod
    def _disks() -> list[dict[str, Any]]:
        disks: list[dict[str, Any]] = []
        seen_mounts: set[str] = set()
        for partition in psutil.disk_partitions(all=False):
            if partition.mountpoint in seen_mounts:
                continue
            seen_mounts.add(partition.mountpoint)
            try:
                usage = psutil.disk_usage(partition.mountpoint)
            except (OSError, PermissionError):
                continue
            disks.append(
                {
                    "filesystem": partition.device,
                    "mount_point": partition.mountpoint,
                    "filesystem_type": partition.fstype,
                    "total_bytes": usage.total,
                    "used_bytes": usage.used,
                    "free_bytes": usage.free,
                    "usage_percent": round(usage.percent, 2),
                }
            )
        return disks

    @staticmethod
    def _load_average() -> dict[str, float]:
        load_1, load_5, load_15 = os.getloadavg()
        return {
            "1_minute": round(load_1, 2),
            "5_minutes": round(load_5, 2),
            "15_minutes": round(load_15, 2),
        }

    @staticmethod
    def _uptime() -> int:
        return max(0, int(time.time() - psutil.boot_time()))

    @staticmethod
    def _temperatures() -> tuple[list[dict[str, Any]], str]:
        try:
            groups = psutil.sensors_temperatures(fahrenheit=False)
        except (AttributeError, OSError, RuntimeError):
            return [], "unavailable"
        if not groups:
            return [], "unavailable"

        sensors: list[dict[str, Any]] = []
        for source, entries in groups.items():
            for entry in entries:
                sensors.append(
                    {
                        "source": source,
                        "label": entry.label or source,
                        "current_celsius": entry.current,
                        "high_celsius": entry.high,
                        "critical_celsius": entry.critical,
                    }
                )
        return sensors, "available" if sensors else "unavailable"

    @staticmethod
    def _os_information() -> dict[str, str]:
        try:
            release = platform.freedesktop_os_release()
        except OSError:
            release = {}
        return {
            "distribution": release.get("PRETTY_NAME", platform.system()),
            "distribution_id": release.get("ID", "unknown"),
            "distribution_version": release.get("VERSION_ID", "unknown"),
            "kernel": platform.release(),
            "architecture": platform.machine(),
        }

    def _status(self, metrics: dict[str, Any], errors: list[str]) -> str:
        if errors or "cpu" not in metrics or "memory" not in metrics:
            return "unknown"
        if metrics["cpu"]["usage_percent"] >= self.settings.cpu_warning_percent:
            return "warning"
        if metrics["memory"]["usage_percent"] >= self.settings.memory_warning_percent:
            return "warning"
        if any(
            disk["usage_percent"] >= self.settings.disk_warning_percent for disk in metrics["disks"]
        ):
            return "warning"
        return "healthy"
