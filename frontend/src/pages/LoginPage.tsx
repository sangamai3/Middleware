import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { loginAndStore, authApi } from '@/api/auth'
import { useAuthStore } from '@/store/authStore'
import './LoginPage.css'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { setAuth, isAuthenticated } = useAuthStore()
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/dashboard'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (isAuthenticated()) navigate(from, { replace: true })
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await loginAndStore(email, password)
      setAuth({ user_id: result.user_id, email: result.email, role: result.role as any }, result.access_token)
      navigate(from, { replace: true })
    } catch (err: any) {
      setError(err.message || 'Login failed. Check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogle = async () => {
    try {
      const { url } = await authApi.googleAuthUrl()
      window.location.href = url
    } catch {
      setError('Google OAuth is not configured.')
    }
  }

  return (
    <div className="login-page">
      {/* ── Left brand panel ── */}
      <div className="login-brand">
        <div className="login-brand__inner">
          <div className="login-brand__logo">
            <div className="login-brand__mark">S</div>
            <span className="login-brand__name">SangamMW</span>
          </div>

          <h2 className="login-brand__heading">
            Enterprise-grade<br />
            <span>integration, simplified.</span>
          </h2>
          <p className="login-brand__sub">
            Connect systems, automate data flows, and operate at scale —
            from a single unified platform.
          </p>

          <div className="login-brand__features">
            <div className="login-brand__feature">
              <div className="login-brand__feat-icon">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <rect x="1" y="1" width="6" height="6" rx="1.5"/>
                  <rect x="9" y="1" width="6" height="6" rx="1.5"/>
                  <rect x="1" y="9" width="6" height="6" rx="1.5"/>
                  <rect x="9" y="9" width="6" height="6" rx="1.5"/>
                </svg>
              </div>
              <div>
                <div className="login-brand__feat-title">Visual Flow Designer</div>
                <div className="login-brand__feat-desc">
                  Build integration pipelines with a drag-and-drop canvas — no code required
                </div>
              </div>
            </div>

            <div className="login-brand__feature">
              <div className="login-brand__feat-icon">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <polyline points="1,11 5,5 8,8 11,3 15,6"/>
                  <circle cx="15" cy="6" r="1.5" fill="currentColor" stroke="none"/>
                </svg>
              </div>
              <div>
                <div className="login-brand__feat-title">Real-time Observability</div>
                <div className="login-brand__feat-desc">
                  Monitor executions, alerts, and data lineage with live dashboards
                </div>
              </div>
            </div>

            <div className="login-brand__feature">
              <div className="login-brand__feat-icon">
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <circle cx="3" cy="8" r="2"/>
                  <circle cx="13" cy="3" r="2"/>
                  <circle cx="13" cy="13" r="2"/>
                  <line x1="5" y1="7" x2="11" y2="4"/>
                  <line x1="5" y1="9" x2="11" y2="12"/>
                </svg>
              </div>
              <div>
                <div className="login-brand__feat-title">Multi-Connector Platform</div>
                <div className="login-brand__feat-desc">
                  CSV, REST APIs, databases, and cloud storage — all in one place
                </div>
              </div>
            </div>
          </div>

          <div className="login-brand__stats">
            <div className="login-brand__stat">
              <div className="login-brand__stat-num">50+</div>
              <div className="login-brand__stat-label">Connectors</div>
            </div>
            <div className="login-brand__stat">
              <div className="login-brand__stat-num">∞</div>
              <div className="login-brand__stat-label">Flows</div>
            </div>
            <div className="login-brand__stat">
              <div className="login-brand__stat-num">99.9%</div>
              <div className="login-brand__stat-label">Uptime SLA</div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Right form panel ── */}
      <div className="login-form-panel">
        <div className="login-form-inner">
          <div className="login-logo">
            <div className="login-logo__mark">S</div>
            <span className="login-logo__name">SangamMW</span>
          </div>

          <h1 className="login-title">Sign in</h1>
          <p className="login-sub">Welcome back to your workspace</p>

          {error && (
            <div className="login-error" role="alert">
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm-.75 4a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0V5zm.75 7a1 1 0 110-2 1 1 0 010 2z"/>
              </svg>
              {error}
            </div>
          )}

          <form className="login-form" onSubmit={handleSubmit}>
            <div className="login-field">
              <label className="login-label" htmlFor="email">Email address</label>
              <input
                id="email"
                className="login-input"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                autoComplete="email"
                autoFocus
              />
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="password">Password</label>
              <input
                id="password"
                className="login-input"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••••"
                required
                autoComplete="current-password"
              />
            </div>

            <div className="login-forgot">
              <a href="#forgot">Forgot password?</a>
            </div>

            <button className="login-btn login-btn--primary" type="submit" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in →'}
            </button>
          </form>

          <div className="login-divider"><span>or continue with</span></div>

          <button className="login-btn login-btn--oauth" type="button" onClick={handleGoogle}>
            <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden="true">
              <path fill="#4285F4" d="M43.6 20.5H24v7h11.3c-1 5.2-5.5 8.9-11.3 8.9-6.6 0-12-5.4-12-12s5.4-12 12-12c3 0 5.8 1.1 7.9 3l5.2-5.2C33.7 7.2 29.1 5 24 5 12.9 5 4 13.9 4 25s8.9 20 20 20c11 0 19.5-7.7 19.5-20 0-1.2-.1-2.4-.4-3.5z"/>
            </svg>
            Continue with Google
          </button>

          <p className="login-saml">
            Using SSO?{' '}
            <a href="/api/v1/auth/saml/login" className="login-link">Sign in with SAML</a>
          </p>

          <div className="login-footer">
            © 2026 SangamMW · Enterprise Integration Platform
          </div>
        </div>
      </div>
    </div>
  )
}
