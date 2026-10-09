import {
  createContext,
  createElement,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { getAccessToken } from '../auth/storage'
import { REFRESH_INTERVAL_MS } from '../constants'
import { usePolling, type UsePollingResult } from './usePolling'

export const SOCKET_HEARTBEAT_MS = 20_000
export const INITIAL_RECONNECT_MS = 1_000
export const MAX_RECONNECT_MS = 30_000
const SEEN_EVENT_LIMIT = 200

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected'
export type DashboardEventType =
  | 'overview_updated'
  | 'agent_updated'
  | 'alert_updated'
  | 'connection'

export interface DashboardEventPayload {
  reason: string
  agent_id?: string
  status?: string
}

export interface DashboardEvent {
  id: string
  type: DashboardEventType
  timestamp: string
  payload: DashboardEventPayload
}

export interface DashboardSocketValue {
  status: ConnectionStatus
  lastEvent: DashboardEvent | null
}

export const DashboardSocketContext = createContext<DashboardSocketValue | undefined>(undefined)

export function dashboardWebSocketUrl(token: string, apiBaseUrl = import.meta.env.VITE_API_BASE_URL): string {
  const pathBase = apiBaseUrl.replace(/\/+$/, '')
  if (pathBase.startsWith('http://') || pathBase.startsWith('https://')) {
    const url = new URL(`${pathBase}/ws/dashboard`)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    url.searchParams.set('token', token)
    return url.toString()
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${pathBase}/ws/dashboard?token=${encodeURIComponent(token)}`
}

function isDashboardEvent(value: unknown): value is DashboardEvent {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const event = value as DashboardEvent
  return (
    typeof event.id === 'string' &&
    typeof event.type === 'string' &&
    typeof event.timestamp === 'string' &&
    typeof event.payload === 'object' &&
    event.payload !== null
  )
}

export function useDashboardSocket(): DashboardSocketValue {
  const [status, setStatus] = useState<ConnectionStatus>(() =>
    getAccessToken() ? 'connecting' : 'disconnected',
  )
  const [lastEvent, setLastEvent] = useState<DashboardEvent | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const reconnectAttemptRef = useRef(0)
  const reconnectTimerRef = useRef<number | null>(null)
  const heartbeatTimerRef = useRef<number | null>(null)
  const seenIdsRef = useRef<Set<string>>(new Set())
  const stoppedRef = useRef(false)

  useEffect(() => {
    stoppedRef.current = false

    function clearTimers() {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      if (heartbeatTimerRef.current !== null) {
        window.clearInterval(heartbeatTimerRef.current)
        heartbeatTimerRef.current = null
      }
    }

    function rememberEvent(event: DashboardEvent) {
      const seen = seenIdsRef.current
      if (seen.has(event.id)) {
        return false
      }
      seen.add(event.id)
      if (seen.size > SEEN_EVENT_LIMIT) {
        const oldest = seen.values().next().value
        if (oldest) {
          seen.delete(oldest)
        }
      }
      return true
    }

    function connect() {
      if (stoppedRef.current) {
        return
      }

      const token = getAccessToken()
      if (!token) {
        setStatus('disconnected')
        return
      }

      clearTimers()
      const previous = socketRef.current
      socketRef.current = null
      previous?.close()
      setStatus('connecting')

      const socket = new WebSocket(dashboardWebSocketUrl(token))
      socketRef.current = socket

      socket.onopen = () => {
        reconnectAttemptRef.current = 0
        setStatus('connected')
        heartbeatTimerRef.current = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send('ping')
          }
        }, SOCKET_HEARTBEAT_MS)
      }

      socket.onmessage = (message) => {
        try {
          const parsed: unknown = JSON.parse(String(message.data))
          if (!isDashboardEvent(parsed) || !rememberEvent(parsed)) {
            return
          }
          if (parsed.type === 'connection') {
            if (parsed.payload.status === 'connected') {
              setStatus('connected')
            }
            return
          }
          setLastEvent(parsed)
        } catch {
          return
        }
      }

      socket.onerror = () => {
        socket.close()
      }

      socket.onclose = () => {
        if (heartbeatTimerRef.current !== null) {
          window.clearInterval(heartbeatTimerRef.current)
          heartbeatTimerRef.current = null
        }
        if (socketRef.current !== socket) {
          return
        }
        socketRef.current = null
        if (stoppedRef.current || !getAccessToken()) {
          setStatus('disconnected')
          return
        }
        setStatus('disconnected')
        const delay = Math.min(
          INITIAL_RECONNECT_MS * 2 ** reconnectAttemptRef.current,
          MAX_RECONNECT_MS,
        )
        reconnectAttemptRef.current += 1
        reconnectTimerRef.current = window.setTimeout(() => {
          connect()
        }, delay)
      }
    }

    if (getAccessToken()) {
      connect()
    }

    return () => {
      stoppedRef.current = true
      clearTimers()
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [])

  return useMemo(() => ({ status, lastEvent }), [lastEvent, status])
}

export function DashboardSocketProvider({ children }: { children: ReactNode }) {
  const value = useDashboardSocket()
  return createElement(DashboardSocketContext.Provider, { value }, children)
}

export function useDashboardConnection(): DashboardSocketValue {
  const context = useContext(DashboardSocketContext)
  if (!context) {
    throw new Error('useDashboardConnection must be used within DashboardSocketProvider')
  }
  return context
}

export function useOptionalDashboardConnection(): DashboardSocketValue | undefined {
  return useContext(DashboardSocketContext)
}

export function useLivePolling<T>(
  fetcher: () => Promise<T>,
  eventTypes: readonly DashboardEventType[],
  options: {
    enabled?: boolean
    agentId?: string
    resetKey?: string | number
    keepPolling?: boolean
    intervalMs?: number
  } = {},
): UsePollingResult<T> {
  const { enabled = true, agentId, resetKey, keepPolling = false, intervalMs: intervalOverride } = options
  const connection = useOptionalDashboardConnection()
  const status = connection?.status ?? 'disconnected'
  const lastEvent = connection?.lastEvent ?? null
  const intervalMs =
    intervalOverride ?? (keepPolling || status !== 'connected' ? REFRESH_INTERVAL_MS : 0)
  const polling = usePolling(fetcher, { enabled, intervalMs, resetKey })
  const retry = polling.retry
  const eventTypesRef = useRef(eventTypes)

  useEffect(() => {
    eventTypesRef.current = eventTypes
  }, [eventTypes])

  useEffect(() => {
    if (!lastEvent || lastEvent.type === 'connection') {
      return
    }
    if (!eventTypesRef.current.includes(lastEvent.type)) {
      return
    }
    if (agentId && lastEvent.payload.agent_id && lastEvent.payload.agent_id !== agentId) {
      return
    }
    retry()
  }, [agentId, lastEvent, retry])

  return polling
}
