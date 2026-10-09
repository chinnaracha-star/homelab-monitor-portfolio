import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthContext'
import type {
  TrendBackup,
  TrendMetric,
  TrendOverview,
  TrendPhotos,
  TrendStorage,
} from '../types/dashboard'
import { TrendsPage } from './TrendsPage'

vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts')
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: unknown }) => (
      <div data-testid="chart-surface">{children as never}</div>
    ),
  }
})

vi.mock('../api/dashboard', () => ({
  getTrendsOverview: vi.fn(),
  getTrendsCpu: vi.fn(),
  getTrendsMemory: vi.fn(),
  getTrendsStorage: vi.fn(),
  getTrendsPhotos: vi.fn(),
  getTrendsBackup: vi.fn(),
}))

import {
  getTrendsBackup,
  getTrendsCpu,
  getTrendsMemory,
  getTrendsOverview,
  getTrendsPhotos,
  getTrendsStorage,
} from '../api/dashboard'

const overview: TrendOverview = {
  cpu_trend: 'rising',
  memory_trend: 'stable',
  storage_trend: 'rising',
  photo_trend: 'rising',
  backup_trend: 'stable',
  overall_health: 'rising',
  overall_score: 82,
  health: { healthy_count: 4, warning_count: 1, critical_count: 0, unknown_count: 0 },
}

const cpu: TrendMetric = {
  latest: 40,
  average_1d: 40,
  average_7d: 22,
  average_30d: 18,
  trend: 'rising',
  difference_percent: 20,
  hourly: [{ timestamp: '2026-09-08T03:00:00Z', label: '03:00', value: 40 }],
  daily: [{ timestamp: '2026-09-08T00:00:00Z', label: '09-08', value: 40 }],
}

const memory: TrendMetric = { ...cpu, latest: 50, average_1d: 50, trend: 'stable' }

const storage: TrendStorage = {
  current_used: 5800,
  used_percent: 58,
  daily_growth_bytes: 800,
  weekly_growth_bytes: 1800,
  monthly_growth_bytes: 1800,
  growth_per_day: 800,
  estimated_days_until_full: 5.25,
  estimated_full_date: '2026-09-13',
  trend: 'rising',
  series: [
    { timestamp: '2026-09-08T03:00:00Z', label: '03:00', value: 55 },
    { timestamp: null, label: '+1d', value: 58 },
  ],
}

const photos: TrendPhotos = {
  today: 200,
  yesterday: 100,
  this_week: 300,
  last_week: 120,
  this_month: 400,
  growth: 300,
  daily: 200,
  weekly: 300,
  monthly: 400,
  expected_next_week: 300,
  trend: 'rising',
  difference_percent: 100,
  series: [{ timestamp: null, label: 'Today', value: 200 }],
}

const backup: TrendBackup = {
  last_30_backups: 2,
  success_rate: 50,
  failure_rate: 50,
  average_duration: 750,
  fastest: 600,
  slowest: 900,
  running_count: 0,
  expected_completion_seconds: null,
  last_backup: '2026-09-08T02:00:00Z',
  trend: 'stable',
  series: [{ timestamp: '2026-09-08T02:00:00Z', label: '09-08 02:00', value: 600 }],
}

function renderPage() {
  return render(
    <AuthContext.Provider
      value={{
        user: {
          id: 'user-admin',
          username: 'admin',
          full_name: 'Administrator',
          role: 'admin',
          is_active: true,
        },
        loading: false,
        login: async () => undefined,
        logout: () => undefined,
      }}
    >
      <TrendsPage />
    </AuthContext.Provider>,
  )
}

describe('Trends page', () => {
  beforeEach(() => {
    vi.mocked(getTrendsOverview).mockResolvedValue(overview)
    vi.mocked(getTrendsCpu).mockResolvedValue(cpu)
    vi.mocked(getTrendsMemory).mockResolvedValue(memory)
    vi.mocked(getTrendsStorage).mockResolvedValue(storage)
    vi.mocked(getTrendsPhotos).mockResolvedValue(photos)
    vi.mocked(getTrendsBackup).mockResolvedValue(backup)
  })

  it('renders cards, forecast, and charts', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Trend Analysis' })).toBeInTheDocument()
    expect(screen.getByLabelText('CPU Trend Rising')).toBeInTheDocument()
    expect(screen.getByLabelText('Storage Forecast Rising')).toBeInTheDocument()
    expect(screen.getByLabelText('Overall Score 82')).toBeInTheDocument()
    expect(screen.getByLabelText('Storage 58.0%')).toBeInTheDocument()
    expect(screen.getByLabelText('Estimated Full 5.25 days')).toBeInTheDocument()
    expect(screen.getByLabelText('Expected photos next week 300')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'CPU Line' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Storage Forecast Line' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Health Pie' })).toBeInTheDocument()
    expect(screen.getAllByTestId('chart-surface').length).toBeGreaterThan(0)
  })

  it('shows loading skeletons', () => {
    vi.mocked(getTrendsOverview).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getTrendsCpu).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getTrendsMemory).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getTrendsStorage).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getTrendsPhotos).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getTrendsBackup).mockImplementation(() => new Promise(() => undefined))
    renderPage()
    expect(screen.getByLabelText('Loading overview')).toBeInTheDocument()
    expect(screen.getByLabelText('Loading history')).toBeInTheDocument()
  })

  it('shows empty chart states', async () => {
    vi.mocked(getTrendsCpu).mockResolvedValue({ ...cpu, hourly: [] })
    vi.mocked(getTrendsPhotos).mockResolvedValue({
      ...photos,
      series: [
        { timestamp: null, label: 'Today', value: 0 },
        { timestamp: null, label: 'Yesterday', value: 0 },
      ],
    })
    renderPage()
    expect(await screen.findByText('No cpu line history yet.')).toBeInTheDocument()
    expect(screen.getByText('No photo growth bar data yet.')).toBeInTheDocument()
  })

  it('shows an error and retries', async () => {
    vi.mocked(getTrendsOverview).mockRejectedValue(new Error('failed'))
    renderPage()
    expect(await screen.findByText('Trend overview failed')).toBeInTheDocument()
    vi.mocked(getTrendsOverview).mockResolvedValue(overview)
    await userEvent.click(screen.getAllByRole('button', { name: 'Retry section' })[0])
    await waitFor(() => {
      expect(screen.getByLabelText('CPU Trend Rising')).toBeInTheDocument()
    })
  })

  it('uses a responsive chart grid', async () => {
    renderPage()
    const grid = await screen.findByLabelText('Trend charts')
    expect(grid.className).toMatch(/chartGrid/)
  })
})
