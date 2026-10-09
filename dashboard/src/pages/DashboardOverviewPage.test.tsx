import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthContext'
import { PwaContext, type PwaContextValue } from '../pwa/PwaProvider'
import type { BackupStatus, DashboardOverview } from '../types/dashboard'
import { DashboardOverviewPage } from './DashboardOverviewPage'

vi.mock('../api/dashboard', () => ({
  getDashboardOverview: vi.fn(),
  getAgents: vi.fn(),
  getActiveAlerts: vi.fn(),
  getBackupStatus: vi.fn(),
  getCapacityStorage: vi.fn(),
  getCapacitySystem: vi.fn(),
  getAnalyticsOverview: vi.fn(),
  getAnalyticsCpu: vi.fn(),
  getAnalyticsMemory: vi.fn(),
  getAnalyticsTemperature: vi.fn(),
  getAnalyticsPhotos: vi.fn(),
  getPhotoServices: vi.fn(),
  getPhotoMonitorStats: vi.fn(),
}))

import {
  getActiveAlerts,
  getAgents,
  getAnalyticsCpu,
  getAnalyticsMemory,
  getAnalyticsOverview,
  getAnalyticsPhotos,
  getAnalyticsTemperature,
  getBackupStatus,
  getCapacityStorage,
  getCapacitySystem,
  getDashboardOverview,
  getPhotoServices,
  getPhotoMonitorStats,
} from '../api/dashboard'

const overview: DashboardOverview = {
  agents: { total: 2, online: 1, offline: 1 },
  reports: { total: 4 },
  groups: { total: 0 },
  group_stats: [],
}

const backup: BackupStatus = {
  read_only: true,
  status: 'running',
  backup_health: 'healthy',
  job_name: 'Daily replication to TS-253 Pro',
  job_type: 'replication',
  progress_percent: 43,
  last_backup: '2026-09-08T02:00:00+00:00',
  next_backup: '2026-09-09T02:00:00+00:00',
  duration_seconds: 1080,
  backup_size_bytes: 2_001_111_162_552,
  last_error: '',
  last_success: '2026-09-08T02:00:00+00:00',
  updated_at: '2026-09-08T02:18:00Z',
  destination: { hostname: 'qnap-backup-01', ip: '192.168.1.253', model: 'TS-253 Pro' },
  history: [
    { period: 'yesterday', label: 'Yesterday', status: 'success' },
    { period: 'today', label: 'Today', status: 'running' },
    { period: 'last_week', label: 'Last Week', status: 'failed' },
  ],
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
      <DashboardOverviewPage />
    </AuthContext.Provider>,
  )
}

describe('Dashboard overview backup cards', () => {
  beforeEach(() => {
    vi.mocked(getDashboardOverview).mockResolvedValue(overview)
    vi.mocked(getAgents).mockResolvedValue([
      {
        id: 'agent-online',
        name: 'mini-pc',
        hostname: 'mini-pc.local',
        version: '0.1.0',
        status: 'online',
        last_seen_at: '2026-09-08T08:35:00Z',
      },
    ])
    vi.mocked(getActiveAlerts).mockResolvedValue([])
    vi.mocked(getBackupStatus).mockResolvedValue(backup)
    vi.mocked(getCapacityStorage).mockResolvedValue({
      current_used: 9.3 * 1024 ** 4,
      current_free: 2.7 * 1024 ** 4,
      capacity: 12 * 1024 ** 4,
      average_daily_growth: 1,
      average_weekly_growth: 7,
      estimated_days_remaining: 138,
      estimated_full_date: '2027-01-26',
      estimated_full_in: '138 Days',
      risk: 'healthy',
      series: [],
    })
    vi.mocked(getCapacitySystem).mockResolvedValue({
      cpu_trend: 'stable',
      memory_trend: 'stable',
      storage_trend: 'stable',
      backup_trend: 'stable',
      overall_score: 95,
      bottleneck: 'none',
      health: { healthy_count: 1, warning_count: 0, critical_count: 0, unknown_count: 0 },
    })
    vi.mocked(getAnalyticsOverview).mockResolvedValue({
      cpu_average: 15,
      memory_average: 42,
      storage_used: 106 * 1024 ** 3,
      photos_today: 12,
      backup_success_rate: 100,
      temperature_average: 46,
      daily: {
        agents_total: 2,
        agents_online: 1,
        alerts_today: 0,
        notifications_today: 0,
        history_points_today: 0,
      },
    })
    vi.mocked(getAnalyticsCpu).mockResolvedValue({
      current: 15,
      average_24h: 15,
      minimum: 10,
      maximum: 20,
      series: [],
    })
    vi.mocked(getAnalyticsMemory).mockResolvedValue({ current: 42, average: 40, series: [] })
    vi.mocked(getAnalyticsTemperature).mockResolvedValue({ current: 46, average: 45, series: [] })
    vi.mocked(getAnalyticsPhotos).mockResolvedValue({
      today: 12,
      yesterday: 0,
      this_week: 12,
      growth: 12,
      series: [],
    })
    vi.mocked(getPhotoServices).mockResolvedValue({
      collected_at: '2026-09-10T00:00:00Z',
      read_only: true,
      services: [],
      stats: { indexed_photos: 79119 },
    } as never)
    vi.mocked(getPhotoMonitorStats).mockResolvedValue({
      today_count: 128,
      last_photo: 'IMG_20260910_140012.jpg',
      last_folder: 'Photos',
      last_update: '2026-09-10T07:00:00Z',
      watch_folder: '/data/photos',
      watch_folders: ['/data/photos'],
      watch_folder_labels: ['Photos'],
      indexed_files: 63086,
      enabled: true,
    })
  })

  it('keeps existing summary cards and adds backup cards', async () => {
    renderPage()
    expect(await screen.findByLabelText('Total Agents 2')).toBeInTheDocument()
    expect(screen.getByLabelText('Online 1')).toBeInTheDocument()
    expect(screen.getByLabelText('Offline 1')).toBeInTheDocument()
    expect(screen.getByLabelText('Total Reports 4')).toBeInTheDocument()
    expect(screen.getByLabelText('Total Groups 0')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Backup' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Photo Monitor' })).toBeInTheDocument()
    expect(screen.getByLabelText('Status 🟢 Running')).toBeInTheDocument()
    expect(screen.getByLabelText('Watching 1 folder')).toBeInTheDocument()
    expect(screen.getAllByText('Photos').length).toBeGreaterThan(0)
    expect(screen.getByLabelText(`Indexed Files ${Number(63086).toLocaleString()} files indexed`)).toBeInTheDocument()
    expect(screen.getByLabelText('Backup TS-253 Pro')).toBeInTheDocument()
    expect(screen.getByLabelText('Healthy healthy')).toBeInTheDocument()
    expect(screen.getByLabelText('Status Online')).toBeInTheDocument()
  })

  it('shows polished metric cards from analytics values', async () => {
    renderPage()
    expect(await screen.findByLabelText(/CPU 15% Status: Normal/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Memory 42% Status: Normal/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Temperature 46°C Status: Normal/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Overall Health Excellent 95 \/ 100 Status: Excellent/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Photos Today \+128/)).toBeInTheDocument()
    expect(screen.getByText('Total Photos')).toBeInTheDocument()
    expect(screen.getByText(Number(79119).toLocaleString())).toBeInTheDocument()
  })

  it('falls back to analytics photos today when the monitor count is missing', async () => {
    vi.mocked(getPhotoMonitorStats).mockResolvedValue({
      last_photo: null,
      last_folder: null,
      last_update: null,
      watch_folder: '/data/photos',
      watch_folders: ['/data/photos'],
      watch_folder_labels: ['Photos'],
      indexed_files: 0,
      enabled: true,
    } as never)
    renderPage()
    expect(await screen.findByLabelText(/Photos Today \+12/)).toBeInTheDocument()
  })

  it('shows health and capacity forecast cards', async () => {
    renderPage()
    expect(await screen.findByLabelText(/Overall Health Excellent 95 \/ 100/)).toBeInTheDocument()
    expect(screen.getByLabelText(/Storage 9\.3 TB \/ 12\.0 TB 78% Status: Normal/)).toBeInTheDocument()
    expect(screen.getByLabelText('Estimated Full 138 Days')).toBeInTheDocument()
  })

  it('shows Critical health when a critical alert is active', async () => {
    vi.mocked(getActiveAlerts).mockResolvedValue([
      {
        id: 'alert-1',
        agent_id: 'agent-online',
        agent_name: 'mini-pc',
        kind: 'cpu_high',
        resource: 'cpu',
        severity: 'critical',
        current_value: 96,
        threshold: 90,
        message: 'CPU high',
        opened_at: '2026-09-10T01:00:00Z',
        last_observed_at: '2026-09-10T01:00:00Z',
        status: 'active',
      },
    ])
    renderPage()
    expect(await screen.findByLabelText(/Overall Health Critical/)).toBeInTheDocument()
  })

  it('shows the PWA install button and offline shell', async () => {
    const install = vi.fn()
    const pwa: PwaContextValue = {
      installed: false,
      canInstall: true,
      serviceWorker: 'registered',
      cacheReady: true,
      version: '0.1.0',
      updateAvailable: false,
      offline: true,
      install,
      checkForUpdate: vi.fn(),
      applyUpdate: vi.fn(),
      dismissUpdate: vi.fn(),
      clearCache: vi.fn(),
    }
    render(
      <PwaContext.Provider value={pwa}>
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
          <DashboardOverviewPage />
        </AuthContext.Provider>
      </PwaContext.Provider>,
    )
    expect(await screen.findByLabelText('Total Agents 2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Install HomeLab Monitor' })).toBeInTheDocument()
    expect(screen.getByLabelText('Offline status')).toBeInTheDocument()
    expect(screen.getByText('Cached Data')).toBeInTheDocument()
    expect(screen.getByLabelText('Monitoring summary').className).toMatch(/statGrid/)
  })
})
