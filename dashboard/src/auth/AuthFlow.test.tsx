import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from './AuthProvider'
import { ProtectedRoute } from './ProtectedRoute'
import { ACCESS_TOKEN_KEY } from './storage'
import { LoginPage } from '../pages/LoginPage'
import { Navbar } from '../components/Navbar'

vi.mock('./api', () => ({
  login: vi.fn(),
  getCurrentUser: vi.fn(),
}))

import { getCurrentUser, login } from './api'

const mockedLogin = vi.mocked(login)
const mockedGetCurrentUser = vi.mocked(getCurrentUser)

const viewer = {
  id: 'user-1',
  username: 'admin',
  full_name: 'Administrator',
  role: 'admin',
  is_active: true,
}

function renderAuthApp(initialEntry: string) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route
              path="/dashboard"
              element={
                <section>
                  <Navbar onToggleSidebar={() => undefined} sidebarOpen={false} />
                  <p>Dashboard home</p>
                </section>
              }
            />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

describe('dashboard authentication', () => {
  beforeEach(() => {
    window.localStorage.clear()
    mockedLogin.mockReset()
    mockedGetCurrentUser.mockReset()
  })

  it('renders the login page', () => {
    renderAuthApp('/login')
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.getByLabelText('Username')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Login' })).toBeInTheDocument()
  })

  it('redirects unauthenticated users from protected routes to login', async () => {
    renderAuthApp('/dashboard')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.queryByText('Dashboard home')).not.toBeInTheDocument()
  })

  it('stores the JWT and redirects to the dashboard after login', async () => {
    const user = userEvent.setup()
    mockedLogin.mockResolvedValue({
      access_token: 'jwt-token',
      token_type: 'bearer',
      expires_in: 3600,
    })
    mockedGetCurrentUser.mockResolvedValue(viewer)

    renderAuthApp('/login')
    await user.type(screen.getByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'admin123')
    await user.click(screen.getByRole('button', { name: 'Login' }))

    expect(await screen.findByText('Dashboard home')).toBeInTheDocument()
    expect(window.localStorage.getItem(ACCESS_TOKEN_KEY)).toBe('jwt-token')
  })

  it('logs out, removes the token, and returns to login', async () => {
    const user = userEvent.setup()
    window.localStorage.setItem(ACCESS_TOKEN_KEY, 'jwt-token')
    mockedGetCurrentUser.mockResolvedValue(viewer)

    renderAuthApp('/dashboard')
    expect(await screen.findByText('Dashboard home')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Logout' }))

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(window.localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull()
  })
})
