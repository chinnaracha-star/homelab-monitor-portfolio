import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthContext'
import type { AuthUser } from '../auth/api'
import type { AgentSummary, GroupSummary } from '../types/dashboard'
import { GroupsPage } from './GroupsPage'

vi.mock('../api/dashboard', () => ({
  getGroups: vi.fn(),
  getAgents: vi.fn(),
  createGroup: vi.fn(),
  assignAgentsToGroup: vi.fn(),
}))

import { assignAgentsToGroup, createGroup, getAgents, getGroups } from '../api/dashboard'

const mockedGetGroups = vi.mocked(getGroups)
const mockedGetAgents = vi.mocked(getAgents)
const mockedCreateGroup = vi.mocked(createGroup)
const mockedAssign = vi.mocked(assignAgentsToGroup)

const groups: GroupSummary[] = [
  {
    id: 'group-rack',
    name: 'Rack A',
    description: 'Primary rack',
    agents: 1,
    online: 1,
    agent_ids: ['agent-one'],
  },
]

const agents: AgentSummary[] = [
  {
    id: 'agent-one',
    name: 'one',
    hostname: 'one.local',
    version: '0.1.0',
    status: 'online',
    last_seen_at: '2026-09-07T12:00:00Z',
  },
  {
    id: 'agent-two',
    name: 'two',
    hostname: 'two.local',
    version: '0.1.0',
    status: 'offline',
    last_seen_at: null,
  },
]

const admin: AuthUser = {
  id: 'user-admin',
  username: 'admin',
  full_name: 'Administrator',
  role: 'admin',
  is_active: true,
}

const viewer: AuthUser = {
  id: 'user-viewer',
  username: 'viewer',
  full_name: 'Viewer',
  role: 'viewer',
  is_active: true,
}

function renderPage(user: AuthUser = admin) {
  return render(
    <AuthContext.Provider
      value={{
        user,
        loading: false,
        login: async () => undefined,
        logout: () => undefined,
      }}
    >
      <MemoryRouter>
        <GroupsPage />
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('Groups page', () => {
  beforeEach(() => {
    mockedGetGroups.mockReset()
    mockedGetAgents.mockReset()
    mockedCreateGroup.mockReset()
    mockedAssign.mockReset()
    mockedGetGroups.mockResolvedValue(groups)
    mockedGetAgents.mockResolvedValue(agents)
  })

  it('renders group cards', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Groups' })).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'Rack A' })).toHaveAttribute('href', '/groups/group-rack')
    expect(screen.getByRole('button', { name: 'Create group' })).toBeInTheDocument()
  })

  it('hides write actions for viewers', async () => {
    renderPage(viewer)
    await screen.findByRole('link', { name: 'Rack A' })
    expect(screen.queryByRole('button', { name: 'Create group' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Assign agents' })).not.toBeInTheDocument()
  })

  it('creates a group from the dialog', async () => {
    const user = userEvent.setup()
    mockedCreateGroup.mockResolvedValue({
      ...groups[0],
      id: 'group-new',
      name: 'Rack B',
      description: 'Second',
      members: [],
      created_at: '2026-09-07T00:00:00Z',
      updated_at: '2026-09-07T00:00:00Z',
    })
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Create group' }))
    await user.type(screen.getByLabelText('Name'), 'Rack B')
    await user.type(screen.getByLabelText('Description'), 'Second')
    await user.click(screen.getAllByRole('button', { name: 'Create group' })[1])
    await waitFor(() => expect(mockedCreateGroup).toHaveBeenCalled())
    expect(mockedCreateGroup).toHaveBeenCalledWith({ name: 'Rack B', description: 'Second' })
  })

  it('searches groups by name', async () => {
    const user = userEvent.setup()
    mockedGetGroups.mockResolvedValue([
      ...groups,
      {
        id: 'group-lab',
        name: 'Lab',
        description: 'Test bench',
        agents: 0,
        online: 0,
        agent_ids: [],
      },
    ])
    renderPage()
    await screen.findByRole('link', { name: 'Rack A' })
    await user.type(screen.getByLabelText('Search groups'), 'Lab')
    expect(screen.getByRole('link', { name: 'Lab' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Rack A' })).not.toBeInTheDocument()
  })

  it('shows a loading state before groups arrive', async () => {
    mockedGetGroups.mockReturnValue(new Promise(() => undefined))
    renderPage()
    expect(await screen.findByLabelText('Loading overview')).toBeInTheDocument()
  })

  it('shows an empty state when there are no groups', async () => {
    mockedGetGroups.mockResolvedValue([])
    renderPage()
    expect(await screen.findByText('No groups yet.')).toBeInTheDocument()
  })

  it('shows an error state when the groups API fails', async () => {
    mockedGetGroups.mockRejectedValue(new Error('offline'))
    renderPage()
    expect(await screen.findByText('Groups API failed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry section' })).toBeInTheDocument()
  })

  it('opens the bulk assign dialog', async () => {
    const user = userEvent.setup()
    mockedAssign.mockResolvedValue({
      ...groups[0],
      members: [],
      created_at: '2026-09-07T00:00:00Z',
      updated_at: '2026-09-07T00:00:00Z',
    })
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Assign agents' }))
    expect(screen.getByRole('heading', { name: 'Assign agents' })).toBeInTheDocument()
    expect(screen.getByLabelText('two')).toBeInTheDocument()
    await user.click(screen.getByLabelText('two'))
    await user.click(screen.getByRole('button', { name: 'Assign' }))
    expect(screen.getByRole('heading', { name: 'Confirm assignment' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Confirm assign' }))
    await waitFor(() => expect(mockedAssign).toHaveBeenCalledWith('group-rack', ['agent-two']))
  })
})
