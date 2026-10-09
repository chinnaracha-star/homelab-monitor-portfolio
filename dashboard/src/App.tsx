import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { PermissionRoute } from './auth/PermissionRoute'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { Layout } from './components/Layout'
import { PwaProvider } from './pwa/PwaProvider'
import { AgentDetailPage } from './pages/AgentDetailPage'
import { AgentsPage } from './pages/AgentsPage'
import { AlertsPage } from './pages/AlertsPage'
import { AlertRulesPage } from './pages/AlertRulesPage'
import { DashboardOverviewPage } from './pages/DashboardOverviewPage'
import { GroupDetailPage } from './pages/GroupDetailPage'
import { GroupsPage } from './pages/GroupsPage'
import { InfrastructurePage } from './pages/InfrastructurePage'
import { PhotoServicesPage } from './pages/PhotoServicesPage'
import { PhotoMonitorPage } from './pages/PhotoMonitorPage'
import { BackupPage } from './pages/BackupPage'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { CapacityPage } from './pages/CapacityPage'
import { DeveloperPage } from './pages/DeveloperPage'
import { InsightsPage } from './pages/InsightsPage'
import { AlertTimelinePage } from './pages/AlertTimelinePage'
import { IncidentsPage } from './pages/IncidentsPage'
import { NotificationCenterPage } from './pages/NotificationCenterPage'
import { PredictionsPage } from './pages/PredictionsPage'
import { ProductionHealthPage } from './pages/ProductionHealthPage'
import { TrendsPage } from './pages/TrendsPage'
import { LoginPage } from './pages/LoginPage'
import { NotificationsPage } from './pages/NotificationsPage'
import { SettingsPage } from './pages/SettingsPage'
import { UsersPage } from './pages/UsersPage'

function App() {
  return (
    <AuthProvider>
      <PwaProvider>
        <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route index element={<Navigate replace to="/dashboard" />} />
              <Route path="dashboard" element={<DashboardOverviewPage />} />
              <Route element={<PermissionRoute permission="analytics" />}>
                <Route path="analytics" element={<AnalyticsPage />} />
                <Route path="analytics/trends" element={<TrendsPage />} />
                <Route path="analytics/capacity" element={<CapacityPage />} />
                <Route path="analytics/insights" element={<InsightsPage />} />
                <Route path="analytics/predictions" element={<PredictionsPage />} />
              </Route>
              <Route path="agents" element={<AgentsPage />} />
              <Route path="agents/:id" element={<AgentDetailPage />} />
              <Route element={<PermissionRoute permission="groups" />}>
                <Route path="groups" element={<GroupsPage />} />
                <Route path="groups/:groupId" element={<GroupDetailPage />} />
              </Route>
              <Route element={<PermissionRoute permission="infrastructure" />}>
                <Route path="infrastructure" element={<InfrastructurePage />} />
              </Route>
              <Route element={<PermissionRoute permission="photo_services" />}>
                <Route path="photo-services" element={<PhotoServicesPage />} />
                <Route path="photo-monitor" element={<PhotoMonitorPage />} />
              </Route>
              <Route element={<PermissionRoute permission="backup" />}>
                <Route path="backup" element={<BackupPage />} />
              </Route>
              <Route path="alerts" element={<AlertsPage />} />
              <Route path="monitoring/alerts/history" element={<AlertTimelinePage />} />
              <Route path="monitoring/incidents" element={<IncidentsPage />} />
              <Route element={<PermissionRoute permission="notifications" />}>
                <Route path="monitoring/notifications" element={<NotificationCenterPage />} />
              </Route>
              <Route element={<PermissionRoute permission="alert_rules" />}>
                <Route path="alert-rules" element={<AlertRulesPage />} />
              </Route>
              <Route element={<PermissionRoute permission="notifications" />}>
                <Route path="notifications" element={<NotificationsPage />} />
              </Route>
              <Route element={<PermissionRoute permission="users" />}>
                <Route path="users" element={<UsersPage />} />
              </Route>
              <Route element={<PermissionRoute permission="settings" />}>
                <Route path="settings" element={<SettingsPage />} />
              </Route>
              <Route element={<PermissionRoute permission="developer" />}>
                <Route path="developer" element={<DeveloperPage />} />
              </Route>
              <Route element={<PermissionRoute permission="operations" />}>
                <Route path="developer/production-health" element={<ProductionHealthPage />} />
              </Route>
              <Route path="*" element={<Navigate replace to="/dashboard" />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
      </PwaProvider>
    </AuthProvider>
  )
}

export default App
