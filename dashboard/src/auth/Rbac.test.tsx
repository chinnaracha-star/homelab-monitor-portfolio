import { render, screen } from '@testing-library/react'
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { AuthUser } from './api'
import { AuthContext, type AuthContextValue } from './AuthContext'
import { can } from './permissions'
import { PermissionRoute } from './PermissionRoute'
import { ProtectedRoute } from './ProtectedRoute'
import { Navbar } from '../components/Navbar'
import { Sidebar } from '../components/Sidebar'

const admin: AuthUser = {
  id: 'user-admin',
  username: 'admin',
  full_name: 'Administrator',
  role: 'admin',
  is_active: true,
}

const operator: AuthUser = {
  id: 'user-operator',
  username: 'operator',
  full_name: 'Operator',
  role: 'operator',
  is_active: true,
}

const viewer: AuthUser = {
  id: 'user-viewer',
  username: 'viewer',
  full_name: 'Viewer',
  role: 'viewer',
  is_active: true,
}

function authValue(user: AuthUser): AuthContextValue {
  return {
    user,
    loading: false,
    login: async () => undefined,
    logout: () => undefined,
  }
}

function renderWithUser(user: AuthUser, initialEntry: string) {
  return render(
    <AuthContext.Provider value={authValue(user)}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/login" element={<p>Sign in</p>} />
          <Route element={<ProtectedRoute />}>
            <Route
              element={
                <section>
                  <Navbar onToggleSidebar={() => undefined} sidebarOpen />
                  <Sidebar open onNavigate={() => undefined} />
                  <Outlet />
                </section>
              }
            >
              <Route path="/dashboard" element={<p>Dashboard home</p>} />
              <Route path="/alerts" element={<p>Alerts home</p>} />
              <Route element={<PermissionRoute permission="users" />}>
                <Route path="/users" element={<h1>Users</h1>} />
              </Route>
              <Route element={<PermissionRoute permission="settings" />}>
                <Route path="/settings" element={<h1>Settings</h1>} />
              </Route>
              <Route element={<PermissionRoute permission="developer" />}>
                <Route path="/developer" element={<h1>Mission Control</h1>} />
              </Route>
            </Route>
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('role-based access control', () => {
  it('grants permissions from a single authorization helper', () => {
    expect(can('admin', 'users')).toBe(true)
    expect(can('admin', 'settings')).toBe(true)
    expect(can('operator', 'alerts')).toBe(true)
    expect(can('operator', 'users')).toBe(false)
    expect(can('viewer', 'dashboard')).toBe(true)
    expect(can('viewer', 'settings')).toBe(false)
    expect(can('viewer', 'groups')).toBe(true)
    expect(can('operator', 'manage_groups')).toBe(true)
    expect(can('viewer', 'manage_groups')).toBe(false)
    expect(can('viewer', 'notifications')).toBe(true)
    expect(can('operator', 'send_notifications')).toBe(true)
    expect(can('viewer', 'send_notifications')).toBe(false)
    expect(can('viewer', 'acknowledge_alerts')).toBe(false)
    expect(can('admin', 'manage_alert_rules')).toBe(true)
    expect(can('operator', 'alert_rules')).toBe(true)
    expect(can('operator', 'manage_alert_rules')).toBe(false)
    expect(can('viewer', 'alert_rules')).toBe(true)
    expect(can('viewer', 'infrastructure')).toBe(true)
    expect(can('operator', 'infrastructure')).toBe(true)
    expect(can('viewer', 'photo_services')).toBe(true)
    expect(can('operator', 'photo_services')).toBe(true)
    expect(can('viewer', 'backup')).toBe(true)
    expect(can('operator', 'backup')).toBe(true)
    expect(can('viewer', 'analytics')).toBe(true)
    expect(can('operator', 'analytics')).toBe(true)
    expect(can('admin', 'analytics')).toBe(true)
    expect(can('admin', 'developer')).toBe(true)
    expect(can('operator', 'developer')).toBe(false)
    expect(can('viewer', 'developer')).toBe(false)
    expect(can('admin', 'operations')).toBe(true)
    expect(can('operator', 'operations')).toBe(true)
    expect(can('viewer', 'operations')).toBe(false)
  })

  it('shows every navigation item for an admin', () => {
    renderWithUser(admin, '/dashboard')
    expect(screen.getAllByRole('link', { name: 'Overview' }).length).toBeGreaterThanOrEqual(2)
    expect(screen.getByLabelText('Analytics')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Trends' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Capacity Planning' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'AI Insights' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Predictive Alerting' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Agents' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Groups' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Infrastructure' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Photo Services' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Photo Monitor' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Backup' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Alerts' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Alert Timeline' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Incidents' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Notification Center' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Alert Rules' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Notifications' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Users' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Settings' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Mission Control' })).toBeInTheDocument()
    expect(screen.getByLabelText('Developer')).toBeInTheDocument()
    expect(screen.getByLabelText('Role admin')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Logout' })).toBeInTheDocument()
  })

  it('hides Users and Settings for an operator', () => {
    renderWithUser(operator, '/dashboard')
    expect(screen.getAllByRole('link', { name: 'Overview' }).length).toBeGreaterThanOrEqual(2)
    expect(screen.getByRole('link', { name: 'Trends' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Capacity Planning' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'AI Insights' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Groups' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Infrastructure' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Photo Services' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Photo Monitor' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Backup' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Alerts' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Alert Timeline' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Incidents' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Notification Center' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Alert Rules' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Notifications' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Users' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Settings' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Mission Control' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Production Health' })).toBeInTheDocument()
    expect(screen.getByLabelText('Role operator')).toBeInTheDocument()
  })

  it('hides Users and Settings for a viewer', () => {
    renderWithUser(viewer, '/dashboard')
    expect(screen.getByRole('link', { name: 'Agents' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Trends' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Capacity Planning' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'AI Insights' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Predictive Alerting' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Groups' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Infrastructure' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Photo Services' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Photo Monitor' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Backup' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Alerts' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Alert Timeline' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Incidents' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Notification Center' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Alert Rules' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Notifications' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Users' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Settings' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Mission Control' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Production Health' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Role viewer')).toBeInTheDocument()
  })

  it('blocks operators from the users route', async () => {
    renderWithUser(operator, '/users')
    expect(await screen.findByRole('heading', { name: 'Permission denied' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Users' })).not.toBeInTheDocument()
  })

  it('blocks operators from mission control', async () => {
    renderWithUser(operator, '/developer')
    expect(await screen.findByRole('heading', { name: 'Permission denied' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Mission Control' })).not.toBeInTheDocument()
  })

  it('blocks viewers from settings and allows the dashboard', () => {
    const settings = renderWithUser(viewer, '/settings')
    expect(screen.getByRole('heading', { name: 'Permission denied' })).toBeInTheDocument()
    settings.unmount()

    renderWithUser(viewer, '/dashboard')
    expect(screen.getByText('Dashboard home')).toBeInTheDocument()
  })

  it('allows admins to open protected administration routes', () => {
    renderWithUser(admin, '/users')
    expect(screen.getByRole('heading', { name: 'Users' })).toBeInTheDocument()
  })
})
