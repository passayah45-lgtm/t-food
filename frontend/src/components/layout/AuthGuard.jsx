import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import Spinner from '../ui/Spinner'

export function RequireAuth({ children, role }) {
  const { user, role: userRole, authContext, loading } = useAuth()
  const location = useLocation()

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <Spinner size="lg" />
    </div>
  )
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />
  const hasRequiredRole = !role || userRole === role || (role === 'admin' && authContext?.is_operations_user)
  if (!hasRequiredRole) return <Navigate to="/" replace />
  return children
}

export function RequireGuest({ children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  if (user) return <Navigate to="/" replace />
  return children
}
