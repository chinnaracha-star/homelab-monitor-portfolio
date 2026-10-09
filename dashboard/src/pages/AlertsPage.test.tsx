import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ActiveAlert } from '../types/dashboard'
import { AlertsPage } from './AlertsPage'

vi.mock('../api/dashboard', () => ({
  getActiveAlerts: vi.fn(),
}))

import { getActiveAlerts } from '../api/dashboard'

const active: ActiveAlert = {
  id: 'alert-active',
  agent_id: 'agent-1',
  agent_name: 'monitor',
  kind: 'cpu_high',
  resource: 'system',
  severity: 'warning',
  current_value: 96,
  threshold: 90,
  message: 'CPU high',
  opened_at: '2026-09-08T08:00:00Z',
  last_observed_at: '2026-09-08T08:03:00Z',
  status: 'active',
  started_at: '2026-09-08T08:00:00Z',
  last_triggered_at: '2026-09-08T08:03:00Z',
  recovered_at: null,
  duration_seconds: 180,
}

const recovered: ActiveAlert = {
  ...active,
  id: 'alert-recovered',
  status: 'recovered',
  recovered_at: '2026-09-08T08:17:00Z',
  duration_seconds: 17 * 60,
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AlertsPage />
    </MemoryRouter>,
  )
}

describe('Alerts page lifecycle', () => {
  beforeEach(() => {
    vi.mocked(getActiveAlerts).mockResolvedValue([active, recovered])
  })

  it('renders ACTIVE and RECOVERED cards with timestamps and duration', async () => {
    renderPage()
    expect(await screen.findByLabelText('Status ACTIVE')).toBeInTheDocument()
    expect(screen.getByLabelText('Status RECOVERED')).toBeInTheDocument()
    expect(screen.getAllByText('Started').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Duration').length).toBeGreaterThan(0)
    expect(screen.getByText('17 min')).toBeInTheDocument()
    expect(screen.getAllByText('Last Triggered').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Recovered').length).toBeGreaterThan(0)
  })

  it('shows a loading skeleton', () => {
    vi.mocked(getActiveAlerts).mockImplementation(() => new Promise(() => undefined))
    renderPage()
    expect(screen.getByLabelText('Loading alerts')).toBeInTheDocument()
  })

  it('shows an empty state', async () => {
    vi.mocked(getActiveAlerts).mockResolvedValue([])
    renderPage()
    expect(await screen.findByText('No alerts yet.')).toBeInTheDocument()
  })

  it('retries after an error', async () => {
    vi.mocked(getActiveAlerts).mockRejectedValue(new Error('failed'))
    renderPage()
    expect(await screen.findByText('Alerts API failed')).toBeInTheDocument()
    vi.mocked(getActiveAlerts).mockResolvedValue([active])
    await userEvent.click(screen.getByRole('button', { name: 'Retry section' }))
    await waitFor(() => {
      expect(screen.getByLabelText('Status ACTIVE')).toBeInTheDocument()
    })
  })
})
