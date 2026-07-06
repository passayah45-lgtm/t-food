import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { login as apiLogin, register as apiRegister, logout as apiLogout, getMe } from '../api/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null)
  const [role, setRole]       = useState(null)
  const [authContext, setAuthContext] = useState({})
  const [loading, setLoading] = useState(true)

  const applyAuthData = useCallback((data = {}) => {
    setUser(data.user || null)
    setRole(data.role || null)
    setAuthContext({
      is_operations_user: Boolean(data.is_operations_user),
      operations_role: data.operations_role || '',
      operations_status: data.operations_status || '',
      operations_permissions: data.operations_permissions || [],
      is_merchant_owner: Boolean(data.is_merchant_owner),
      is_merchant_staff: Boolean(data.is_merchant_staff),
      is_delivery_partner: data.role === 'partner',
    })
  }, [])

  const bootstrap = useCallback(async () => {
    const token = localStorage.getItem('access_token')
    if (!token) { setLoading(false); return }
    try {
      const { data } = await getMe()
      applyAuthData(data)
    } catch {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      setUser(null)
      setRole(null)
      setAuthContext({})
    } finally {
      setLoading(false)
    }
  }, [applyAuthData])

  useEffect(() => { bootstrap() }, [bootstrap])

  const login = async (credentials) => {
    const { data } = await apiLogin(credentials)
    localStorage.setItem('access_token',  data.access)
    localStorage.setItem('refresh_token', data.refresh)
    applyAuthData(data)
    return data
  }

  const register = async (payload) => {
    const { data } = await apiRegister(payload)
    localStorage.setItem('access_token',  data.access)
    localStorage.setItem('refresh_token', data.refresh)
    applyAuthData(data)
    return data
  }

  const logout = async () => {
    try {
      const refresh = localStorage.getItem('refresh_token')
      await apiLogout({ refresh })
    } catch { /* ignore */ }
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setUser(null)
    setRole(null)
    setAuthContext({})
  }

  return (
    <AuthContext.Provider value={{ user, role, authContext, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
