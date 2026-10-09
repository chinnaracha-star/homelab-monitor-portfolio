import type { ReactNode } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { AnalyticsSeriesPoint } from '../types/dashboard'
import { formatThaiDateTime } from '../utils/thaiDate'
import { EmptyState } from './EmptyState'
import styles from '../pages/Pages.module.css'

function chartData(series: AnalyticsSeriesPoint[]) {
  return series.map((point, index) => ({
    label: point.label,
    value: point.value,
    timestamp: point.timestamp,
    key: `${point.label}-${index}`,
  }))
}

function ChartTooltip({
  active,
  payload,
  unit,
}: {
  active?: boolean
  payload?: { name?: string; value?: number; payload?: { timestamp?: string | null; label?: string } }[]
  unit?: string
}) {
  if (!active || !payload?.length) {
    return null
  }
  const item = payload[0]
  const stamp = item.payload?.timestamp ? formatThaiDateTime(item.payload.timestamp, false) : item.payload?.label
  return (
    <div className={styles.chartTooltip}>
      <p>{stamp}</p>
      <p>
        {item.name}: {item.value}
        {unit ?? ''}
      </p>
    </div>
  )
}

function ChartShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className={styles.chartPanel}>
      <h3 className={styles.groupTitle}>{title}</h3>
      <div className={styles.chartSurface}>{children}</div>
    </article>
  )
}

export function AnalyticsLineChart({
  title,
  series,
  color,
  unit,
}: {
  title: string
  series: AnalyticsSeriesPoint[]
  color: string
  unit: string
}) {
  if (series.length === 0) {
    return <EmptyState message={`No ${title.toLowerCase()} history yet.`} />
  }
  const gradientId = `line-${title.replaceAll(/\s+/g, '-').toLowerCase()}`
  return (
    <ChartShell title={title}>
      <ResponsiveContainer width="100%" height={256} initialDimension={{ width: 800, height: 256 }}>
        <LineChart data={chartData(series)} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 3" />
          <XAxis dataKey="label" minTickGap={24} />
          <YAxis unit={unit === '%' ? '%' : undefined} />
          <Tooltip content={<ChartTooltip unit={unit} />} />
          <Legend />
          <Line
            type="monotone"
            dataKey="value"
            name={title}
            stroke={color}
            strokeWidth={2.2}
            dot={false}
            connectNulls
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

export function AnalyticsAreaChart({
  title,
  series,
  color,
}: {
  title: string
  series: AnalyticsSeriesPoint[]
  color: string
}) {
  if (series.length === 0) {
    return <EmptyState message={`No ${title.toLowerCase()} history yet.`} />
  }
  const gradientId = `area-${title.replaceAll(/\s+/g, '-').toLowerCase()}`
  return (
    <ChartShell title={title}>
      <ResponsiveContainer width="100%" height={256} initialDimension={{ width: 800, height: 256 }}>
        <AreaChart data={chartData(series)} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.38} />
              <stop offset="100%" stopColor={color} stopOpacity={0.04} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 3" />
          <XAxis dataKey="label" minTickGap={24} />
          <YAxis unit="%" />
          <Tooltip content={<ChartTooltip unit="%" />} />
          <Legend />
          <Area
            type="monotone"
            dataKey="value"
            name={title}
            stroke={color}
            strokeWidth={2}
            fill={`url(#${gradientId})`}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

export function AnalyticsBarChart({
  title,
  series,
  color,
}: {
  title: string
  series: AnalyticsSeriesPoint[]
  color: string
}) {
  if (series.every((point) => point.value == null || point.value === 0)) {
    return <EmptyState message={`No ${title.toLowerCase()} data yet.`} />
  }
  return (
    <ChartShell title={title}>
      <ResponsiveContainer width="100%" height={256} initialDimension={{ width: 800, height: 256 }}>
        <BarChart data={chartData(series)} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 3" />
          <XAxis dataKey="label" minTickGap={12} />
          <YAxis />
          <Tooltip content={<ChartTooltip />} />
          <Legend />
          <Bar dataKey="value" name={title} fill={color} radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

export function AnalyticsPieChart({
  title,
  slices,
}: {
  title: string
  slices: { label: string; value: number; color: string }[]
}) {
  if (slices.every((slice) => slice.value === 0)) {
    return <EmptyState message={`No ${title.toLowerCase()} data yet.`} />
  }
  return (
    <ChartShell title={title}>
      <ResponsiveContainer width="100%" height={256} initialDimension={{ width: 800, height: 256 }}>
        <PieChart>
          <Pie data={slices} dataKey="value" nameKey="label" cx="50%" cy="50%" outerRadius={80} label>
            {slices.map((slice) => (
              <Cell fill={slice.color} key={slice.label} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </ChartShell>
  )
}

export function AnalyticsGaugeChart({ title, score }: { title: string; score: number }) {
  const remaining = Math.max(0, 100 - score)
  if (score === 0 && remaining === 0) {
    return <EmptyState message={`No ${title.toLowerCase()} data yet.`} />
  }
  const slices = [
    { label: 'Score', value: score, color: '#059669' },
    { label: 'Remaining', value: remaining, color: '#e2e8f0' },
  ]
  return (
    <article className={styles.chartPanel}>
      <h3 className={styles.groupTitle}>{title}</h3>
      <p className={styles.reportMeta}>{score.toFixed(1)} / 100</p>
      <div className={styles.chartSurface}>
        <ResponsiveContainer width="100%" height={256} initialDimension={{ width: 800, height: 256 }}>
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="label"
              cx="50%"
              cy="50%"
              innerRadius={55}
              outerRadius={80}
            >
              {slices.map((slice) => (
                <Cell fill={slice.color} key={slice.label} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </article>
  )
}
