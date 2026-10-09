import { memo } from 'react'
import styles from './Components.module.css'

export type IconName =
  | 'cpu'
  | 'memory'
  | 'storage'
  | 'photo'
  | 'backup'
  | 'docker'
  | 'immich'
  | 'qnap'
  | 'temperature'
  | 'alert'
  | 'notification'
  | 'agent'
  | 'mission'
  | 'analytics'
  | 'trend'
  | 'capacity'
  | 'insights'
  | 'overview'
  | 'groups'
  | 'users'
  | 'settings'
  | 'infrastructure'

const PATHS: Record<IconName, string> = {
  cpu: 'M9 9h6v6H9zM4 12h2m12 0h2M12 4v2m0 12v2',
  memory: 'M5 8h14v8H5zM8 8v8m4-8v8m4-8v8',
  storage: 'M4 7h16v3H4zM4 14h16v3H4z',
  photo: 'M4 7h16v12H4zM8 11l3 4 2-2 3 4',
  backup: 'M12 5v10m0 0-3-3m3 3 3-3M5 19h14',
  docker: 'M5 14h3v3H5zm4 0h3v3H9zm4 0h3v3h-3zM7 10h3v3H7zm4 0h3v3h-3z',
  immich: 'M12 5l6 4v6l-6 4-6-4V9z',
  qnap: 'M5 8h14v8H5zM8 12h8',
  temperature: 'M10 14V7a2 2 0 1 1 4 0v7a3 3 0 1 1-4 0z',
  alert: 'M12 5 4 19h16L12 5zm0 6v4m0 2h.01',
  notification: 'M6 16h12l-1-5a5 5 0 0 0-10 0zM10 18a2 2 0 0 0 4 0',
  agent: 'M12 7a3 3 0 1 0 0-0.01M6 19a6 6 0 0 1 12 0',
  mission: 'M4 6h16M4 12h10M4 18h16',
  analytics: 'M5 19V9m5 10V5m5 14v-7m5 7V8',
  trend: 'M4 16l5-5 4 3 7-8',
  capacity: 'M4 18h16M6 18V8h4v10m4 0V4h4v14',
  insights: 'M12 4a6 6 0 0 1 3 11v3H9v-3a6 6 0 0 1 3-11z',
  overview: 'M4 5h7v7H4zM13 5h7v4h-7zM13 11h7v8h-7zM4 14h7v5H4z',
  groups: 'M8 10a2 2 0 1 0 0-0.01M16 10a2 2 0 1 0 0-0.01M5 18a3 3 0 0 1 6 0m4 0a3 3 0 0 1 6 0',
  users: 'M12 8a3 3 0 1 0 0-0.01M6 19a6 6 0 0 1 12 0',
  settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM4 12h2m12 0h2M12 4v2m0 12v2',
  infrastructure: 'M4 16h16v3H4zM7 8h3v8H7zm7 4h3v4h-3z',
}

export const Icon = memo(function Icon({
  name,
  label,
}: {
  name: IconName
  label?: string
}) {
  return (
    <svg
      aria-hidden={label ? undefined : true}
      aria-label={label}
      className={styles.icon}
      fill="none"
      role={label ? 'img' : undefined}
      viewBox="0 0 24 24"
    >
      <path d={PATHS[name]} stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
    </svg>
  )
})
