import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthContext'
import type { GroupDetail, GroupSummary } from '../types/dashboard'
import { GroupDetailPage } from './GroupDetailPage'

vi.mock('../api/dashboard', () => ({
  getGroup: vi.fn(),
  getGroups: vi.fn(),
  getAgents: vi.fn(),
  updateGroup: vi.fn(),
  deleteGroup: vi.fn(),
  assignAgentsToGroup: vi.fn(),
  removeAgentFromGroup: vi.fn(),
}))

import { deleteGroup, getAgents, getGroup, getGroups, removeAgentFromGroup } from '../api/dashboard'

const mockedGetGroup = vi.mocked(getGroup)
const mockedGetGroups = vi.mocked(getGroups)
const mockedGetAgents = vi.mocked(getAgents)
const mockedDeleteGroup = vi.mocked(deleteGroup)
const mockedRemove = vi.mocked(removeAgentFromGroup)

const group: GroupDetail = {
  id: 'group-rack',
  name: 'Rack A',
  description: 'Primary rack',
  agents: 1,
  online: 1,
  agent_ids: ['agent-one'],
  created_at: '2026-09-07T00:00:00Z',
  updated_at: '2026-09-07T00:00:00Z',
  members: [
    {
      id: 'agent-one',
      name: 'one',
      hostname: 'one.local',
      version: '0.1.0',
      status: 'online',
      last_seen_at: '2026-09-07T12:00:00Z',
    },
  ],
}

const groups: GroupSummary[] = [
  {
    id: group.id,
    name: group.name,
    description: group.description,
    agents: group.agents,
    online: group.online,
    agent_ids: group.agent_ids,
  },
]

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
      <MemoryRouter initialEntries={['/groups/group-rack']}>
        <Routes>
          <Route path="/groups/:groupId" element={<GroupDetailPage />} />
          <Route path="/groups" element={<p>Groups list</p>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('Group detail page', () => {
  beforeEach(() => {
    mockedGetGroup.mockReset()
    mockedGetGroups.mockReset()
    mockedGetAgents.mockReset()
    mockedDeleteGroup.mockReset()
    mockedRemove.mockReset()
    mockedGetGroup.mockResolvedValue(group)
    mockedGetGroups.mockResolvedValue(groups)
    mockedGetAgents.mockResolvedValue(group.members)
  })

  it('shows group members and summary', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Rack A' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'one' })).toHaveAttribute('href', '/agents/agent-one')
    expect(screen.getByRole('button', { name: 'Assign agents' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit group' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Delete group' })).toBeInTheDocument()
  })

  it('removes an agent after confirmation', async () => {
    const user = userEvent.setup()
    mockedRemove.mockResolvedValue({ ...group, agents: 0, online: 0, agent_ids: [], members: [] })
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Remove from group' }))
    expect(screen.getByRole('heading', { name: 'Remove agent' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Remove agent' }))
    await waitFor(() => expect(mockedRemove).toHaveBeenCalledWith('group-rack', 'agent-one'))
  })

  it('deletes a group and returns to the list', async () => {
    const user = userEvent.setup()
    mockedDeleteGroup.mockResolvedValue()
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Delete group' }))
    await user.click(screen.getByRole('button', { name: 'Confirm delete' }))
    await waitFor(() => expect(mockedDeleteGroup).toHaveBeenCalledWith('group-rack'))
    expect(await screen.findByText('Groups list')).toBeInTheDocument()
  })
})
