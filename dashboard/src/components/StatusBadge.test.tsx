import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusBadge } from './StatusBadge'
import { RelativeTime } from './RelativeTime'

describe('StatusBadge', () => {
  it('renders online, offline, and unknown agent badges', () => {
    const { rerender } = render(<StatusBadge status="online" />)
    expect(screen.getByLabelText('Status Online')).toBeInTheDocument()
    rerender(<StatusBadge status="offline" />)
    expect(screen.getByLabelText('Status Offline')).toBeInTheDocument()
    rerender(<StatusBadge status="unknown" />)
    expect(screen.getByLabelText('Status Unknown')).toBeInTheDocument()
  })

  it('renders systemd running and stopped badges', () => {
    const { rerender } = render(<StatusBadge kind="service" status="running" />)
    expect(screen.getByLabelText('Status Running')).toBeInTheDocument()
    rerender(<StatusBadge kind="service" status="stopped" />)
    expect(screen.getByLabelText('Status Stopped')).toBeInTheDocument()
  })

  it('renders ACTIVE and RECOVERED lifecycle badges', () => {
    const { rerender } = render(<StatusBadge kind="lifecycle" status="active" />)
    expect(screen.getByLabelText('Status ACTIVE')).toBeInTheDocument()
    rerender(<StatusBadge kind="lifecycle" status="recovered" />)
    expect(screen.getByLabelText('Status RECOVERED')).toBeInTheDocument()
  })
})

describe('RelativeTime', () => {
  it('shows relative time with a Thai tooltip', () => {
    render(<RelativeTime now={Date.parse('2026-09-08T08:35:21Z')} value="2026-09-08T08:35:09Z" />)
    const time = screen.getByText('12 seconds ago')
    expect(time).toHaveAttribute('title', '8 กันยายน 2569\n15:35:09 น.')
  })
})
