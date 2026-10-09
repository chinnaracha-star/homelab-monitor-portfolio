import socket
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HOMELAB_",
        case_sensitive=False,
        extra="ignore",
    )

    server_url: str = ""
    agent_name: str = Field(default_factory=socket.gethostname)
    agent_token: SecretStr | None = None
    report_interval: int = Field(default=60, ge=15, le=3600)
    config_revision: int = Field(default=0, ge=0)
    request_timeout: float = Field(default=10.0, gt=0, le=120)
    retry_attempts: int = Field(default=3, ge=1, le=10)
    retry_initial_backoff: float = Field(default=1.0, ge=0, le=60)
    retry_max_backoff: float = Field(default=30.0, ge=0, le=300)
    buffer_path: Path = Path("./state/agent-buffer.db")
    buffer_max_reports: int = Field(default=1000, ge=1, le=100_000)
    cpu_warning_percent: float = Field(default=90.0, ge=0, le=100)
    memory_warning_percent: float = Field(default=90.0, ge=0, le=100)
    disk_warning_percent: float = Field(default=90.0, ge=0, le=100)
    log_level: str = "INFO"

    def require_runtime_credentials(self) -> tuple[str, str]:
        token = self.agent_token.get_secret_value() if self.agent_token else ""
        if not self.server_url:
            raise ValueError("HOMELAB_SERVER_URL is required for the run command")
        if not token:
            raise ValueError("HOMELAB_AGENT_TOKEN is required for the run command")
        return self.server_url.rstrip("/"), token
