import { Routes, Route, Navigate } from 'react-router-dom'
import { AppHeader } from '@/components/ui/AppHeader'
import { ProtectedRoute } from '@/components/ui/ProtectedRoute'
import { ToastProvider } from '@/components/ui/Toast'
import { CommandPalette } from '@/components/ui/CommandPalette'
import { FlowsPage } from '@/pages/FlowsPage'
import { FlowDesignerPage } from '@/pages/FlowDesignerPage'
import { RunsPage } from '@/pages/RunsPage'
import { ConnectionsPage } from '@/pages/ConnectionsPage'
import { LoginPage } from '@/pages/LoginPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { GatewayPage } from '@/pages/GatewayPage'
import { AdminPage } from '@/pages/AdminPage'
import { LineagePage } from '@/pages/LineagePage'
import { TemplatesPage } from '@/pages/TemplatesPage'
import { NotificationsPage } from '@/pages/NotificationsPage'
import { SchedulerPage } from '@/pages/SchedulerPage'
import { InsightsPage } from '@/pages/InsightsPage'
import { FlowInsightsPage } from '@/pages/FlowInsightsPage'
import { LogSearchPage } from '@/pages/LogSearchPage'
import { BusinessEventsPage } from '@/pages/BusinessEventsPage'
import './App.css'

function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="app">
      <AppHeader />
      <main className="app__main">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <ToastProvider>
    <CommandPalette />
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected — viewer+ */}
      <Route path="/" element={
        <ProtectedRoute>
          <AppShell>
            <Navigate to="/dashboard" replace />
          </AppShell>
        </ProtectedRoute>
      } />
      <Route path="/dashboard" element={
        <ProtectedRoute>
          <AppShell><DashboardPage /></AppShell>
        </ProtectedRoute>
      } />
      <Route path="/flows" element={
        <ProtectedRoute>
          <AppShell><FlowsPage /></AppShell>
        </ProtectedRoute>
      } />
      <Route path="/flows/:id" element={
        <ProtectedRoute>
          <AppShell><FlowDesignerPage /></AppShell>
        </ProtectedRoute>
      } />
      <Route path="/runs" element={
        <ProtectedRoute>
          <AppShell><RunsPage /></AppShell>
        </ProtectedRoute>
      } />
      <Route path="/connections" element={
        <ProtectedRoute>
          <AppShell><ConnectionsPage /></AppShell>
        </ProtectedRoute>
      } />

      {/* Protected — developer+ */}
      <Route path="/gateway" element={
        <ProtectedRoute minRole="developer">
          <AppShell><GatewayPage /></AppShell>
        </ProtectedRoute>
      } />

      {/* Protected — developer+ */}
      <Route path="/lineage" element={
        <ProtectedRoute minRole="developer">
          <AppShell><LineagePage /></AppShell>
        </ProtectedRoute>
      } />
      <Route path="/templates" element={
        <ProtectedRoute minRole="developer">
          <AppShell><TemplatesPage /></AppShell>
        </ProtectedRoute>
      } />
      <Route path="/notifications" element={
        <ProtectedRoute minRole="operator">
          <AppShell><NotificationsPage /></AppShell>
        </ProtectedRoute>
      } />
      <Route path="/scheduler" element={
        <ProtectedRoute minRole="operator">
          <AppShell><SchedulerPage /></AppShell>
        </ProtectedRoute>
      } />

      {/* Phase 14 — Insights, Logs, Business Events */}
      <Route path="/insights" element={
        <ProtectedRoute>
          <AppShell><InsightsPage /></AppShell>
        </ProtectedRoute>
      } />
      <Route path="/insights/flows/:id" element={
        <ProtectedRoute>
          <AppShell><FlowInsightsPage /></AppShell>
        </ProtectedRoute>
      } />
      <Route path="/logs" element={
        <ProtectedRoute>
          <AppShell><LogSearchPage /></AppShell>
        </ProtectedRoute>
      } />
      <Route path="/events" element={
        <ProtectedRoute>
          <AppShell><BusinessEventsPage /></AppShell>
        </ProtectedRoute>
      } />

      {/* Protected — admin only */}
      <Route path="/admin" element={
        <ProtectedRoute minRole="admin">
          <AppShell><AdminPage /></AppShell>
        </ProtectedRoute>
      } />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
    </ToastProvider>
  )
}
