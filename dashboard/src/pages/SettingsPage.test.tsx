import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthContext'
import { PwaProvider } from '../pwa/PwaProvider'
import type { NotificationSettings } from '../types/dashboard'
import { SettingsPage } from './SettingsPage'

vi.mock('../api/dashboard', () => ({
  getNotificationSettings: vi.fn(),
  updateNotificationSettings: vi.fn(),
  sendTestNotification: vi.fn(),
  sendTelegramTestReport: vi.fn(),
  getRemoteAccess: vi.fn(),
  getPhotoMonitorSettings: vi.fn(),
  updatePhotoMonitorSettings: vi.fn(),
}))

import {
  getNotificationSettings,
  getRemoteAccess,
  sendTelegramTestReport,
  sendTestNotification,
  updateNotificationSettings,
  getPhotoMonitorSettings,
  updatePhotoMonitorSettings,
} from '../api/dashboard'

const mockedGet = vi.mocked(getNotificationSettings)
const mockedUpdate = vi.mocked(updateNotificationSettings)
const mockedTest = vi.mocked(sendTestNotification)
const mockedReport = vi.mocked(sendTelegramTestReport)
const mockedRemote = vi.mocked(getRemoteAccess)

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

function renderSettings(role: 'admin' | 'operator' | 'viewer' = 'admin') {
  return render(
    <AuthContext.Provider
      value={{
        user: {
          id: `user-${role}`,
          username: role,
          full_name: role,
          role,
          is_active: true,
        },
        loading: false,
        login: async () => undefined,
        logout: () => undefined,
      }}
    >
      <PwaProvider>
        <SettingsPage />
      </PwaProvider>
    </AuthContext.Provider>,
  )
}

const settings: NotificationSettings = {
  telegram: {
    enabled: false,
    configured: false,
    api_base_url: 'https://api.telegram.org',
    chat_id: '',
    bot_token_set: false,
    last_test: null,
  },
  discord: { enabled: false, configured: false, webhook_url_set: false },
  slack: { enabled: false, configured: false, webhook_url_set: false },
  email: {
    enabled: false,
    configured: false,
    host: '',
    port: 587,
    username: '',
    from_address: '',
    to_address: '',
    use_tls: true,
    password_set: false,
  },
  reports: {
    hourly_enabled: false,
    daily_enabled: false,
    weekly_enabled: false,
    hour_interval: 1,
    daily_time: '08:00',
    weekly_day: 'sunday',
    weekly_time: '08:00',
    timezone: 'Asia/Bangkok',
    hourly: { enabled: false, last_sent: null, next_scheduled: '2026-09-08T10:00:00+07:00', status: 'disabled' },
    daily: { enabled: false, last_sent: null, next_scheduled: '2026-09-09T08:00:00+07:00', status: 'disabled' },
    weekly: { enabled: false, last_sent: null, next_scheduled: '2026-09-13T08:00:00+07:00', status: 'disabled' },
  },
}

describe('Settings page', () => {
  beforeEach(() => {
    window.localStorage.clear()
    mockedGet.mockReset()
    mockedUpdate.mockReset()
    mockedTest.mockReset()
    mockedReport.mockReset()
    mockedRemote.mockReset()
    mockedRemote.mockResolvedValue(remote)
    mockedGet.mockResolvedValue(settings)
    vi.mocked(getPhotoMonitorSettings).mockResolvedValue({
      enabled: false,
      watch_folder: '/data/photos',
      watch_folders: ['/data/photos', '/data/photos/library-a'],
      recursive: true,
      scan_interval_seconds: 10,
      max_events: 500,
      auto_delete_days: 0,
    })
    vi.mocked(updatePhotoMonitorSettings).mockImplementation(async (payload) => payload)
    mockedUpdate.mockResolvedValue({
      ...settings,
      discord: { enabled: true, configured: true, webhook_url_set: true },
    })
  })

  it('saves notification channel settings', async () => {
    const user = userEvent.setup()
    renderSettings()
    expect(await screen.findByRole('heading', { name: 'Telegram' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Discord' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Slack' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Email' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Scheduled Reports' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Telegram Test' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Deployment' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Application' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Photo Monitor Settings' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Remote Access' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copy URL' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Open Dashboard' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send Test Report' })).toBeInTheDocument()
    expect(screen.getByLabelText('Scheduled report cards').className).toMatch(/statGrid/)
    expect(screen.getByLabelText('Hourly Report Disabled')).toBeInTheDocument()
    expect(screen.getAllByText(/Last Sent:/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Next Scheduled:/).length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Enable Hourly Report')).toBeInTheDocument()
    expect(screen.getByText('Not configured')).toBeInTheDocument()
    expect(screen.getByText(/Last test:/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Test Message' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send Discord test' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send Slack test' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send email test' })).toBeInTheDocument()
    await user.click(screen.getByLabelText('Enable Discord'))
    await user.type(screen.getByLabelText('Discord webhook URL'), 'https://discord.example/api')
    await user.click(screen.getByRole('button', { name: 'Save notification settings' }))
    await waitFor(() => expect(mockedUpdate).toHaveBeenCalled())
  })

  it('sends a Telegram test message and refreshes last test', async () => {
    const user = userEvent.setup()
    mockedTest.mockResolvedValue({
      total: 1,
      notifications: [{ id: 'n1', channel: 'telegram', status: 'sent' }],
    })
    mockedGet
      .mockResolvedValueOnce(settings)
      .mockResolvedValueOnce({
        ...settings,
        telegram: {
          ...settings.telegram,
          configured: true,
          last_test: '2026-09-08T02:00:00+00:00',
        },
      })
    renderSettings()
    expect(await screen.findByText('Last test: Never')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Test Message' }))
    await waitFor(() => expect(mockedTest).toHaveBeenCalledWith('telegram'))
    expect(await screen.findByText('Telegram test message sent.')).toBeInTheDocument()
    expect(mockedGet).toHaveBeenCalledTimes(2)
  })

  it('shows an error state when settings fail to load', async () => {
    mockedGet.mockRejectedValue(new Error('offline'))
    render(
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
        <PwaProvider>
          <SettingsPage />
        </PwaProvider>
      </AuthContext.Provider>,
    )
    expect(await screen.findByText('offline')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry section' })).toBeInTheDocument()
  })

  it('hides the test report button for operators', async () => {
    renderSettings('operator')
    expect(await screen.findByRole('heading', { name: 'Scheduled Reports' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Send Test Report' })).not.toBeInTheDocument()
  })

  it('sends a Telegram test report with loading, success, and error toasts', async () => {
    const user = userEvent.setup()
    let finish: ((value: { status: string; notification_id: string; sent_at: string; provider: string }) => void) | undefined
    mockedReport.mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    renderSettings()
    const button = await screen.findByRole('button', { name: 'Send Test Report' })
    expect(screen.getByRole('heading', { name: 'Telegram Test' }).closest('section')?.className).toMatch(
      /reportsSection/,
    )
    await user.click(button)
    expect(await screen.findByText('Sending...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send Test Report' })).toBeDisabled()
    finish?.({
      status: 'sent',
      notification_id: 'n-test',
      sent_at: '2026-09-08T09:42:18Z',
      provider: 'telegram',
    })
    expect(await screen.findByText('Telegram Test Report Sent')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send Test Report' })).toBeEnabled()
    mockedReport.mockRejectedValueOnce(new Error('offline'))
    await user.click(screen.getByRole('button', { name: 'Send Test Report' }))
    expect(await screen.findByText('Unable to deliver Telegram report.')).toBeInTheDocument()
  })

  it('copies and opens the remote dashboard URL', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })
    const open = vi.fn()
    window.open = open
    renderSettings()
    await user.click(await screen.findByRole('button', { name: 'Copy URL' }))
    expect(writeText).toHaveBeenCalledWith('https://monitor.example.com')
    expect(await screen.findByText('Remote dashboard URL copied.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Open Dashboard' }))
    expect(open).toHaveBeenCalledWith(
      'https://monitor.example.com',
      '_blank',
      'noopener,noreferrer',
    )
  })

  it('saves Photo Monitor settings', async () => {
    const user = userEvent.setup()
    renderSettings()
    expect(await screen.findByRole('heading', { name: 'Photo Monitor Settings' })).toBeInTheDocument()
    await user.click(screen.getByLabelText('Enable Photo Monitor'))
    await user.click(screen.getByRole('button', { name: 'Save Photo Monitor settings' }))
    await waitFor(() => expect(updatePhotoMonitorSettings).toHaveBeenCalled())
    expect(await screen.findByText('Photo Monitor settings saved')).toBeInTheDocument()
  })

  it('adds a watch folder from settings', async () => {
    const user = userEvent.setup()
    renderSettings()
    expect(await screen.findByText('Photos')).toBeInTheDocument()
    expect(screen.getByText('Library A')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Add folder'), '/data/photos/library-b')
    await user.click(screen.getByRole('button', { name: '+ Add Folder' }))
    expect(screen.getByText('Library B')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Save Photo Monitor settings' }))
    await waitFor(() => expect(updatePhotoMonitorSettings).toHaveBeenCalled())
    const payload = vi.mocked(updatePhotoMonitorSettings).mock.calls.at(-1)?.[0]
    expect(payload?.watch_folders).toEqual([
      '/data/photos',
      '/data/photos/library-a',
      '/data/photos/library-b',
    ])
  })

  it('validates public URLs live, previews buttons, and warns on save without changing delivery payload', async () => {
    const user = userEvent.setup()
    renderSettings()
    const dashboard = await screen.findByLabelText('Dashboard Public URL')
    const immich = screen.getByLabelText('Immich Public URL')
    const qnap = screen.getByLabelText('QNAP Public URL')
    expect(screen.getByRole('heading', { name: 'Telegram Buttons Preview' })).toBeInTheDocument()
    expect(screen.getAllByText((_, node) => node?.getAttribute('data-status') === 'empty').length).toBeGreaterThan(0)

    await user.type(dashboard, 'https://monitor.example.com')
    expect(await screen.findByText((_, node) => node?.getAttribute('data-status') === 'valid')).toBeInTheDocument()
    expect(document.querySelector('[data-preview="dashboard"]')?.getAttribute('data-enabled')).toBe('yes')

    await user.clear(dashboard)
    await user.type(dashboard, 'http://localhost')
    expect(await screen.findByText('This URL cannot be opened by Telegram.')).toBeInTheDocument()
    expect(document.querySelector('[data-preview="dashboard"]')?.getAttribute('data-enabled')).toBe('no')

    await user.clear(dashboard)
    await user.type(dashboard, 'http://dashboard:8080')
    expect(await screen.findByText('This address is only reachable inside Docker.')).toBeInTheDocument()

    await user.clear(immich)
    await user.type(immich, 'ftp://photos.example')
    expect(await screen.findAllByText('This URL cannot be opened by Telegram.')).toHaveLength(1)

    await user.type(qnap, 'https://nas.example.com')
    expect(document.querySelector('[data-preview="qnap"]')?.getAttribute('data-enabled')).toBe('yes')

    await user.click(screen.getByRole('button', { name: 'Save notification settings' }))
    await waitFor(() => expect(mockedUpdate).toHaveBeenCalled())
    const saved = mockedUpdate.mock.calls.at(-1)?.[0] as Record<string, unknown>
    expect(saved).not.toHaveProperty('dashboard_public_url')
    expect(JSON.stringify(saved)).not.toContain('dashboard:8080')
    expect(
      await screen.findByText(
        'Dashboard URL is invalid. Telegram messages will be sent without the Dashboard button.',
      ),
    ).toBeInTheDocument()
  })

  it('includes public URL button availability in the Telegram Test Report summary', async () => {
    const user = userEvent.setup()
    mockedReport.mockResolvedValue({
      status: 'sent',
      notification_id: 'n-test',
      sent_at: '2026-09-08T09:42:18Z',
      provider: 'telegram',
    })
    renderSettings()
    await user.type(await screen.findByLabelText('Dashboard Public URL'), 'http://api:8000')
    await user.type(screen.getByLabelText('Immich Public URL'), 'https://immich.example')
    await user.click(screen.getByRole('button', { name: 'Send Test Report' }))
    await waitFor(() => expect(mockedReport).toHaveBeenCalledTimes(1))
    expect(mockedReport.mock.calls[0]?.length ?? 0).toBeLessThanOrEqual(1)
    expect(await screen.findByText('Telegram Test Report Sent')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Telegram Test', level: 4 })).toBeInTheDocument()
    expect(screen.getByText(/Dashboard button ❌ Disabled/)).toBeInTheDocument()
    expect(screen.getByText(/Immich button ✅ Enabled/)).toBeInTheDocument()
    expect(screen.getByText(/QNAP button ❌ Disabled/)).toBeInTheDocument()
    expect(screen.getByText(/Message delivery ✅ Successful/)).toBeInTheDocument()
  })
})
