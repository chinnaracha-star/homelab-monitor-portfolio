from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from homelab_monitor import __version__ as APP_VERSION
from homelab_monitor.agent_presence import presence_for_agents
from homelab_monitor.analytics import AnalyticsService, _round
from homelab_monitor.capacity_planning import CapacityPlanningService
from homelab_monitor.connectors.http import as_int
from homelab_monitor.database import Base
from homelab_monitor.history import as_utc
from homelab_monitor.infrastructure import get_infrastructure_service
from homelab_monitor.models import (
    Agent,
    AgentGroup,
    Alert,
    AlertRule,
    MetricReport,
    Notification,
    OpsSnapshot,
    User,
)
from homelab_monitor.realtime import hub
from homelab_monitor.schemas import (
    DeveloperActivityItem,
    DeveloperAgentService,
    DeveloperBuildStatus,
    DeveloperGitStatus,
    DeveloperOverviewResponse,
    DeveloperPhaseProgress,
    DeveloperProgress,
    DeveloperProjectStatus,
    DeveloperRuntimeStatus,
    DeveloperStatistics,
    DeveloperSystemHealth,
    DeveloperTestStatus,
)
from homelab_monitor.settings import get_settings
from homelab_monitor.trends import TrendService, _health_bucket

CURRENT_PHASE = 11
CURRENT_SPRINT = "11.5"
PHASE_PERCENTS = (100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 90)
ROADMAP = "Phase 11: Backup, Observability, Multi-agent, Performance, Operations, Mission Control"
MILESTONE = "Sprint 11.5 Operations Center / RC2"
REPO_ROOT = Path(__file__).resolve().parents[3]
METADATA_PATH = REPO_ROOT / "state" / "developer-metadata.json"
ACTIVITY_LIMIT = 20


class DeveloperDashboardService:
    def __init__(
        self,
        analytics: AnalyticsService | None = None,
        trends: TrendService | None = None,
        capacity: CapacityPlanningService | None = None,
        metadata_path: Path | None = None,
    ) -> None:
        self.analytics = analytics or AnalyticsService()
        self.trends = trends or TrendService(analytics=self.analytics)
        self.capacity = capacity or CapacityPlanningService(
            analytics=self.analytics, trends=self.trends
        )
        self.metadata_path = metadata_path or METADATA_PATH

    def overview(self, db: Session) -> DeveloperOverviewResponse:
        settings = get_settings()
        metadata = self._metadata()
        git = self._git_status()
        trend = self.trends.overview(db)
        capacity = self.capacity.system(db)
        health = self._system_health(trend, capacity)
        return DeveloperOverviewResponse(
            project=DeveloperProjectStatus(
                application_version=APP_VERSION,
                build_time=self._meta_str(metadata, "build_time"),
                environment=settings.environment,
                current_phase=CURRENT_PHASE,
                current_sprint=CURRENT_SPRINT,
                git=git,
            ),
            runtime=self._runtime(db, settings),
            build=self._build(settings, metadata),
            tests=self._tests(metadata),
            progress=self._progress(),
            statistics=self._statistics(db),
            activity=self._activity(db),
            health=health,
            capacity_score=capacity.overall_score,
            agent_service=self.agent_service(db),
        )

    def agent_service(self, db: Session) -> DeveloperAgentService:
        """Return the existing systemd and agent-presence runtime snapshot."""
        return self._agent_service(db, get_settings())

    def _runtime(self, db: Session, settings) -> DeveloperRuntimeStatus:
        database = "healthy"
        try:
            db.execute(text("SELECT 1"))
        except SQLAlchemyError:
            database = "critical"
        infra = self._infra_status()
        return DeveloperRuntimeStatus(
            api="healthy",
            dashboard=infra.get("docker", "unknown"),
            agent=self._agent_status(db),
            database=database,
            docker=infra.get("docker", "unknown"),
            websocket="healthy" if getattr(hub, "_loop", None) is not None else "unknown",
            telegram=self._telegram_status(settings),
            immich=infra.get("immich", "unknown"),
            qumagie=infra.get("qumagie", "unknown"),
            qnap=infra.get("qnap", "unknown"),
            backup=infra.get("backup", "unknown"),
        )

    def _agent_status(self, db: Session) -> str:
        agents = list(db.scalars(select(Agent)).all())
        if not agents:
            return "unknown"
        presences = presence_for_agents(db, agents)
        if any(item.status == "online" for item in presences.values()):
            return "healthy"
        if any(item.status == "offline" for item in presences.values()):
            return "critical"
        return "warning"

    def _agent_service(self, db: Session, settings) -> DeveloperAgentService:
        agents = list(db.scalars(select(Agent)).all())
        presences = presence_for_agents(db, agents)
        best: Agent | None = None
        best_contact: datetime | None = None
        for agent in agents:
            contact = presences[agent.id].contact_at
            if best is None:
                best = agent
                best_contact = contact
                continue
            if contact is not None and (best_contact is None or contact > best_contact):
                best = agent
                best_contact = contact
        presence = presences.get(best.id) if best is not None else None
        properties = self._systemd_show("homelab-agent")
        active = (properties.get("ActiveState") or "").lower()
        sub = (properties.get("SubState") or "").lower()
        unit_file = (properties.get("UnitFileState") or "").lower()
        pid_raw = properties.get("MainPID") or "0"
        try:
            pid = int(pid_raw)
        except ValueError:
            pid = 0
        restart_raw = properties.get("NRestarts") or ""
        try:
            restart_count = int(restart_raw) if restart_raw != "" else None
        except ValueError:
            restart_count = None
        if active == "activating" or sub in {"auto-restart", "reload", "start"}:
            state = "restarting"
        elif active == "active" and sub == "running":
            state = "running"
        elif active in {"inactive", "failed"}:
            state = "stopped"
        else:
            state = "unknown"
        if unit_file == "enabled":
            enabled = "enabled"
        elif unit_file == "disabled":
            enabled = "disabled"
        else:
            enabled = "unknown"
        systemd_status = None
        if properties:
            systemd_status = f"{active or 'unknown'}/{sub or 'unknown'}"
        interval = settings.agent_report_interval_seconds
        last_check_in = as_utc(best.last_seen_at) if best and best.last_seen_at else None
        last_report = presence.last_report_at if presence else None
        contact = presence.contact_at if presence else None
        next_eta = contact + timedelta(seconds=interval) if contact is not None else None
        agent_status = presence.status if presence is not None else "unknown"
        return DeveloperAgentService(
            state=state,
            enabled=enabled,
            agent_status=agent_status,
            last_heartbeat=last_check_in,
            last_check_in=last_check_in,
            last_report=last_report,
            next_report_eta=next_eta,
            pid=pid or None,
            restart_count=restart_count,
            report_interval_seconds=interval,
            systemd_status=systemd_status,
        )

    def _systemd_show(self, unit: str) -> dict[str, str]:
        try:
            result = subprocess.run(
                [
                    "systemctl",
                    "show",
                    unit,
                    "--property=ActiveState,SubState,UnitFileState,MainPID,NRestarts",
                ],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return {}
        if result.returncode != 0:
            return {}
        values: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key] = value
        return values

    def _telegram_status(self, settings) -> str:
        if not settings.telegram_enabled:
            return "unknown"
        token = settings.telegram_bot_token
        chat = settings.telegram_chat_id
        has_token = bool(token.get_secret_value() if token else "")
        if has_token and chat:
            return "healthy"
        return "unknown"

    def _infra_status(self) -> dict[str, str]:
        try:
            _, services = get_infrastructure_service().snapshot()
        except Exception:
            return {}
        return {item.service: _health_bucket(item.status) for item in services}

    def _build(self, settings, metadata: dict) -> DeveloperBuildStatus:
        return DeveloperBuildStatus(
            last_build=self._meta_str(metadata, "last_build"),
            build_status=self._meta_status(metadata, "build_status"),
            backend=self._meta_status(metadata, "backend"),
            frontend=self._meta_status(metadata, "frontend"),
            docker_compose=self._meta_status(metadata, "docker_compose"),
            application_version=APP_VERSION,
            environment=settings.environment,
        )

    def _tests(self, metadata: dict) -> DeveloperTestStatus:
        return DeveloperTestStatus(
            backend_tests=self._meta_status(metadata, "backend_tests"),
            frontend_tests=self._meta_status(metadata, "frontend_tests"),
            lint=self._meta_status(metadata, "lint"),
            ruff=self._meta_status(metadata, "ruff"),
            build=self._meta_status(metadata, "build"),
            qa=self._meta_status(metadata, "qa"),
        )

    def _progress(self) -> DeveloperProgress:
        phases = [
            DeveloperPhaseProgress(phase=index + 1, percent=float(percent))
            for index, percent in enumerate(PHASE_PERCENTS)
        ]
        completed = _round(sum(PHASE_PERCENTS) / len(PHASE_PERCENTS)) or 0.0
        return DeveloperProgress(
            phases=phases,
            current_sprint=CURRENT_SPRINT,
            roadmap=ROADMAP,
            completed_percent=completed,
            current_milestone=MILESTONE,
        )

    def _statistics(self, db: Session) -> DeveloperStatistics:
        latest_photo = db.scalar(
            select(OpsSnapshot)
            .where(OpsSnapshot.kind == "photo")
            .order_by(OpsSnapshot.observed_at.desc())
            .limit(1)
        )
        photos = as_int(latest_photo.payload.get("indexed_photos")) if latest_photo else 0
        return DeveloperStatistics(
            rest_apis=self._openapi_count(),
            database_tables=len(Base.metadata.tables),
            agents=self._count(db, Agent),
            groups=self._count(db, AgentGroup),
            users=self._count(db, User),
            alert_rules=self._count(db, AlertRule),
            notifications=self._count(db, Notification),
            photos=photos,
            docker_services=self._compose_services(),
            frontend_pages=self._count_files(
                REPO_ROOT / "dashboard" / "src" / "pages", "*Page.tsx"
            ),
            react_components=self._count_files(
                REPO_ROOT / "dashboard" / "src" / "components", "*.tsx"
            ),
            backend_modules=self._count_files(
                REPO_ROOT / "api" / "src" / "homelab_monitor", "*.py"
            ),
            test_count=self._count_files(REPO_ROOT / "tests", "test_*.py"),
            frontend_test_count=self._count_files(REPO_ROOT / "dashboard" / "src", "*.test.tsx"),
        )

    def _activity(self, db: Session) -> list[DeveloperActivityItem]:
        items: list[DeveloperActivityItem] = []
        for report in db.scalars(
            select(MetricReport).order_by(MetricReport.received_at.desc()).limit(ACTIVITY_LIMIT)
        ):
            items.append(
                DeveloperActivityItem(
                    kind="report",
                    message=f"Report {report.report_id}",
                    timestamp=as_utc(report.received_at),
                )
            )
        for alert in db.scalars(
            select(Alert).order_by(Alert.updated_at.desc()).limit(ACTIVITY_LIMIT)
        ):
            items.append(
                DeveloperActivityItem(
                    kind="alert",
                    message=alert.message or alert.kind,
                    timestamp=as_utc(alert.updated_at),
                )
            )
        for notice in db.scalars(
            select(Notification).order_by(Notification.created_at.desc()).limit(ACTIVITY_LIMIT)
        ):
            items.append(
                DeveloperActivityItem(
                    kind="notification",
                    message=f"{notice.channel} {notice.status}",
                    timestamp=as_utc(notice.created_at),
                )
            )
        for snapshot in db.scalars(
            select(OpsSnapshot).order_by(OpsSnapshot.observed_at.desc()).limit(ACTIVITY_LIMIT)
        ):
            kind = "photo snapshot" if snapshot.kind == "photo" else "backup snapshot"
            if snapshot.kind not in {"photo", "backup"}:
                kind = f"{snapshot.kind} snapshot"
            items.append(
                DeveloperActivityItem(
                    kind=kind,
                    message=f"{snapshot.kind} observed",
                    timestamp=as_utc(snapshot.observed_at),
                )
            )
        items.sort(
            key=lambda item: item.timestamp or datetime(1970, 1, 1, tzinfo=UTC),
            reverse=True,
        )
        return items[:ACTIVITY_LIMIT]

    def _system_health(self, trend, capacity) -> DeveloperSystemHealth:
        health = trend.health
        total = (
            health.healthy_count
            + health.warning_count
            + health.critical_count
            + health.unknown_count
        )
        infra = (health.healthy_count / total * 100) if total else 50.0
        overall = _round((capacity.overall_score + trend.overall_score + infra) / 3)
        return DeveloperSystemHealth(
            overall_health=overall or 0.0,
            overall_capacity=capacity.overall_score,
            overall_trend=trend.overall_score,
            overall_infrastructure=_round(infra) or 0.0,
        )

    def _git_status(self) -> DeveloperGitStatus:
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")
        commit = self._git("rev-parse", "--short", "HEAD")
        porcelain = self._git("status", "--porcelain")
        if branch is None and commit is None and porcelain is None:
            return DeveloperGitStatus()
        modified = 0
        untracked = 0
        if porcelain is not None:
            for line in porcelain.splitlines():
                if line.startswith("??"):
                    untracked += 1
                elif line.strip():
                    modified += 1
        dirty = None if porcelain is None else bool(porcelain)
        working = None if dirty is None else ("dirty" if dirty else "clean")
        return DeveloperGitStatus(
            branch=branch,
            commit=commit,
            dirty=dirty,
            working_tree=working,
            modified_files=modified if porcelain is not None else None,
            untracked_files=untracked if porcelain is not None else None,
            ahead_count=self._git_int("rev-list", "--count", "@{upstream}..HEAD"),
            behind_count=self._git_int("rev-list", "--count", "HEAD..@{upstream}"),
        )

    def _git(self, *args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def _git_int(self, *args: str) -> int | None:
        value = self._git(*args)
        if value is None or value == "":
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _metadata(self) -> dict:
        try:
            payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _meta_str(self, metadata: dict, key: str) -> str | None:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
        return None

    def _meta_status(self, metadata: dict, key: str) -> str:
        value = str(metadata.get(key, "unknown")).strip().lower()
        if value in {"passed", "failed", "unknown"}:
            return value
        return "unknown"

    def _count(self, db: Session, model: type) -> int:
        return int(db.scalar(select(func.count()).select_from(model)) or 0)

    def _count_files(self, folder: Path, pattern: str) -> int:
        if not folder.exists():
            return 0
        return len([path for path in folder.rglob(pattern) if path.is_file()])

    def _compose_services(self) -> int:
        path = REPO_ROOT / "docker-compose.yml"
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return 0
        in_services = False
        count = 0
        for line in lines:
            if line.startswith("services:"):
                in_services = True
                continue
            if in_services and line and not line.startswith(" "):
                break
            if (
                in_services
                and line.startswith("  ")
                and not line.startswith("    ")
                and line.strip().endswith(":")
                and not line.strip().startswith("#")
            ):
                count += 1
        return count

    def _openapi_count(self) -> int:
        try:
            from homelab_monitor.main import app

            return len(app.openapi().get("paths", {}))
        except Exception:
            return 0
