from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx
import psutil
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from homelab_monitor.developer_dashboard import DeveloperDashboardService
from homelab_monitor.models import Agent, Alert, MetricHistory, Notification
from homelab_monitor.notifications.config import load_payload, telegram_credentials
from homelab_monitor.performance import collect_and_store, time_query
from homelab_monitor.photo_watcher import get_photo_watcher_service
from homelab_monitor.realtime import hub
from homelab_monitor.remote_access import RemoteAccessService
from homelab_monitor.schemas import (
    AgentRuntimeResponse,
    DockerContainerResponse,
    ObservabilitySnapshot,
    ProductionHealthCheck,
    ProductionHealthResponse,
    ProductionNetworkResponse,
    ProductionRuntimeResponse,
    ProductionStorageResponse,
    TailscaleRuntimeResponse,
    TelegramRuntimeResponse,
)
from homelab_monitor.settings import Settings, get_settings
from homelab_monitor.sqlite_backup import load_state, sqlite_status_payload

HealthStatus = Literal["healthy", "warning", "critical", "unknown"]


def _status_for_percent(value: float | None) -> HealthStatus:
    if value is None:
        return "unknown"
    if value > 90:
        return "critical"
    if value > 80:
        return "warning"
    return "healthy"


def _database_path(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite:///"):
        return None
    raw = database_url.removeprefix("sqlite:///")
    if raw == ":memory:":
        return None
    return Path(raw).resolve()


def _folder_size(path: Path) -> int | None:
    if not path.exists():
        return 0
    try:
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
    except OSError:
        return None


def _run(command: list[str], timeout: float = 2.0) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


class ProductionHealthService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        remote_access: RemoteAccessService | None = None,
        developer: DeveloperDashboardService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.remote_access = remote_access or RemoteAccessService(settings=self.settings)
        self.developer = developer or DeveloperDashboardService()

    def runtime(self, db: Session) -> ProductionRuntimeResponse:
        agent = self.developer.agent_service(db)
        agent_state = agent.state
        if agent_state == "unknown" and agent.agent_status == "online":
            agent_state = "running"
        elif agent_state == "unknown" and agent.agent_status == "offline":
            agent_state = "stopped"
        containers = self._docker_containers()
        return ProductionRuntimeResponse(
            agent=AgentRuntimeResponse(
                state=agent_state,
                restart_count=agent.restart_count,
                last_heartbeat=agent.last_heartbeat,
                last_report=agent.last_report,
                last_metrics_upload=agent.last_report,
            ),
            docker_available=containers is not None,
            containers=containers or [],
            telegram=self._telegram(db),
            tailscale=self._tailscale(),
        )

    def storage(self) -> ProductionStorageResponse:
        database_path = _database_path(self.settings.database_url)
        target = database_path.parent if database_path is not None else Path.cwd()
        try:
            usage = psutil.disk_usage(str(target))
            percent = round(float(usage.percent), 2)
            free = int(usage.free)
            filesystem = str(target.anchor or target)
        except (OSError, RuntimeError):
            percent = None
            free = None
            filesystem = str(target)
        try:
            counters = psutil.disk_io_counters()
        except (OSError, RuntimeError):
            counters = None
        try:
            cpu_times = psutil.cpu_times_percent(interval=None)
            io_wait = getattr(cpu_times, "iowait", None)
        except (OSError, RuntimeError):
            io_wait = None
        database_size = None
        if database_path is not None:
            try:
                database_size = database_path.stat().st_size
            except OSError:
                database_size = 0
        return ProductionStorageResponse(
            filesystem=filesystem,
            disk_usage_percent=percent,
            free_space_bytes=free,
            database_size_bytes=database_size,
            log_size_bytes=_folder_size(Path(self.settings.log_dir))
            if self.settings.log_dir
            else 0,
            disk_read_bytes=int(counters.read_bytes) if counters else None,
            disk_write_bytes=int(counters.write_bytes) if counters else None,
            io_wait_percent=round(float(io_wait), 2) if io_wait is not None else None,
            status=_status_for_percent(percent),
        )

    def network(self) -> ProductionNetworkResponse:
        lan_ip = self._lan_ip()
        tailscale = self._tailscale()
        latency = None
        internet: HealthStatus = "unknown"
        started = time.perf_counter()
        try:
            with socket.create_connection(("1.1.1.1", 443), timeout=0.75):
                latency = round((time.perf_counter() - started) * 1000, 2)
                internet = "healthy" if latency < 250 else "warning"
        except OSError:
            internet = "critical"
        try:
            socket.getaddrinfo("one.one.one.one", 443)
            dns: HealthStatus = "healthy"
        except OSError:
            dns = "critical"
        try:
            counters = psutil.net_io_counters()
        except (OSError, RuntimeError):
            counters = None
        errors = None
        if counters:
            errors = int(counters.errin + counters.errout + counters.dropin + counters.dropout)
        return ProductionNetworkResponse(
            lan_ip=lan_ip,
            tailscale_ip=tailscale.ip,
            gateway=self._gateway(),
            internet=internet,
            latency_ms=latency,
            dns=dns,
            upload_bytes=int(counters.bytes_sent) if counters else None,
            download_bytes=int(counters.bytes_recv) if counters else None,
            network_errors=errors,
        )

    def health(self, db: Session) -> ProductionHealthResponse:
        now = datetime.now(UTC)
        runtime = self.runtime(db)
        storage = self.storage()
        checks = [self._api_check(now), self._database_check(db, now), self._dashboard_check(now)]
        websocket_status: HealthStatus = "healthy" if hub._loop is not None else "warning"
        checks.append(
            self._check(
                "WebSocket",
                websocket_status,
                now,
                f"Realtime hub active; {hub.manager.client_count} client(s) connected."
                if websocket_status == "healthy"
                else "Realtime hub is not bound to an event loop.",
                cause="API startup is incomplete or the realtime task stopped.",
                action="Restart the API service and verify /api/v1/ws/dashboard.",
            )
        )
        agent_status: HealthStatus
        if runtime.agent.state == "running":
            agent_status = "healthy"
        elif runtime.agent.state == "stopped":
            agent_status = "critical"
        else:
            agent_status = "unknown"
        checks.append(
            self._check(
                "Agent",
                agent_status,
                now,
                f"Agent runtime is {runtime.agent.state}.",
                cause="The systemd agent may be stopped or has not reported yet.",
                action="Run systemctl status homelab-monitor-agent and restart it if needed.",
            )
        )
        telegram_status: HealthStatus
        if runtime.telegram.bot_connected is False or (
            runtime.telegram.last_failed_send
            and (
                not runtime.telegram.last_successful_send
                or runtime.telegram.last_failed_send > runtime.telegram.last_successful_send
            )
        ):
            telegram_status = "warning"
        elif runtime.telegram.bot_connected:
            telegram_status = "healthy"
        else:
            telegram_status = "unknown"
        checks.append(
            self._check(
                "Telegram",
                telegram_status,
                now,
                "Telegram delivery is configured."
                if runtime.telegram.bot_connected
                else "Telegram is not configured.",
                cause=runtime.telegram.failure_reason or "Bot token or chat ID is unavailable.",
                action="Verify Telegram settings and send a test message.",
            )
        )
        tailscale_status: HealthStatus = "healthy" if runtime.tailscale.connected else "warning"
        checks.append(
            self._check(
                "Tailscale",
                tailscale_status,
                now,
                "Tailnet HTTPS access is connected."
                if runtime.tailscale.connected and runtime.tailscale.https
                else "Tailnet HTTPS access is not fully available.",
                cause="tailscaled, MagicDNS, or Tailscale Serve may be unavailable.",
                action="Run tailscale status and tailscale serve status.",
            )
        )
        docker_status: HealthStatus = "unknown"
        if runtime.docker_available:
            docker_status = (
                "warning"
                if any(
                    item.status != "running" or item.health == "unhealthy"
                    for item in runtime.containers
                )
                else "healthy"
            )
        checks.append(
            self._check(
                "Docker",
                docker_status,
                now,
                f"{len(runtime.containers)} container(s) discovered."
                if runtime.docker_available
                else "Docker is unavailable to the API process.",
                cause="Docker is stopped, or its CLI/socket is not exposed to the API.",
                action="Run docker compose ps and verify Docker socket permissions.",
            )
        )
        checks.append(
            self._check(
                "Storage",
                storage.status,
                now,
                f"Disk usage is {storage.disk_usage_percent}%."
                if storage.disk_usage_percent is not None
                else "Disk usage is unavailable.",
                cause="The monitored filesystem is full or cannot be read.",
                action="Free disk space and verify the database and log volumes.",
            )
        )
        memory = round(float(psutil.virtual_memory().percent), 2)
        cpu = round(float(psutil.cpu_percent(interval=None)), 2)
        checks.append(self._resource_check("Memory", memory, now))
        checks.append(self._resource_check("CPU", cpu, now))
        sqlite = sqlite_status_payload(self.settings)
        backup_status: HealthStatus
        if sqlite["integrity"] == "PASS":
            backup_status = "healthy"
        elif sqlite["status"] == "failed":
            backup_status = "critical"
        elif sqlite["enabled"]:
            backup_status = "unknown"
        else:
            backup_status = "warning"
        checks.append(
            self._check(
                "SQLite Backup",
                backup_status,
                now,
                f"Latest backup integrity is {sqlite['integrity']}."
                if sqlite["latest_file"]
                else "No SQLite backup has completed yet.",
                cause="The scheduled gzip backup failed verification.",
                action="Inspect /var/lib/homelab-monitor/backups and API logs.",
            )
        )
        watcher = get_photo_watcher_service(self.settings)
        photo_status: HealthStatus = "healthy" if watcher.last_successful_scan else "unknown"
        checks.append(
            self._check(
                "Photo Monitor",
                photo_status,
                now,
                "Photo Monitor has completed a scan."
                if watcher.last_successful_scan
                else "Photo Monitor has not completed a successful scan yet.",
                latency=float(self.settings.photo_scan_interval_seconds * 1000),
                cause="CIFS watch folders may be unmounted.",
                action="Verify /mnt photo mounts and Photo Monitor settings.",
            )
        )
        active_alerts = int(
            db.scalar(select(func.count()).select_from(Alert).where(Alert.status == "active")) or 0
        )
        weighted = {
            "API": 18,
            "Database": 18,
            "Agent": 12,
            "CPU": 8,
            "Memory": 8,
            "Storage": 12,
            "SQLite Backup": 8,
            "Telegram": 8,
            "Photo Monitor": 8,
        }
        score = 100
        by_component = {item.component: item for item in checks}
        for component, weight in weighted.items():
            item = by_component.get(component)
            if item is None:
                continue
            status = item.status
            if status == "critical":
                score -= weight
            elif status in {"warning", "unknown"}:
                score -= weight // 2
        score -= min(10, active_alerts * 2)
        score = max(0, score)
        label: Literal["excellent", "good", "warning", "critical"]
        if score >= 90:
            label = "excellent"
        elif score >= 75:
            label = "good"
        elif score >= 50:
            label = "warning"
        else:
            label = "critical"
        observability = self._observability(db, runtime, storage, sqlite, now, by_component)
        database = by_component.get("Database")
        query_ms = database.latency_ms if database else time_query(db)
        performance = collect_and_store(db, self.settings, query_ms=query_ms)
        return ProductionHealthResponse(
            generated_at=now,
            score=score,
            status=label,
            checks=checks,
            last_self_check=now,
            last_backup=observability.last_backup,
            last_telegram=observability.last_telegram,
            last_photo_scan=observability.last_photo_scan,
            last_agent_checkin=observability.last_agent_checkin,
            observability=observability,
            performance=performance,
        )

    def _observability(
        self,
        db: Session,
        runtime: ProductionRuntimeResponse,
        storage: ProductionStorageResponse,
        sqlite: dict,
        now: datetime,
        by_component: dict[str, ProductionHealthCheck],
    ) -> ObservabilitySnapshot:
        history = list(
            db.scalars(
                select(MetricHistory).order_by(MetricHistory.timestamp.desc()).limit(24)
            ).all()
        )
        cpu_history = [
            float(row.cpu_percent) for row in reversed(history) if row.cpu_percent is not None
        ]
        memory_history = [
            float(row.memory_percent) for row in reversed(history) if row.memory_percent is not None
        ]
        disk_history = [
            float(row.disk_percent) for row in reversed(history) if row.disk_percent is not None
        ]
        telegram_rows = list(
            db.scalars(select(Notification).where(Notification.channel == "telegram")).all()
        )
        sent = sum(1 for row in telegram_rows if row.status == "sent")
        failed = sum(1 for row in telegram_rows if row.status == "failed")
        telegram_rate = round((sent / (sent + failed)) * 100, 1) if sent + failed else None
        backups = Path(self.settings.backup_path)
        ok_files = list(backups.glob("homelab-monitor-*.sqlite3.gz")) if backups.exists() else []
        failed_files = list(backups.glob("*.failed")) if backups.exists() else []
        backup_rate = (
            round((len(ok_files) / (len(ok_files) + len(failed_files))) * 100, 1)
            if ok_files or failed_files
            else None
        )
        last_backup = None
        if sqlite.get("latest_at"):
            try:
                last_backup = datetime.fromisoformat(str(sqlite["latest_at"]))
            except ValueError:
                last_backup = None
        last_agent = db.scalar(select(func.max(Agent.last_seen_at)))
        watcher = get_photo_watcher_service(self.settings)
        latest_state = load_state(self.settings).get("latest", {})
        previous_size = int(latest_state.get("uncompressed_bytes") or 0)
        current_size = storage.database_size_bytes or 0
        growth = current_size - previous_size if previous_size else None
        api_check = by_component.get("API")
        photo_check = by_component.get("Photo Monitor")
        api_latency = api_check.latency_ms if api_check else 0.0
        photo_latency = photo_check.latency_ms if photo_check else None
        return ObservabilitySnapshot(
            last_self_check=now,
            last_backup=last_backup,
            last_telegram=runtime.telegram.last_successful_send,
            last_photo_scan=watcher.last_successful_scan,
            last_agent_checkin=last_agent,
            api_latency_ms=api_latency,
            database_size_bytes=storage.database_size_bytes,
            database_growth_bytes=growth,
            telegram_success_rate=telegram_rate,
            photo_monitor_latency_ms=getattr(watcher, "last_scan_duration_ms", photo_latency),
            backup_success_rate=backup_rate,
            cpu_history=cpu_history[-12:],
            memory_history=memory_history[-12:],
            disk_history=disk_history[-12:],
        )

    def _api_check(self, now: datetime) -> ProductionHealthCheck:
        return self._check("API", "healthy", now, "API process is responding.", latency=0.0)

    def _database_check(self, db: Session, now: datetime) -> ProductionHealthCheck:
        started = time.perf_counter()
        try:
            db.execute(text("SELECT 1"))
        except Exception as error:
            return self._check(
                "Database",
                "critical",
                now,
                "Database query failed.",
                error=str(error),
                cause="SQLite is unavailable, locked, or its volume is not mounted.",
                action="Verify the database volume and run docker compose up -d api.",
            )
        latency = round((time.perf_counter() - started) * 1000, 2)
        return self._check("Database", "healthy", now, "SQLite query succeeded.", latency=latency)

    def _dashboard_check(self, now: datetime) -> ProductionHealthCheck:
        url = self.settings.dashboard_health_url.strip()
        if not url:
            return self._check(
                "Dashboard",
                "unknown",
                now,
                "Dashboard probe URL is not configured.",
                cause="HOMELAB_DASHBOARD_HEALTH_URL is empty.",
                action="Set the dashboard health URL for this deployment.",
            )
        started = time.perf_counter()
        try:
            response = httpx.get(url, timeout=1.0, follow_redirects=True)
            latency = round((time.perf_counter() - started) * 1000, 2)
            response.raise_for_status()
        except (httpx.HTTPError, OSError) as error:
            return self._check(
                "Dashboard",
                "critical",
                now,
                "Dashboard HTTP probe failed.",
                error=str(error),
                cause="The nginx dashboard container may be stopped or unreachable.",
                action="Run docker compose up -d dashboard and inspect nginx logs.",
            )
        return self._check(
            "Dashboard", "healthy", now, "Dashboard HTTP probe succeeded.", latency=latency
        )

    def _resource_check(
        self, component: str, value: float | None, now: datetime
    ) -> ProductionHealthCheck:
        status = _status_for_percent(value)
        return self._check(
            component,
            status,
            now,
            f"{component} usage is {value}%."
            if value is not None
            else f"{component} is unavailable.",
            cause=f"{component} utilization exceeds the production threshold.",
            action=f"Inspect the processes consuming {component.lower()} resources.",
        )

    def _check(
        self,
        component: str,
        status: HealthStatus,
        now: datetime,
        message: str,
        *,
        latency: float | None = None,
        error: str | None = None,
        cause: str | None = None,
        action: str | None = None,
    ) -> ProductionHealthCheck:
        unhealthy = status in {"warning", "critical"}
        return ProductionHealthCheck(
            component=component,
            status=status,
            last_check=now,
            latency_ms=latency,
            message=message,
            warning=message if status == "warning" else None,
            error=error if status == "critical" else None,
            possible_cause=cause if unhealthy else None,
            recommended_action=action if unhealthy else None,
        )

    def _telegram(self, db: Session) -> TelegramRuntimeResponse:
        credentials = telegram_credentials(self.settings, load_payload(db))
        configured = bool(
            credentials["enabled"] and credentials["bot_token"] and credentials["chat_id"]
        )
        rows = list(
            db.scalars(
                select(Notification)
                .where(Notification.channel == "telegram")
                .order_by(Notification.created_at.desc())
            ).all()
        )
        successful = next(
            (row.sent_at or row.updated_at for row in rows if row.status == "sent"), None
        )
        failed = next((row for row in rows if row.status == "failed"), None)
        return TelegramRuntimeResponse(
            bot_connected=configured,
            last_successful_send=successful,
            last_failed_send=(failed.updated_at if failed else None),
            failure_reason=(failed.error_message if failed else None),
            retry_queue=sum(1 for row in rows if row.status == "pending"),
        )

    def _tailscale(self) -> TailscaleRuntimeResponse:
        access = self.remote_access.snapshot()
        tailnet = None
        if access.hostname and "." in access.hostname:
            tailnet = access.hostname.split(".", 1)[1]
        return TailscaleRuntimeResponse(
            connected=access.status == "connected",
            tailnet=tailnet,
            magic_dns=True if access.hostname else None,
            connection_type="unknown",
            exit_node=None,
            remote_access_url=(
                f"https://{access.hostname}" if access.hostname and access.https else None
            ),
            hostname=access.hostname,
            ip=access.tailnet_ip,
            https=access.https,
        )

    def _docker_containers(self) -> list[DockerContainerResponse] | None:
        if shutil.which("docker") is None:
            return None
        result = _run(["docker", "ps", "-a", "--format", "{{json .}}"], timeout=3.0)
        if result is None or result.returncode != 0:
            return None
        rows: list[dict[str, object]] = []
        try:
            rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        except json.JSONDecodeError:
            return None
        items: list[DockerContainerResponse] = []
        for row in rows:
            name = str(row.get("Names") or row.get("ID") or "unknown")
            status_text = str(row.get("Status") or "unknown")
            health = "unknown"
            if "(healthy)" in status_text:
                health = "healthy"
            elif "(unhealthy)" in status_text:
                health = "unhealthy"
            items.append(
                DockerContainerResponse(
                    container=name,
                    status="running" if status_text.lower().startswith("up") else "stopped",
                    health=health,
                    image=str(row.get("Image") or ""),
                    running_since=status_text,
                )
            )
        if not items:
            return items
        inspect = _run(["docker", "inspect", *[item.container for item in items]], timeout=4.0)
        if inspect is None or inspect.returncode != 0:
            return items
        try:
            details = json.loads(inspect.stdout)
        except json.JSONDecodeError:
            return items
        by_name = {item.container: item for item in items}
        for detail in details:
            name = str(detail.get("Name", "")).lstrip("/")
            item = by_name.get(name)
            state = detail.get("State", {})
            if item is None or not isinstance(state, dict):
                continue
            item.restart_count = int(detail.get("RestartCount", 0))
            item.running_since = str(state.get("StartedAt") or item.running_since)
            health_data = state.get("Health")
            if isinstance(health_data, dict):
                item.health = str(health_data.get("Status") or item.health)
        return items

    def _lan_ip(self) -> str | None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("1.1.1.1", 80))
                return str(sock.getsockname()[0])
        except OSError:
            return None

    def _gateway(self) -> str | None:
        result = _run(["ip", "route", "show", "default"])
        if result and result.returncode == 0:
            parts = result.stdout.split()
            if "via" in parts:
                index = parts.index("via") + 1
                if index < len(parts):
                    return parts[index]
        return None
