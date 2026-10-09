export interface DashboardOverview {
  agents: {
    total: number
    online: number
    offline: number
  }
  reports: {
    total: number
  }
  groups: {
    total: number
  }
  group_stats: GroupOverviewStat[]
}

export interface GroupOverviewStat {
  id: string
  name: string
  agents: number
  online: number
}

export interface AgentSummary {
  id: string
  name: string
  hostname: string
  version: string
  status: string
  last_seen_at: string | null
  groups?: string[]
  labels?: string[]
  tags?: string[]
}

export interface AgentDetail extends AgentSummary {
  configuration_revision: number
  capabilities: string[]
}

export interface DiskMetrics {
  filesystem: string
  mount_point: string
  filesystem_type: string
  total_bytes: number
  used_bytes: number
  free_bytes: number
  usage_percent: number
}

export interface TemperatureMetrics {
  source: string
  label: string
  current_celsius: number
  high_celsius: number | null
  critical_celsius: number | null
}

export interface SystemMetrics {
  hostname?: string
  os?: {
    distribution: string
    distribution_id: string
    distribution_version: string
    kernel: string
    architecture: string
  }
  cpu?: {
    usage_percent: number
    logical_count: number
    physical_count: number
  }
  memory?: {
    total_bytes: number
    used_bytes: number
    available_bytes: number
    usage_percent: number
  }
  disks?: DiskMetrics[]
  load_average?: {
    '1_minute': number
    '5_minutes': number
    '15_minutes': number
  }
  uptime_seconds?: number
  temperatures?: TemperatureMetrics[]
}

export interface ReportModule {
  module: string
  status: string
  summary: string
  metrics: SystemMetrics | Record<string, unknown>
  diagnostics: Record<string, unknown>
}

export interface LatestMetricReport {
  id: string
  agent_id: string
  report_id: string
  schema_version: string
  observed_at: string
  received_at: string
  payload: {
    modules: ReportModule[]
    [key: string]: unknown
  }
}

export interface HistoryPoint {
  timestamp: string
  cpu_percent: number | null
  memory_percent: number | null
  disk_percent: number | null
  temperature_celsius: number | null
  network_rx_bytes: number | null
  network_tx_bytes: number | null
}

export interface AgentHistory {
  agent_id: string
  interval: '1m' | '5m' | '15m' | '1h'
  from: string
  to: string
  points: HistoryPoint[]
}

export interface ActiveAlert {
  id: string
  agent_id: string
  agent_name: string
  kind: string
  resource: string
  severity: string
  current_value: number | null
  threshold: number | null
  message: string
  opened_at: string
  last_observed_at: string
  status?: string
  started_at?: string | null
  last_triggered_at?: string | null
  recovered_at?: string | null
  duration_seconds?: number | null
}

export interface GroupSummary {
  id: string
  name: string
  description: string
  agents: number
  online: number
  agent_ids: string[]
}

export interface GroupDetail extends GroupSummary {
  created_at: string
  updated_at: string
  members: AgentSummary[]
}

export interface GroupSummaryList {
  total: number
  groups: GroupSummary[]
}

export type NotificationChannel = 'telegram' | 'discord' | 'slack' | 'email'
export type NotificationStatus = 'pending' | 'sent' | 'failed'

export interface NotificationDelivery {
  id: string
  alert_id: string | null
  channel: NotificationChannel
  recipient: string
  status: NotificationStatus
  error_message: string
  sent_at: string | null
  created_at: string
  updated_at: string
}

export interface NotificationList {
  total: number
  notifications: NotificationDelivery[]
}

export interface TelegramNotificationSettings {
  enabled: boolean
  configured: boolean
  api_base_url: string
  chat_id: string
  bot_token_set: boolean
  last_test: string | null
}

export interface WebhookNotificationSettings {
  enabled: boolean
  configured: boolean
  webhook_url_set: boolean
}

export interface EmailNotificationSettings {
  enabled: boolean
  configured: boolean
  host: string
  port: number
  username: string
  from_address: string
  to_address: string
  use_tls: boolean
  password_set: boolean
}

export interface ScheduledReportCard {
  enabled: boolean
  last_sent: string | null
  next_scheduled: string | null
  status: string
}

export interface ScheduledReportsSettings {
  hourly_enabled: boolean
  daily_enabled: boolean
  weekly_enabled: boolean
  hour_interval: number
  daily_time: string
  weekly_day: string
  weekly_time: string
  timezone: string
  hourly: ScheduledReportCard
  daily: ScheduledReportCard
  weekly: ScheduledReportCard
}

export interface TelegramTestReportResult {
  status: string
  notification_id: string | null
  sent_at: string | null
  provider: string
}

export interface NotificationSettings {
  telegram: TelegramNotificationSettings
  discord: WebhookNotificationSettings
  slack: WebhookNotificationSettings
  email: EmailNotificationSettings
  reports: ScheduledReportsSettings
}

export type AlertMetric =
  | 'cpu_percent'
  | 'memory_percent'
  | 'disk_percent'
  | 'temperature_celsius'
  | 'agent_offline'

export type AlertOperator = '>' | '>=' | '<' | '<=' | '==' | '!='
export type AlertSeverity = 'critical' | 'high' | 'medium' | 'low'
export type AlertAppliesTo = 'all' | 'group' | 'agent'

export interface AlertRule {
  id: string
  name: string
  description: string
  metric: AlertMetric
  operator: AlertOperator
  threshold: number
  severity: AlertSeverity
  enabled: boolean
  cooldown_seconds: number
  applies_to: AlertAppliesTo
  group_id: string | null
  agent_id: string | null
  preview: string
  created_at: string
  updated_at: string
}

export interface AlertRulePayload {
  name: string
  description: string
  metric: AlertMetric
  operator: AlertOperator
  threshold: number
  severity: AlertSeverity
  enabled: boolean
  cooldown_seconds: number
  applies_to: AlertAppliesTo
  group_id?: string | null
  agent_id?: string | null
}

export type InfrastructureStatus = 'healthy' | 'degraded' | 'unhealthy' | 'unknown'

export interface QnapDiskRecord {
  bay: number | null
  alias: string | null
  installed: boolean
  is_ssd: boolean | null
  temperature_celsius: number | null
  temp_alert: number | null
  temperature_status: string
  manufacturer: null
  model: null
  capacity_bytes: null
  smart_status: null
  abnormal_sector_count: null
}

export interface InfrastructureSnapshot {
  service: string
  status: InfrastructureStatus
  version: string
  updated_at: string
  summary: Record<string, string | number | boolean | null | QnapDiskRecord[]>
}

export interface InfrastructureSummary {
  collected_at: string
  services: InfrastructureSnapshot[]
}

export interface PhotoGrowth {
  today: number
  yesterday: number
  this_week: number
}

export interface StorageHistory {
  today: number
  yesterday: number
  last_week: number
}

export interface PhotoStats {
  indexed_photos: number
  indexed_videos: number
  albums: number
  users: number
  storage_used: number
  storage_free: number
  storage_percent: number
  thumbnail_queue: number
  face_queue: number
  last_scan: string
  capacity_bytes: number
  storage_health: string
  storage_percent_metric: number
  thumbnail_queue_metric: number
  face_queue_metric: number
  immich_health: number
  qumagie_health: number
  storage_history: StorageHistory
  photo_growth: PhotoGrowth
}

export interface PhotoServicesSummary {
  collected_at: string
  read_only: boolean
  services: InfrastructureSnapshot[]
  stats: PhotoStats
}

export interface PhotoEvent {
  id: number
  filename: string
  folder: string
  size_bytes: number
  created_at: string
  telegram_sent: boolean
}

export interface PhotoEventList {
  items: PhotoEvent[]
}

export interface PhotoMonitorStats {
  today_count: number
  last_photo: string | null
  last_folder?: string | null
  last_update: string | null
  watch_folder: string
  watch_folders?: string[]
  watch_folder_labels?: string[]
  indexed_files?: number
  status?: string
  enabled: boolean
}

export interface PhotoMonitorSettings {
  enabled: boolean
  watch_folder: string
  watch_folders?: string[]
  watch_folder_labels?: string[]
  recursive: boolean
  scan_interval_seconds: 5 | 10 | 30 | 60
  max_events: 100 | 500 | 1000
  auto_delete_days: 0 | 30 | 90
}

export interface BackupDestination {
  hostname: string
  ip: string
  model: string
}

export interface BackupHistoryPeriod {
  period: string
  label: string
  status: string
}

export interface SqliteBackupStatus {
  enabled: boolean
  status: string
  latest_file: string
  latest_at: string
  size_bytes: number
  uncompressed_bytes: number
  next_scheduled: string
  retention_daily: number
  retention_weekly: number
  retention_monthly: number
  last_verification: string
  integrity: string
  stored_path: string
  duration_seconds: number
  error: string
}

export interface BackupStatus {
  read_only: boolean
  status: string
  backup_health: string
  job_name: string
  job_type: string
  progress_percent: number
  last_backup: string
  next_backup: string
  duration_seconds: number
  backup_size_bytes: number
  last_error: string
  last_success: string
  updated_at: string
  destination: BackupDestination
  history: BackupHistoryPeriod[]
  sqlite?: SqliteBackupStatus | null
}

export interface AnalyticsSeriesPoint {
  timestamp: string | null
  label: string
  value: number | null
}

export interface AnalyticsCpu {
  current: number | null
  average_24h: number | null
  minimum: number | null
  maximum: number | null
  series: AnalyticsSeriesPoint[]
}

export interface AnalyticsMemory {
  current: number | null
  average: number | null
  series: AnalyticsSeriesPoint[]
}

export interface AnalyticsStorage {
  current: number
  daily_growth: number
  weekly_growth: number
  series: AnalyticsSeriesPoint[]
}

export interface AnalyticsTemperature {
  current: number | null
  average: number | null
  series: AnalyticsSeriesPoint[]
}

export interface AnalyticsPhotos {
  today: number
  yesterday: number
  this_week: number
  growth: number
  series: AnalyticsSeriesPoint[]
}

export interface AnalyticsBackup {
  last_backup: string
  duration_seconds: number | null
  success_rate: number | null
  series: AnalyticsSeriesPoint[]
}

export interface AnalyticsDailyOverview {
  agents_total: number
  agents_online: number
  alerts_today: number
  notifications_today: number
  history_points_today: number
}

export interface AnalyticsOverview {
  cpu_average: number | null
  memory_average: number | null
  storage_used: number
  photos_today: number
  backup_success_rate: number | null
  temperature_average: number | null
  daily: AnalyticsDailyOverview
}

export interface TrendMetric {
  latest: number | null
  average_1d: number | null
  average_7d: number | null
  average_30d: number | null
  trend: string
  difference_percent: number | null
  hourly: AnalyticsSeriesPoint[]
  daily: AnalyticsSeriesPoint[]
}

export interface TrendStorage {
  current_used: number
  used_percent: number | null
  daily_growth_bytes: number
  weekly_growth_bytes: number
  monthly_growth_bytes: number
  growth_per_day: number
  estimated_days_until_full: number | null
  estimated_full_date: string
  trend: string
  series: AnalyticsSeriesPoint[]
}

export interface TrendPhotos {
  today: number
  yesterday: number
  this_week: number
  last_week: number
  this_month: number
  growth: number
  daily: number
  weekly: number
  monthly: number
  expected_next_week: number
  trend: string
  difference_percent: number | null
  series: AnalyticsSeriesPoint[]
}

export interface TrendBackup {
  last_30_backups: number
  success_rate: number | null
  failure_rate: number | null
  average_duration: number | null
  fastest: number | null
  slowest: number | null
  running_count: number
  expected_completion_seconds: number | null
  last_backup: string
  trend: string
  series: AnalyticsSeriesPoint[]
}

export interface TrendHealth {
  healthy_count: number
  warning_count: number
  critical_count: number
  unknown_count: number
}

export interface TrendOverview {
  cpu_trend: string
  memory_trend: string
  storage_trend: string
  photo_trend: string
  backup_trend: string
  overall_health: string
  overall_score: number
  health: TrendHealth
}

export interface CapacityStorage {
  current_used: number
  current_free: number
  capacity: number
  average_daily_growth: number
  average_weekly_growth: number
  estimated_days_remaining: number | null
  estimated_full_date: string
  estimated_full_in?: string
  risk: string
  series: AnalyticsSeriesPoint[]
}

export interface CapacityPhotos {
  photos_today: number
  photos_this_week: number
  average_photos_per_day: number
  expected_photos_next_month: number
  expected_storage_next_month: number
  average_size_per_photo: number
  series: AnalyticsSeriesPoint[]
}

export interface CapacityBackup {
  destination_capacity: number
  current_backup_size: number
  growth_per_day: number
  estimated_days_remaining: number | null
  estimated_full_date: string
  success_percent: number | null
  average_duration: number | null
  trend: string
  series: AnalyticsSeriesPoint[]
}

export interface CapacitySystem {
  cpu_trend: string
  memory_trend: string
  storage_trend: string
  backup_trend: string
  overall_score: number
  bottleneck: string
  health: TrendHealth
}

export interface CapacityOverview {
  storage_remaining_days: number | null
  estimated_full_date: string
  growth_per_day: number
  photo_forecast: number
  backup_forecast: string
  capacity_score: number
  bottleneck: string
  storage_risk: string
  backup_risk: string
  recommendations: string[]
  series: AnalyticsSeriesPoint[]
}

export interface DeveloperGit {
  branch: string | null
  commit: string | null
  dirty: boolean | null
  working_tree: string | null
  modified_files: number | null
  untracked_files: number | null
  ahead_count: number | null
  behind_count: number | null
}

export interface DeveloperOverview {
  project: {
    application_version: string
    build_time: string | null
    environment: string
    current_phase: number
    current_sprint: string
    git: DeveloperGit
  }
  runtime: Record<
    | 'api'
    | 'dashboard'
    | 'agent'
    | 'database'
    | 'docker'
    | 'websocket'
    | 'telegram'
    | 'immich'
    | 'qumagie'
    | 'qnap'
    | 'backup',
    string
  >
  build: {
    last_build: string | null
    build_status: string
    backend: string
    frontend: string
    docker_compose: string
    application_version: string
    environment: string
  }
  tests: {
    backend_tests: string
    frontend_tests: string
    lint: string
    ruff: string
    build: string
    qa: string
  }
  progress: {
    phases: { phase: number; percent: number }[]
    current_sprint: string
    roadmap: string
    completed_percent: number
    current_milestone: string
  }
  statistics: {
    rest_apis: number
    database_tables: number
    agents: number
    groups: number
    users: number
    alert_rules: number
    notifications: number
    photos: number
    docker_services: number
    frontend_pages: number
    react_components: number
    backend_modules: number
    test_count: number
    frontend_test_count: number
  }
  activity: { kind: string; message: string; timestamp: string | null }[]
  health: {
    overall_health: number
    overall_capacity: number
    overall_trend: number
    overall_infrastructure: number
  }
  capacity_score: number
  agent_service: {
    state: string
    enabled: string
    agent_status: string
    last_heartbeat: string | null
    last_check_in: string | null
    last_report: string | null
    next_report_eta: string | null
    pid: number | null
    restart_count: number | null
    report_interval_seconds: number
    systemd_status: string | null
  }
}

export interface InsightItem {
  summary: string
  severity: string
  recommendation: string
}

export interface InsightStorage extends InsightItem {
  estimated_days: number | null
}

export interface InsightSystem {
  cpu: InsightItem
  memory: InsightItem
  infrastructure: InsightItem
}

export interface InsightOverview {
  overall: InsightItem
  storage: InsightStorage
  cpu: InsightItem
  memory: InsightItem
  backup: InsightItem
  photos: InsightItem
  infrastructure: InsightItem
  recommendation: string
  severity: string
}

export interface AlertHistoryEntry {
  id: string
  alert_type: string
  severity: string
  started_at: string
  recovered_at: string | null
  duration_seconds: number | null
  agent_id: string
  agent_name: string
  source: string
  threshold: number | null
  peak_value: number | null
  status: string
}

export interface AlertStatistics {
  active_alerts: number
  recovered_today: number
  average_duration_seconds: number
  critical_count: number
  warning_count: number
  recovery_rate: number
  recovered: number
  total: number
}

export interface IncidentSummary {
  id: string
  started_at: string
  recovered_at: string | null
  duration_seconds: number | null
  agent_id: string
  agent_name: string
  severity: string
  status: string
  alert_count: number
  cause: string
}

export interface IncidentDetail extends IncidentSummary {
  affected_alerts: AlertHistoryEntry[]
}

export interface IncidentStatistics {
  average_duration_seconds: number
  open_count: number
  recovered_count: number
  critical_count: number
  warning_count: number
  incident_count: number
  top_affected_agent: string
}

export interface NotificationCenterItem {
  id: string
  title: string
  description: string
  severity: string
  source: string
  kind: string
  agent_id: string | null
  agent_name: string | null
  read_state: string
  created_at: string
}

export interface NotificationHistory {
  items: NotificationCenterItem[]
  groups: { date: string; label: string; items: NotificationCenterItem[] }[]
}

export interface NotificationCenterStatistics {
  unread: number
  today: number
  this_week: number
  critical: number
  total: number
}

export interface NotificationDeliveryMetrics {
  total_sent: number
  total_success: number
  total_failed: number
  success_rate: number
  average_duration_ms: number
  max_duration_ms: number
  average_retry_count: number
  last_notification_at: string | null
}

export interface NotificationDeliveryHistoryItem {
  id: string
  created_at: string
  sent_at: string | null
  channel: string
  event: string
  success: boolean
  retry_count: number
  duration_ms: number
  error_message: string | null
}

export interface NotificationDeliveryHistory {
  items: NotificationDeliveryHistoryItem[]
}

export interface PredictionForecast {
  horizon_days: number
  summary: string
  value: number | null
  unit: string
}

export interface PredictionMetric {
  risk: string
  summary: string
  recommendation: string
  forecasts: PredictionForecast[]
  series: { timestamp: string | null; label: string; value: number }[]
}

export interface PredictionOverview {
  overall_risk: string
  storage: PredictionMetric
  system: PredictionMetric
  photos: PredictionMetric
  backup: PredictionMetric
  recommendations: string[]
  summary: string
}

export type RemoteAccessStatus = 'connected' | 'disconnected' | 'not_installed' | 'unknown'

export interface RemoteAccess {
  enabled: boolean
  provider: string
  hostname: string | null
  tailnet_ip: string | null
  https: boolean
  serve_enabled: boolean
  funnel_enabled: boolean
  public: boolean
  status: RemoteAccessStatus
}

export type ProductionHealthStatus = 'healthy' | 'warning' | 'critical' | 'unknown'

export interface ProductionHealthCheck {
  component: string
  status: ProductionHealthStatus
  last_check: string
  latency_ms: number | null
  message: string
  warning: string | null
  error: string | null
  possible_cause: string | null
  recommended_action: string | null
}

export interface ObservabilitySnapshot {
  last_self_check: string | null
  last_backup: string | null
  last_telegram: string | null
  last_photo_scan: string | null
  last_agent_checkin: string | null
  api_latency_ms: number | null
  database_size_bytes: number | null
  database_growth_bytes: number | null
  telegram_success_rate: number | null
  photo_monitor_latency_ms: number | null
  backup_success_rate: number | null
  cpu_history: number[]
  memory_history: number[]
  disk_history: number[]
}

export interface ProductionHealth {
  generated_at: string
  score: number
  status: 'excellent' | 'good' | 'warning' | 'critical'
  checks: ProductionHealthCheck[]
  last_self_check?: string | null
  last_backup?: string | null
  last_telegram?: string | null
  last_photo_scan?: string | null
  last_agent_checkin?: string | null
  observability?: ObservabilitySnapshot | null
  performance?: PerformanceSnapshot | null
}

export interface PerformanceWindow {
  samples: number
  api_ms: number | null
  query_ms: number | null
  photo_scan_ms: number | null
  backup_seconds: number | null
}

export interface PerformanceSnapshot {
  generated_at: string
  performance_score: number
  reliability_score: number
  current: Record<string, number | null | undefined>
  windows: Record<string, PerformanceWindow>
}

export interface OperationItem {
  id: string
  label: string
  admin_only: boolean
}

export interface OperationHistoryItem {
  id: string
  operation: string
  label: string
  status: string
  progress: string
  actor: string
  started_at: string
  finished_at: string | null
  ok: boolean | null
  detail: string
  duration_ms?: number
}

export interface ProductionRuntime {
  agent: {
    state: string
    restart_count: number | null
    last_heartbeat: string | null
    last_report: string | null
    last_metrics_upload: string | null
  }
  docker_available: boolean
  containers: {
    container: string
    status: string
    health: string
    restart_count: number | null
    image: string
    running_since: string | null
  }[]
  telegram: {
    bot_connected: boolean | null
    last_successful_send: string | null
    last_failed_send: string | null
    failure_reason: string | null
    retry_queue: number
  }
  tailscale: {
    connected: boolean
    tailnet: string | null
    magic_dns: boolean | null
    connection_type: string
    exit_node: string | null
    remote_access_url: string | null
    hostname: string | null
    ip: string | null
    https: boolean
  }
}

export interface ProductionStorage {
  filesystem: string
  disk_usage_percent: number | null
  free_space_bytes: number | null
  database_size_bytes: number | null
  log_size_bytes: number | null
  disk_read_bytes: number | null
  disk_write_bytes: number | null
  io_wait_percent: number | null
  status: ProductionHealthStatus
}

export interface ProductionNetwork {
  lan_ip: string | null
  tailscale_ip: string | null
  gateway: string | null
  internet: ProductionHealthStatus
  latency_ms: number | null
  dns: ProductionHealthStatus
  upload_bytes: number | null
  download_bytes: number | null
  network_errors: number | null
}

export interface ProductionHealthOverview {
  health: ProductionHealth
  runtime: ProductionRuntime
  storage: ProductionStorage
  network: ProductionNetwork
}
