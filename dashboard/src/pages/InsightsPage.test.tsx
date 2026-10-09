import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthContext'
import type { InsightOverview } from '../types/dashboard'
import { InsightsPage } from './InsightsPage'

vi.mock('../api/dashboard', () => ({
  getInsightsOverview: vi.fn(),
}))

import { getInsightsOverview } from '../api/dashboard'

const overview: InsightOverview = {
  overall: {
    summary: 'Storage capacity should be reviewed.',
    severity: 'critical',
    recommendation: 'Consider adding larger disks.',
  },
  storage: {
    summary: 'Estimated capacity will be reached in 5.25 days.',
    severity: 'critical',
    recommendation: 'Consider adding larger disks.',
    estimated_days: 5.25,
  },
  cpu: { summary: 'CPU usage has remained stable.', severity: 'info', recommendation: '' },
  memory: { summary: 'Memory usage is healthy.', severity: 'info', recommendation: '' },
  backup: { summary: 'Backup success rate is excellent.', severity: 'info', recommendation: '' },
  photos: { summary: 'Photo library continues to grow.', severity: 'info', recommendation: '' },
  infrastructure: { summary: 'All monitored services are healthy.', severity: 'info', recommendation: '' },
  recommendation: 'Storage capacity should be reviewed.',
  severity: 'critical',
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
      <InsightsPage />
    </AuthContext.Provider>,
  )
}

describe('AI Insights page', () => {
  beforeEach(() => {
    vi.mocked(getInsightsOverview).mockResolvedValue(overview)
  })

  it('renders insight cards and severity badges', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: 'AI Insights' })).toBeInTheDocument()
    expect(screen.getByLabelText('Overall Summary critical')).toBeInTheDocument()
    expect(screen.getByLabelText('Storage Insight severity critical')).toBeInTheDocument()
    expect(screen.getByLabelText('CPU Insight severity info')).toBeInTheDocument()
    expect(screen.getByText('Estimated capacity will be reached in 5.25 days.')).toBeInTheDocument()
    expect(screen.getAllByText('Consider adding larger disks.').length).toBeGreaterThan(0)
    expect(screen.getByText('All monitored services are healthy.')).toBeInTheDocument()
  })

  it('shows empty insight copy', async () => {
    vi.mocked(getInsightsOverview).mockResolvedValue({
      ...overview,
      overall: { summary: '', severity: 'unknown', recommendation: '' },
    })
    renderPage()
    expect(await screen.findByText('No insights yet.')).toBeInTheDocument()
  })

  it('shows loading skeletons', () => {
    vi.mocked(getInsightsOverview).mockImplementation(() => new Promise(() => undefined))
    renderPage()
    expect(screen.getByLabelText('Loading overview')).toBeInTheDocument()
  })

  it('shows an error and retries', async () => {
    vi.mocked(getInsightsOverview).mockRejectedValue(new Error('failed'))
    renderPage()
    expect(await screen.findByText('Insights failed')).toBeInTheDocument()
    vi.mocked(getInsightsOverview).mockResolvedValue(overview)
    await userEvent.click(screen.getByRole('button', { name: 'Retry section' }))
    await waitFor(() => {
      expect(screen.getByLabelText('Overall Summary critical')).toBeInTheDocument()
    })
  })

  it('uses a responsive insight grid', async () => {
    renderPage()
    const grid = await screen.findByLabelText('Insight cards')
    expect(grid.className).toMatch(/insightGrid/)
  })
})
