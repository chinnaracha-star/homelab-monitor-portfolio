from datetime import UTC, datetime

from homelab_monitor.photo_folders import display_folder_name
from homelab_monitor.telegram import BANGKOK
from homelab_monitor.telegram_links import (
    is_telegram_button_url,
    resolve_dashboard_url,
    resolve_immich_url,
    resolve_qnap_url,
)

_MONTHS = (
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def format_photo_size(size_bytes: int) -> str:
    megabytes = size_bytes / (1024 * 1024)
    return f"{megabytes:.1f} MB"


def format_photo_stamp(value: datetime) -> tuple[str, str]:
    stamp = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    local = stamp.astimezone(BANGKOK)
    date_line = f"{local.day} {_MONTHS[local.month]} {local.year}"
    return date_line, local.strftime("%H:%M:%S")


def _link_lines() -> list[str]:
    lines: list[str] = []
    mapping = (
        ("Dashboard", resolve_dashboard_url()),
        ("Immich", resolve_immich_url()),
        ("QNAP", resolve_qnap_url()),
    )
    for label, url in mapping:
        if not url or not is_telegram_button_url(url):
            continue
        if lines:
            lines.append("")
        lines.extend([label, url])
    return lines


def format_new_photo_message(
    *,
    filename: str,
    folder: str,
    size_bytes: int,
    created_at: datetime,
    source: str = "QNAP",
) -> str:
    del size_bytes
    date_line, time_line = format_photo_stamp(created_at)
    lines = [
        "📷 New Photo Detected",
        "",
        "Folder",
        display_folder_name(folder),
        "",
        "Filename",
        filename,
        "",
        "Time",
        date_line,
        time_line,
        "",
        "Source",
        source,
    ]
    links = _link_lines()
    if links:
        lines.extend(["", *links])
    return "\n".join(lines)


def format_new_photos_batch_message(
    *,
    folder: str,
    filenames: list[str],
    source: str = "QNAP",
) -> str:
    del source
    lines = [
        f"📷 {len(filenames)} New Photos",
        "",
        "Folder",
        display_folder_name(folder),
        "",
        "Files",
        *[filename or "—" for filename in filenames],
    ]
    links = _link_lines()
    if links:
        lines.extend(["", *links])
    return "\n".join(lines)
