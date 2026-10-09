import { isNotFound } from '../utils/errors'
import { apiClient } from './client'
import type {
  ActiveAlert,
  AgentDetail,
  AgentHistory,
  AgentSummary,
  DashboardOverview,
  GroupDetail,
  GroupSummary,
  GroupSummaryList,
  LatestMetricReport,
  NotificationDelivery,
  NotificationList,
  NotificationSettings,
  TelegramTestReportResult,
  AlertRule,
  AlertRulePayload,
  InfrastructureSnapshot,
  InfrastructureSummary,
  PhotoServicesSummary,
  PhotoEventList,
  PhotoEvent,
  PhotoMonitorStats,
  PhotoMonitorSettings,
  BackupStatus,
  AnalyticsOverview,
  AnalyticsCpu,
  AnalyticsMemory,
  AnalyticsStorage,
  AnalyticsTemperature,
  AnalyticsPhotos,
  AnalyticsBackup,
  TrendOverview,
  TrendMetric,
  TrendStorage,
  TrendPhotos,
  TrendBackup,
  CapacityOverview,
  CapacityStorage,
  CapacityPhotos,
  CapacityBackup,
  CapacitySystem,
  DeveloperOverview,
  InsightOverview,
  InsightStorage,
  InsightSystem,
  InsightItem,
  AlertHistoryEntry,
  AlertStatistics,
  IncidentSummary,
  IncidentDetail,
  IncidentStatistics,
  NotificationHistory,
  NotificationCenterStatistics,
  NotificationDeliveryMetrics,
  NotificationDeliveryHistory,
  PredictionOverview,
  PredictionMetric,
  RemoteAccess,
  ProductionHealth,
  ProductionHealthOverview,
  ProductionNetwork,
  ProductionRuntime,
  ProductionStorage,
  OperationHistoryItem,
  OperationItem,
} from '../types/dashboard'

export async function getDashboardOverview(): Promise<DashboardOverview> {
  const response = await apiClient.get<DashboardOverview>('/dashboard/overview')
  return response.data
}

export async function getAgents(): Promise<AgentSummary[]> {
  const response = await apiClient.get<AgentSummary[]>('/agents')
  return response.data
}

export async function getAgent(agentId: string): Promise<AgentDetail> {
  const response = await apiClient.get<AgentDetail>(`/agents/${encodeURIComponent(agentId)}`)
  return response.data
}

export async function getLatestAgentReport(agentId: string): Promise<LatestMetricReport> {
  const response = await apiClient.get<LatestMetricReport>(
    `/agents/${encodeURIComponent(agentId)}/latest-report`,
  )
  return response.data
}

export async function getActiveAlerts(includeRecovered = false): Promise<ActiveAlert[]> {
  try {
    const response = await apiClient.get<ActiveAlert[]>('/alerts/active', {
      params: includeRecovered ? { include_recovered: true } : undefined,
    })
    return response.data
  } catch (error) {
    if (isNotFound(error)) {
      return []
    }
    throw error
  }
}

export async function getAgentHistory(
  agentId: string,
  params: { from: string; to: string; interval: AgentHistory['interval'] },
): Promise<AgentHistory> {
  const response = await apiClient.get<AgentHistory>(
    `/history/agents/${encodeURIComponent(agentId)}`,
    { params },
  )
  return response.data
}

export async function getGroups(): Promise<GroupSummary[]> {
  const response = await apiClient.get<GroupSummary[]>('/groups')
  return response.data
}

export async function getGroupsSummary(): Promise<GroupSummaryList> {
  const response = await apiClient.get<GroupSummaryList>('/groups/summary')
  return response.data
}

export async function getGroup(groupId: string): Promise<GroupDetail> {
  const response = await apiClient.get<GroupDetail>(`/groups/${encodeURIComponent(groupId)}`)
  return response.data
}

export async function createGroup(payload: { name: string; description: string }): Promise<GroupDetail> {
  const response = await apiClient.post<GroupDetail>('/groups', payload)
  return response.data
}

export async function updateGroup(
  groupId: string,
  payload: { name: string; description: string },
): Promise<GroupDetail> {
  const response = await apiClient.put<GroupDetail>(
    `/groups/${encodeURIComponent(groupId)}`,
    payload,
  )
  return response.data
}

export async function deleteGroup(groupId: string): Promise<void> {
  await apiClient.delete(`/groups/${encodeURIComponent(groupId)}`)
}

export async function assignAgentsToGroup(groupId: string, agentIds: string[]): Promise<GroupDetail> {
  const response = await apiClient.post<GroupDetail>(
    `/groups/${encodeURIComponent(groupId)}/agents`,
    { agent_ids: agentIds },
  )
  return response.data
}

export async function removeAgentFromGroup(groupId: string, agentId: string): Promise<GroupDetail> {
  const response = await apiClient.delete<GroupDetail>(
    `/groups/${encodeURIComponent(groupId)}/agents/${encodeURIComponent(agentId)}`,
  )
  return response.data
}

export async function getNotifications(): Promise<NotificationList> {
  const response = await apiClient.get<NotificationList>('/notifications')
  return response.data
}

export async function getNotification(notificationId: string): Promise<NotificationDelivery> {
  const response = await apiClient.get<NotificationDelivery>(
    `/notifications/${encodeURIComponent(notificationId)}`,
  )
  return response.data
}

export async function sendTestNotification(
  channel?: NotificationDelivery['channel'],
): Promise<NotificationList> {
  const response = await apiClient.post<NotificationList>(
    '/notifications/test',
    channel ? { channel } : {},
  )
  return response.data
}

export async function sendTelegramTestReport(): Promise<TelegramTestReportResult> {
  const response = await apiClient.post<TelegramTestReportResult>('/notifications/test-report')
  return response.data
}

export async function retryNotification(notificationId: string): Promise<NotificationDelivery> {
  const response = await apiClient.post<NotificationDelivery>(
    `/notifications/${encodeURIComponent(notificationId)}/retry`,
  )
  return response.data
}

export async function getNotificationSettings(): Promise<NotificationSettings> {
  const response = await apiClient.get<NotificationSettings>('/settings/notifications')
  return response.data
}

export async function updateNotificationSettings(
  payload: Record<string, unknown>,
): Promise<NotificationSettings> {
  const response = await apiClient.put<NotificationSettings>('/settings/notifications', payload)
  return response.data
}

export async function getAlertRules(): Promise<AlertRule[]> {
  const response = await apiClient.get<AlertRule[]>('/alert-rules')
  return response.data
}

export async function createAlertRule(payload: AlertRulePayload): Promise<AlertRule> {
  const response = await apiClient.post<AlertRule>('/alert-rules', payload)
  return response.data
}

export async function updateAlertRule(ruleId: string, payload: AlertRulePayload): Promise<AlertRule> {
  const response = await apiClient.put<AlertRule>(`/alert-rules/${encodeURIComponent(ruleId)}`, payload)
  return response.data
}

export async function setAlertRuleEnabled(ruleId: string, enabled: boolean): Promise<AlertRule> {
  const response = await apiClient.patch<AlertRule>(
    `/alert-rules/${encodeURIComponent(ruleId)}/enable`,
    { enabled },
  )
  return response.data
}

export async function deleteAlertRule(ruleId: string): Promise<void> {
  await apiClient.delete(`/alert-rules/${encodeURIComponent(ruleId)}`)
}

export async function getInfrastructure(): Promise<InfrastructureSummary> {
  const response = await apiClient.get<InfrastructureSummary>('/infrastructure')
  return response.data
}

export async function getInfrastructureService(service: string): Promise<InfrastructureSnapshot> {
  const response = await apiClient.get<InfrastructureSnapshot>(
    `/infrastructure/${encodeURIComponent(service)}`,
  )
  return response.data
}

export async function getPhotoServices(): Promise<PhotoServicesSummary> {
  const response = await apiClient.get<PhotoServicesSummary>('/photo-services')
  return response.data
}

export async function getPhotoEvents(limit = 20): Promise<PhotoEventList> {
  const response = await apiClient.get<PhotoEventList>('/photos', { params: { limit } })
  return response.data
}

export async function getLatestPhoto(): Promise<PhotoEvent> {
  const response = await apiClient.get<PhotoEvent>('/photos/latest')
  return response.data
}

export async function getPhotoMonitorStats(): Promise<PhotoMonitorStats> {
  const response = await apiClient.get<PhotoMonitorStats>('/photos/stats')
  return response.data
}

export async function getPhotoMonitorSettings(): Promise<PhotoMonitorSettings> {
  const response = await apiClient.get<PhotoMonitorSettings>('/photos/settings')
  return response.data
}

export async function updatePhotoMonitorSettings(
  payload: PhotoMonitorSettings,
): Promise<PhotoMonitorSettings> {
  const response = await apiClient.put<PhotoMonitorSettings>('/photos/settings', payload)
  return response.data
}

export async function getBackupStatus(): Promise<BackupStatus> {
  const response = await apiClient.get<BackupStatus>('/backup')
  return response.data
}

export async function getAnalyticsOverview(): Promise<AnalyticsOverview> {
  const response = await apiClient.get<AnalyticsOverview>('/analytics/overview')
  return response.data
}

export async function getAnalyticsCpu(): Promise<AnalyticsCpu> {
  const response = await apiClient.get<AnalyticsCpu>('/analytics/cpu')
  return response.data
}

export async function getAnalyticsMemory(): Promise<AnalyticsMemory> {
  const response = await apiClient.get<AnalyticsMemory>('/analytics/memory')
  return response.data
}

export async function getAnalyticsStorage(): Promise<AnalyticsStorage> {
  const response = await apiClient.get<AnalyticsStorage>('/analytics/storage')
  return response.data
}

export async function getAnalyticsTemperature(): Promise<AnalyticsTemperature> {
  const response = await apiClient.get<AnalyticsTemperature>('/analytics/temperature')
  return response.data
}

export async function getAnalyticsPhotos(): Promise<AnalyticsPhotos> {
  const response = await apiClient.get<AnalyticsPhotos>('/analytics/photos')
  return response.data
}

export async function getAnalyticsBackup(): Promise<AnalyticsBackup> {
  const response = await apiClient.get<AnalyticsBackup>('/analytics/backup')
  return response.data
}

export async function getTrendsOverview(): Promise<TrendOverview> {
  const response = await apiClient.get<TrendOverview>('/trends/overview')
  return response.data
}

export async function getTrendsCpu(): Promise<TrendMetric> {
  const response = await apiClient.get<TrendMetric>('/trends/cpu')
  return response.data
}

export async function getTrendsMemory(): Promise<TrendMetric> {
  const response = await apiClient.get<TrendMetric>('/trends/memory')
  return response.data
}

export async function getTrendsStorage(): Promise<TrendStorage> {
  const response = await apiClient.get<TrendStorage>('/trends/storage')
  return response.data
}

export async function getTrendsPhotos(): Promise<TrendPhotos> {
  const response = await apiClient.get<TrendPhotos>('/trends/photos')
  return response.data
}

export async function getTrendsBackup(): Promise<TrendBackup> {
  const response = await apiClient.get<TrendBackup>('/trends/backup')
  return response.data
}

export async function getCapacityOverview(): Promise<CapacityOverview> {
  const response = await apiClient.get<CapacityOverview>('/capacity/overview')
  return response.data
}

export async function getCapacityStorage(): Promise<CapacityStorage> {
  const response = await apiClient.get<CapacityStorage>('/capacity/storage')
  return response.data
}

export async function getCapacityPhotos(): Promise<CapacityPhotos> {
  const response = await apiClient.get<CapacityPhotos>('/capacity/photos')
  return response.data
}

export async function getCapacityBackup(): Promise<CapacityBackup> {
  const response = await apiClient.get<CapacityBackup>('/capacity/backup')
  return response.data
}

export async function getCapacitySystem(): Promise<CapacitySystem> {
  const response = await apiClient.get<CapacitySystem>('/capacity/system')
  return response.data
}

export async function getDeveloperOverview(): Promise<DeveloperOverview> {
  const response = await apiClient.get<DeveloperOverview>('/developer/overview')
  return response.data
}

export async function getRemoteAccess(): Promise<RemoteAccess> {
  const response = await apiClient.get<RemoteAccess>('/system/remote-access')
  return response.data
}

export async function getOperations(): Promise<OperationItem[]> {
  const response = await apiClient.get<OperationItem[]>('/operations')
  return response.data
}

export async function getOperationHistory(): Promise<OperationHistoryItem[]> {
  const response = await apiClient.get<OperationHistoryItem[]>('/operations/history')
  return response.data
}

export async function runOperation(operationId: string): Promise<OperationHistoryItem> {
  const response = await apiClient.post<OperationHistoryItem>(
    `/operations/${encodeURIComponent(operationId)}/run`,
    { confirm: true },
  )
  return response.data
}

export async function getProductionHealthOverview(): Promise<ProductionHealthOverview> {
  const [health, runtime, storage, network] = await Promise.all([
    apiClient.get<ProductionHealth>('/system/health'),
    apiClient.get<ProductionRuntime>('/system/runtime'),
    apiClient.get<ProductionStorage>('/system/storage'),
    apiClient.get<ProductionNetwork>('/system/network'),
  ])
  return {
    health: health.data,
    runtime: runtime.data,
    storage: storage.data,
    network: network.data,
  }
}

export async function getInsightsOverview(): Promise<InsightOverview> {
  const response = await apiClient.get<InsightOverview>('/insights/overview')
  return response.data
}

export async function getInsightsStorage(): Promise<InsightStorage> {
  const response = await apiClient.get<InsightStorage>('/insights/storage')
  return response.data
}

export async function getInsightsSystem(): Promise<InsightSystem> {
  const response = await apiClient.get<InsightSystem>('/insights/system')
  return response.data
}

export async function getInsightsPhotos(): Promise<InsightItem> {
  const response = await apiClient.get<InsightItem>('/insights/photos')
  return response.data
}

export async function getInsightsBackup(): Promise<InsightItem> {
  const response = await apiClient.get<InsightItem>('/insights/backup')
  return response.data
}

export async function getAlertHistory(): Promise<AlertHistoryEntry[]> {
  const response = await apiClient.get<AlertHistoryEntry[]>('/alerts/history')
  return response.data
}

export async function getAlertStatistics(): Promise<AlertStatistics> {
  const response = await apiClient.get<AlertStatistics>('/alerts/statistics')
  return response.data
}

export async function getIncidents(): Promise<IncidentSummary[]> {
  const response = await apiClient.get<IncidentSummary[]>('/incidents')
  return response.data
}

export async function getIncident(incidentId: string): Promise<IncidentDetail> {
  const response = await apiClient.get<IncidentDetail>(`/incidents/${encodeURIComponent(incidentId)}`)
  return response.data
}

export async function getIncidentStatistics(): Promise<IncidentStatistics> {
  const response = await apiClient.get<IncidentStatistics>('/incidents/statistics')
  return response.data
}

export async function getNotificationHistory(): Promise<NotificationHistory> {
  const response = await apiClient.get<NotificationHistory>('/notifications/history')
  return response.data
}

export async function getNotificationCenterStatistics(): Promise<NotificationCenterStatistics> {
  const response = await apiClient.get<NotificationCenterStatistics>('/notifications/statistics')
  return response.data
}

export async function getNotificationMetrics(): Promise<NotificationDeliveryMetrics> {
  const response = await apiClient.get<NotificationDeliveryMetrics>('/notifications/metrics')
  return response.data
}

export async function getNotificationDeliveryHistory(): Promise<NotificationDeliveryHistory> {
  const response = await apiClient.get<NotificationDeliveryHistory>('/notifications/delivery-history')
  return response.data
}

const predictionTimeout = 20_000

export async function getPredictionsOverview(): Promise<PredictionOverview> {
  const response = await apiClient.get<PredictionOverview>('/predictions/overview', {
    timeout: predictionTimeout,
  })
  return response.data
}

export async function getPredictionsStorage(): Promise<PredictionMetric> {
  const response = await apiClient.get<PredictionMetric>('/predictions/storage', {
    timeout: predictionTimeout,
  })
  return response.data
}

export async function getPredictionsSystem(): Promise<PredictionMetric> {
  const response = await apiClient.get<PredictionMetric>('/predictions/system', {
    timeout: predictionTimeout,
  })
  return response.data
}

export async function getPredictionsPhotos(): Promise<PredictionMetric> {
  const response = await apiClient.get<PredictionMetric>('/predictions/photos', {
    timeout: predictionTimeout,
  })
  return response.data
}

export async function getPredictionsBackup(): Promise<PredictionMetric> {
  const response = await apiClient.get<PredictionMetric>('/predictions/backup', {
    timeout: predictionTimeout,
  })
  return response.data
}

export interface KnowledgeItem {
  kind: string
  title: string
  timestamp: string
  details: Record<string, unknown>
}

export interface KnowledgeList {
  generated_at: string
  count: number
  items: KnowledgeItem[]
}

export async function getKnowledge(query = '', kind = 'all'): Promise<KnowledgeList> {
  const response = await apiClient.get<KnowledgeList>('/knowledge', {
    params: { q: query, kind },
  })
  return response.data
}

export async function exportKnowledge(query = '', kind = 'all'): Promise<Blob> {
  const response = await apiClient.get<Blob>('/knowledge/export', {
    params: { q: query, kind },
    responseType: 'blob',
  })
  return response.data
}
