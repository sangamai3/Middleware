import { NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/api/auth'
import { clearToken } from '@/api/client'
import './AppHeader.css'

const ROLE_COLORS: Record<string, string> = {
  admin: '#FF8A8A',
  developer: '#7CC4FF',
  operator: '#F5C842',
  viewer: '#A9B4BE',
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'
  document.documentElement.dataset.theme = next
  localStorage.setItem('sangam_mw.theme', next)
}

function NavItem({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) => `sidebar-link${isActive ? ' sidebar-link--active' : ''}`}
    >
      <span className="sidebar-link__icon">{icon}</span>
      <span className="sidebar-link__label">{label}</span>
    </NavLink>
  )
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
    <aside className="app-sidebar">
      {/* Brand */}
      <div className="sidebar-brand">
        <NavLink to="/dashboard" className="sidebar-brand__link">
          <div className="sidebar-brand__mark">S</div>
          <div>
            <span className="sidebar-brand__name">SangamMW</span>
            <span className="sidebar-brand__tag">Integration Cloud</span>
          </div>
        </NavLink>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        <div className="sidebar-group">
          <NavItem to="/dashboard" label="Dashboard" icon={
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="1" y="1" width="6" height="6" rx="1.5"/>
              <rect x="9" y="1" width="6" height="6" rx="1.5"/>
              <rect x="1" y="9" width="6" height="6" rx="1.5"/>
              <rect x="9" y="9" width="6" height="6" rx="1.5"/>
            </svg>
          }/>
        </div>

        <div className="sidebar-group">
          <div className="sidebar-group__label">Integrations</div>
          <NavItem to="/flows" label="Flows" icon={
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="2.5" cy="8" r="1.5"/>
              <circle cx="13.5" cy="4" r="1.5"/>
              <circle cx="13.5" cy="12" r="1.5"/>
              <polyline points="4,8 8,8 8,4 12,4"/>
              <polyline points="8,8 8,12 12,12"/>
            </svg>
          }/>
          <NavItem to="/connections" label="Connections" icon={
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M10 2l2 2-2 2"/>
              <path d="M4 14l-2-2 2-2"/>
              <path d="M12 4H6a2 2 0 00-2 2v4"/>
              <path d="M4 12h6a2 2 0 002-2V6"/>
            </svg>
          }/>
          <NavItem to="/templates" label="Templates" icon={
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="2" y="2" width="12" height="12" rx="2"/>
              <line x1="2" y1="6" x2="14" y2="6"/>
              <line x1="6" y1="6" x2="6" y2="14"/>
            </svg>
          }/>
        </div>

        <div className="sidebar-group">
          <div className="sidebar-group__label">Operations</div>
          <NavItem to="/runs" label="Runs" icon={
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <polygon points="4,2 14,8 4,14" fill="none"/>
            </svg>
          }/>
          <NavItem to="/scheduler" label="Scheduler" icon={
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="8" cy="8" r="6"/>
              <polyline points="8,4.5 8,8 10.5,10.5"/>
            </svg>
          }/>
          <NavItem to="/notifications" label="Alerts" icon={
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M8 2a5 5 0 015 5v2l1 2H2l1-2V7a5 5 0 015-5z"/>
              <path d="M6.5 13a1.5 1.5 0 003 0"/>
            </svg>
          }/>
        </div>

        <div className="sidebar-group">
          <div className="sidebar-group__label">Analytics</div>
          <NavItem to="/insights" label="Insights" icon={
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <polyline points="1,12 5,7 8,9 11,5 15,8"/>
              <line x1="1" y1="14" x2="15" y2="14"/>
            </svg>
          }/>
          <NavItem to="/logs" label="Logs" icon={
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <line x1="2" y1="4" x2="14" y2="4"/>
              <line x1="2" y1="8" x2="10" y2="8"/>
              <line x1="2" y1="12" x2="12" y2="12"/>
            </svg>
          }/>
          <NavItem to="/lineage" label="Lineage" icon={
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="2" cy="8" r="1.5"/>
              <circle cx="8" cy="4" r="1.5"/>
              <circle cx="8" cy="12" r="1.5"/>
              <circle cx="14" cy="8" r="1.5"/>
              <line x1="3.5" y1="8" x2="6.5" y2="5"/>
              <line x1="3.5" y1="8" x2="6.5" y2="11"/>
              <line x1="9.5" y1="4" x2="12.5" y2="7"/>
              <line x1="9.5" y1="12" x2="12.5" y2="9"/>
            </svg>
          }/>
          <NavItem to="/events" label="Events" icon={
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="8" cy="8" r="6"/>
              <circle cx="8" cy="8" r="2.5" fill="currentColor" stroke="none"/>
            </svg>
          }/>
        </div>

        <div className="sidebar-group">
          <div className="sidebar-group__label">Platform</div>
          <NavItem to="/gateway" label="Gateway" icon={
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="2" y="5" width="12" height="6" rx="1.5"/>
              <circle cx="5" cy="8" r="1" fill="currentColor" stroke="none"/>
              <line x1="8" y1="6.5" x2="13" y2="6.5"/>
              <line x1="8" y1="9.5" x2="13" y2="9.5"/>
            </svg>
          }/>
          {user?.role === 'admin' && (
            <NavItem to="/admin" label="Admin" icon={
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="8" cy="6" r="3"/>
                <path d="M2 14c0-3.3 2.7-6 6-6s6 2.7 6 6"/>
              </svg>
            }/>
          )}
        </div>
      </nav>

      {/* User footer */}
      {isAuthenticated() && user && (
        <div className="sidebar-footer">
          <button type="button" className="sidebar-theme" onClick={toggleTheme}>
            Toggle light / dark theme
          </button>
          <div className="sidebar-user">
            <div className="sidebar-avatar" title={user.email}>
              {user.email[0].toUpperCase()}
            </div>
            <div className="sidebar-user-info">
              <span className="sidebar-user-email">{user.email}</span>
              <span className="sidebar-user-role" style={{ color: ROLE_COLORS[user.role] ?? '#64748B' }}>
                {user.role}
              </span>
            </div>
            <button className="sidebar-logout" onClick={handleLogout} title="Sign out">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" width="14" height="14">
                <path d="M6 14H3a1 1 0 01-1-1V3a1 1 0 011-1h3"/>
                <polyline points="11,11 14,8 11,5"/>
                <line x1="14" y1="8" x2="6" y2="8"/>
              </svg>
            </button>
          </div>
        </div>
      )}
    </aside>
  )
}
