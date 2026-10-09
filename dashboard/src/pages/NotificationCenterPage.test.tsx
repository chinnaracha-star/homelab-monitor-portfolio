import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  NotificationCenterStatistics,
  NotificationDeliveryHistory,
  NotificationDeliveryMetrics,
  NotificationHistory,
} from '../types/dashboard'
import { formatLocalDateTime } from '../utils/format'
import { NotificationCenterPage } from './NotificationCenterPage'

vi.mock('../api/dashboard', () => ({
  getNotificationHistory: vi.fn(),
  getNotificationCenterStatistics: vi.fn(),
  getNotificationMetrics: vi.fn(),
  getNotificationDeliveryHistory: vi.fn(),
}))

import {
  getNotificationCenterStatistics,
  getNotificationDeliveryHistory,
  getNotificationHistory,
  getNotificationMetrics,
} from '../api/dashboard'

const stats: NotificationCenterStatistics = {
  unread: 1,
  today: 1,
  this_week: 1,
  critical: 1,
  total: 1,
}

const metrics: NotificationDeliveryMetrics = {
  total_sent: 120,
  total_success: 118,
  total_failed: 2,
  success_rate: 98.4,
  average_duration_ms: 145,
  max_duration_ms: 510,
  average_retry_count: 0.12,
  last_notification_at: '2026-09-11T09:13:21Z',
}

const deliveryHistory: NotificationDeliveryHistory = {
  items: [
    {
      id: 'd1',
      created_at: '2026-09-11T09:13:21Z',
      sent_at: '2026-09-11T09:13:21Z',
      channel: 'telegram',
      event: 'activated',
      success: true,
      retry_count: 0,
      duration_ms: 145,
      error_message: null,
    },
    {
      id: 'd2',
      created_at: '2026-09-11T09:14:00Z',
      sent_at: null,
      channel: 'telegram',
      event: 'recovered',
      success: false,
      retry_count: 2,
      duration_ms: 510,
      error_message: 'telegram down',
    },
  ],
}

const history: NotificationHistory = {
  items: [
    {
      id: 'n1',
      title: 'cpu high',
      description: 'CPU recovered',
      severity: 'critical',
      source: 'telegram',
      kind: 'alert',
      agent_id: 'agent-1',
      agent_name: 'monitor',
      read_state: 'unread',
      created_at: '2026-09-08T08:00:00Z',
    },
    {
      id: 'n2',
      title: 'Hourly Report',
      description: 'Sent',
      severity: 'info',
      source: 'telegram',
      kind: 'hourly_report',
      agent_id: null,
      agent_name: null,
      read_state: 'read',
      created_at: '2026-09-08T09:00:00Z',
    },
    {
      id: 'n3',
      title: 'Test Report',
      description: 'Sent',
      severity: 'info',
      source: 'telegram',
      kind: 'test_report',
      agent_id: null,
      agent_name: null,
      read_state: 'read',
      created_at: '2026-09-08T09:05:00Z',
    },
  ],
  groups: [],
}

describe('Notification Center page', () => {
  beforeEach(() => {
    vi.mocked(getNotificationCenterStatistics).mockResolvedValue(stats)
    vi.mocked(getNotificationHistory).mockResolvedValue(history)
    vi.mocked(getNotificationMetrics).mockResolvedValue(metrics)
    vi.mocked(getNotificationDeliveryHistory).mockResolvedValue(deliveryHistory)
  })

  it('shows skeleton cards while metrics load', async () => {
    vi.mocked(getNotificationMetrics).mockImplementation(() => new Promise(() => {}))
    render(<NotificationCenterPage />)
    expect(await screen.findByLabelText('Loading notification metrics')).toBeInTheDocument()
    expect(screen.getByLabelText('Loading Notifications Sent')).toBeInTheDocument()
    expect(screen.getByLabelText('Loading Success Rate')).toBeInTheDocument()
  })

  it('renders formatted delivery metric cards', async () => {
    render(<NotificationCenterPage />)
    expect(await screen.findByRole('heading', { name: 'Notification Center' })).toBeInTheDocument()
    expect(screen.getByLabelText('Notification delivery metrics').className).toMatch(/metricsCardGrid/)
    expect(screen.getByLabelText('Notifications Sent 120')).toBeInTheDocument()
    expect(screen.getByLabelText('Success Rate 98.4 % ↑ Stable')).toBeInTheDocument()
    expect(screen.getByLabelText('Failed Notifications 2 Needs attention')).toBeInTheDocument()
    expect(screen.getByLabelText('Average Delivery Time 145 ms Fast')).toBeInTheDocument()
    expect(screen.getByLabelText('Average Retry Count 0.12 Excellent')).toBeInTheDocument()
    expect(
      screen.getByLabelText(`Last Notification Time ${formatLocalDateTime(metrics.last_notification_at)}`),
    ).toBeInTheDocument()
    expect(await screen.findByLabelText('Unread 1')).toBeInTheDocument()
    expect(screen.getByLabelText('Notification timeline')).toBeInTheDocument()
    expect(screen.getByLabelText('Notification filters')).toBeInTheDocument()
    expect(screen.getByText('Hourly Report')).toBeInTheDocument()
    expect(screen.getByText('Test Report')).toBeInTheDocument()
  })

  it('shows a no-failures trend when every delivery succeeded', async () => {
    vi.mocked(getNotificationMetrics).mockResolvedValue({
      ...metrics,
      total_failed: 0,
      success_rate: 100,
    })
    render(<NotificationCenterPage />)
    expect(await screen.findByLabelText('Failed Notifications 0 No failures')).toBeInTheDocument()
    expect(screen.getByLabelText('Success Rate 100.0 % ↑ Stable')).toBeInTheDocument()
  })

  it('shows skeleton rows while delivery history loads', async () => {
    vi.mocked(getNotificationDeliveryHistory).mockImplementation(() => new Promise(() => {}))
    render(<NotificationCenterPage />)
    expect(await screen.findByLabelText('Loading delivery history')).toBeInTheDocument()
  })

  it('shows an empty delivery history state', async () => {
    vi.mocked(getNotificationDeliveryHistory).mockResolvedValue({ items: [] })
    render(<NotificationCenterPage />)
    expect(await screen.findByText('No notification history yet.')).toBeInTheDocument()
  })

  it('renders formatted success and failed delivery rows', async () => {
    render(<NotificationCenterPage />)
    expect(await screen.findByRole('heading', { name: 'Delivery History' })).toBeInTheDocument()
    expect(screen.getByLabelText('Delivery history table').className).toMatch(/deliveryTableWrap/)
    expect(screen.getByLabelText('Delivery history cards').className).toMatch(/deliveryCardList/)
    expect(screen.getAllByText('Telegram').length).toBeGreaterThan(0)
    expect(screen.getAllByText('🟠 Activated').length).toBeGreaterThan(0)
    expect(screen.getAllByText('🔵 Recovered').length).toBeGreaterThan(0)
    expect(screen.getAllByText('🟢 Success').length).toBeGreaterThan(0)
    expect(screen.getAllByText('🔴 Failed').length).toBeGreaterThan(0)
    expect(screen.getAllByLabelText('status 🟢 Success').length).toBeGreaterThan(0)
    expect(screen.getAllByLabelText('event 🟠 Activated').length).toBeGreaterThan(0)
    expect(screen.getAllByLabelText('channel Telegram').length).toBeGreaterThan(0)
    expect(screen.getAllByText('145 ms').length).toBeGreaterThan(0)
    expect(screen.getAllByText('510 ms').length).toBeGreaterThan(0)
    expect(screen.getAllByText('-').length).toBeGreaterThan(0)
    expect(screen.getAllByText('telegram down').length).toBeGreaterThan(0)
    expect(screen.getAllByText('0').length).toBeGreaterThan(0)
    expect(screen.getAllByText('2').length).toBeGreaterThan(0)
    expect(screen.getAllByText(formatLocalDateTime('2026-09-11T09:13:21Z')).length).toBeGreaterThan(0)
  })

  it('retries delivery history independently', async () => {
    vi.mocked(getNotificationDeliveryHistory).mockRejectedValue(new Error('failed'))
    render(<NotificationCenterPage />)
    expect(await screen.findByText('Delivery history failed')).toBeInTheDocument()
    expect(screen.getByLabelText('Notification delivery metrics')).toBeInTheDocument()
    vi.mocked(getNotificationDeliveryHistory).mockResolvedValue(deliveryHistory)
    await userEvent.click(screen.getByRole('button', { name: 'Retry section' }))
    await waitFor(() => {
      expect(screen.getByLabelText('Delivery history table')).toBeInTheDocument()
    })
  })

  it('shows empty and retry', async () => {
    vi.mocked(getNotificationHistory).mockResolvedValue({ items: [], groups: [] })
    render(<NotificationCenterPage />)
    expect(await screen.findByText('No notifications yet.')).toBeInTheDocument()
    expect(screen.getByLabelText('Notification filters').className).toMatch(/filterBar/)
  })

  it('searches delivery history by channel, event, and error', async () => {
    render(<NotificationCenterPage />)
    expect(await screen.findByText('Showing 2 of 2 notifications')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Search'), 'telegram down')
    expect(screen.getByText('Showing 1 of 2 notifications')).toBeInTheDocument()
    expect(screen.getAllByText('🔴 Failed').length).toBeGreaterThan(0)
    expect(screen.queryByText('🟢 Success')).not.toBeInTheDocument()
  })

  it('filters delivery history by status', async () => {
    render(<NotificationCenterPage />)
    expect(await screen.findByText('Showing 2 of 2 notifications')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Status'), 'Success')
    expect(screen.getByText('Showing 1 of 2 notifications')).toBeInTheDocument()
    expect(screen.getAllByText('🟢 Success').length).toBeGreaterThan(0)
    expect(screen.queryByText('🔴 Failed')).not.toBeInTheDocument()
  })

  it('filters delivery history by event', async () => {
    render(<NotificationCenterPage />)
    expect(await screen.findByText('Showing 2 of 2 notifications')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Event'), 'Recovered')
    expect(screen.getByText('Showing 1 of 2 notifications')).toBeInTheDocument()
    expect(screen.getAllByText('🔵 Recovered').length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Delivery history table')).not.toHaveTextContent('🟠 Activated')
    expect(screen.getByLabelText('Delivery history cards')).not.toHaveTextContent('🟠 Activated')
  })

  it('applies combined delivery filters', async () => {
    render(<NotificationCenterPage />)
    expect(await screen.findByText('Showing 2 of 2 notifications')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Search'), 'telegram')
    await userEvent.selectOptions(screen.getByLabelText('Status'), 'Failed')
    await userEvent.selectOptions(screen.getByLabelText('Event'), 'Recovered')
    await userEvent.selectOptions(screen.getByLabelText('Channel'), 'Telegram')
    expect(screen.getByText('Showing 1 of 2 notifications')).toBeInTheDocument()
    expect(screen.getAllByText('telegram down').length).toBeGreaterThan(0)
    expect(screen.queryByText('🟢 Success')).not.toBeInTheDocument()
  })

  it('shows an empty filtered delivery state and restores after clearing search', async () => {
    render(<NotificationCenterPage />)
    const search = await screen.findByLabelText('Search')
    await userEvent.type(search, 'does-not-match')
    expect(screen.getByText('Showing 0 of 2 notifications')).toBeInTheDocument()
    expect(screen.getByText('No matching notifications.')).toBeInTheDocument()
    expect(screen.queryByLabelText('Delivery history table')).not.toBeInTheDocument()
    await userEvent.clear(search)
    expect(screen.getByText('Showing 2 of 2 notifications')).toBeInTheDocument()
    expect(screen.getByLabelText('Delivery history table')).toBeInTheDocument()
  })

  it('matches delivery search case-insensitively', async () => {
    render(<NotificationCenterPage />)
    await userEvent.type(await screen.findByLabelText('Search'), 'TELEGRAM DOWN')
    expect(screen.getByText('Showing 1 of 2 notifications')).toBeInTheDocument()
    expect(screen.getAllByText('telegram down').length).toBeGreaterThan(0)
  })

  it('retries after an error', async () => {
    vi.mocked(getNotificationHistory).mockRejectedValue(new Error('failed'))
    vi.mocked(getNotificationCenterStatistics).mockRejectedValue(new Error('failed'))
    vi.mocked(getNotificationMetrics).mockRejectedValue(new Error('failed'))
    render(<NotificationCenterPage />)
    expect(await screen.findByText('Notification center failed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry section' })).toBeInTheDocument()
    vi.mocked(getNotificationHistory).mockResolvedValue(history)
    vi.mocked(getNotificationCenterStatistics).mockResolvedValue(stats)
    vi.mocked(getNotificationMetrics).mockResolvedValue(metrics)
    vi.mocked(getNotificationDeliveryHistory).mockResolvedValue(deliveryHistory)
    await userEvent.click(screen.getByRole('button', { name: 'Retry section' }))
    await waitFor(() => {
      expect(screen.getByLabelText('Notification timeline')).toBeInTheDocument()
      expect(screen.getByLabelText('Success Rate 98.4 % ↑ Stable')).toBeInTheDocument()
    })
  })
})
