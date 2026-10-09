import { memo, useCallback, useMemo, useState } from 'react'
import { getAgentHistory } from '../api/dashboard'
import { useLivePolling } from '../hooks/useDashboardSocket'
import {
  DEFAULT_HISTORY_RANGE,
  HISTORY_RANGES,
  downloadTextFile,
  historyExportFilename,
  historyPointsToCsv,
  historyWindow,
  toHistoryChartPoints,
  type HistoryRange,
} from '../utils/history'
import { AgentHistoryCharts } from './AgentHistoryCharts'
import { EmptyState } from './EmptyState'
import { RenderGuard } from './RenderGuard'
import { SectionError } from './SectionError'
import { ChartSkeleton } from './Skeleton'
import componentStyles from './Components.module.css'
import styles from '../pages/Pages.module.css'

const HISTORY_EVENTS = ['overview_updated', 'agent_updated'] as const

interface AgentHistorySectionProps {
  agentId: string
  agentName: string
}

export const AgentHistorySection = memo(function AgentHistorySection({
  agentId,
  agentName,
}: AgentHistorySectionProps) {
  const [range, setRange] = useState<HistoryRange>(DEFAULT_HISTORY_RANGE)

  const loadHistory = useCallback(() => {
    const rangeWindow = historyWindow(range)
    return getAgentHistory(agentId, rangeWindow)
  }, [agentId, range])

  const history = useLivePolling(loadHistory, HISTORY_EVENTS, {
    agentId,
    resetKey: `${agentId}:${range}`,
  })

  const chartData = useMemo(
    () => toHistoryChartPoints(Array.isArray(history.data?.points) ? history.data.points : []),
    [history.data],
  )

  const handleExport = useCallback(() => {
    const exportPoints = history.data?.points
    if (!Array.isArray(exportPoints) || exportPoints.length === 0) {
      return
    }
    downloadTextFile(historyExportFilename(agentName), historyPointsToCsv(exportPoints))
  }, [agentName, history.data])

  return (
    <section className={styles.section} aria-labelledby="agent-history-title">
      <div className={styles.historyToolbar}>
        <h2 className={styles.sectionTitle} id="agent-history-title">
          History
        </h2>
        <div className={styles.historyActions}>
          <div className={componentStyles.filterGroup} role="group" aria-label="History range">
            {HISTORY_RANGES.map((item) => (
              <button
                className={`${componentStyles.filterButton} ${range === item.id ? componentStyles.filterActive : ''}`}
                key={item.id}
                type="button"
                aria-pressed={range === item.id}
                onClick={() => setRange(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <button
            className={styles.exportButton}
            type="button"
            disabled={chartData.length === 0}
            onClick={handleExport}
          >
            Export CSV
          </button>
        </div>
      </div>

      {history.error ? (
        <SectionError title="History API failed" onRetry={history.retry} />
      ) : null}
      {!history.data && !history.error ? <ChartSkeleton /> : null}
      {history.data && chartData.length === 0 && !history.error ? (
        <EmptyState message="No metric history for this range." />
      ) : null}
      {chartData.length > 0 ? (
        <RenderGuard fallback={<EmptyState message="Unable to render history charts." />}>
          <AgentHistoryCharts data={chartData} />
        </RenderGuard>
      ) : null}
    </section>
  )
})
