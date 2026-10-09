from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from homelab_monitor.analytics import AnalyticsService, _now, _round
from homelab_monitor.capacity_planning import CapacityPlanningService, _bytes_label, _risk_from_days
from homelab_monitor.schemas import (
    PredictionForecast,
    PredictionMetricResponse,
    PredictionOverviewResponse,
)
from homelab_monitor.trends import TrendService

HORIZONS = (7, 30, 90)
SEVERITY_RANK = {"unknown": 0, "healthy": 1, "info": 1, "warning": 2, "critical": 3}


def _worse(left: str, right: str) -> str:
    if SEVERITY_RANK.get(right, 0) > SEVERITY_RANK.get(left, 0):
        return right
    return left


class PredictionService:
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

    def storage(self, db: Session, *, now: datetime | None = None) -> PredictionMetricResponse:
        end = now or _now()
        payload = self.capacity.storage(db, now=end)
        days_90 = None
        if payload.average_daily_growth > 0 and payload.capacity > 0:
            target = payload.capacity * 0.9
            remaining = target - payload.current_used
            if remaining > 0:
                days_90 = _round(remaining / payload.average_daily_growth)
        risk = payload.risk
        if days_90 is not None and days_90 <= 30:
            risk = _worse(risk, "critical")
        elif days_90 is not None and days_90 <= 90:
            risk = _worse(risk, "warning")
        forecasts = []
        for horizon in HORIZONS:
            if days_90 is None:
                if payload.average_daily_growth <= 0:
                    summary = "Storage growth is unknown."
                else:
                    summary = "Storage stays below 90%."
            elif days_90 <= horizon:
                summary = f"Will reach 90% estimated in {days_90} days."
            else:
                summary = f"Stays below 90% for the next {horizon} days."
            forecasts.append(
                PredictionForecast(
                    horizon_days=horizon,
                    summary=summary,
                    value=days_90,
                    unit="days",
                )
            )
        summary = forecasts[1].summary if forecasts else "Storage growth is unknown."
        recommendation = (
            "Plan additional storage capacity."
            if risk in {"warning", "critical"}
            else "No storage action required."
        )
        return PredictionMetricResponse(
            risk=risk,
            summary=summary,
            recommendation=recommendation,
            forecasts=forecasts,
            series=payload.series,
        )

    def system(self, db: Session, *, now: datetime | None = None) -> PredictionMetricResponse:
        end = now or _now()
        cpu = self.trends.cpu(db, now=end)
        memory = self.trends.memory(db, now=end)
        cpu_weekly = None
        if cpu.average_1d is not None and cpu.average_7d not in {None, 0}:
            cpu_weekly = _round(((cpu.average_1d - cpu.average_7d) / abs(cpu.average_7d)) * 100)
        risk = "unknown"
        cpu_rising = cpu.trend == "rising" or (cpu_weekly is not None and cpu_weekly >= 6)
        if cpu.latest is None and memory.latest is None:
            risk = "unknown"
        elif cpu_rising or memory.trend == "rising":
            risk = "warning"
        else:
            risk = "healthy"
        if cpu.average_1d is not None and cpu.average_1d >= 90:
            risk = "critical"
        cpu_summary = (
            f"Average increasing {cpu_weekly}% per week."
            if cpu_weekly is not None and cpu_weekly > 0
            else f"CPU trend is {cpu.trend}."
        )
        if memory.trend == "stable":
            memory_summary = "Memory is stable."
        else:
            memory_summary = f"Memory trend is {memory.trend}."
        forecasts = [
            PredictionForecast(
                horizon_days=horizon,
                summary=f"{cpu_summary} {memory_summary}",
                value=cpu.average_1d,
                unit="percent",
            )
            for horizon in HORIZONS
        ]
        return PredictionMetricResponse(
            risk=risk,
            summary=f"{cpu_summary} {memory_summary}".strip(),
            recommendation=(
                "Review CPU load."
                if risk in {"warning", "critical"}
                else "System load is acceptable."
            ),
            forecasts=forecasts,
            series=cpu.daily or cpu.hourly,
        )

    def photos(self, db: Session, *, now: datetime | None = None) -> PredictionMetricResponse:
        end = now or _now()
        photos = self.capacity.photos(db, now=end)
        daily = photos.average_size_per_photo * photos.average_photos_per_day
        forecasts = []
        for horizon in HORIZONS:
            expected = int(daily * horizon) if daily else 0
            label = _bytes_label(float(expected)) if expected else "0 B"
            forecasts.append(
                PredictionForecast(
                    horizon_days=horizon,
                    summary=f"Expected {label} over the next {horizon} days.",
                    value=float(expected),
                    unit="bytes",
                )
            )
        risk = "warning" if daily > 0 else "unknown"
        if photos.photos_today == 0 and photos.photos_this_week == 0:
            risk = "unknown"
        month = forecasts[1]
        return PredictionMetricResponse(
            risk=risk if risk != "warning" else "healthy",
            summary=(
                month.summary.replace("30 days", "next 30 days")
                if month
                else "Photo growth is unknown."
            ),
            recommendation="Monitor library growth." if daily > 0 else "No photo growth yet.",
            forecasts=forecasts,
            series=photos.series,
        )

    def backup(self, db: Session, *, now: datetime | None = None) -> PredictionMetricResponse:
        end = now or _now()
        backup = self.capacity.backup(db, now=end)
        days = backup.estimated_days_remaining
        risk = _risk_from_days(days, backup.growth_per_day)
        forecasts = []
        for horizon in HORIZONS:
            if days is None:
                summary = "Backup destination capacity is unknown."
            elif days <= horizon:
                summary = f"Destination may become full in {days} days."
            else:
                summary = f"Backup destination stays below capacity for {horizon} days."
            forecasts.append(
                PredictionForecast(horizon_days=horizon, summary=summary, value=days, unit="days")
            )
        return PredictionMetricResponse(
            risk=risk,
            summary=forecasts[1].summary if forecasts else "Backup capacity is unknown.",
            recommendation=(
                "Expand backup destination storage."
                if risk in {"warning", "critical"}
                else "Backup destination has sufficient capacity."
            ),
            forecasts=forecasts,
            series=backup.series,
        )

    def overview(self, db: Session, *, now: datetime | None = None) -> PredictionOverviewResponse:
        end = now or _now()
        storage = self.storage(db, now=end)
        system = self.system(db, now=end)
        photos = self.photos(db, now=end)
        backup = self.backup(db, now=end)
        overall = "unknown"
        for item in (storage, system, photos, backup):
            overall = _worse(overall, item.risk)
        recommendations = [
            item.recommendation for item in (storage, system, photos, backup) if item.recommendation
        ]
        return PredictionOverviewResponse(
            overall_risk=overall,
            storage=storage,
            system=system,
            photos=photos,
            backup=backup,
            recommendations=recommendations,
            summary=storage.summary,
        )
