import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AgentHistorySection } from './AgentHistorySection'
import type { AgentHistory } from '../types/dashboard'
import { historyExportFilename, historyPointsToCsv } from '../utils/history'

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
  getAgentHistory: vi.fn(),
}))

import { getAgentHistory } from '../api/dashboard'

const mockedGetHistory = vi.mocked(getAgentHistory)

const sampleHistory: AgentHistory = {
  agent_id: 'agent-1',
  interval: '15m',
  from: '2026-09-06T14:00:00Z',
  to: '2026-09-07T14:00:00Z',
  points: [
    {
      timestamp: '2026-09-07T13:00:00Z',
      cpu_percent: 12,
      memory_percent: 40,
      disk_percent: 55,
      temperature_celsius: 48,
      network_rx_bytes: 100,
      network_tx_bytes: 200,
    },
    {
      timestamp: '2026-09-07T13:15:00Z',
      cpu_percent: 18,
      memory_percent: 42,
      disk_percent: 56,
      temperature_celsius: 49,
      network_rx_bytes: 110,
      network_tx_bytes: 210,
    },
  ],
}

describe('AgentHistorySection', () => {
  beforeEach(() => {
    mockedGetHistory.mockReset()
  })

  it('renders history charts for the selected range', async () => {
    mockedGetHistory.mockResolvedValue(sampleHistory)
    render(<AgentHistorySection agentId="agent-1" agentName="mini-pc" />)

    expect(screen.getByLabelText('Loading history')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'History' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'CPU' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Memory' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Disk' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Temperature' })).toBeInTheDocument()
    expect(screen.getAllByTestId('chart-surface')).toHaveLength(4)
    expect(mockedGetHistory).toHaveBeenCalledWith(
      'agent-1',
      expect.objectContaining({ interval: '15m' }),
    )
  })

  it('requests a new window when the range changes', async () => {
    const user = userEvent.setup()
    mockedGetHistory.mockResolvedValue(sampleHistory)
    render(<AgentHistorySection agentId="agent-1" agentName="mini-pc" />)
    await screen.findByRole('heading', { name: 'CPU' })

    await user.click(screen.getByRole('button', { name: '1h' }))
    await waitFor(() => {
      expect(mockedGetHistory).toHaveBeenCalledWith(
        'agent-1',
        expect.objectContaining({ interval: '1m' }),
      )
    })
  })

  it('shows an empty state when no points are returned', async () => {
    mockedGetHistory.mockResolvedValue({ ...sampleHistory, points: [] })
    render(<AgentHistorySection agentId="agent-1" agentName="mini-pc" />)
    expect(await screen.findByText('No metric history for this range.')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'CPU' })).not.toBeInTheDocument()
  })

  it('downloads CSV for the current chart data', async () => {
    const user = userEvent.setup()
    mockedGetHistory.mockResolvedValue(sampleHistory)
    const click = vi.fn()
    HTMLAnchorElement.prototype.click = click
    const createObjectURL = vi.fn(() => 'blob:history')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL })

    render(<AgentHistorySection agentId="agent-1" agentName="mini-pc" />)
    await screen.findByRole('heading', { name: 'CPU' })
    await user.click(screen.getByRole('button', { name: 'Export CSV' }))

    expect(createObjectURL).toHaveBeenCalled()
    expect(click).toHaveBeenCalled()
    const csv = historyPointsToCsv(sampleHistory.points)
    expect(csv).toContain('cpu_percent')
    expect(csv).toContain('12')
    expect(historyExportFilename('mini-pc', new Date(2026, 8, 7, 14, 32))).toBe(
      'mini-pc-20260907-1432.csv',
    )
    vi.unstubAllGlobals()
  })
})
