export type Role = 'admin' | 'operator' | 'viewer'

export type Permission =
  | 'dashboard'
  | 'agents'
  | 'reports'
  | 'alerts'
  | 'acknowledge_alerts'
  | 'groups'
  | 'manage_groups'
  | 'users'
  | 'settings'
  | 'notifications'
  | 'send_notifications'
  | 'alert_rules'
  | 'manage_alert_rules'
  | 'infrastructure'
  | 'photo_services'
  | 'backup'
  | 'analytics'
  | 'developer'
  | 'operations'

export interface NavItem {
  to?: string
  label: string
  permission: Permission
  children?: readonly NavItem[]
}

const ROLE_PERMISSIONS: Record<Role, readonly Permission[]> = {
  admin: [
    'dashboard',
    'agents',
    'reports',
    'alerts',
    'acknowledge_alerts',
    'groups',
    'manage_groups',
    'users',
    'settings',
    'notifications',
    'send_notifications',
    'alert_rules',
    'manage_alert_rules',
    'infrastructure',
    'photo_services',
    'backup',
    'analytics',
    'developer',
    'operations',
  ],
  operator: [
    'dashboard',
    'agents',
    'reports',
    'alerts',
    'acknowledge_alerts',
    'groups',
    'manage_groups',
    'notifications',
    'send_notifications',
    'alert_rules',
    'infrastructure',
    'photo_services',
    'backup',
    'analytics',
    'operations',
  ],
  viewer: [
    'dashboard',
    'agents',
    'reports',
    'alerts',
    'groups',
    'notifications',
    'alert_rules',
    'infrastructure',
    'photo_services',
    'backup',
    'analytics',
  ],
}

export const NAV_ITEMS: readonly NavItem[] = [
  { to: '/dashboard', label: 'Overview', permission: 'dashboard' },
  {
    label: 'Analytics',
    permission: 'analytics',
    children: [
      { to: '/analytics', label: 'Overview', permission: 'analytics' },
      { to: '/analytics/trends', label: 'Trends', permission: 'analytics' },
      { to: '/analytics/capacity', label: 'Capacity Planning', permission: 'analytics' },
      { to: '/analytics/insights', label: 'AI Insights', permission: 'analytics' },
      { to: '/analytics/predictions', label: 'Predictive Alerting', permission: 'analytics' },
    ],
  },
  { to: '/agents', label: 'Agents', permission: 'agents' },
  { to: '/groups', label: 'Groups', permission: 'groups' },
  { to: '/infrastructure', label: 'Infrastructure', permission: 'infrastructure' },
  { to: '/photo-services', label: 'Photo Services', permission: 'photo_services' },
  { to: '/photo-monitor', label: 'Photo Monitor', permission: 'photo_services' },
  { to: '/backup', label: 'Backup', permission: 'backup' },
  {
    label: 'Monitoring',
    permission: 'alerts',
    children: [
      { to: '/alerts', label: 'Alerts', permission: 'alerts' },
      { to: '/monitoring/alerts/history', label: 'Alert Timeline', permission: 'alerts' },
      { to: '/monitoring/incidents', label: 'Incidents', permission: 'alerts' },
      { to: '/monitoring/notifications', label: 'Notification Center', permission: 'notifications' },
    ],
  },
  { to: '/alert-rules', label: 'Alert Rules', permission: 'alert_rules' },
  { to: '/notifications', label: 'Notifications', permission: 'notifications' },
  { to: '/users', label: 'Users', permission: 'users' },
  { to: '/settings', label: 'Settings', permission: 'settings' },
  {
    label: 'Developer',
    permission: 'operations',
    children: [
      { to: '/developer', label: 'Mission Control', permission: 'developer' },
      { to: '/developer/production-health', label: 'Production Health', permission: 'operations' },
    ],
  },
]

function isRole(value: string): value is Role {
  return value === 'admin' || value === 'operator' || value === 'viewer'
}

export function can(role: string | null | undefined, permission: Permission): boolean {
  if (!role || !isRole(role)) {
    return false
  }
  return ROLE_PERMISSIONS[role].includes(permission)
}
