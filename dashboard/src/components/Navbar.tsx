import { memo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useOptionalDashboardConnection } from '../hooks/useDashboardSocket'
import { ConnectionStatusBadge } from './ConnectionStatusBadge'
import styles from './Layout.module.css'

interface NavbarProps {
  sidebarOpen: boolean
  onToggleSidebar: () => void
}

export const Navbar = memo(function Navbar({ sidebarOpen, onToggleSidebar }: NavbarProps) {
  const { user, logout } = useAuth()
  const socket = useOptionalDashboardConnection()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    void navigate('/login', { replace: true })
  }

  return (
    <header className={styles.navbar}>
      <button
        className={styles.menuButton}
        type="button"
        aria-expanded={sidebarOpen}
        aria-controls="app-sidebar"
        aria-label={sidebarOpen ? 'Close navigation' : 'Open navigation'}
        onClick={onToggleSidebar}
      >
        <span aria-hidden="true">{sidebarOpen ? '✕' : '☰'}</span>
      </button>
      <div className={styles.brand}>
        <span className={styles.brandMark} aria-hidden="true">
          HM
        </span>
        <span>HomeLab Monitor</span>
      </div>
      <div className={styles.session}>
        {socket ? <ConnectionStatusBadge status={socket.status} /> : null}
        {user ? (
          <>
            <span className={styles.userName}>{user.username}</span>
            <span className={styles.userRole} aria-label={`Role ${user.role}`}>
              {user.role}
            </span>
            <button className={styles.logoutButton} type="button" onClick={handleLogout}>
              Logout
            </button>
          </>
        ) : null}
      </div>
    </header>
  )
})
