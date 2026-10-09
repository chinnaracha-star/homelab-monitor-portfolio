"""Combine queued Telegram jobs into a single batched message."""

from __future__ import annotations

from homelab_monitor.notification_queue import NotificationJob, new_notification_job

BATCH_WINDOW_SECONDS = 10.0

_ACTIVATED_LABELS = {
    "CPU Usage High": "CPU High",
    "Memory Usage High": "Memory High",
    "Disk Usage High": "Disk High",
    "Temperature High": "Temperature High",
    "Agent Offline": "Agent Offline",
}

_RECOVERED_LABELS = {
    "CPU Usage Recovered": "CPU Normal",
    "Memory Usage Recovered": "Memory Normal",
    "Disk Usage Recovered": "Disk Normal",
    "Temperature Recovered": "Temperature Normal",
    "Agent Recovered": "Agent Online",
}


def _title_from_message(message: str) -> str:
    first = message.splitlines()[0] if message else ""
    return first.lstrip("🔴🟢🚨✅• ").strip()


def bullet_label(job: NotificationJob) -> str:
    title = _title_from_message(job.message)
    if job.event == "recovered":
        return _RECOVERED_LABELS.get(title, title)
    return _ACTIVATED_LABELS.get(title, title)


def format_batch_message(jobs: list[NotificationJob]) -> str:
    if len(jobs) == 1:
        return jobs[0].message
    activated = [job for job in jobs if job.event != "recovered"]
    recovered = [job for job in jobs if job.event == "recovered"]
    if activated and recovered:
        lines = [
            "🚨 Activated",
            "",
            *[f"• {bullet_label(job)}" for job in activated],
            "",
            "✅ Recovered",
            "",
            *[f"• {bullet_label(job)}" for job in recovered],
        ]
    elif recovered:
        lines = [
            "✅ HomeLab Recovery",
            "",
            *[f"• {bullet_label(job)}" for job in recovered],
        ]
    else:
        lines = [
            "🚨 HomeLab Alerts",
            "",
            *[f"• {bullet_label(job)}" for job in activated],
        ]
    return "\n".join(lines)


def coalesce_jobs(jobs: list[NotificationJob]) -> NotificationJob:
    if len(jobs) == 1:
        return jobs[0]
    event = "recovered" if all(job.event == "recovered" for job in jobs) else "activated"
    return new_notification_job(
        channel="telegram",
        event=event,
        message=format_batch_message(jobs),
        retry_count=0,
    )
