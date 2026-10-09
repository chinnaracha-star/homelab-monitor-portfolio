import { useCallback, useEffect, useRef, useState, type TouchEvent } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { DashboardSocketProvider, useDashboardConnection } from '../hooks/useDashboardSocket'
import { AlertBanner } from './AlertBanner'
import { PwaUpdateBanner } from './PwaUpdateBanner'
import styles from './Layout.module.css'
import { Navbar } from './Navbar'
import { RealtimeDisconnectedBanner } from './RealtimeDisconnectedBanner'
import { Sidebar } from './Sidebar'

export function Layout() {
  return (
    <DashboardSocketProvider>
      <LayoutShell />
    </DashboardSocketProvider>
  )
}

function LayoutShell() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const { status } = useDashboardConnection()
  const closeSidebar = useCallback(() => setSidebarOpen(false), [])
  const toggleSidebar = useCallback(() => setSidebarOpen((open) => !open), [])
  const startY = useRef<number | null>(null)

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        closeSidebar()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [closeSidebar])

  function onTouchStart(event: TouchEvent<HTMLElement>) {
    if (window.scrollY > 8) {
      startY.current = null
      return
    }
    startY.current = event.touches[0]?.clientY ?? null
  }

  function onTouchEnd(event: TouchEvent<HTMLElement>) {
    const start = startY.current
    startY.current = null
    if (start == null) {
      return
    }
    const end = event.changedTouches[0]?.clientY ?? start
    if (end - start > 70) {
      setRefreshing(true)
      window.dispatchEvent(new Event('homelab-pull-refresh'))
      window.setTimeout(() => setRefreshing(false), 800)
    }
  }

  return (
    <section className={styles.shell}>
      <Navbar sidebarOpen={sidebarOpen} onToggleSidebar={toggleSidebar} />
      <section className={styles.body}>
        {sidebarOpen ? (
          <button
            className={styles.backdrop}
            type="button"
            aria-label="Close navigation"
            onClick={closeSidebar}
          />
        ) : null}
        <Sidebar open={sidebarOpen} onNavigate={closeSidebar} />
        <main
          className={styles.main}
          id="main-content"
          onTouchEnd={onTouchEnd}
          onTouchStart={onTouchStart}
        >
          <nav aria-label="Quick actions" className={styles.quickActions}>
            <Link to="/dashboard">Overview</Link>
            <Link to="/alerts">Alerts</Link>
            <Link to="/photo-monitor">Photos</Link>
            <Link to="/backup">Backup</Link>
          </nav>
          {refreshing ? <p className={styles.pullHint}>Refreshing…</p> : <p className={styles.pullHint}>Pull down to refresh</p>}
          <PwaUpdateBanner />
          {status === 'disconnected' ? <RealtimeDisconnectedBanner /> : null}
          <AlertBanner />
          <Outlet />
        </main>
      </section>
    </section>
  )
}
