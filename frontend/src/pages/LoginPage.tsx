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
      <div className="login-card">
        <div className="login-logo">
          <span className="login-logo__mark">S</span>
          <span className="login-logo__name">SangamMW</span>
        </div>
        <h1 className="login-title">Sign in</h1>
        <p className="login-sub">Open-source iPaaS · Integration Platform</p>

        {error && <div className="login-error" role="alert">{error}</div>}

        <form className="login-form" onSubmit={handleSubmit}>
          <label className="login-label" htmlFor="email">Email</label>
          <input
            id="email"
            className="login-input"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="dev@example.com"
            required
            autoComplete="email"
          />

          <label className="login-label" htmlFor="password">Password</label>
          <input
            id="password"
            className="login-input"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="••••••••"
            required
            autoComplete="current-password"
          />

          <button className="login-btn login-btn--primary" type="submit" disabled={loading}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <div className="login-divider"><span>or</span></div>

        <button className="login-btn login-btn--oauth" type="button" onClick={handleGoogle}>
          <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
            <path fill="#4285F4" d="M43.6 20.5H24v7h11.3c-1 5.2-5.5 8.9-11.3 8.9-6.6 0-12-5.4-12-12s5.4-12 12-12c3 0 5.8 1.1 7.9 3l5.2-5.2C33.7 7.2 29.1 5 24 5 12.9 5 4 13.9 4 25s8.9 20 20 20c11 0 19.5-7.7 19.5-20 0-1.2-.1-2.4-.4-3.5-1.1 0-.5-1-.5-1z"/>
          </svg>
          Continue with Google
        </button>

        <p className="login-saml">
          Using SSO?{' '}
          <a href="/api/v1/auth/saml/login" className="login-link">Sign in with SAML</a>
        </p>
      </div>
    </div>
  )
}
