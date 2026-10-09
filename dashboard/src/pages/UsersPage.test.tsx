import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/AuthContext'
import { UsersPage } from './UsersPage'
import type { ManagedUser } from '../types/users'

vi.mock('../api/users', () => ({
  listUsers: vi.fn(),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  resetUserPassword: vi.fn(),
  updateUserStatus: vi.fn(),
  deleteUser: vi.fn(),
}))

import {
  createUser,
  deleteUser,
  listUsers,
  resetUserPassword,
  updateUser,
} from '../api/users'

const mockedListUsers = vi.mocked(listUsers)
const mockedCreateUser = vi.mocked(createUser)
const mockedUpdateUser = vi.mocked(updateUser)
const mockedDeleteUser = vi.mocked(deleteUser)
const mockedResetPassword = vi.mocked(resetUserPassword)

const users: ManagedUser[] = [
  {
    id: 'user-admin',
    username: 'admin',
    full_name: 'Administrator',
    role: 'admin',
    is_active: true,
    created_at: '2026-09-07T00:00:00Z',
    updated_at: '2026-09-07T00:00:00Z',
  },
  {
    id: 'user-operator',
    username: 'operator',
    full_name: 'Operator',
    role: 'operator',
    is_active: true,
    created_at: '2026-09-07T00:00:00Z',
    updated_at: '2026-09-07T00:00:00Z',
  },
  {
    id: 'user-alice',
    username: 'alice',
    full_name: 'Alice Admin',
    role: 'admin',
    is_active: true,
    created_at: '2026-09-07T00:00:00Z',
    updated_at: '2026-09-07T00:00:00Z',
  },
  {
    id: 'user-bob',
    username: 'bob',
    full_name: 'Bob Viewer',
    role: 'viewer',
    is_active: false,
    created_at: '2026-09-07T00:00:00Z',
    updated_at: '2026-09-07T00:00:00Z',
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
      <UsersPage />
    </AuthContext.Provider>,
  )
}

describe('Users page', () => {
  beforeEach(() => {
    mockedListUsers.mockReset()
    mockedCreateUser.mockReset()
    mockedUpdateUser.mockReset()
    mockedDeleteUser.mockReset()
    mockedResetPassword.mockReset()
    mockedListUsers.mockResolvedValue(users)
  })

  it('lists users', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Users' })).toBeInTheDocument()
    expect(await screen.findByRole('table', { name: 'Dashboard users' })).toBeInTheDocument()
    expect(screen.getByText('alice')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create User' })).toBeInTheDocument()
  })

  it('opens the create dialog', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('table', { name: 'Dashboard users' })
    await user.click(screen.getByRole('button', { name: 'Create User' }))
    expect(screen.getByRole('heading', { name: 'Create User' })).toBeInTheDocument()
    expect(screen.getByLabelText('Username')).toBeInTheDocument()
    expect(screen.getByLabelText('Full name')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByLabelText('Role')).toBeInTheDocument()
    expect(screen.getByLabelText('Active')).toBeInTheDocument()
  })

  it('opens the edit dialog', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('alice')
    const editButtons = screen.getAllByRole('button', { name: 'Edit User' })
    await user.click(editButtons[2])
    expect(screen.getByRole('heading', { name: 'Edit User' })).toBeInTheDocument()
    expect(screen.getByLabelText('Full name')).toHaveValue('Alice Admin')
  })

  it('opens the delete confirmation dialog', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('alice')
    const deleteButtons = screen.getAllByRole('button', { name: 'Delete User' })
    await user.click(deleteButtons[2])
    expect(screen.getByRole('heading', { name: 'Delete User' })).toBeInTheDocument()
    expect(screen.getByText(/Delete alice/)).toBeInTheDocument()
  })

  it('filters users by role', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('alice')
    await user.click(screen.getByRole('button', { name: 'viewer' }))
    const table = screen.getByRole('table', { name: 'Dashboard users' })
    expect(within(table).getByText('bob')).toBeInTheDocument()
    expect(within(table).queryByText('alice')).not.toBeInTheDocument()
    expect(within(table).queryByText('operator')).not.toBeInTheDocument()
  })

  it('searches by username and full name', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('alice')
    await user.type(screen.getByLabelText('Search users'), 'Alice')
    const table = screen.getByRole('table', { name: 'Dashboard users' })
    expect(within(table).getByText('alice')).toBeInTheDocument()
    expect(within(table).queryByText('bob')).not.toBeInTheDocument()
    expect(within(table).queryByText('operator')).not.toBeInTheDocument()
  })

  it('creates a user from the dialog', async () => {
    const user = userEvent.setup()
    mockedCreateUser.mockResolvedValue({
      ...users[2],
      id: 'user-new',
      username: 'charlie',
      full_name: 'Charlie',
    })
    renderPage()
    await screen.findByRole('button', { name: 'Create User' })
    await user.click(screen.getByRole('button', { name: 'Create User' }))
    await user.type(screen.getByLabelText('Username'), 'charlie')
    await user.type(screen.getByLabelText('Full name'), 'Charlie')
    await user.type(screen.getByLabelText('Password'), 'password123')
    await user.click(screen.getAllByRole('button', { name: 'Create User' })[1])
    await waitFor(() => expect(mockedCreateUser).toHaveBeenCalled())
    expect(mockedCreateUser).toHaveBeenCalledWith({
      username: 'charlie',
      full_name: 'Charlie',
      password: 'password123',
      role: 'viewer',
      is_active: true,
    })
  })
})
