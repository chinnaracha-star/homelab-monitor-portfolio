import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthContext'
import type { NotificationList } from '../types/dashboard'
import { NotificationsPage } from './NotificationsPage'

vi.mock('../api/dashboard', () => ({
  getNotifications: vi.fn(),
  retryNotification: vi.fn(),
  sendTestNotification: vi.fn(),
}))

import { getNotifications, retryNotification, sendTestNotification } from '../api/dashboard'

const mockedList = vi.mocked(getNotifications)
const mockedRetry = vi.mocked(retryNotification)
const mockedTest = vi.mocked(sendTestNotification)

const payload: NotificationList = {
  total: 1,
  notifications: [
    {
      id: 'note-1',
      alert_id: 'alert-1',
      channel: 'discord',
      recipient: 'configured webhook',
      status: 'failed',
      error_message: 'HTTP 500',
      sent_at: null,
      created_at: '2026-09-08T00:00:00Z',
      updated_at: '2026-09-08T00:00:00Z',
    },
  ],
}

function renderPage(role: 'admin' | 'viewer' = 'admin') {
  return render(
    <AuthContext.Provider
      value={{
        user: {
          id: 'user-1',
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
      <NotificationsPage />
    </AuthContext.Provider>,
  )
}

describe('Notifications page', () => {
  beforeEach(() => {
    mockedList.mockReset()
    mockedRetry.mockReset()
    mockedTest.mockReset()
    mockedList.mockResolvedValue(payload)
  })

  it('lists delivery status and retries failures', async () => {
    const user = userEvent.setup()
    mockedRetry.mockResolvedValue({ ...payload.notifications[0], status: 'sent' })
    renderPage()
    expect(await screen.findByRole('table', { name: 'Notification deliveries' })).toBeInTheDocument()
    expect(screen.getByText('discord')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(mockedRetry).toHaveBeenCalledWith('note-1'))
  })

  it('hides write actions for viewers', async () => {
    renderPage('viewer')
    await screen.findByText('discord')
    expect(screen.queryByRole('button', { name: 'Send test' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
  })

  it('shows an empty state when there is no history', async () => {
    mockedList.mockResolvedValue({ total: 0, notifications: [] })
    renderPage()
    expect(await screen.findByText('No notifications yet.')).toBeInTheDocument()
  })

  it('shows a loading state before history arrives', async () => {
    mockedList.mockReturnValue(new Promise(() => undefined))
    renderPage()
    expect(await screen.findByLabelText('Loading notifications')).toBeInTheDocument()
  })

  it('shows an error state when the notifications API fails', async () => {
    mockedList.mockRejectedValue(new Error('offline'))
    renderPage()
    expect(await screen.findByText('Notifications API failed')).toBeInTheDocument()
  })
})
