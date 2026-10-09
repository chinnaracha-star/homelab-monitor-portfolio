import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthContext'
import type { InfrastructureSummary } from '../types/dashboard'
import { InfrastructurePage } from './InfrastructurePage'

vi.mock('../api/dashboard', () => ({
  getInfrastructure: vi.fn(),
}))

import { getInfrastructure } from '../api/dashboard'

const mockedGet = vi.mocked(getInfrastructure)

const payload: InfrastructureSummary = {
  collected_at: '2026-09-08T01:00:00Z',
  services: [
    {
      service: 'qnap',
      status: 'healthy',
      version: '5.2.1',
      updated_at: '2026-09-08T01:00:00Z',
      summary: {
        hostname: 'qnap-lab-01',
        online: true,
        model: 'TS-453Be',
        storage_percent: 41.5,
        sys_tempc: 34,
        cpu_tempc: 43,
        disk_temp_warning_c: 55,
        disk_temp_critical_c: 60,
        disks: [
          {
            bay: 1,
            alias: '3.5" SATA HDD 1',
            installed: true,
            is_ssd: false,
            temperature_celsius: 42,
            temp_alert: 0,
            temperature_status: 'normal',
            manufacturer: null,
            model: null,
            capacity_bytes: null,
            smart_status: null,
            abnormal_sector_count: null,
          },
          {
            bay: 2,
            alias: '3.5" SATA HDD 2',
            installed: true,
            is_ssd: false,
            temperature_celsius: null,
            temp_alert: 0,
            temperature_status: 'unknown',
            manufacturer: null,
            model: null,
            capacity_bytes: null,
            smart_status: null,
            abnormal_sector_count: null,
          },
          {
            bay: 3,
            alias: null,
            installed: true,
            is_ssd: false,
            temperature_celsius: 55,
            temp_alert: 0,
            temperature_status: 'warning',
            manufacturer: null,
            model: null,
            capacity_bytes: null,
            smart_status: null,
            abnormal_sector_count: null,
          },
          {
            bay: 4,
            alias: null,
            installed: true,
            is_ssd: false,
            temperature_celsius: 60,
            temp_alert: 0,
            temperature_status: 'critical',
            manufacturer: null,
            model: null,
            capacity_bytes: null,
            smart_status: null,
            abnormal_sector_count: null,
          },
        ],
      },
    },
    {
      service: 'docker',
      status: 'healthy',
      version: '27.3.1',
      updated_at: '2026-09-08T01:00:00Z',
      summary: { running_containers: 12, stopped_containers: 2 },
    },
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
      <InfrastructurePage />
    </AuthContext.Provider>,
  )
}

describe('Infrastructure page', () => {
  beforeEach(() => {
    mockedGet.mockReset()
    mockedGet.mockResolvedValue(payload)
  })

  it('renders connector cards with status and summary', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Infrastructure' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'QNAP connector' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Docker connector' })).toBeInTheDocument()
    expect(screen.getByText('qnap-lab-01')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'QNAP disk health' })).toBeInTheDocument()
    expect(screen.getByText('HDD 1')).toBeInTheDocument()
    expect(screen.getByText('HDD 4')).toBeInTheDocument()
    expect(screen.getByText('42°C')).toBeInTheDocument()
    expect(screen.getByText('Normal')).toBeInTheDocument()
    expect(screen.getByText('Warning')).toBeInTheDocument()
    expect(screen.getByText('Critical')).toBeInTheDocument()
    expect(screen.getByText('Temperature: Unknown')).toBeInTheDocument()
    expect(screen.getByText('3.5" SATA HDD 1')).toBeInTheDocument()
    expect(screen.getByText('System Temp').parentElement).toHaveTextContent('34°C')
    expect(screen.getByText('CPU Temp').parentElement).toHaveTextContent('43°C')
    expect(screen.getByText('SMART: Unavailable')).toBeInTheDocument()
    expect(screen.queryByText('SMART: Good')).not.toBeInTheDocument()
    expect(screen.getByText('Threshold: Warning 55°C / Critical 60°C')).toBeInTheDocument()
    expect(screen.getByText('Version 5.2.1')).toBeInTheDocument()
  })

  it('shows QNAP offline without a zero temperature', async () => {
    mockedGet.mockResolvedValue({
      ...payload,
      services: [
        {
          ...payload.services[0],
          status: 'unhealthy',
          summary: { hostname: 'qnap-lab-01', online: false, temperature_celsius: null, model: 'TS-453Be' },
        },
      ],
    })
    renderPage()
    expect(await screen.findByText('Disk Temperature: unavailable')).toBeInTheDocument()
    expect(screen.queryByText('0°C')).not.toBeInTheDocument()
  })

  it('shows unavailable storage instead of zero percent', async () => {
    mockedGet.mockResolvedValue({
      ...payload,
      services: [
        {
          ...payload.services[0],
          summary: { ...payload.services[0].summary, storage_percent: null, storage_used_percent: null },
        },
      ],
    })
    renderPage()
    expect(await screen.findByText('Unavailable')).toBeInTheDocument()
    expect(screen.queryByText('0%')).not.toBeInTheDocument()
    expect(screen.queryByText('0.0%')).not.toBeInTheDocument()
  })

  it('retries after an API failure', async () => {
    const user = userEvent.setup()
    mockedGet.mockRejectedValueOnce(new Error('offline'))
    mockedGet.mockResolvedValue(payload)
    renderPage()
    expect(await screen.findByText('Infrastructure API failed')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry section' }))
    expect(await screen.findByRole('article', { name: 'QNAP connector' })).toBeInTheDocument()
  })

  it('shows a loading state before data arrives', async () => {
    mockedGet.mockReturnValue(new Promise(() => undefined))
    renderPage()
    expect(await screen.findByLabelText('Loading overview')).toBeInTheDocument()
  })

  it('shows an empty state when no connectors report', async () => {
    mockedGet.mockResolvedValue({ collected_at: '2026-09-08T01:00:00Z', services: [] })
    renderPage()
    expect(
      await screen.findByText('No infrastructure connectors reported a snapshot.'),
    ).toBeInTheDocument()
  })

  it('retries a single connector card', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('article', { name: 'QNAP connector' })
    await user.click(screen.getAllByRole('button', { name: 'Retry' })[0])
    await waitFor(() => expect(mockedGet.mock.calls.length).toBeGreaterThan(1))
  })
})
