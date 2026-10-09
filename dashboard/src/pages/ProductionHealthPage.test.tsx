import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ProductionHealthOverview } from '../types/dashboard'
import { ProductionHealthPage } from './ProductionHealthPage'

vi.mock('../api/dashboard', () => ({ getProductionHealthOverview: vi.fn() }))

import { getProductionHealthOverview } from '../api/dashboard'

const overview: ProductionHealthOverview = {
  health: {
    generated_at: '2026-09-09T01:00:00Z',
    score: 82,
    status: 'good',
    checks: [
      {
        component: 'API',
        status: 'healthy',
        last_check: '2026-09-09T01:00:00Z',
        latency_ms: 1.2,
        message: 'API process is responding.',
        warning: null,
        error: null,
        possible_cause: null,
        recommended_action: null,
      },
      {
        component: 'Docker',
        status: 'warning',
        last_check: '2026-09-09T01:00:00Z',
        latency_ms: null,
        message: 'Docker is unavailable.',
        warning: 'Docker is unavailable.',
        error: null,
        possible_cause: 'Docker socket is not exposed.',
        recommended_action: 'Run docker compose ps.',
      },
    ],
  },
  runtime: {
    agent: {
      state: 'running',
      restart_count: 1,
      last_heartbeat: '2026-09-09T01:00:00Z',
      last_report: '2026-09-09T01:00:00Z',
      last_metrics_upload: '2026-09-09T01:00:00Z',
    },
    docker_available: false,
    containers: [],
    telegram: {
      bot_connected: true,
      last_successful_send: null,
      last_failed_send: null,
      failure_reason: null,
      retry_queue: 0,
    },
    tailscale: {
      connected: true,
      tailnet: 'monitor.example.com',
      magic_dns: true,
      connection_type: 'unknown',
      exit_node: null,
      remote_access_url: 'https://monitor.example.com',
      hostname: 'monitor.example.com',
      ip: '100.64.0.10',
      https: true,
    },
  },
  storage: {
    filesystem: '/',
    disk_usage_percent: 40,
    free_space_bytes: 1024,
    database_size_bytes: 512,
    log_size_bytes: 256,
    disk_read_bytes: 100,
    disk_write_bytes: 200,
    io_wait_percent: 0.5,
    status: 'healthy',
  },
  network: {
    lan_ip: '192.168.1.10',
    tailscale_ip: '100.64.0.10',
    gateway: '192.168.1.1',
    internet: 'healthy',
    latency_ms: 12,
    dns: 'healthy',
    upload_bytes: 1000,
    download_bytes: 2000,
    network_errors: 0,
  },
}

describe('Production Health page', () => {
  beforeEach(() => {
    vi.mocked(getProductionHealthOverview).mockResolvedValue(overview)
  })

  it('renders component health, runtime, resources, and diagnostics', async () => {
    render(<ProductionHealthPage />)

    expect(await screen.findByRole('heading', { name: 'Production Health' })).toBeInTheDocument()
    expect(screen.getByLabelText('Production health score 82')).toBeInTheDocument()
    expect(screen.getByLabelText('API healthy')).toBeInTheDocument()
    expect(screen.getByText('Docker socket is not exposed.')).toBeInTheDocument()
    expect(screen.getByText('https://monitor.example.com')).toBeInTheDocument()
    expect(screen.getByText('Docker is unavailable to the API process.')).toBeInTheDocument()
  })
})
