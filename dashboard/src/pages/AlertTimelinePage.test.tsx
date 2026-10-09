import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { AlertHistoryEntry, AlertStatistics } from '../types/dashboard'
import { AlertTimelinePage } from './AlertTimelinePage'

vi.mock('../api/dashboard', () => ({
  getAlertHistory: vi.fn(),
  getAlertStatistics: vi.fn(),
}))

import { getAlertHistory, getAlertStatistics } from '../api/dashboard'

const stats: AlertStatistics = {
  active_alerts: 1,
  recovered_today: 1,
  average_duration_seconds: 180,
  critical_count: 1,
  warning_count: 1,
  recovery_rate: 50,
  recovered: 1,
  total: 2,
}

const recovered: AlertHistoryEntry = {
  id: 'a1',
  alert_type: 'cpu_high',
  severity: 'critical',
  started_at: '2026-09-08T08:00:00Z',
  recovered_at: '2026-09-08T08:03:00Z',
  duration_seconds: 180,
  agent_id: 'agent-1',
  agent_name: 'monitor',
  source: 'system',
  threshold: 90,
  peak_value: 96,
  status: 'recovered',
}

describe('Alert Timeline page', () => {
  beforeEach(() => {
    vi.mocked(getAlertStatistics).mockResolvedValue(stats)
    vi.mocked(getAlertHistory).mockResolvedValue([recovered])
  })

  it('renders cards, timeline, duration, and filters', async () => {
    render(<AlertTimelinePage />)
    expect(await screen.findByRole('heading', { name: 'Alert Timeline' })).toBeInTheDocument()
    expect(screen.getByLabelText('Active Alerts 1')).toBeInTheDocument()
    expect(screen.getByLabelText('Alert timeline')).toBeInTheDocument()
    expect(screen.getByLabelText('Average Duration 3 min')).toBeInTheDocument()
    expect(screen.getAllByText('3 min').length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Alert filters')).toBeInTheDocument()
    expect(screen.getByLabelText('Status RECOVERED')).toBeInTheDocument()
  })

  it('shows loading, empty, retry, and a responsive filter bar', async () => {
    vi.mocked(getAlertHistory).mockImplementation(() => new Promise(() => undefined))
    vi.mocked(getAlertStatistics).mockImplementation(() => new Promise(() => undefined))
    const { unmount } = render(<AlertTimelinePage />)
    expect(screen.getByLabelText('Loading overview')).toBeInTheDocument()
    unmount()
    vi.mocked(getAlertStatistics).mockResolvedValue(stats)
    vi.mocked(getAlertHistory).mockResolvedValue([])
    render(<AlertTimelinePage />)
    expect(await screen.findByText('No alert history yet.')).toBeInTheDocument()
    expect(screen.getByLabelText('Alert filters').className).toMatch(/filterBar/)
  })

  it('retries after an error', async () => {
    vi.mocked(getAlertHistory).mockRejectedValue(new Error('failed'))
    vi.mocked(getAlertStatistics).mockRejectedValue(new Error('failed'))
    render(<AlertTimelinePage />)
    expect(await screen.findByText('Alert timeline failed')).toBeInTheDocument()
    vi.mocked(getAlertHistory).mockResolvedValue([recovered])
    vi.mocked(getAlertStatistics).mockResolvedValue(stats)
    await userEvent.click(screen.getByRole('button', { name: 'Retry section' }))
    await waitFor(() => {
      expect(screen.getByLabelText('Alert timeline')).toBeInTheDocument()
    })
  })
})
