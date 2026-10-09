CHANNELS = ("telegram", "discord", "slack", "email")
RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 0.05
SETTINGS_ROW_ID = 1
SECRET_UNCHANGED = None
REPORT_RECIPIENTS = ("hourly_report", "daily_report", "weekly_report", "test_report")
REPORT_TITLES = {
    "hourly_report": "Hourly Report",
    "daily_report": "Daily Report",
    "weekly_report": "Weekly Report",
    "test_report": "Test Report",
}


def channel_payload(payload: dict, channel: str) -> dict:
    raw = payload.get(channel)
    return raw if isinstance(raw, dict) else {}
