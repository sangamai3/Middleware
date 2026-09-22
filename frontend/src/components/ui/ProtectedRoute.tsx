import { Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import type { UserRole } from '@/store/authStore'

interface Props {
  children: React.ReactNode
  minRole?: UserRole
}

export function ProtectedRoute({ children, minRole = 'viewer' }: Props) {
  const { isAuthenticated, hasRole } = useAuthStore()
  const location = useLocation()

  if (!isAuthenticated()) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (!hasRole(minRole)) {
    return (
      <div className="auth-denied">
        <h2>Access denied</h2>
        <p>You need at least the <strong>{minRole}</strong> role to view this page.</p>
      </div>
    )
  }

  return <>{children}</>
}
