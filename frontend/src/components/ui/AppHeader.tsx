import { NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/api/auth'
import { clearToken } from '@/api/client'
import './AppHeader.css'

const ROLE_COLORS: Record<string, string> = {
  admin: '#ef4444',
  developer: '#2563eb',
  operator: '#ca8a04',
  viewer: '#6b7280',
}

export function AppHeader() {
  const navigate = useNavigate()
  const { user, logout, isAuthenticated } = useAuthStore()

  async function handleLogout() {
    try { await authApi.logout() } catch {}
    clearToken()
    logout()
    navigate('/login')
  }

  return (
    <header className="app-header">
      <div className="app-header__brand">
        <NavLink to="/dashboard" className="app-header__brand-link">
          <span className="app-header__logo">⚡</span>
          <span className="app-header__name">SangamMW</span>
        </NavLink>
      </div>
      <nav className="app-header__nav">
        <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'nav-link nav-link--active' : 'nav-link'}>Dashboard</NavLink>
        <NavLink to="/flows" className={({ isActive }) => isActive ? 'nav-link nav-link--active' : 'nav-link'}>Flows</NavLink>
        <NavLink to="/runs" className={({ isActive }) => isActive ? 'nav-link nav-link--active' : 'nav-link'}>Runs</NavLink>
        <NavLink to="/connections" className={({ isActive }) => isActive ? 'nav-link nav-link--active' : 'nav-link'}>Connections</NavLink>
        <NavLink to="/gateway" className={({ isActive }) => isActive ? 'nav-link nav-link--active' : 'nav-link'}>Gateway</NavLink>
        <NavLink to="/templates" className={({ isActive }) => isActive ? 'nav-link nav-link--active' : 'nav-link'}>Templates</NavLink>
        <NavLink to="/lineage" className={({ isActive }) => isActive ? 'nav-link nav-link--active' : 'nav-link'}>Lineage</NavLink>
        <NavLink to="/notifications" className={({ isActive }) => isActive ? 'nav-link nav-link--active' : 'nav-link'}>Alerts</NavLink>
        <NavLink to="/scheduler" className={({ isActive }) => isActive ? 'nav-link nav-link--active' : 'nav-link'}>Scheduler</NavLink>
        <NavLink to="/insights" className={({ isActive }) => isActive ? 'nav-link nav-link--active' : 'nav-link'}>Insights</NavLink>
        <NavLink to="/logs" className={({ isActive }) => isActive ? 'nav-link nav-link--active' : 'nav-link'}>Logs</NavLink>
        {user?.role === 'admin' && (
          <NavLink to="/admin" className={({ isActive }) => isActive ? 'nav-link nav-link--active' : 'nav-link'}>Admin</NavLink>
        )}
      </nav>
      {isAuthenticated() && user && (
        <div className="app-header__user">
          <div className="user-avatar" title={user.email}>
            {user.email[0].toUpperCase()}
          </div>
          <div className="user-info">
            <span className="user-email">{user.email}</span>
            <span className="user-role-badge" style={{ color: ROLE_COLORS[user.role] ?? '#6b7280' }}>
              {user.role}
            </span>
          </div>
          <button className="logout-btn" onClick={handleLogout} title="Sign out">
            ↩
          </button>
        </div>
      )}
    </header>
  )
}
