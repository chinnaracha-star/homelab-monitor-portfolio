import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { RemoteAccess } from '../types/dashboard'
import { RemoteAccessCard } from './RemoteAccessCard'

const connected: RemoteAccess = {
  enabled: true,
  provider: 'tailscale',
  hostname: 'monitor.example.com',
  tailnet_ip: '100.64.0.12',
  https: true,
  serve_enabled: true,
  funnel_enabled: false,
  public: false,
  status: 'connected',
}

describe('Remote Access card', () => {
  it('renders a connected Tailscale snapshot', () => {
    render(<RemoteAccessCard access={connected} />)
    expect(screen.getByRole('heading', { name: 'Remote Access' })).toBeInTheDocument()
    expect(screen.getByLabelText('Connection Connected')).toBeInTheDocument()
    expect(screen.getByLabelText('Hostname monitor.example.com')).toBeInTheDocument()
    expect(screen.getByLabelText('Dashboard Public URL https://monitor.example.com')).toBeInTheDocument()
    expect(screen.getByLabelText('HTTPS Enabled')).toBeInTheDocument()
    expect(screen.getByLabelText('Serve Enabled')).toBeInTheDocument()
    expect(screen.getByLabelText('Funnel Disabled')).toBeInTheDocument()
    expect(screen.getByLabelText('Public Exposure No')).toBeInTheDocument()
    expect(screen.getByLabelText('Tailnet IP 100.64.0.12')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Copy URL' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Remote access status').className).toMatch(/remoteAccessGrid/)
  })

  it('renders disconnected and unknown states', () => {
    const { rerender } = render(
      <RemoteAccessCard access={{ ...connected, status: 'disconnected', enabled: false }} />,
    )
    expect(screen.getByLabelText('Connection Disconnected')).toBeInTheDocument()
    rerender(<RemoteAccessCard access={{ ...connected, status: 'unknown', enabled: false }} />)
    expect(screen.getByLabelText('Connection Unknown')).toBeInTheDocument()
    rerender(
      <RemoteAccessCard
        access={{
          ...connected,
          status: 'not_installed',
          hostname: null,
          tailnet_ip: null,
          https: false,
          serve_enabled: false,
        }}
      />,
    )
    expect(screen.getByLabelText('Connection Disconnected')).toBeInTheDocument()
    expect(screen.getByLabelText('Hostname —')).toBeInTheDocument()
  })

  it('copies and opens the Tailnet URL from Settings actions', async () => {
    const user = userEvent.setup()
    const onCopy = vi.fn()
    const onOpen = vi.fn()
    render(<RemoteAccessCard access={connected} showActions onCopy={onCopy} onOpen={onOpen} />)
    await user.click(screen.getByRole('button', { name: 'Copy URL' }))
    await user.click(screen.getByRole('button', { name: 'Open Dashboard' }))
    expect(onCopy).toHaveBeenCalledWith('https://monitor.example.com')
    expect(onOpen).toHaveBeenCalledWith('https://monitor.example.com')
  })

  it('disables copy and open when no hostname is available', () => {
    render(
      <RemoteAccessCard
        access={{ ...connected, hostname: null }}
        showActions
        onCopy={vi.fn()}
        onOpen={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: 'Copy URL' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Open Dashboard' })).toBeDisabled()
  })
})
