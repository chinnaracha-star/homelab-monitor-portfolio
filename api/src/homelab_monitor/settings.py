from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="HOMELAB_",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    environment: str = "development"
    database_url: str = "sqlite:///./data/homelab-monitor.db"
    log_level: str = "INFO"
    log_dir: str = ""
    registration_key: str = Field(min_length=24)
    agent_report_interval_seconds: int = Field(default=60, ge=15, le=3600)
    minimum_agent_version: str = "0.1.0"
    latest_agent_version: str = "0.1.0"
    alert_cpu_threshold_percent: float = Field(default=90.0, ge=0, le=100)
    alert_memory_threshold_percent: float = Field(default=90.0, ge=0, le=100)
    alert_disk_threshold_percent: float = Field(default=90.0, ge=0, le=100)
    alert_temperature_threshold_celsius: float = Field(default=85.0, ge=-100, le=250)
    agent_offline_after_seconds: int = Field(default=180, ge=30, le=86_400)
    alert_evaluation_interval_seconds: int = Field(default=30, ge=5, le=3600)
    telegram_api_base_url: str = Field(
        default="https://api.telegram.org",
        validation_alias=AliasChoices(
            "TELEGRAM_API_BASE_URL",
            "HOMELAB_TELEGRAM_API_BASE_URL",
        ),
    )
    telegram_bot_token: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "TELEGRAM_BOT_TOKEN",
            "HOMELAB_TELEGRAM_BOT_TOKEN",
        ),
    )
    telegram_chat_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "TELEGRAM_CHAT_ID",
            "HOMELAB_TELEGRAM_CHAT_ID",
        ),
    )
    telegram_request_timeout: float = Field(
        default=30.0,
        gt=0,
        le=120,
        validation_alias=AliasChoices(
            "TELEGRAM_REQUEST_TIMEOUT",
            "HOMELAB_TELEGRAM_REQUEST_TIMEOUT",
        ),
    )
    telegram_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "TELEGRAM_ENABLED",
            "HOMELAB_TELEGRAM_ENABLED",
        ),
    )
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_expire_minutes: int = Field(default=60, ge=1, le=10_080)
    bootstrap_admin_password: SecretStr | None = None
    bootstrap_operator_password: SecretStr | None = None
    bootstrap_viewer_password: SecretStr | None = None
    notification_worker_enabled: bool = True
    infrastructure_mock: bool = True
    infrastructure_refresh_seconds: int = Field(default=30, ge=5, le=3600)
    infrastructure_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    qnap_url: str = ""
    qnap_username: str = ""
    qnap_password: SecretStr | None = None
    qnap_sid: str = ""
    qnap_tls_verify: bool = True
    qnap_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    docker_url: str = ""
    immich_url: str = ""
    immich_api_key: SecretStr | None = None
    qumagie_url: str = ""
    qumagie_api_key: SecretStr | None = None
    backup_url: str = ""
    backup_enabled: bool = True
    backup_path: str = "/var/lib/homelab-monitor/backups"
    backup_retention_daily: int = Field(default=7, ge=1, le=90)
    backup_retention_weekly: int = Field(default=4, ge=1, le=52)
    backup_retention_monthly: int = Field(default=6, ge=1, le=36)
    backup_time: str = "02:00"
    backup_timezone: str = "Asia/Bangkok"
    photo_watch_folder: str = "/data/photos"
    photo_watch_folders: list[str] = Field(
        default_factory=lambda: [
            "/data/photos",
            "/data/photos/library-a",
            "/data/photos/library-b",
            "/data/photos/library-c",
            "/data/photos/library-d",
            "/data/photos/library-e",
        ]
    )
    photo_watcher_enabled: bool = True
    photo_scan_interval_seconds: int = Field(default=5, ge=5, le=60)
    tailscale_bin: str = "tailscale"
    tailscale_socket: str = "/var/run/tailscale/tailscaled.sock"
    tailscale_timeout_seconds: float = Field(default=2.0, gt=0, le=15)
    dashboard_health_url: str = ""
    api_health_url: str = ""
    dashboard_public_url: str = ""
    immich_public_url: str = ""
    qnap_public_url: str = ""
    dashboard_port: int = Field(default=18081, ge=1, le=65535)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
