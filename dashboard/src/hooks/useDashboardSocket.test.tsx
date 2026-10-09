import { act, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ACCESS_TOKEN_KEY } from '../auth/storage'
import { REFRESH_INTERVAL_MS } from '../constants'
import {
  DashboardSocketProvider,
  INITIAL_RECONNECT_MS,
  dashboardWebSocketUrl,
  useDashboardConnection,
  useDashboardSocket,
  useLivePolling,
} from './useDashboardSocket'

class MockWebSocket {
  static instances: MockWebSocket[] = []
  static OPEN = 1
  static CONNECTING = 0
  static CLOSING = 2
  static CLOSED = 3

  url: string
  readyState = MockWebSocket.CONNECTING
  sent: string[] = []
  onopen: ((event?: Event) => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onerror: ((event?: Event) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  send(data: string) {
    this.sent.push(data)
  }

  close(code = 1000) {
    this.readyState = MockWebSocket.CLOSED
    this.onclose?.({ code })
  }

  open() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.()
  }

  emit(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) })
  }
}

function StatusProbe() {
  const { status, lastEvent } = useDashboardSocket()
  return (
    <section>
      <p>{status}</p>
      <p data-testid="event-id">{lastEvent?.id ?? 'none'}</p>
      <p data-testid="event-type">{lastEvent?.type ?? 'none'}</p>
    </section>
  )
}

function ProviderStatusProbe() {
  const { status, lastEvent } = useDashboardConnection()
  return (
    <section>
      <p>{status}</p>
      <p data-testid="event-type">{lastEvent?.type ?? 'none'}</p>
    </section>
  )
}

function LiveDataProbe({
  fetcher,
  keepPolling = false,
}: {
  fetcher: () => Promise<string>
  keepPolling?: boolean
}) {
  const { data } = useLivePolling(fetcher, ['agent_updated', 'overview_updated', 'alert_updated'], {
    keepPolling,
  })
  return <p data-testid="live-data">{data ?? 'empty'}</p>
}

describe('useDashboardSocket', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
    window.localStorage.setItem(ACCESS_TOKEN_KEY, 'jwt-token')
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    window.localStorage.clear()
  })

  it('builds a websocket URL that includes the dashboard token', () => {
    expect(dashboardWebSocketUrl('jwt-token', '/api/v1')).toContain('/api/v1/ws/dashboard?token=jwt-token')
  })

  it('connects automatically and reports connected status', async () => {
    render(<StatusProbe />)
    expect(screen.getByText('connecting')).toBeInTheDocument()

    act(() => {
      MockWebSocket.instances[0]?.open()
    })

    expect(await screen.findByText('connected')).toBeInTheDocument()
    expect(MockWebSocket.instances).toHaveLength(1)
  })

  it('updates lastEvent from websocket messages and ignores duplicates', async () => {
    render(<StatusProbe />)
    act(() => {
      MockWebSocket.instances[0]?.open()
    })
    await screen.findByText('connected')

    const event = {
      id: 'evt-1',
      type: 'agent_updated',
      timestamp: '2026-09-07T14:00:00Z',
      payload: { reason: 'check_in', agent_id: 'agent-1' },
    }

    act(() => {
      MockWebSocket.instances[0]?.emit(event)
      MockWebSocket.instances[0]?.emit(event)
    })

    expect(screen.getByTestId('event-id')).toHaveTextContent('evt-1')
    expect(screen.getByTestId('event-type')).toHaveTextContent('agent_updated')
  })

  it('reconnects with exponential backoff after a disconnect', async () => {
    vi.useFakeTimers()
    render(<StatusProbe />)

    act(() => {
      MockWebSocket.instances[0]?.open()
    })
    expect(screen.getByText('connected')).toBeInTheDocument()

    act(() => {
      MockWebSocket.instances[0]?.close(1006)
    })
    expect(screen.getByText('disconnected')).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(INITIAL_RECONNECT_MS)
    })

    expect(MockWebSocket.instances).toHaveLength(2)
    expect(screen.getByText('connecting')).toBeInTheDocument()

    act(() => {
      MockWebSocket.instances[1]?.open()
    })
    expect(screen.getByText('connected')).toBeInTheDocument()
  })

  it('refreshes live data when a matching event arrives', async () => {
    const fetcher = vi.fn(async () => 'initial')

    render(
      <DashboardSocketProvider>
        <ProviderStatusProbe />
        <LiveDataProbe fetcher={fetcher} />
      </DashboardSocketProvider>,
    )

    act(() => {
      MockWebSocket.instances[0]?.open()
    })
    expect(await screen.findByTestId('live-data')).toHaveTextContent('initial')
    fetcher.mockResolvedValue('updated')

    act(() => {
      MockWebSocket.instances[0]?.emit({
        id: 'evt-2',
        type: 'agent_updated',
        timestamp: '2026-09-07T14:01:00Z',
        payload: { reason: 'report', agent_id: 'agent-1' },
      })
    })

    await waitFor(() => {
      expect(screen.getByTestId('live-data')).toHaveTextContent('updated')
    })
  })

  it('keeps polling while the websocket is connected when keepPolling is set', async () => {
    const setIntervalSpy = vi.spyOn(window, 'setInterval')
    const fetcher = vi.fn(async () => 'tick')

    render(
      <DashboardSocketProvider>
        <LiveDataProbe fetcher={fetcher} keepPolling />
      </DashboardSocketProvider>,
    )

    act(() => {
      MockWebSocket.instances[0]?.open()
    })
    expect(await screen.findByTestId('live-data')).toHaveTextContent('tick')
    expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), REFRESH_INTERVAL_MS)
    setIntervalSpy.mockRestore()
  })

  it('refreshes live data after alert_updated', async () => {
    const fetcher = vi.fn(async () => 'initial')

    render(
      <DashboardSocketProvider>
        <LiveDataProbe fetcher={fetcher} />
      </DashboardSocketProvider>,
    )

    act(() => {
      MockWebSocket.instances[0]?.open()
    })
    expect(await screen.findByTestId('live-data')).toHaveTextContent('initial')
    fetcher.mockResolvedValue('from-alert')

    act(() => {
      MockWebSocket.instances[0]?.emit({
        id: 'evt-alert',
        type: 'alert_updated',
        timestamp: '2026-09-07T14:02:00Z',
        payload: { reason: 'threshold' },
      })
    })

    await waitFor(() => {
      expect(screen.getByTestId('live-data')).toHaveTextContent('from-alert')
    })
  })
})
