import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthContext'
import type { BackupStatus } from '../types/dashboard'
import { BackupPage } from './BackupPage'

vi.mock('../api/dashboard', () => ({
  getBackupStatus: vi.fn(),
}))

import { getBackupStatus } from '../api/dashboard'

const mockedGet = vi.mocked(getBackupStatus)

const payload: BackupStatus = {
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
  destination: {
    hostname: 'qnap-backup-01',
    ip: '192.168.1.253',
    model: 'TS-253 Pro',
  },
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
      <BackupPage />
    </AuthContext.Provider>,
  )
}

describe('Backup page', () => {
  beforeEach(() => {
    mockedGet.mockReset()
    mockedGet.mockResolvedValue(payload)
  })

  it('renders backup cards', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Backup' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Backup Status card' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Backup Progress card' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Last Backup card' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Next Backup card' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Duration card' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Backup Size card' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Destination NAS card' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Health Badge card' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Last Error card' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: 'Backup History card' })).toBeInTheDocument()
    expect(screen.getByText('TS-253 Pro')).toBeInTheDocument()
    expect(screen.getByText('18 min')).toBeInTheDocument()
    expect(screen.getByText('1.82 TB')).toBeInTheDocument()
    expect(screen.getAllByText('Running').length).toBeGreaterThan(0)
    expect(screen.getAllByText('43.0%').length).toBeGreaterThan(0)
    expect(screen.getByText('Yesterday')).toBeInTheDocument()
    expect(screen.getByText('Success')).toBeInTheDocument()
    expect(screen.getByText('Last Week')).toBeInTheDocument()
    expect(screen.getByText('Failed')).toBeInTheDocument()
    expect(screen.getByLabelText('Backup Healthy')).toBeInTheDocument()
  })

  it('retries after an API failure', async () => {
    const user = userEvent.setup()
    mockedGet.mockRejectedValueOnce(new Error('offline'))
    mockedGet.mockResolvedValue(payload)
    renderPage()
    expect(await screen.findByText('Backup API failed')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry section' }))
    expect(await screen.findByRole('article', { name: 'Backup Status card' })).toBeInTheDocument()
  })

  it('shows a loading state before data arrives', async () => {
    mockedGet.mockReturnValue(new Promise(() => undefined))
    renderPage()
    expect(await screen.findByLabelText('Loading overview')).toBeInTheDocument()
  })

  it('shows an empty state when no job is reported', async () => {
    mockedGet.mockResolvedValue({
      ...payload,
      status: 'unknown',
      job_name: '',
    })
    renderPage()
    expect(await screen.findByText('No backup job has reported a snapshot.')).toBeInTheDocument()
  })

  it('retries from the page action', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('article', { name: 'Backup Status card' })
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(mockedGet.mock.calls.length).toBeGreaterThan(1))
  })

  it('uses a responsive backup card grid', async () => {
    renderPage()
    const grid = await screen.findByLabelText('Backup cards')
    expect(grid.className).toMatch(/cardGrid/)
  })
})
