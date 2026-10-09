import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthContext'
import type { AuthUser } from '../auth/api'
import type { AgentSummary, AlertRule, GroupSummary } from '../types/dashboard'
import { AlertRulesPage } from './AlertRulesPage'

vi.mock('../api/dashboard', () => ({
  getAlertRules: vi.fn(),
  createAlertRule: vi.fn(),
  updateAlertRule: vi.fn(),
  setAlertRuleEnabled: vi.fn(),
  deleteAlertRule: vi.fn(),
  getGroups: vi.fn(),
  getAgents: vi.fn(),
}))

import {
  createAlertRule,
  deleteAlertRule,
  getAgents,
  getAlertRules,
  getGroups,
  setAlertRuleEnabled,
  updateAlertRule,
} from '../api/dashboard'

const mockedList = vi.mocked(getAlertRules)
const mockedCreate = vi.mocked(createAlertRule)
const mockedUpdate = vi.mocked(updateAlertRule)
const mockedEnable = vi.mocked(setAlertRuleEnabled)
const mockedDelete = vi.mocked(deleteAlertRule)
const mockedGroups = vi.mocked(getGroups)
const mockedAgents = vi.mocked(getAgents)

const cpuRule: AlertRule = {
  id: 'rule-cpu',
  name: 'CPU high',
  description: 'Busy hosts',
  metric: 'cpu_percent',
  operator: '>',
  threshold: 90,
  severity: 'critical',
  enabled: true,
  cooldown_seconds: 60,
  applies_to: 'all',
  group_id: null,
  agent_id: null,
  preview: 'If CPU is greater than 90% create Critical alert.',
  created_at: '2026-09-08T00:00:00Z',
  updated_at: '2026-09-08T00:00:00Z',
}

const memoryRule: AlertRule = {
  ...cpuRule,
  id: 'rule-memory',
  name: 'Memory high',
  metric: 'memory_percent',
  severity: 'high',
  enabled: false,
  cooldown_seconds: 0,
  preview: 'If memory is greater than 90% create High alert.',
}

const groups: GroupSummary[] = [
  {
    id: 'group-rack',
    name: 'Rack A',
    description: '',
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
    last_seen_at: '2026-09-08T00:00:00Z',
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
      <AlertRulesPage />
    </AuthContext.Provider>,
  )
}

describe('Alert Rules page', () => {
  beforeEach(() => {
    mockedList.mockReset()
    mockedCreate.mockReset()
    mockedUpdate.mockReset()
    mockedEnable.mockReset()
    mockedDelete.mockReset()
    mockedGroups.mockReset()
    mockedAgents.mockReset()
    mockedList.mockResolvedValue([cpuRule, memoryRule])
    mockedGroups.mockResolvedValue(groups)
    mockedAgents.mockResolvedValue(agents)
    mockedCreate.mockResolvedValue(cpuRule)
    mockedUpdate.mockResolvedValue({ ...cpuRule, threshold: 85 })
    mockedEnable.mockResolvedValue({ ...cpuRule, enabled: false })
    mockedDelete.mockResolvedValue(undefined)
  })

  it('lists rules with badges, cooldown, and preview', async () => {
    renderPage()
    const table = await screen.findByRole('table', { name: 'Alert rules' })
    expect(within(table).getByText('CPU high')).toBeInTheDocument()
    expect(within(table).getByText('If CPU is greater than 90% create Critical alert.')).toBeInTheDocument()
    expect(within(table).getByText('1m')).toBeInTheDocument()
    expect(within(table).getByText('critical')).toBeInTheDocument()
    expect(within(table).getByText('cpu percent')).toBeInTheDocument()
  })

  it('creates a rule and shows the preview sentence', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('table', { name: 'Alert rules' })
    await user.click(screen.getByRole('button', { name: 'Create rule' }))
    expect(screen.getByRole('heading', { name: 'Create alert rule' })).toBeInTheDocument()
    expect(
      screen.getAllByText('If CPU is greater than 90% create Critical alert.').length,
    ).toBeGreaterThan(0)
    await user.type(screen.getByLabelText('Name'), 'CPU busy')
    await user.click(screen.getByRole('button', { name: 'Create alert rule' }))
    await waitFor(() => expect(mockedCreate).toHaveBeenCalled())
  })

  it('edits a rule', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('table', { name: 'Alert rules' })
    await user.click(screen.getAllByRole('button', { name: 'Edit' })[0])
    expect(screen.getByRole('heading', { name: 'Edit alert rule' })).toBeInTheDocument()
    await user.clear(screen.getByLabelText('Threshold'))
    await user.type(screen.getByLabelText('Threshold'), '85')
    await user.click(screen.getByRole('button', { name: 'Save rule' }))
    await waitFor(() => expect(mockedUpdate).toHaveBeenCalled())
  })

  it('deletes a rule', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('table', { name: 'Alert rules' })
    await user.click(screen.getAllByRole('button', { name: 'Delete' })[0])
    await user.click(screen.getByRole('button', { name: 'Delete rule' }))
    await waitFor(() => expect(mockedDelete).toHaveBeenCalledWith('rule-cpu'))
  })

  it('enables and disables a rule', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('table', { name: 'Alert rules' })
    await user.click(screen.getByRole('button', { name: 'Disable' }))
    await waitFor(() => expect(mockedEnable).toHaveBeenCalledWith('rule-cpu', false))
    await user.click(screen.getByRole('button', { name: 'Enable' }))
    await waitFor(() => expect(mockedEnable).toHaveBeenCalledWith('rule-memory', true))
  })

  it('filters by metric and searches by name', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('table', { name: 'Alert rules' })
    await user.selectOptions(screen.getByLabelText('Metric'), 'memory_percent')
    expect(screen.getByText('Memory high')).toBeInTheDocument()
    expect(screen.queryByText('CPU high')).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Metric'), 'all')
    await user.type(screen.getByLabelText('Search rules'), 'CPU')
    expect(screen.getByText('CPU high')).toBeInTheDocument()
    expect(screen.queryByText('Memory high')).not.toBeInTheDocument()
  })

  it('hides write actions for viewers', async () => {
    renderPage(viewer)
    await screen.findByText('CPU high')
    expect(screen.queryByRole('button', { name: 'Create rule' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
  })
})
