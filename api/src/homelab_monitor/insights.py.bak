from sqlalchemy.orm import Session

from homelab_monitor.analytics import AnalyticsService
from homelab_monitor.capacity_planning import CapacityPlanningService
from homelab_monitor.schemas import (
    InsightBackupResponse,
    InsightItem,
    InsightOverviewResponse,
    InsightPhotosResponse,
    InsightStorageResponse,
    InsightSystemResponse,
)
from homelab_monitor.settings import get_settings
from homelab_monitor.trends import TrendService

SEVERITY_RANK = {"unknown": 0, "info": 1, "warning": 2, "critical": 3}


def _item(summary: str, severity: str, recommendation: str = "") -> InsightItem:
    return InsightItem(summary=summary, severity=severity, recommendation=recommendation)


def _worse(left: str, right: str) -> str:
    if SEVERITY_RANK.get(right, 0) > SEVERITY_RANK.get(left, 0):
        return right
    return left


class InsightService:
    def __init__(
        self,
        analytics: AnalyticsService | None = None,
        trends: TrendService | None = None,
        capacity: CapacityPlanningService | None = None,
    ) -> None:
        self.analytics = analytics or AnalyticsService()
        self.trends = trends or TrendService(analytics=self.analytics)
        self.capacity = capacity or CapacityPlanningService(
            analytics=self.analytics, trends=self.trends
        )

    def storage(self, db: Session) -> InsightStorageResponse:
        payload = self.capacity.storage(db)
        item = self._storage_insight(payload)
        return InsightStorageResponse(
            summary=item.summary,
            severity=item.severity,
            recommendation=item.recommendation,
            estimated_days=payload.estimated_days_remaining,
        )

    def photos(self, db: Session) -> InsightPhotosResponse:
        photos = self.trends.photos(db)
        item = self._photos_insight(photos)
        return InsightPhotosResponse.model_validate(item.model_dump())

    def backup(self, db: Session) -> InsightBackupResponse:
        backup = self.capacity.backup(db)
        item = self._backup_insight(backup)
        return InsightBackupResponse.model_validate(item.model_dump())

    def system(self, db: Session) -> InsightSystemResponse:
        cpu = self.trends.cpu(db)
        memory = self.trends.memory(db)
        health = self.trends.health()
        return InsightSystemResponse(
            cpu=self._cpu_insight(cpu),
            memory=self._memory_insight(memory),
            infrastructure=self._infra_insight(health),
        )

    def overview(self, db: Session) -> InsightOverviewResponse:
        storage = self.storage(db)
        photos = self.photos(db)
        backup = self.backup(db)
        system = self.system(db)
        overall = self._overall(
            storage, system.cpu, system.memory, backup, photos, system.infrastructure
        )
        return InsightOverviewResponse(
            overall=overall,
            storage=storage,
            cpu=system.cpu,
            memory=system.memory,
            backup=backup,
            photos=photos,
            infrastructure=system.infrastructure,
            recommendation=overall.recommendation or overall.summary,
            severity=overall.severity,
        )

    def _storage_insight(self, storage) -> InsightItem:
        days = storage.estimated_days_remaining
        if storage.risk == "unknown":
            return _item("Storage growth is unknown.", "unknown")
        if storage.risk == "critical":
            summary = (
                f"Estimated capacity will be reached in {days} days."
                if days is not None
                else "Storage capacity is critically low."
            )
            return _item(summary, "critical", "Consider adding larger disks.")
        if storage.risk == "warning":
            summary = (
                f"Estimated capacity will be reached in {days} days."
                if days is not None
                else "Storage capacity should be reviewed."
            )
            return _item(summary, "warning", "Consider adding larger disks.")
        if storage.average_daily_growth > 0 and storage.trend == "rising":
            return _item("Storage is growing rapidly.", "warning")
        return _item("Storage usage is stable.", "info")

    def _cpu_insight(self, cpu) -> InsightItem:
        if cpu.latest is None and cpu.average_1d is None:
            return _item("CPU usage is unknown.", "unknown")
        threshold = get_settings().alert_cpu_threshold_percent
        average = cpu.average_1d
        if average is not None and average >= threshold:
            return _item("CPU usage is high.", "critical")
        if cpu.trend == "rising":
            return _item("CPU trend is rising.", "warning")
        if average is not None and average < threshold:
            if cpu.trend == "stable":
                return _item("CPU usage has remained stable.", "info")
            return _item("Average CPU remains below threshold.", "info")
        return _item("CPU usage has remained stable.", "info")

    def _memory_insight(self, memory) -> InsightItem:
        if memory.latest is None and memory.average_1d is None:
            return _item("Memory usage is unknown.", "unknown")
        threshold = get_settings().alert_memory_threshold_percent
        average = memory.average_1d
        if average is not None and average >= threshold:
            return _item("Memory usage is high.", "critical")
        if memory.trend == "rising":
            return _item("Memory usage has increased.", "warning")
        return _item("Memory usage is healthy.", "info")

    def _photos_insight(self, photos) -> InsightItem:
        if photos.today == 0 and photos.this_week == 0:
            return _item("Photo growth is unknown.", "unknown")
        if photos.last_week > 0 and photos.this_week > photos.last_week:
            return _item("Growth is above weekly average.", "warning")
        return _item("Photo library continues to grow.", "info")

    def _backup_insight(self, backup) -> InsightItem:
        if backup.success_percent is None and backup.trend == "unknown":
            return _item("Backup status is unknown.", "unknown")
        if backup.trend == "critical" or (
            backup.success_percent is not None and backup.success_percent < 50
        ):
            return _item("Recent backup failures detected.", "critical")
        if backup.success_percent is not None and backup.success_percent >= 80:
            return _item("Backup success rate is excellent.", "info")
        return _item("Backup success rate should be monitored.", "warning")

    def _infra_insight(self, health) -> InsightItem:
        total = (
            health.healthy_count
            + health.warning_count
            + health.critical_count
            + health.unknown_count
        )
        if total == 0:
            return _item("Infrastructure status is unknown.", "unknown")
        if health.critical_count > 0:
            if health.critical_count == 1:
                return _item("One infrastructure service requires attention.", "critical")
            return _item(
                f"{health.critical_count} infrastructure services require attention.",
                "critical",
            )
        if health.warning_count > 0:
            if health.warning_count == 1:
                return _item("One infrastructure service requires attention.", "warning")
            return _item(
                f"{health.warning_count} infrastructure services require attention.",
                "warning",
            )
        if health.healthy_count == total:
            return _item("All monitored services are healthy.", "info")
        return _item("Infrastructure health is mixed.", "warning")

    def _overall(
        self,
        storage: InsightItem,
        cpu: InsightItem,
        memory: InsightItem,
        backup: InsightItem,
        photos: InsightItem,
        infrastructure: InsightItem,
    ) -> InsightItem:
        items = (storage, cpu, memory, backup, photos, infrastructure)
        severity = "unknown"
        for item in items:
            severity = _worse(severity, item.severity)
        if severity == "unknown":
            return _item("No insight data is available yet.", "unknown")
        if severity == "critical":
            if storage.severity == "critical":
                return _item(
                    "Storage capacity should be reviewed.",
                    "critical",
                    storage.recommendation,
                )
            if backup.severity == "critical":
                return _item(
                    "Backup reliability should be reviewed.",
                    "critical",
                    backup.recommendation,
                )
            return _item("Immediate attention is required.", "critical")
        if severity == "warning":
            return _item("Some metrics should be reviewed.", "warning")
        return _item("No immediate action required.", "info")
