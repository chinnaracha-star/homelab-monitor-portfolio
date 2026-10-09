import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthContext'
import type {
  CapacityBackup,
  CapacityOverview,
  CapacityPhotos,
  CapacityStorage,
  CapacitySystem,
} from '../types/dashboard'
import { CapacityPage } from './CapacityPage'

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
  getCapacityOverview: vi.fn(),
  getCapacityStorage: vi.fn(),
  getCapacityPhotos: vi.fn(),
  getCapacityBackup: vi.fn(),
  getCapacitySystem: vi.fn(),
}))

import {
  getCapacityBackup,
  getCapacityOverview,
  getCapacityPhotos,
  getCapacityStorage,
  getCapacitySystem,
} from '../api/dashboard'

const overview: CapacityOverview = {
  storage_remaining_days: 5.25,
  estimated_full_date: '2026-09-13',
  growth_per_day: 800,
  photo_forecast: 1286,
  backup_forecast: 'sufficient',
  capacity_score: 64,
  bottleneck: 'storage',
  storage_risk: 'critical',
  backup_risk: 'healthy',
  recommendations: [
    'Storage will be full in approximately 5.25 days.',
    'Consider upgrading to a larger NAS.',
  ],
  series: [{ timestamp: null, label: '+1d', value: 60 }],
}

const storage: CapacityStorage = {
  current_used: 5800,
  current_free: 4200,
  capacity: 10000,
  average_daily_growth: 800,
  average_weekly_growth: 1800,
  estimated_days_remaining: 5.25,
  estimated_full_date: '2026-09-13',
  risk: 'critical',
  series: [
    { timestamp: '2026-09-08T03:00:00Z', label: '03:00', value: 55 },
    { timestamp: null, label: '+1d', value: 58 },
  ],
}

const photos: CapacityPhotos = {
  photos_today: 200,
  photos_this_week: 300,
  average_photos_per_day: 42.86,
  expected_photos_next_month: 1286,
  expected_storage_next_month: 11500,
  average_size_per_photo: 4.46,
  series: [{ timestamp: null, label: 'Next month', value: 1286 }],
}

const backup: CapacityBackup = {
  destination_capacity: 12000000000000,
  current_backup_size: 1700,
  growth_per_day: 100,
  estimated_days_remaining: 180,
  estimated_full_date: '2027-03-07',
  success_percent: 100,
  average_duration: 750,
  trend: 'healthy',
  series: [{ timestamp: '2026-09-08T02:00:00Z', label: '09-08', value: 1700 }],
}

const system: CapacitySystem = {
  cpu_trend: 'rising',
  memory_trend: 'rising',
  storage_trend: 'rising',
  backup_trend: 'rising',
  overall_score: 64,
  bottleneck: 'storage',
  health: { healthy_count: 5, warning_count: 0, critical_count: 0, unknown_count: 0 },
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
      <CapacityPage />
    </AuthContext.Provider>,
  )
}

describe('Capacity Planning page', () => {
  beforeEach(() => {
    vi.mocked(getCapacityOverview).mockResolvedValue(overview)
    vi.mocked(getCapacityStorage).mockResolvedValue(storage)
    vi.mocked(getCapacityPhotos).mockResolvedValue(photos)
    vi.mocked(getCapacityBackup).mockResolvedValue(backup)
    vi.mocked(getCapacitySystem).mockResolvedValue(system)
  })

  it('renders cards, recommendations, and charts', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Capacity Planning' })).toBeInTheDocument()
    expect(screen.getByLabelText('Storage Remaining 5.25 days')).toBeInTheDocument()
    expect(screen.getByLabelText('Estimated Full Date 13 กันยายน 2569')).toBeInTheDocument()
    expect(screen.getByLabelText('Photo Forecast 1,286')).toBeInTheDocument()
    expect(screen.getByLabelText('Capacity Score 64')).toBeInTheDocument()
    expect(screen.getByText('Consider upgrading to a larger NAS.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Storage Projection' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Photo Projection' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Backup Growth' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Capacity Score Gauge' })).toBeInTheDocument()
    expect(screen.getAllByTestId('chart-surface').length).toBeGreaterThan(0)
  })

  it('shows loading skeletons', () => {
    vi.mocked(getCapacityOverview).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getCapacityStorage).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getCapacityPhotos).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getCapacityBackup).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getCapacitySystem).mockImplementation(() => new Promise(() => undefined))
    renderPage()
    expect(screen.getByLabelText('Loading overview')).toBeInTheDocument()
    expect(screen.getByLabelText('Loading history')).toBeInTheDocument()
  })

  it('shows empty chart states', async () => {
    vi.mocked(getCapacityStorage).mockResolvedValue({ ...storage, series: [] })
    vi.mocked(getCapacityPhotos).mockResolvedValue({
      ...photos,
      series: [{ timestamp: null, label: 'Today', value: 0 }],
    })
    vi.mocked(getCapacityOverview).mockResolvedValue({ ...overview, recommendations: [] })
    renderPage()
    expect(await screen.findByText('No storage projection history yet.')).toBeInTheDocument()
    expect(screen.getByText('No photo projection data yet.')).toBeInTheDocument()
    expect(screen.getByText('No capacity recommendations yet.')).toBeInTheDocument()
  })

  it('shows an error and retries', async () => {
    vi.mocked(getCapacityOverview).mockRejectedValue(new Error('failed'))
    renderPage()
    expect(await screen.findByText('Capacity overview failed')).toBeInTheDocument()
    vi.mocked(getCapacityOverview).mockResolvedValue(overview)
    await userEvent.click(screen.getAllByRole('button', { name: 'Retry section' })[0])
    await waitFor(() => {
      expect(screen.getByLabelText('Capacity Score 64')).toBeInTheDocument()
    })
  })

  it('uses a responsive chart grid', async () => {
    renderPage()
    const grid = await screen.findByLabelText('Capacity charts')
    expect(grid.className).toMatch(/chartGrid/)
  })
})
