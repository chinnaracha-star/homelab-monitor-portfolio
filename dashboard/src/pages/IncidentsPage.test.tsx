import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { IncidentStatistics, IncidentSummary } from '../types/dashboard'
import { IncidentsPage } from './IncidentsPage'

vi.mock('../api/dashboard', () => ({
  getIncidents: vi.fn(),
  getIncidentStatistics: vi.fn(),
  getIncident: vi.fn(),
}))

import { getIncident, getIncidentStatistics, getIncidents } from '../api/dashboard'

const stats: IncidentStatistics = {
  average_duration_seconds: 120,
  open_count: 1,
  recovered_count: 0,
  critical_count: 1,
  warning_count: 0,
  incident_count: 1,
  top_affected_agent: 'monitor',
}

const summary: IncidentSummary = {
  id: 'inc-1',
  started_at: '2026-09-08T08:00:00Z',
  recovered_at: null,
  duration_seconds: 120,
  agent_id: 'agent-1',
  agent_name: 'monitor',
  severity: 'critical',
  status: 'active',
  alert_count: 2,
  cause: 'cpu_high',
}

describe('Incidents page', () => {
  beforeEach(() => {
    vi.mocked(getIncidentStatistics).mockResolvedValue(stats)
    vi.mocked(getIncidents).mockResolvedValue([summary])
    vi.mocked(getIncident).mockResolvedValue({
      ...summary,
      affected_alerts: [],
    })
  })

  it('renders cards, timeline, and incident details', async () => {
    render(<IncidentsPage />)
    expect(await screen.findByRole('heading', { name: 'Incidents' })).toBeInTheDocument()
    expect(screen.getByLabelText('Open Incidents 1')).toBeInTheDocument()
    expect(screen.getByLabelText('Incident timeline')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /monitor/ }))
    await waitFor(() => {
      expect(screen.getByLabelText('Incident details')).toBeInTheDocument()
    })
  })

  it('shows empty, loading, retry, and a responsive timeline', async () => {
    vi.mocked(getIncidents).mockResolvedValue([])
    render(<IncidentsPage />)
    expect(await screen.findByText('No incidents yet.')).toBeInTheDocument()
    expect(screen.getByLabelText('Incident statistics').className).toMatch(/statGrid/)
  })

  it('retries after an error', async () => {
    vi.mocked(getIncidents).mockRejectedValue(new Error('failed'))
    vi.mocked(getIncidentStatistics).mockRejectedValue(new Error('failed'))
    render(<IncidentsPage />)
    expect(await screen.findByText('Incidents failed')).toBeInTheDocument()
    vi.mocked(getIncidents).mockResolvedValue([summary])
    vi.mocked(getIncidentStatistics).mockResolvedValue(stats)
    await userEvent.click(screen.getByRole('button', { name: 'Retry section' }))
    await waitFor(() => {
      expect(screen.getByLabelText('Incident timeline')).toBeInTheDocument()
    })
  })
})
