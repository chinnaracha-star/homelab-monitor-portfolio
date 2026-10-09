from homelab_monitor.notification_batch import coalesce_jobs, format_batch_message
from homelab_monitor.notification_queue import NotificationQueue, new_notification_job
from homelab_monitor.notification_worker import MAX_ATTEMPTS, NotificationWorker


def _activated(title: str, extra: str = "Current:\n95%"):
    return new_notification_job(
        channel="telegram",
        event="activated",
        message=f"🔴 {title}\n\n{extra}",
    )


def _recovered(title: str, extra: str = "Recovered after\n\n2 minutes"):
    return new_notification_job(
        channel="telegram",
        event="recovered",
        message=f"🟢 {title}\n\n{extra}",
    )


def _worker(queue: NotificationQueue, sender, *, retry_delay: float = 0) -> NotificationWorker:
    return NotificationWorker(
        queue,
        sender,
        retry_delay_seconds=retry_delay,
        batch_window_seconds=0,
        sleep=lambda _: None,
    )


def test_single_notification_keeps_original_format() -> None:
    job = _activated("CPU Usage High")
    queue = NotificationQueue()
    queue.enqueue(job)
    sent: list[str] = []

    class Capture:
        def send(self, item) -> None:
            sent.append(item.message)

    assert _worker(queue, Capture()).process_one() is True
    assert sent == [job.message]
    assert "🚨 HomeLab Alerts" not in sent[0]


def test_activated_batch_sends_one_message() -> None:
    queue = NotificationQueue()
    queue.enqueue(_activated("CPU Usage High"))
    queue.enqueue(_activated("Memory Usage High"))
    queue.enqueue(_activated("Temperature High"))
    sent: list[str] = []

    class Capture:
        def send(self, item) -> None:
            sent.append(item.message)

    assert _worker(queue, Capture()).process_one() is True
    assert len(sent) == 1
    assert sent[0] == ("🚨 HomeLab Alerts\n\n• CPU High\n• Memory High\n• Temperature High")
    assert len(queue) == 0


def test_recovered_batch_sends_one_message() -> None:
    queue = NotificationQueue()
    queue.enqueue(_recovered("CPU Usage Recovered"))
    queue.enqueue(_recovered("Memory Usage Recovered"))
    sent: list[str] = []

    class Capture:
        def send(self, item) -> None:
            sent.append(item.message)

    assert _worker(queue, Capture()).process_one() is True
    assert sent == ["✅ HomeLab Recovery\n\n• CPU Normal\n• Memory Normal"]


def test_mixed_batch_uses_two_sections() -> None:
    queue = NotificationQueue()
    queue.enqueue(_activated("CPU Usage High"))
    queue.enqueue(_recovered("Memory Usage Recovered"))
    queue.enqueue(_activated("Temperature High"))
    sent: list[str] = []

    class Capture:
        def send(self, item) -> None:
            sent.append(item.message)

    assert _worker(queue, Capture()).process_one() is True
    assert sent == [
        "🚨 Activated\n\n• CPU High\n• Temperature High\n\n✅ Recovered\n\n• Memory Normal"
    ]


def test_batch_fifo_is_preserved_inside_sections() -> None:
    jobs = [
        _activated("Memory Usage High"),
        _activated("CPU Usage High"),
        _activated("Temperature High"),
    ]
    assert format_batch_message(jobs).splitlines()[2:] == [
        "• Memory High",
        "• CPU High",
        "• Temperature High",
    ]


def test_multiple_notifications_are_coalesced_into_one_job() -> None:
    jobs = [
        _activated("CPU Usage High"),
        _activated("Memory Usage High"),
    ]
    combined = coalesce_jobs(jobs)
    assert combined.message.startswith("🚨 HomeLab Alerts")
    assert combined.retry_count == 0
    assert jobs[0].message != combined.message


def test_retry_after_batch_failure(caplog) -> None:
    queue = NotificationQueue()
    queue.enqueue(_activated("CPU Usage High"))
    queue.enqueue(_activated("Memory Usage High"))
    attempts: list[str] = []

    class Boom:
        def send(self, job) -> None:
            attempts.append(job.message)
            raise RuntimeError("telegram down")

    worker = _worker(queue, Boom(), retry_delay=0)
    caplog.set_level("WARNING")
    worker.process_one()
    assert len(queue) == 1
    retry_job = queue.snapshot()[0]
    assert retry_job.retry_count == 1
    assert "🚨 HomeLab Alerts" in retry_job.message
    assert "• CPU High" in retry_job.message
    assert "• Memory High" in retry_job.message

    worker.process_one()
    worker.process_one()
    assert len(attempts) == MAX_ATTEMPTS
    assert len(queue) == 0
    assert all("HomeLab Alerts" in message for message in attempts)
    assert any("notification_dropped" in record.message for record in caplog.records)
