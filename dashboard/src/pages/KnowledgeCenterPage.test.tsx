import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { KnowledgeCenterPage } from './KnowledgeCenterPage'

vi.mock('../api/dashboard', () => ({
  getKnowledge: vi.fn(),
  exportKnowledge: vi.fn(),
}))

import { getKnowledge } from '../api/dashboard'

describe('Knowledge Center', () => {
  beforeEach(() => {
    vi.mocked(getKnowledge).mockResolvedValue({
      generated_at: '2026-09-21T00:00:00Z',
      count: 1,
      items: [{ kind: 'incident', title: 'CPU high', timestamp: '2026-09-21T00:00:00Z', details: {} }],
    })
  })

  it('renders timeline items', async () => {
    render(<KnowledgeCenterPage />)
    expect(await screen.findByRole('heading', { name: 'Knowledge Center' })).toBeInTheDocument()
    expect(screen.getByLabelText('Knowledge timeline')).toBeInTheDocument()
    expect(screen.getByText('CPU high')).toBeInTheDocument()
  })
})
