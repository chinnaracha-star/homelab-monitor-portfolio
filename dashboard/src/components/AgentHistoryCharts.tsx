import {
  Brush,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { SERVICE_COLORS } from '../utils/colors'
import { formatThaiDateTime } from '../utils/thaiDate'
import type { HistoryChartPoint } from '../utils/history'
import styles from '../pages/Pages.module.css'

const CHARTS = [
  { key: 'cpu', title: 'CPU', color: SERVICE_COLORS.cpu, unit: '%' },
  { key: 'memory', title: 'Memory', color: SERVICE_COLORS.memory, unit: '%' },
  { key: 'disk', title: 'Disk', color: SERVICE_COLORS.storage, unit: '%' },
  { key: 'temperature', title: 'Temperature', color: SERVICE_COLORS.temperature, unit: '°C' },
] as const

interface AgentHistoryChartsProps {
  data: HistoryChartPoint[]
}

function HistoryTooltip({
  active,
  payload,
  unit,
}: {
  active?: boolean
  payload?: { name?: string; value?: number; payload?: { timestamp?: string } }[]
  unit?: string
}) {
  if (!active || !payload?.length) {
    return null
  }
  const item = payload[0]
  return (
    <div className={styles.chartTooltip}>
      <p>{item.payload?.timestamp ? formatThaiDateTime(item.payload.timestamp, false) : ''}</p>
      <p>
        {item.name}: {item.value}
        {unit ?? ''}
      </p>
    </div>
  )
}

export function AgentHistoryCharts({ data }: AgentHistoryChartsProps) {
  return (
    <section className={styles.chartGrid} aria-label="Metric history charts">
      {CHARTS.map((chart) => (
        <article className={styles.chartPanel} key={chart.key}>
          <h3 className={styles.groupTitle}>{chart.title}</h3>
          <div className={styles.chartSurface}>
            <ResponsiveContainer
              width="100%"
              height={256}
              initialDimension={{ width: 800, height: 256 }}
            >
              <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 3" />
                <XAxis dataKey="label" minTickGap={24} />
                <YAxis
                  domain={chart.key === 'temperature' ? ['auto', 'auto'] : [0, 100]}
                  unit={chart.unit === '%' ? '%' : undefined}
                />
                <Tooltip content={<HistoryTooltip unit={chart.unit} />} />
                <Legend />
                <Brush dataKey="label" height={18} stroke={chart.color} />
                <Line
                  type="monotone"
                  dataKey={chart.key}
                  name={chart.title}
                  stroke={chart.color}
                  strokeWidth={2.2}
                  dot={false}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>
      ))}
    </section>
  )
}
