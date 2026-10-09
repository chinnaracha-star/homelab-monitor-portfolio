from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentRegistrationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
    hostname: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=50)
    capabilities: list[str] = Field(default_factory=list, max_length=50)


class AgentRegistrationResponse(BaseModel):
    agent_id: str
    agent_token: str
    report_interval_seconds: int
    config_revision: int
    message: str = "Store this agent token securely; it will not be shown again."


class AgentCheckInRequest(BaseModel):
    version: str = Field(min_length=1, max_length=50)
    observed_at: datetime
    config_revision: int = Field(default=0, ge=0)


class AgentControlResponse(BaseModel):
    next_report_in: int
    config_revision: int
    configuration: dict[str, Any] | None = None
    minimum_agent_version: str
    latest_agent_version: str
    update_available: bool
    commands: list[dict[str, Any]] = Field(default_factory=list)


class ModuleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module: str = Field(min_length=1, max_length=50)
    status: Literal["healthy", "warning", "critical", "unknown"]
    summary: str = Field(min_length=1, max_length=500)
    metrics: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class MetricReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(min_length=1, max_length=64)
    schema_version: str = Field(default="1.0", max_length=20)
    observed_at: datetime
    config_revision: int = Field(default=0, ge=0)
    modules: list[ModuleResult] = Field(min_length=1, max_length=100)


class MetricReportResponse(BaseModel):
    accepted: bool
    duplicate: bool
    report_id: str
    control: AgentControlResponse


class PhotoMonitorHealth(BaseModel):
    status: Literal["pass", "fail", "unknown"] = "unknown"
    running: bool = False
    telegram_configured: bool = False
    pending: int = 0
    last_telegram_at: datetime | None = None
    reasons: list[str] = []
    enabled: bool = False
    baseline_loaded: bool = False
    watching: bool = False
    current_month: str = ""
    last_scan: datetime | None = None
    last_event: datetime | None = None
    self_check: Literal["PASS", "WARN", "FAIL", "UNKNOWN"] = "UNKNOWN"


class JobRegistryHealth(BaseModel):
    status: Literal["pass", "warning", "unknown"] = "unknown"
    validated: bool = False
    registered_jobs: int = 0
    factory_jobs: int = 0
    warnings: list[str] = []


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    service: str
    version: str
    database: Literal["up", "down"]
    timestamp: datetime
    photo_monitor: PhotoMonitorHealth = PhotoMonitorHealth()
    job_registry: JobRegistryHealth = JobRegistryHealth()


class RemoteAccessResponse(BaseModel):
    enabled: bool = False
    provider: str = "tailscale"
    hostname: str | None = None
    tailnet_ip: str | None = None
    https: bool = False
    serve_enabled: bool = False
    funnel_enabled: bool = False
    public: bool = False
    status: Literal["connected", "disconnected", "not_installed", "unknown"] = "unknown"


class ProductionHealthCheck(BaseModel):
    component: str
    status: Literal["healthy", "warning", "critical", "unknown"] = "unknown"
    last_check: datetime
    latency_ms: float | None = None
    message: str = ""
    warning: str | None = None
    error: str | None = None
    possible_cause: str | None = None
    recommended_action: str | None = None


class ObservabilitySnapshot(BaseModel):
    last_self_check: datetime | None = None
    last_backup: datetime | None = None
    last_telegram: datetime | None = None
    last_photo_scan: datetime | None = None
    last_agent_checkin: datetime | None = None
    api_latency_ms: float | None = None
    database_size_bytes: int | None = None
    database_growth_bytes: int | None = None
    telegram_success_rate: float | None = None
    photo_monitor_latency_ms: float | None = None
    backup_success_rate: float | None = None
    cpu_history: list[float] = []
    memory_history: list[float] = []
    disk_history: list[float] = []


class PerformanceWindow(BaseModel):
    samples: int = 0
    api_ms: float | None = None
    query_ms: float | None = None
    photo_scan_ms: float | None = None
    backup_seconds: float | None = None


class PerformanceSnapshot(BaseModel):
    generated_at: datetime
    performance_score: int = 0
    reliability_score: int = 0
    current: dict = Field(default_factory=dict)
    windows: dict[str, PerformanceWindow] = Field(default_factory=dict)


class ProductionHealthResponse(BaseModel):
    generated_at: datetime
    score: int
    status: Literal["excellent", "good", "warning", "critical"]
    checks: list[ProductionHealthCheck] = []
    last_self_check: datetime | None = None
    last_backup: datetime | None = None
    last_telegram: datetime | None = None
    last_photo_scan: datetime | None = None
    last_agent_checkin: datetime | None = None
    observability: ObservabilitySnapshot | None = None
    performance: PerformanceSnapshot | None = None


class AgentRuntimeResponse(BaseModel):
    state: str = "unknown"
    restart_count: int | None = None
    last_heartbeat: datetime | None = None
    last_report: datetime | None = None
    last_metrics_upload: datetime | None = None


class DockerContainerResponse(BaseModel):
    container: str
    status: str = "unknown"
    health: str = "unknown"
    restart_count: int | None = None
    image: str = ""
    running_since: str | None = None


class TelegramRuntimeResponse(BaseModel):
    bot_connected: bool | None = None
    last_successful_send: datetime | None = None
    last_failed_send: datetime | None = None
    failure_reason: str | None = None
    retry_queue: int = 0


class TailscaleRuntimeResponse(BaseModel):
    connected: bool = False
    tailnet: str | None = None
    magic_dns: bool | None = None
    connection_type: str = "unknown"
    exit_node: str | None = None
    remote_access_url: str | None = None
    hostname: str | None = None
    ip: str | None = None
    https: bool = False


class ProductionRuntimeResponse(BaseModel):
    agent: AgentRuntimeResponse = AgentRuntimeResponse()
    docker_available: bool = False
    containers: list[DockerContainerResponse] = []
    telegram: TelegramRuntimeResponse = TelegramRuntimeResponse()
    tailscale: TailscaleRuntimeResponse = TailscaleRuntimeResponse()


class ProductionStorageResponse(BaseModel):
    filesystem: str = ""
    disk_usage_percent: float | None = None
    free_space_bytes: int | None = None
    database_size_bytes: int | None = None
    log_size_bytes: int | None = None
    disk_read_bytes: int | None = None
    disk_write_bytes: int | None = None
    io_wait_percent: float | None = None
    status: Literal["healthy", "warning", "critical", "unknown"] = "unknown"


class ProductionNetworkResponse(BaseModel):
    lan_ip: str | None = None
    tailscale_ip: str | None = None
    gateway: str | None = None
    internet: Literal["healthy", "warning", "critical", "unknown"] = "unknown"
    latency_ms: float | None = None
    dns: Literal["healthy", "warning", "critical", "unknown"] = "unknown"
    upload_bytes: int | None = None
    download_bytes: int | None = None
    network_errors: int | None = None


class AgentCountResponse(BaseModel):
    total: int
    online: int
    offline: int


class ReportCountResponse(BaseModel):
    total: int


class GroupCountResponse(BaseModel):
    total: int


class GroupOverviewItem(BaseModel):
    id: str
    name: str
    agents: int
    online: int


class DashboardOverviewResponse(BaseModel):
    agents: AgentCountResponse
    reports: ReportCountResponse
    groups: GroupCountResponse
    group_stats: list[GroupOverviewItem]


class AgentSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    hostname: str
    version: str
    status: str
    last_seen_at: datetime | None


class AgentDetailResponse(AgentSummaryResponse):
    configuration_revision: int
    capabilities: list[str]


class LatestMetricReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    report_id: str
    schema_version: str
    observed_at: datetime
    received_at: datetime
    payload: dict[str, Any]


class ActiveAlertResponse(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    kind: str
    resource: str
    severity: str
    current_value: float | None
    threshold: float | None
    message: str
    opened_at: datetime
    last_observed_at: datetime
    status: str = "active"
    started_at: datetime | None = None
    last_triggered_at: datetime | None = None
    recovered_at: datetime | None = None
    duration_seconds: int | None = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    full_name: str
    role: str
    is_active: bool


class UserResponse(CurrentUserResponse):
    created_at: datetime
    updated_at: datetime


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=72)
    role: Literal["admin", "operator", "viewer"]
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    role: Literal["admin", "operator", "viewer"]
    is_active: bool


class UserPasswordRequest(BaseModel):
    password: str = Field(min_length=8, max_length=72)


class UserStatusRequest(BaseModel):
    is_active: bool


class AlertAcknowledgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    status: str


class GroupCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9 ._-]*$")
    description: str = Field(default="", max_length=500)


class GroupUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9 ._-]*$")
    description: str = Field(default="", max_length=500)


class GroupMembershipRequest(BaseModel):
    agent_ids: list[str] = Field(min_length=1, max_length=200)


class GroupSummaryResponse(BaseModel):
    id: str
    name: str
    description: str
    agents: int
    online: int
    agent_ids: list[str]


class GroupDetailResponse(GroupSummaryResponse):
    created_at: datetime
    updated_at: datetime
    members: list[AgentSummaryResponse]


class GroupSummaryListResponse(BaseModel):
    total: int
    groups: list[GroupSummaryResponse]


class MetricHistoryPoint(BaseModel):
    timestamp: datetime
    cpu_percent: float | None
    memory_percent: float | None
    disk_percent: float | None
    temperature_celsius: float | None
    network_rx_bytes: float | None
    network_tx_bytes: float | None


class MetricHistoryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    agent_id: str
    interval: Literal["1m", "5m", "15m", "1h"]
    from_time: datetime = Field(alias="from")
    to_time: datetime = Field(alias="to")
    points: list[MetricHistoryPoint]


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_id: str | None
    channel: str
    recipient: str
    status: str
    error_message: str
    sent_at: datetime | None
    created_at: datetime
    updated_at: datetime


class NotificationListResponse(BaseModel):
    total: int
    notifications: list[NotificationResponse]


class NotificationTestRequest(BaseModel):
    channel: Literal["telegram", "discord", "slack", "email"] | None = None


class NotificationTestReportResponse(BaseModel):
    status: str
    notification_id: str | None = None
    sent_at: datetime | None = None
    provider: str = "telegram"


class TelegramSettingsPublic(BaseModel):
    enabled: bool
    configured: bool
    api_base_url: str
    chat_id: str
    bot_token_set: bool
    last_test: datetime | None = None


class WebhookSettingsPublic(BaseModel):
    enabled: bool
    configured: bool
    webhook_url_set: bool


class EmailSettingsPublic(BaseModel):
    enabled: bool
    configured: bool
    host: str
    port: int
    username: str
    from_address: str
    to_address: str
    use_tls: bool
    password_set: bool


class ScheduledReportCard(BaseModel):
    enabled: bool = False
    last_sent: datetime | None = None
    next_scheduled: datetime | None = None
    status: str = "disabled"


class ScheduledReportsSettings(BaseModel):
    hourly_enabled: bool = False
    daily_enabled: bool = False
    weekly_enabled: bool = False
    hour_interval: int = 1
    daily_time: str = "08:00"
    weekly_day: str = "sunday"
    weekly_time: str = "08:00"
    timezone: str = "Asia/Bangkok"
    hourly: ScheduledReportCard = ScheduledReportCard()
    daily: ScheduledReportCard = ScheduledReportCard()
    weekly: ScheduledReportCard = ScheduledReportCard()


class NotificationSettingsResponse(BaseModel):
    telegram: TelegramSettingsPublic
    discord: WebhookSettingsPublic
    slack: WebhookSettingsPublic
    email: EmailSettingsPublic
    reports: ScheduledReportsSettings = ScheduledReportsSettings()


class TelegramSettingsUpdate(BaseModel):
    enabled: bool | None = None
    api_base_url: str | None = None
    chat_id: str | None = None
    bot_token: str | None = None


class WebhookSettingsUpdate(BaseModel):
    enabled: bool | None = None
    webhook_url: str | None = None


class EmailSettingsUpdate(BaseModel):
    enabled: bool | None = None
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = None
    password: str | None = None
    from_address: str | None = None
    to_address: str | None = None
    use_tls: bool | None = None


class ScheduledReportsUpdate(BaseModel):
    hourly_enabled: bool | None = None
    daily_enabled: bool | None = None
    weekly_enabled: bool | None = None
    hour_interval: int | None = Field(default=None, ge=1, le=24)
    daily_time: str | None = None
    weekly_day: str | None = None
    weekly_time: str | None = None
    timezone: str | None = None


class NotificationSettingsUpdateRequest(BaseModel):
    telegram: TelegramSettingsUpdate | None = None
    discord: WebhookSettingsUpdate | None = None
    slack: WebhookSettingsUpdate | None = None
    email: EmailSettingsUpdate | None = None
    reports: ScheduledReportsUpdate | None = None


class AlertRuleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9 ._-]*$")
    description: str = Field(default="", max_length=500)
    metric: Literal[
        "cpu_percent",
        "memory_percent",
        "disk_percent",
        "temperature_celsius",
        "agent_offline",
    ]
    operator: Literal[">", ">=", "<", "<=", "==", "!="]
    threshold: float
    severity: Literal["critical", "high", "medium", "low"]
    enabled: bool = True
    cooldown_seconds: int = Field(default=0, ge=0, le=86_400)
    applies_to: Literal["all", "group", "agent"] = "all"
    group_id: str | None = None
    agent_id: str | None = None


class AlertRuleUpdateRequest(AlertRuleCreateRequest):
    pass


class AlertRuleEnableRequest(BaseModel):
    enabled: bool


class AlertRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    metric: str
    operator: str
    threshold: float
    severity: str
    enabled: bool
    cooldown_seconds: int
    applies_to: str
    group_id: str | None
    agent_id: str | None
    preview: str
    created_at: datetime
    updated_at: datetime


class InfrastructureSnapshotResponse(BaseModel):
    service: str
    status: str
    version: str
    updated_at: datetime
    summary: dict[str, Any]


class InfrastructureSummaryResponse(BaseModel):
    collected_at: datetime
    services: list[InfrastructureSnapshotResponse]


class StorageHistoryResponse(BaseModel):
    today: int = 0
    yesterday: int = 0
    last_week: int = 0


class PhotoGrowthResponse(BaseModel):
    today: int = 0
    yesterday: int = 0
    this_week: int = 0


class PhotoStatsResponse(BaseModel):
    indexed_photos: int = 0
    indexed_videos: int = 0
    albums: int = 0
    users: int = 0
    storage_used: int = 0
    storage_free: int = 0
    storage_percent: float = 0
    thumbnail_queue: int = 0
    face_queue: int = 0
    last_scan: str = ""
    capacity_bytes: int = 0
    storage_health: str = "unknown"
    storage_percent_metric: float = 0
    thumbnail_queue_metric: int = 0
    face_queue_metric: int = 0
    immich_health: int = 0
    qumagie_health: int = 0
    storage_history: StorageHistoryResponse = StorageHistoryResponse()
    photo_growth: PhotoGrowthResponse = PhotoGrowthResponse()


class PhotoServicesResponse(BaseModel):
    collected_at: datetime
    read_only: bool = True
    services: list[InfrastructureSnapshotResponse]
    stats: PhotoStatsResponse


class BackupDestinationResponse(BaseModel):
    hostname: str = ""
    ip: str = ""
    model: str = "TS-253 Pro"


class BackupHistoryPeriodResponse(BaseModel):
    period: str
    label: str
    status: str


class AnalyticsSeriesPoint(BaseModel):
    timestamp: datetime | None = None
    label: str
    value: float | None = None


class AnalyticsCpuResponse(BaseModel):
    current: float | None = None
    average_24h: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    series: list[AnalyticsSeriesPoint] = []


class AnalyticsMemoryResponse(BaseModel):
    current: float | None = None
    average: float | None = None
    series: list[AnalyticsSeriesPoint] = []


class AnalyticsStorageResponse(BaseModel):
    current: int = 0
    daily_growth: int = 0
    weekly_growth: int = 0
    series: list[AnalyticsSeriesPoint] = []


class AnalyticsTemperatureResponse(BaseModel):
    current: float | None = None
    average: float | None = None
    series: list[AnalyticsSeriesPoint] = []


class AnalyticsPhotosResponse(BaseModel):
    today: int = 0
    yesterday: int = 0
    this_week: int = 0
    growth: int = 0
    series: list[AnalyticsSeriesPoint] = []


class AnalyticsBackupResponse(BaseModel):
    last_backup: str = ""
    duration_seconds: int | None = None
    success_rate: float | None = None
    series: list[AnalyticsSeriesPoint] = []


class AnalyticsDailyOverview(BaseModel):
    agents_total: int = 0
    agents_online: int = 0
    alerts_today: int = 0
    notifications_today: int = 0
    history_points_today: int = 0


class AnalyticsOverviewResponse(BaseModel):
    cpu_average: float | None = None
    memory_average: float | None = None
    storage_used: int = 0
    photos_today: int = 0
    backup_success_rate: float | None = None
    temperature_average: float | None = None
    daily: AnalyticsDailyOverview = AnalyticsDailyOverview()


class TrendCpuResponse(BaseModel):
    latest: float | None = None
    average_1d: float | None = None
    average_7d: float | None = None
    average_30d: float | None = None
    trend: str = "stable"
    difference_percent: float | None = None
    hourly: list[AnalyticsSeriesPoint] = []
    daily: list[AnalyticsSeriesPoint] = []


class TrendMemoryResponse(TrendCpuResponse):
    pass


class TrendStorageResponse(BaseModel):
    current_used: int = 0
    used_percent: float | None = None
    daily_growth_bytes: int = 0
    weekly_growth_bytes: int = 0
    monthly_growth_bytes: int = 0
    growth_per_day: float = 0
    estimated_days_until_full: float | None = None
    estimated_full_date: str = ""
    trend: str = "stable"
    series: list[AnalyticsSeriesPoint] = []


class TrendPhotosResponse(BaseModel):
    today: int = 0
    yesterday: int = 0
    this_week: int = 0
    last_week: int = 0
    this_month: int = 0
    growth: int = 0
    daily: int = 0
    weekly: int = 0
    monthly: int = 0
    expected_next_week: int = 0
    trend: str = "stable"
    difference_percent: float | None = None
    series: list[AnalyticsSeriesPoint] = []


class TrendBackupResponse(BaseModel):
    last_30_backups: int = 0
    success_rate: float | None = None
    failure_rate: float | None = None
    average_duration: float | None = None
    fastest: int | None = None
    slowest: int | None = None
    running_count: int = 0
    expected_completion_seconds: int | None = None
    last_backup: str = ""
    trend: str = "stable"
    series: list[AnalyticsSeriesPoint] = []


class TrendHealthSummary(BaseModel):
    healthy_count: int = 0
    warning_count: int = 0
    critical_count: int = 0
    unknown_count: int = 0


class TrendOverviewResponse(BaseModel):
    cpu_trend: str = "stable"
    memory_trend: str = "stable"
    storage_trend: str = "stable"
    photo_trend: str = "stable"
    backup_trend: str = "stable"
    overall_health: str = "stable"
    overall_score: float = 0
    health: TrendHealthSummary = TrendHealthSummary()


class CapacityStorageResponse(BaseModel):
    current_used: int = 0
    current_free: int = 0
    capacity: int = 0
    average_daily_growth: float = 0
    average_weekly_growth: float = 0
    estimated_days_remaining: float | None = None
    estimated_full_date: str = ""
    estimated_full_in: str = "Unknown"
    risk: str = "unknown"
    series: list[AnalyticsSeriesPoint] = []


class CapacityPhotosResponse(BaseModel):
    photos_today: int = 0
    photos_this_week: int = 0
    average_photos_per_day: float = 0
    expected_photos_next_month: int = 0
    expected_storage_next_month: int = 0
    average_size_per_photo: float = 0
    series: list[AnalyticsSeriesPoint] = []


class CapacityBackupResponse(BaseModel):
    destination_capacity: int = 0
    current_backup_size: int = 0
    growth_per_day: float = 0
    estimated_days_remaining: float | None = None
    estimated_full_date: str = ""
    success_percent: float | None = None
    average_duration: float | None = None
    trend: str = "unknown"
    series: list[AnalyticsSeriesPoint] = []


class CapacitySystemResponse(BaseModel):
    cpu_trend: str = "stable"
    memory_trend: str = "stable"
    storage_trend: str = "stable"
    backup_trend: str = "stable"
    overall_score: float = 0
    bottleneck: str = "unknown"
    health: TrendHealthSummary = TrendHealthSummary()


class CapacityOverviewResponse(BaseModel):
    storage_remaining_days: float | None = None
    estimated_full_date: str = ""
    growth_per_day: float = 0
    photo_forecast: int = 0
    backup_forecast: str = ""
    capacity_score: float = 0
    bottleneck: str = "unknown"
    storage_risk: str = "unknown"
    backup_risk: str = "unknown"
    recommendations: list[str] = []
    series: list[AnalyticsSeriesPoint] = []


class InsightItem(BaseModel):
    summary: str = ""
    severity: str = "unknown"
    recommendation: str = ""


class InsightStorageResponse(InsightItem):
    estimated_days: float | None = None


class InsightPhotosResponse(InsightItem):
    pass


class InsightBackupResponse(InsightItem):
    pass


class InsightSystemResponse(BaseModel):
    cpu: InsightItem = InsightItem()
    memory: InsightItem = InsightItem()
    infrastructure: InsightItem = InsightItem()


class InsightOverviewResponse(BaseModel):
    overall: InsightItem = InsightItem()
    storage: InsightStorageResponse = InsightStorageResponse()
    cpu: InsightItem = InsightItem()
    memory: InsightItem = InsightItem()
    backup: InsightBackupResponse = InsightBackupResponse()
    photos: InsightPhotosResponse = InsightPhotosResponse()
    infrastructure: InsightItem = InsightItem()
    recommendation: str = ""
    severity: str = "unknown"


class DeveloperGitStatus(BaseModel):
    branch: str | None = None
    commit: str | None = None
    dirty: bool | None = None
    working_tree: str | None = None
    modified_files: int | None = None
    untracked_files: int | None = None
    ahead_count: int | None = None
    behind_count: int | None = None


class DeveloperProjectStatus(BaseModel):
    application_version: str = "1.0.0-rc3"
    build_time: str | None = None
    environment: str = "development"
    current_phase: int = 9
    current_sprint: str = "11.5"
    git: DeveloperGitStatus = DeveloperGitStatus()


class DeveloperRuntimeStatus(BaseModel):
    api: str = "unknown"
    dashboard: str = "unknown"
    agent: str = "unknown"
    database: str = "unknown"
    docker: str = "unknown"
    websocket: str = "unknown"
    telegram: str = "unknown"
    immich: str = "unknown"
    qumagie: str = "unknown"
    qnap: str = "unknown"
    backup: str = "unknown"


class DeveloperAgentService(BaseModel):
    state: str = "unknown"
    enabled: str = "unknown"
    agent_status: str = "unknown"
    last_heartbeat: datetime | None = None
    last_check_in: datetime | None = None
    last_report: datetime | None = None
    next_report_eta: datetime | None = None
    pid: int | None = None
    restart_count: int | None = None
    report_interval_seconds: int = 60
    systemd_status: str | None = None


class DeveloperBuildStatus(BaseModel):
    last_build: str | None = None
    build_status: str = "unknown"
    backend: str = "unknown"
    frontend: str = "unknown"
    docker_compose: str = "unknown"
    application_version: str = "1.0.0-rc3"
    environment: str = "development"


class DeveloperTestStatus(BaseModel):
    backend_tests: str = "unknown"
    frontend_tests: str = "unknown"
    lint: str = "unknown"
    ruff: str = "unknown"
    build: str = "unknown"
    qa: str = "unknown"


class DeveloperPhaseProgress(BaseModel):
    phase: int
    percent: float = 0


class DeveloperProgress(BaseModel):
    phases: list[DeveloperPhaseProgress] = []
    current_sprint: str = "11.5"
    roadmap: str = ""
    completed_percent: float = 0
    current_milestone: str = ""


class DeveloperStatistics(BaseModel):
    rest_apis: int = 0
    database_tables: int = 0
    agents: int = 0
    groups: int = 0
    users: int = 0
    alert_rules: int = 0
    notifications: int = 0
    photos: int = 0
    docker_services: int = 0
    frontend_pages: int = 0
    react_components: int = 0
    backend_modules: int = 0
    test_count: int = 0
    frontend_test_count: int = 0


class DeveloperActivityItem(BaseModel):
    kind: str
    message: str
    timestamp: datetime | None = None


class DeveloperSystemHealth(BaseModel):
    overall_health: float = 0
    overall_capacity: float = 0
    overall_trend: float = 0
    overall_infrastructure: float = 0


class DeveloperOverviewResponse(BaseModel):
    project: DeveloperProjectStatus = DeveloperProjectStatus()
    runtime: DeveloperRuntimeStatus = DeveloperRuntimeStatus()
    build: DeveloperBuildStatus = DeveloperBuildStatus()
    tests: DeveloperTestStatus = DeveloperTestStatus()
    progress: DeveloperProgress = DeveloperProgress()
    statistics: DeveloperStatistics = DeveloperStatistics()
    activity: list[DeveloperActivityItem] = []
    health: DeveloperSystemHealth = DeveloperSystemHealth()
    capacity_score: float = 0
    agent_service: DeveloperAgentService = DeveloperAgentService()


class AlertHistoryEntry(BaseModel):
    id: str
    alert_type: str
    severity: str
    started_at: datetime
    recovered_at: datetime | None = None
    duration_seconds: int | None = None
    agent_id: str
    agent_name: str
    source: str
    threshold: float | None = None
    peak_value: float | None = None
    status: str = "active"


class AlertStatisticsResponse(BaseModel):
    active_alerts: int = 0
    recovered_today: int = 0
    average_duration_seconds: float = 0
    critical_count: int = 0
    warning_count: int = 0
    recovery_rate: float = 0
    recovered: int = 0
    total: int = 0


class IncidentSummaryResponse(BaseModel):
    id: str
    started_at: datetime
    recovered_at: datetime | None = None
    duration_seconds: int | None = None
    agent_id: str
    agent_name: str
    severity: str
    status: str
    alert_count: int = 0
    cause: str = ""


class IncidentDetailResponse(IncidentSummaryResponse):
    affected_alerts: list[AlertHistoryEntry] = []


class IncidentStatisticsResponse(BaseModel):
    average_duration_seconds: float = 0
    open_count: int = 0
    recovered_count: int = 0
    critical_count: int = 0
    warning_count: int = 0
    incident_count: int = 0
    top_affected_agent: str = ""


class NotificationCenterItem(BaseModel):
    id: str
    title: str
    description: str = ""
    severity: str = "info"
    source: str
    kind: str
    agent_id: str | None = None
    agent_name: str | None = None
    read_state: str = "unread"
    created_at: datetime


class NotificationDayGroup(BaseModel):
    date: str
    label: str
    items: list[NotificationCenterItem] = []


class NotificationHistoryResponse(BaseModel):
    items: list[NotificationCenterItem] = []
    groups: list[NotificationDayGroup] = []


class NotificationDeliveryHistoryItem(BaseModel):
    id: str
    created_at: datetime
    sent_at: datetime | None = None
    channel: str
    event: str
    success: bool
    retry_count: int
    duration_ms: int
    error_message: str | None = None


class NotificationDeliveryHistoryResponse(BaseModel):
    items: list[NotificationDeliveryHistoryItem] = []


class NotificationMetricsResponse(BaseModel):
    total_sent: int
    total_success: int
    total_failed: int
    success_rate: float
    average_duration_ms: int
    max_duration_ms: int
    average_retry_count: float
    last_notification_at: datetime | None = None


class NotificationStatisticsResponse(BaseModel):
    unread: int = 0
    today: int = 0
    this_week: int = 0
    critical: int = 0
    total: int = 0


class PredictionForecast(BaseModel):
    horizon_days: int
    summary: str = ""
    value: float | None = None
    unit: str = ""


class PredictionMetricResponse(BaseModel):
    risk: str = "unknown"
    summary: str = ""
    recommendation: str = ""
    forecasts: list[PredictionForecast] = []
    series: list[AnalyticsSeriesPoint] = []


class PredictionOverviewResponse(BaseModel):
    overall_risk: str = "unknown"
    storage: PredictionMetricResponse = PredictionMetricResponse()
    system: PredictionMetricResponse = PredictionMetricResponse()
    photos: PredictionMetricResponse = PredictionMetricResponse()
    backup: PredictionMetricResponse = PredictionMetricResponse()
    recommendations: list[str] = []
    summary: str = ""


class PhotoEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    folder: str
    size_bytes: int
    created_at: datetime
    telegram_sent: bool


class PhotoEventListResponse(BaseModel):
    items: list[PhotoEventResponse] = []


class PhotoMonitorStatsResponse(BaseModel):
    today_count: int = 0
    last_photo: str | None = None
    last_folder: str | None = None
    last_update: datetime | None = None
    watch_folder: str = ""
    watch_folders: list[str] = []
    watch_folder_labels: list[str] = []
    indexed_files: int = 0
    status: str = "stopped"
    enabled: bool = False

    @field_validator("watch_folders", mode="before")
    @classmethod
    def coerce_watch_folders(cls, value: object) -> list[str]:
        return list(value) if isinstance(value, list) else []

    @field_validator("watch_folder_labels", mode="before")
    @classmethod
    def coerce_watch_folder_labels(cls, value: object) -> list[str]:
        return list(value) if isinstance(value, list) else []


class PhotoMonitorSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enabled: bool
    watch_folder: str
    watch_folders: list[str] = []
    watch_folder_labels: list[str] = []
    recursive: bool
    scan_interval_seconds: int
    max_events: int
    auto_delete_days: int

    @field_validator("watch_folders", mode="before")
    @classmethod
    def coerce_watch_folders(cls, value: object) -> list[str]:
        return list(value) if isinstance(value, list) else []

    @field_validator("watch_folder_labels", mode="before")
    @classmethod
    def coerce_watch_folder_labels(cls, value: object) -> list[str]:
        return list(value) if isinstance(value, list) else []


class PhotoMonitorSettingsUpdateRequest(BaseModel):
    enabled: bool
    watch_folder: str = ""
    watch_folders: list[str] = Field(default_factory=list)
    recursive: bool = True
    scan_interval_seconds: Literal[5, 10, 30, 60] = 5
    max_events: Literal[100, 500, 1000] = 500
    auto_delete_days: Literal[0, 30, 90] = 0

    @model_validator(mode="after")
    def normalize_watch_folders(self) -> "PhotoMonitorSettingsUpdateRequest":
        folders = [item.strip() for item in self.watch_folders if item.strip()]
        if len(folders) != len(set(folders)):
            raise ValueError("Duplicate watch folders are not allowed")
        if not folders and self.watch_folder.strip():
            folders = [self.watch_folder.strip()]
        if not folders:
            raise ValueError("At least one watch folder is required")
        unique: list[str] = []
        seen: set[str] = set()
        for item in folders:
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)
        self.watch_folders = unique
        self.watch_folder = unique[0]
        return self


class SqliteBackupStatusResponse(BaseModel):
    enabled: bool = True
    status: str = "unknown"
    latest_file: str = ""
    latest_at: str = ""
    size_bytes: int = 0
    uncompressed_bytes: int = 0
    next_scheduled: str = ""
    retention_daily: int = 7
    retention_weekly: int = 4
    retention_monthly: int = 6
    last_verification: str = ""
    integrity: str = "unknown"
    stored_path: str = ""
    duration_seconds: float = 0
    error: str = ""


class BackupStatusResponse(BaseModel):
    read_only: bool = True
    status: str
    backup_health: str = "unknown"
    job_name: str = ""
    job_type: str = ""
    progress_percent: float = 0
    last_backup: str = ""
    next_backup: str = ""
    duration_seconds: int = 0
    backup_size_bytes: int = 0
    last_error: str = ""
    last_success: str = ""
    updated_at: datetime
    destination: BackupDestinationResponse
    history: list[BackupHistoryPeriodResponse] = []
    sqlite: SqliteBackupStatusResponse | None = None
