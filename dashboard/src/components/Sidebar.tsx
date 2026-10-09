import { memo } from 'react'
import { NavLink } from 'react-router-dom'
import { NAV_ITEMS, type NavItem } from '../auth/permissions'
import { useCan } from '../auth/useCan'
import { Icon, type IconName } from './Icon'
import styles from './Layout.module.css'

const NAV_ICONS: Record<string, IconName> = {
  '/dashboard': 'overview',
  '/analytics': 'analytics',
  '/analytics/trends': 'trend',
  '/analytics/capacity': 'capacity',
  '/analytics/insights': 'insights',
  '/analytics/predictions': 'trend',
  '/agents': 'agent',
  '/groups': 'groups',
  '/infrastructure': 'infrastructure',
  '/photo-services': 'photo',
  '/photo-monitor': 'photo',
  '/backup': 'backup',
  '/alerts': 'alert',
  '/monitoring/alerts/history': 'alert',
  '/monitoring/incidents': 'groups',
  '/monitoring/notifications': 'notification',
  '/alert-rules': 'alert',
  '/notifications': 'notification',
  '/users': 'users',
  '/settings': 'settings',
  '/developer': 'mission',
  '/developer/production-health': 'infrastructure',
}

interface SidebarProps {
  open: boolean
  onNavigate: () => void
}

function navClassName({ isActive }: { isActive: boolean }) {
  return `${styles.navLink} ${isActive ? styles.active : ''}`.trim()
}

function NavEntries({ items, onNavigate }: { items: readonly NavItem[]; onNavigate: () => void }) {
  const can = useCan()
  return (
    <>
      {items
        .filter((item) => can(item.permission))
        .map((item) => {
          if (item.children?.length) {
            const children = item.children.filter((child) => can(child.permission) && child.to)
            if (children.length === 0) {
              return null
            }
            return (
              <section className={styles.navGroup} key={item.label} aria-label={item.label}>
                <p className={styles.navGroupLabel}>{item.label}</p>
                {children.map((child) => (
                  <NavLink
                    className={navClassName}
                    end={child.to === '/analytics'}
                    key={child.to}
                    to={child.to ?? '/'}
                    onClick={onNavigate}
                  >
                    {NAV_ICONS[child.to ?? ''] ? <Icon name={NAV_ICONS[child.to ?? '']} /> : null}
                    {child.label}
                  </NavLink>
                ))}
              </section>
            )
          }
          if (!item.to) {
            return null
          }
          return (
            <NavLink className={navClassName} key={item.to} to={item.to} onClick={onNavigate}>
              {NAV_ICONS[item.to] ? <Icon name={NAV_ICONS[item.to]} /> : null}
              {item.label}
            </NavLink>
          )
        })}
    </>
  )
}

export const Sidebar = memo(function Sidebar({ open, onNavigate }: SidebarProps) {
  return (
    <aside className={`${styles.sidebar} ${open ? styles.sidebarOpen : ''}`} id="app-sidebar">
      <nav className={styles.navigation} aria-label="Primary navigation">
        <NavEntries items={NAV_ITEMS} onNavigate={onNavigate} />
      </nav>
    </aside>
  )
})
