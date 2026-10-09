"""Background worker that delivers queued Telegram notifications."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from homelab_monitor.database import get_engine
from homelab_monitor.models import Notification
from homelab_monitor.notification_batch import BATCH_WINDOW_SECONDS, coalesce_jobs
from homelab_monitor.notification_history import (
    NotificationHistoryService,
    get_notification_history_service,
)
from homelab_monitor.notification_queue import (
    NotificationJob,
    NotificationQueue,
    get_notification_queue,
)
from homelab_monitor.notifications.service import NotificationService
from homelab_monitor.realtime import hub
from homelab_monitor.settings import Settings
from homelab_monitor.sqlite_diagnostics import writer_operation

logger = logging.getLogger("homelab_monitor.notification_worker")

MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5.0


class TelegramSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, job: NotificationJob) -> None:
        if job.channel != "telegram":
            logger.warning(
                "notification_channel_ignored",
                extra={"job_id": job.id, "channel": job.channel},
            )
            return
        try:
            service = NotificationService.from_settings(self._settings)
        except ValueError as error:
            logger.warning(
                "telegram_configuration_invalid",
                extra={"job_id": job.id, "reason": str(error)},
            )
            return
        if service is None:
            logger.info("telegram_notification_skipped", extra={"job_id": job.id})
            return
        try:
            service.send_text(job.message)
            _record_delivery(job, recipient=service.recipient, error="")
        finally:
            service.close()


class NotificationWorker:
    def __init__(
        self,
        queue: NotificationQueue,
        sender: TelegramSender,
        *,
        max_attempts: int = MAX_ATTEMPTS,
        retry_delay_seconds: float = RETRY_DELAY_SECONDS,
        batch_window_seconds: float = BATCH_WINDOW_SECONDS,
        sleep=time.sleep,
        history: NotificationHistoryService | None = None,
    ) -> None:
        self._queue = queue
        self._sender = sender
        self._max_attempts = max_attempts
        self._retry_delay_seconds = retry_delay_seconds
        self._batch_window_seconds = batch_window_seconds
        self._sleep = sleep
        self._history = history or get_notification_history_service()

    def _collect_batch(self) -> list[NotificationJob] | None:
        first = self._queue.dequeue()
        if first is None:
            return None
        jobs = [first]
        if first.retry_count > 0:
            return jobs
        if self._batch_window_seconds <= 0:
            while True:
                nxt = self._queue.dequeue()
                if nxt is None:
                    break
                jobs.append(nxt)
            return jobs
        deadline = time.monotonic() + self._batch_window_seconds
        while True:
            nxt = self._queue.dequeue()
            if nxt is not None:
                jobs.append(nxt)
                continue
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self._sleep(min(0.05, remaining))
        return jobs

    def process_one(self) -> bool:
        jobs = self._collect_batch()
        if not jobs:
            return False
        job = coalesce_jobs(jobs)
        started_at = datetime.now(UTC)
        started = time.perf_counter()
        try:
            self._sender.send(job)
            self._history.record_attempt(
                notification_id=job.id,
                channel=job.channel,
                event=job.event,
                success=True,
                retry_count=job.retry_count,
                duration_ms=int((time.perf_counter() - started) * 1000),
                error_message=None,
                created_at=started_at,
                sent_at=datetime.now(UTC),
            )
            logger.info(
                "notification_sent",
                extra={"job_id": job.id, "channel": job.channel, "event": job.event},
            )
            return True
        except Exception as error:
            duration_ms = int((time.perf_counter() - started) * 1000)
            self._history.record_attempt(
                notification_id=job.id,
                channel=job.channel,
                event=job.event,
                success=False,
                retry_count=job.retry_count,
                duration_ms=duration_ms,
                error_message=str(error)[:1000],
                created_at=started_at,
                sent_at=None,
            )
            job.retry_count += 1
            logger.exception(
                "notification_delivery_failed",
                extra={
                    "job_id": job.id,
                    "channel": job.channel,
                    "attempt": job.retry_count,
                },
            )
            if job.retry_count >= self._max_attempts:
                logger.warning(
                    "notification_dropped",
                    extra={
                        "job_id": job.id,
                        "channel": job.channel,
                        "retry_count": job.retry_count,
                        "reason": str(error)[:500],
                    },
                )
                _record_delivery(job, recipient=job.channel, error=str(error)[:1000])
                return True
            self._sleep(self._retry_delay_seconds)
            self._queue.enqueue(job)
            return True


def _record_delivery(job: NotificationJob, *, recipient: str, error: str) -> None:
    try:
        with writer_operation("notification_worker_update"), Session(get_engine()) as db:
            db.add(
                Notification(
                    alert_id=None,
                    channel=job.channel,
                    recipient=recipient,
                    status="failed" if error else "sent",
                    error_message=error,
                    sent_at=None if error else datetime.now(UTC),
                )
            )
            db.commit()
        hub.publish("overview_updated", reason="notification_updated")
        hub.publish("alert_updated", reason="notification_updated")
    except Exception:
        logger.exception("notification_record_failed", extra={"job_id": job.id})


async def run_notification_worker(settings: Settings) -> None:
    if not settings.notification_worker_enabled:
        logger.info("notification_worker_disabled")
        return
    worker = NotificationWorker(get_notification_queue(), TelegramSender(settings))
    while True:
        try:
            processed = await asyncio.to_thread(worker.process_one)
        except Exception:
            logger.exception("notification_worker_crashed")
            processed = False
        if not processed:
            await asyncio.sleep(0.25)
