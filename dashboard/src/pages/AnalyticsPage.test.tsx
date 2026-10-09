import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthContext'
import type {
  AnalyticsBackup,
  AnalyticsCpu,
  AnalyticsMemory,
  AnalyticsOverview,
  AnalyticsPhotos,
  AnalyticsStorage,
  AnalyticsTemperature,
} from '../types/dashboard'
import { AnalyticsPage } from './AnalyticsPage'

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
  getAnalyticsOverview: vi.fn(),
  getAnalyticsCpu: vi.fn(),
  getAnalyticsMemory: vi.fn(),
  getAnalyticsStorage: vi.fn(),
  getAnalyticsTemperature: vi.fn(),
  getAnalyticsPhotos: vi.fn(),
  getAnalyticsBackup: vi.fn(),
}))

import {
  getAnalyticsBackup,
  getAnalyticsCpu,
  getAnalyticsMemory,
  getAnalyticsOverview,
  getAnalyticsPhotos,
  getAnalyticsStorage,
  getAnalyticsTemperature,
} from '../api/dashboard'

const overview: AnalyticsOverview = {
  cpu_average: 15.5,
  memory_average: 30,
  storage_used: 1500,
  photos_today: 200,
  backup_success_rate: 50,
  temperature_average: 45,
  daily: {
    agents_total: 1,
    agents_online: 1,
    alerts_today: 0,
    notifications_today: 1,
    history_points_today: 2,
  },
}

const cpu: AnalyticsCpu = {
  current: 20,
  average_24h: 15.5,
  minimum: 10,
  maximum: 20,
  series: [{ timestamp: '2026-09-08T03:00:00Z', label: '03:00', value: 15.5 }],
}

const memory: AnalyticsMemory = {
  current: 40,
  average: 30,
  series: [{ timestamp: '2026-09-08T03:00:00Z', label: '03:00', value: 30 }],
}

const storage: AnalyticsStorage = {
  current: 1500,
  daily_growth: 300,
  weekly_growth: 500,
  series: [{ timestamp: '2026-09-08T03:00:00Z', label: '03:00', value: 40 }],
}

const temperature: AnalyticsTemperature = {
  current: 50,
  average: 45,
  series: [{ timestamp: '2026-09-08T03:00:00Z', label: '03:00', value: 45 }],
}

const photos: AnalyticsPhotos = {
  today: 200,
  yesterday: 100,
  this_week: 300,
  growth: 300,
  series: [
    { timestamp: null, label: 'Today', value: 200 },
    { timestamp: null, label: 'Yesterday', value: 100 },
    { timestamp: null, label: 'This week', value: 300 },
  ],
}

const backup: AnalyticsBackup = {
  last_backup: '2026-09-07T02:00:00+00:00',
  duration_seconds: 400,
  success_rate: 50,
  series: [{ timestamp: '2026-09-08T02:00:00Z', label: '09-08 02:00', value: 400 }],
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
      <AnalyticsPage />
    </AuthContext.Provider>,
  )
}

describe('Analytics page', () => {
  beforeEach(() => {
    vi.mocked(getAnalyticsOverview).mockResolvedValue(overview)
    vi.mocked(getAnalyticsCpu).mockResolvedValue(cpu)
    vi.mocked(getAnalyticsMemory).mockResolvedValue(memory)
    vi.mocked(getAnalyticsStorage).mockResolvedValue(storage)
    vi.mocked(getAnalyticsTemperature).mockResolvedValue(temperature)
    vi.mocked(getAnalyticsPhotos).mockResolvedValue(photos)
    vi.mocked(getAnalyticsBackup).mockResolvedValue(backup)
  })

  it('renders summary cards and charts', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Analytics' })).toBeInTheDocument()
    expect(screen.getByLabelText('Average CPU 15.5%')).toBeInTheDocument()
    expect(screen.getByLabelText('Average Memory 30.0%')).toBeInTheDocument()
    expect(screen.getByLabelText(/Storage Used/)).toBeInTheDocument()
    expect(screen.getByLabelText('Photos Today 200')).toBeInTheDocument()
    expect(screen.getByLabelText('Backup Success Rate 50.0%')).toBeInTheDocument()
    expect(screen.getByLabelText('Average Temperature 45.0°C')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Daily Overview' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'CPU Trend' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Memory Trend' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Storage Trend' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Temperature Trend' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Photo Growth' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Backup Duration' })).toBeInTheDocument()
    expect(screen.getAllByTestId('chart-surface').length).toBeGreaterThan(0)
  })

  it('shows loading skeletons', () => {
    vi.mocked(getAnalyticsOverview).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getAnalyticsCpu).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getAnalyticsMemory).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getAnalyticsStorage).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getAnalyticsTemperature).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getAnalyticsPhotos).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getAnalyticsBackup).mockImplementation(() => new Promise(() => undefined))
    renderPage()
    expect(screen.getByLabelText('Loading overview')).toBeInTheDocument()
    expect(screen.getByLabelText('Loading history')).toBeInTheDocument()
  })

  it('shows empty chart states', async () => {
    vi.mocked(getAnalyticsCpu).mockResolvedValue({ ...cpu, series: [] })
    vi.mocked(getAnalyticsPhotos).mockResolvedValue({
      ...photos,
      series: [
        { timestamp: null, label: 'Today', value: 0 },
        { timestamp: null, label: 'Yesterday', value: 0 },
        { timestamp: null, label: 'This week', value: 0 },
      ],
    })
    renderPage()
    expect(await screen.findByText('No cpu trend history yet.')).toBeInTheDocument()
    expect(screen.getByText('No photo growth data yet.')).toBeInTheDocument()
  })

  it('shows an error and retries', async () => {
    vi.mocked(getAnalyticsOverview).mockRejectedValue(new Error('failed'))
    renderPage()
    expect(await screen.findByText('Analytics overview failed')).toBeInTheDocument()
    vi.mocked(getAnalyticsOverview).mockResolvedValue(overview)
    await userEvent.click(screen.getAllByRole('button', { name: 'Retry section' })[0])
    await waitFor(() => {
      expect(screen.getByLabelText('Average CPU 15.5%')).toBeInTheDocument()
    })
  })

  it('uses a responsive chart grid', async () => {
    renderPage()
    const grid = await screen.findByLabelText('Analytics charts')
    expect(grid.className).toMatch(/chartGrid/)
  })
})
