import { useMemo, useState, type FormEvent } from 'react'
import {
  createUser,
  deleteUser,
  listUsers,
  resetUserPassword,
  updateUser,
  updateUserStatus,
} from '../api/users'
import { useAuth } from '../auth/AuthContext'
import { ConfirmDialog, ModalDialog } from '../components/UserDialogs'
import { EmptyState } from '../components/EmptyState'
import { SectionError } from '../components/SectionError'
import { TableSkeleton } from '../components/Skeleton'
import { usePolling } from '../hooks/usePolling'
import type { ManagedUser, UserRole } from '../types/users'
import { getErrorMessage } from '../utils/errors'
import componentStyles from '../components/Components.module.css'
import pageStyles from './Pages.module.css'
import styles from './UsersPage.module.css'

type RoleFilter = 'all' | UserRole
type StatusFilter = 'all' | 'active' | 'inactive'
type DialogState =
  | { type: 'create' }
  | { type: 'edit'; user: ManagedUser }
  | { type: 'password-confirm'; user: ManagedUser }
  | { type: 'password'; user: ManagedUser }
  | { type: 'delete'; user: ManagedUser }
  | { type: 'disable'; user: ManagedUser }
  | null

const emptyCreate = {
  username: '',
  full_name: '',
  password: '',
  role: 'viewer' as UserRole,
  is_active: true,
}

export function UsersPage() {
  const { user: currentUser } = useAuth()
  const { data: users, error, retry: loadUsers } = usePolling(listUsers)
  const [query, setQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [dialog, setDialog] = useState<DialogState>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [createForm, setCreateForm] = useState(emptyCreate)
  const [editForm, setEditForm] = useState({
    full_name: '',
    role: 'viewer' as UserRole,
    is_active: true,
  })
  const [newPassword, setNewPassword] = useState('')

  const visibleUsers = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (users ?? []).filter((user) => {
      const matchesQuery =
        needle.length === 0 ||
        user.username.toLowerCase().includes(needle) ||
        user.full_name.toLowerCase().includes(needle)
      const matchesRole = roleFilter === 'all' || user.role === roleFilter
      const matchesStatus =
        statusFilter === 'all' ||
        (statusFilter === 'active' ? user.is_active : !user.is_active)
      return matchesQuery && matchesRole && matchesStatus
    })
  }, [query, roleFilter, statusFilter, users])

  function showToast(message: string) {
    setToast(message)
    setDialog(null)
    setFormError(null)
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError(null)
    try {
      await createUser(createForm)
      setCreateForm(emptyCreate)
      await loadUsers()
      showToast('User created.')
    } catch (requestError) {
      setFormError(getErrorMessage(requestError))
    }
  }

  async function handleEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (dialog?.type !== 'edit') {
      return
    }
    setFormError(null)
    try {
      await updateUser(dialog.user.id, editForm)
      await loadUsers()
      showToast('User updated.')
    } catch (requestError) {
      setFormError(getErrorMessage(requestError))
    }
  }

  async function handlePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (dialog?.type !== 'password') {
      return
    }
    setFormError(null)
    try {
      await resetUserPassword(dialog.user.id, newPassword)
      setNewPassword('')
      await loadUsers()
      showToast('Password reset.')
    } catch (requestError) {
      setFormError(getErrorMessage(requestError))
    }
  }

  async function handleDelete() {
    if (dialog?.type !== 'delete') {
      return
    }
    try {
      await deleteUser(dialog.user.id)
      await loadUsers()
      showToast('User deleted.')
    } catch (requestError) {
      setFormError(getErrorMessage(requestError))
    }
  }

  async function handleDisable() {
    if (dialog?.type !== 'disable') {
      return
    }
    try {
      await updateUserStatus(dialog.user.id, false)
      await loadUsers()
      showToast('User disabled.')
    } catch (requestError) {
      setFormError(getErrorMessage(requestError))
    }
  }

  async function handleEnable(user: ManagedUser) {
    try {
      await updateUserStatus(user.id, true)
      await loadUsers()
      showToast('User enabled.')
    } catch (requestError) {
      setFormError(getErrorMessage(requestError))
    }
  }

  function openEdit(user: ManagedUser) {
    setFormError(null)
    setEditForm({
      full_name: user.full_name,
      role: user.role,
      is_active: user.is_active,
    })
    setDialog({ type: 'edit', user })
  }

  return (
    <section className={pageStyles.page}>
      <header className={pageStyles.pageHeader}>
        <div>
          <p className={pageStyles.eyebrow}>Administration</p>
          <h1 className={pageStyles.title}>Users</h1>
          <p className={pageStyles.description}>
            Create and manage dashboard accounts. Only administrators can change users.
          </p>
        </div>
        <button
          className={styles.primaryButton}
          type="button"
          onClick={() => {
            setFormError(null)
            setCreateForm(emptyCreate)
            setDialog({ type: 'create' })
          }}
        >
          Create User
        </button>
      </header>

      {toast ? (
        <p className={styles.toast} role="status">
          {toast}
        </p>
      ) : null}

      {error ? (
        <SectionError title="Users API failed" message={error} onRetry={() => void loadUsers()} />
      ) : null}
      {!users && !error ? <TableSkeleton /> : null}

      {users ? (
        <section className={styles.toolbarRow} aria-label="User search and filters">
          <label className={componentStyles.searchLabel} htmlFor="user-search">
            Search users
            <input
              className={componentStyles.searchInput}
              id="user-search"
              type="search"
              value={query}
              placeholder="Search username or full name"
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <div className={componentStyles.filterGroup} role="group" aria-label="Role filter">
            {(['all', 'admin', 'operator', 'viewer'] as const).map((role) => (
              <button
                className={`${componentStyles.filterButton} ${roleFilter === role ? componentStyles.filterActive : ''}`}
                key={role}
                type="button"
                aria-pressed={roleFilter === role}
                onClick={() => setRoleFilter(role)}
              >
                {role === 'all' ? 'All roles' : role}
              </button>
            ))}
          </div>
          <div className={componentStyles.filterGroup} role="group" aria-label="Status filter">
            {(['all', 'active', 'inactive'] as const).map((status) => (
              <button
                className={`${componentStyles.filterButton} ${statusFilter === status ? componentStyles.filterActive : ''}`}
                key={status}
                type="button"
                aria-pressed={statusFilter === status}
                onClick={() => setStatusFilter(status)}
              >
                {status === 'all' ? 'All statuses' : status}
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {users && users.length === 0 ? <EmptyState message="No users found." /> : null}
      {users && users.length > 0 && visibleUsers.length === 0 ? (
        <EmptyState message="No users match the current search or filters." />
      ) : null}

      {visibleUsers.length > 0 ? (
        <section className={componentStyles.tableWrapper}>
          <table className={componentStyles.table} aria-label="Dashboard users">
            <thead>
              <tr>
                <th scope="col">Username</th>
                <th scope="col">Full name</th>
                <th scope="col">Role</th>
                <th scope="col">Status</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleUsers.map((user) => {
                const isSelf = currentUser?.id === user.id
                return (
                  <tr key={user.id}>
                    <td className={componentStyles.agentName}>{user.username}</td>
                    <td>{user.full_name}</td>
                    <td>{user.role}</td>
                    <td>
                      <span
                        className={`${componentStyles.badge} ${user.is_active ? componentStyles.online : componentStyles.offline}`}
                      >
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      <div className={styles.actions}>
                        <button
                          className={styles.actionButton}
                          type="button"
                          onClick={() => openEdit(user)}
                        >
                          Edit User
                        </button>
                        <button
                          className={styles.actionButton}
                          type="button"
                          onClick={() => {
                            setFormError(null)
                            setNewPassword('')
                            setDialog({ type: 'password-confirm', user })
                          }}
                        >
                          Reset Password
                        </button>
                        {user.is_active ? (
                          <button
                            className={styles.actionButton}
                            type="button"
                            disabled={isSelf}
                            onClick={() => {
                              setFormError(null)
                              setDialog({ type: 'disable', user })
                            }}
                          >
                            Disable
                          </button>
                        ) : (
                          <button
                            className={styles.actionButton}
                            type="button"
                            onClick={() => void handleEnable(user)}
                          >
                            Enable
                          </button>
                        )}
                        <button
                          className={styles.dangerButton}
                          type="button"
                          disabled={isSelf}
                          onClick={() => {
                            setFormError(null)
                            setDialog({ type: 'delete', user })
                          }}
                        >
                          Delete User
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </section>
      ) : null}

      <>
      {dialog?.type === 'create' ? (
      <ModalDialog
        open
        title="Create User"
        onClose={() => setDialog(null)}
      >
        <form className={styles.form} onSubmit={(event) => void handleCreate(event)}>
          <label className={styles.label} htmlFor="create-username">
            Username
            <input
              className={styles.input}
              id="create-username"
              name="username"
              minLength={3}
              maxLength={30}
              required
              value={createForm.username}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, username: event.target.value }))
              }
            />
          </label>
          <label className={styles.label} htmlFor="create-full-name">
            Full name
            <input
              className={styles.input}
              id="create-full-name"
              name="full_name"
              required
              value={createForm.full_name}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, full_name: event.target.value }))
              }
            />
          </label>
          <label className={styles.label} htmlFor="create-password">
            Password
            <input
              className={styles.input}
              id="create-password"
              name="password"
              type="password"
              minLength={8}
              required
              value={createForm.password}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, password: event.target.value }))
              }
            />
          </label>
          <label className={styles.label} htmlFor="create-role">
            Role
            <select
              className={styles.input}
              id="create-role"
              name="role"
              value={createForm.role}
              onChange={(event) =>
                setCreateForm((current) => ({
                  ...current,
                  role: event.target.value as UserRole,
                }))
              }
            >
              <option value="admin">admin</option>
              <option value="operator">operator</option>
              <option value="viewer">viewer</option>
            </select>
          </label>
          <label className={styles.checkbox} htmlFor="create-active">
            <input
              id="create-active"
              name="is_active"
              type="checkbox"
              checked={createForm.is_active}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, is_active: event.target.checked }))
              }
            />
            Active
          </label>
          {formError && dialog?.type === 'create' ? (
            <p className={styles.formError} role="alert">
              {formError}
            </p>
          ) : null}
          <div className={styles.dialogActions}>
            <button className={styles.secondaryButton} type="button" onClick={() => setDialog(null)}>
              Cancel
            </button>
            <button className={styles.primaryButton} type="submit">
              Create User
            </button>
          </div>
        </form>
      </ModalDialog>
      ) : null}

      {dialog?.type === 'edit' ? (
      <ModalDialog
        open
        title="Edit User"
        onClose={() => setDialog(null)}
      >
        <form className={styles.form} onSubmit={(event) => void handleEdit(event)}>
          <label className={styles.label} htmlFor="edit-full-name">
            Full name
            <input
              className={styles.input}
              id="edit-full-name"
              name="full_name"
              required
              value={editForm.full_name}
              onChange={(event) =>
                setEditForm((current) => ({ ...current, full_name: event.target.value }))
              }
            />
          </label>
          <label className={styles.label} htmlFor="edit-role">
            Role
            <select
              className={styles.input}
              id="edit-role"
              name="role"
              value={editForm.role}
              onChange={(event) =>
                setEditForm((current) => ({ ...current, role: event.target.value as UserRole }))
              }
            >
              <option value="admin">admin</option>
              <option value="operator">operator</option>
              <option value="viewer">viewer</option>
            </select>
          </label>
          <label className={styles.checkbox} htmlFor="edit-active">
            <input
              id="edit-active"
              name="is_active"
              type="checkbox"
              checked={editForm.is_active}
              onChange={(event) =>
                setEditForm((current) => ({ ...current, is_active: event.target.checked }))
              }
            />
            Active
          </label>
          {formError && dialog?.type === 'edit' ? (
            <p className={styles.formError} role="alert">
              {formError}
            </p>
          ) : null}
          <div className={styles.dialogActions}>
            <button className={styles.secondaryButton} type="button" onClick={() => setDialog(null)}>
              Cancel
            </button>
            <button className={styles.primaryButton} type="submit">
              Save
            </button>
          </div>
        </form>
      </ModalDialog>
      ) : null}

      {dialog?.type === 'password-confirm' ? (
      <ConfirmDialog
        open
        title="Confirm password reset"
        message={`Reset the password for ${dialog.user.username}?`}
        confirmLabel="Continue"
        onClose={() => setDialog(null)}
        onConfirm={() => {
          setFormError(null)
          setNewPassword('')
          setDialog({ type: 'password', user: dialog.user })
        }}
      />
      ) : null}

      {dialog?.type === 'password' ? (
      <ModalDialog
        open
        title="Reset Password"
        onClose={() => setDialog(null)}
      >
        <form className={styles.form} onSubmit={(event) => void handlePassword(event)}>
          <label className={styles.label} htmlFor="reset-password">
            New password
            <input
              className={styles.input}
              id="reset-password"
              name="password"
              type="password"
              minLength={8}
              required
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
          </label>
          {formError ? (
            <p className={styles.formError} role="alert">
              {formError}
            </p>
          ) : null}
          <div className={styles.dialogActions}>
            <button className={styles.secondaryButton} type="button" onClick={() => setDialog(null)}>
              Cancel
            </button>
            <button className={styles.dangerButton} type="submit">
              Reset Password
            </button>
          </div>
        </form>
      </ModalDialog>
      ) : null}

      {dialog?.type === 'delete' ? (
      <ConfirmDialog
        open
        title="Delete User"
        message={`Delete ${dialog.user.username}? This cannot be undone.`}
        confirmLabel="Delete User"
        onClose={() => setDialog(null)}
        onConfirm={() => void handleDelete()}
      />
      ) : null}

      {dialog?.type === 'disable' ? (
      <ConfirmDialog
        open
        title="Disable User"
        message={`Disable ${dialog.user.username}? They will not be able to sign in.`}
        confirmLabel="Disable"
        onClose={() => setDialog(null)}
        onConfirm={() => void handleDisable()}
      />
      ) : null}
      </>
    </section>
  )
}
