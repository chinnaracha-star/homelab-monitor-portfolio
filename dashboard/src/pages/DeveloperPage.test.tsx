import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthContext'
import { PwaContext, type PwaContextValue } from '../pwa/PwaProvider'
import type { DeveloperOverview } from '../types/dashboard'
import { DeveloperPage } from './DeveloperPage'

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
  getDeveloperOverview: vi.fn(),
  getRemoteAccess: vi.fn(),
}))

import { getDeveloperOverview, getRemoteAccess } from '../api/dashboard'

const overview: DeveloperOverview = {
  project: {
    application_version: '1.0.0-rc3',
    build_time: null,
    environment: 'development',
    current_phase: 9,
    current_sprint: '11.5',
    git: {
      branch: 'main',
      commit: 'abcdef1',
      dirty: true,
      working_tree: 'dirty',
      modified_files: 4,
      untracked_files: 2,
      ahead_count: 0,
      behind_count: 0,
    },
  },
  runtime: {
    api: 'healthy',
    dashboard: 'healthy',
    agent: 'unknown',
    database: 'healthy',
    docker: 'healthy',
    websocket: 'unknown',
    telegram: 'unknown',
    immich: 'healthy',
    qumagie: 'healthy',
    qnap: 'healthy',
    backup: 'healthy',
  },
  build: {
    last_build: null,
    build_status: 'unknown',
    backend: 'unknown',
    frontend: 'unknown',
    docker_compose: 'unknown',
    application_version: '1.0.0-rc3',
    environment: 'development',
  },
  tests: {
    backend_tests: 'unknown',
    frontend_tests: 'unknown',
    lint: 'unknown',
    ruff: 'unknown',
    build: 'unknown',
    qa: 'unknown',
  },
  progress: {
    phases: [
      { phase: 1, percent: 100 },
      { phase: 9, percent: 70 },
      { phase: 10, percent: 0 },
    ],
    current_sprint: '11.5',
    roadmap: 'Phase 9: Analytics, Trends, Capacity, Mission Control',
    completed_percent: 87,
    current_milestone: 'Sprint 9.3.5 Developer Dashboard',
  },
  statistics: {
    rest_apis: 40,
    database_tables: 12,
    agents: 1,
    groups: 0,
    users: 4,
    alert_rules: 0,
    notifications: 0,
    photos: 12,
    docker_services: 2,
    frontend_pages: 16,
    react_components: 20,
    backend_modules: 30,
    test_count: 20,
    frontend_test_count: 17,
  },
  activity: [
    { kind: 'photo snapshot', message: 'photo observed', timestamp: '2026-09-08T04:00:00Z' },
  ],
  health: {
    overall_health: 72,
    overall_capacity: 64,
    overall_trend: 70,
    overall_infrastructure: 100,
  },
  capacity_score: 64,
  agent_service: {
    state: 'running',
    enabled: 'enabled',
    agent_status: 'online',
    last_heartbeat: '2026-09-08T08:35:09Z',
    last_check_in: '2026-09-08T08:35:09Z',
    last_report: '2026-09-08T08:35:00Z',
    next_report_eta: '2026-09-08T08:36:00Z',
    pid: 42,
    restart_count: 3,
    report_interval_seconds: 60,
    systemd_status: 'active/running',
  },
}

const remote = {
  enabled: true,
  provider: 'tailscale',
  hostname: 'monitor.example.com',
  tailnet_ip: '100.64.0.12',
  https: true,
  serve_enabled: true,
  funnel_enabled: false,
  public: false,
  status: 'connected' as const,
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
      <DeveloperPage />
    </AuthContext.Provider>,
  )
}

describe('Mission Control page', () => {
  beforeEach(() => {
    vi.mocked(getDeveloperOverview).mockResolvedValue(overview)
    vi.mocked(getRemoteAccess).mockResolvedValue(remote)
  })

  it('renders cards, timeline, and gauge', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Mission Control' })).toBeInTheDocument()
    expect(screen.getByLabelText('Version v1.0.0-rc3')).toBeInTheDocument()
    expect(screen.getByLabelText('Environment development')).toBeInTheDocument()
    expect(screen.getByLabelText('Branch main')).toBeInTheDocument()
    expect(screen.getByLabelText('Commit abcdef1')).toBeInTheDocument()
    expect(screen.getByLabelText('Git Dirty YES')).toBeInTheDocument()
    expect(screen.getByLabelText('Working Tree Dirty')).toBeInTheDocument()
    expect(screen.getByLabelText('Sprint 11.5')).toBeInTheDocument()
    expect(screen.getByLabelText('Recent timeline')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Agent Runtime' })).toBeInTheDocument()
    expect(screen.getByLabelText('Agent runtime')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Backend Status' })).toBeInTheDocument()
    expect(screen.getByLabelText('Status Running')).toBeInTheDocument()
    expect(screen.getByLabelText('Status Online')).toBeInTheDocument()
    expect(screen.getByLabelText('Restart Counter 3')).toBeInTheDocument()
    expect(screen.getByLabelText('Report Interval 60s')).toBeInTheDocument()
    expect(screen.getByLabelText('PID 42')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Phase Progress' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Remote Access' })).toBeInTheDocument()
    expect(screen.getByLabelText('Connection Connected')).toBeInTheDocument()
    expect(screen.getByLabelText('Remote access status').className).toMatch(/remoteAccessGrid/)
    expect(screen.getAllByTestId('chart-surface').length).toBeGreaterThan(0)
  })

  it('shows loading skeletons', () => {
    vi.mocked(getDeveloperOverview).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getRemoteAccess).mockImplementation(() => new Promise(() => undefined))
    renderPage()
    expect(screen.getAllByLabelText('Loading overview').length).toBeGreaterThan(0)
  })

  it('shows empty activity', async () => {
    vi.mocked(getDeveloperOverview).mockResolvedValue({ ...overview, activity: [] })
    renderPage()
    expect(await screen.findByText('No recent activity yet.')).toBeInTheDocument()
  })

  it('shows an error and retries', async () => {
    vi.mocked(getDeveloperOverview).mockRejectedValue(new Error('failed'))
    renderPage()
    expect(await screen.findByText('Mission Control failed')).toBeInTheDocument()
    vi.mocked(getDeveloperOverview).mockResolvedValue(overview)
    await userEvent.click(screen.getByRole('button', { name: 'Retry section' }))
    await waitFor(() => {
      expect(screen.getByLabelText('Version v1.0.0-rc3')).toBeInTheDocument()
    })
  })

  it('retries remote access independently', async () => {
    vi.mocked(getRemoteAccess).mockRejectedValue(new Error('offline'))
    renderPage()
    expect(await screen.findByText('Remote Access failed')).toBeInTheDocument()
    vi.mocked(getRemoteAccess).mockResolvedValue(remote)
    await userEvent.click(screen.getByRole('button', { name: 'Retry section' }))
    await waitFor(() => {
      expect(screen.getByLabelText('Connection Connected')).toBeInTheDocument()
    })
  })

  it('uses a responsive chart grid', async () => {
    renderPage()
    const grid = await screen.findByLabelText('Developer charts')
    expect(grid.className).toMatch(/chartGrid/)
  })

  it('shows Offline Mode in the Mission Control header', async () => {
    const pwa: PwaContextValue = {
      installed: true,
      canInstall: false,
      serviceWorker: 'registered',
      cacheReady: true,
      version: '0.1.0',
      updateAvailable: false,
      offline: true,
      install: vi.fn(),
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
          <DeveloperPage />
        </AuthContext.Provider>
      </PwaContext.Provider>,
    )
    expect(await screen.findByText('Offline Mode')).toBeInTheDocument()
  })
})
