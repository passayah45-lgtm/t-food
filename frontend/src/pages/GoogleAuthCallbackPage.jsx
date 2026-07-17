import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext'
import Spinner from '../components/ui/Spinner'
import useTitle from '../hooks/useTitle'

function safeNext(value) {
  if (!value || !value.startsWith('/') || value.startsWith('//')) return ''
  return value
}

function roleDestination(data, next) {
  if (next) return next
  if (data.role === 'admin') return '/operations'
  if (data.role === 'partner') return '/partner/dashboard'
  if (data.role === 'merchant') return '/merchant/dashboard'
  return '/'
}

export default function GoogleAuthCallbackPage() {
  const { t } = useTranslation()
  useTitle(t('auth.googleCompleting'))
  const { completeOAuthLogin } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    const complete = async () => {
      const params = new URLSearchParams(window.location.hash.replace(/^#/, ''))
      const access = params.get('access')
      const refresh = params.get('refresh')
      const error = params.get('error')
      const next = safeNext(params.get('next'))
      window.history.replaceState(null, '', '/auth/google/callback')

      if (error === 'role_required') {
        toast.error(t('auth.googleRoleRequired'))
        navigate('/register', { replace: true })
        return
      }

      if (!access || !refresh) {
        toast.error(t('auth.googleLoginFailed'))
        navigate('/login', { replace: true })
        return
      }

      try {
        const data = await completeOAuthLogin({ access, refresh })
        toast.success(t('auth.welcomeBack', { name: data.user.first_name || data.user.username }))
        navigate(roleDestination(data, next), { replace: true })
      } catch {
        toast.error(t('auth.googleLoginFailed'))
        navigate('/login', { replace: true })
      }
    }

    complete()
  }, [completeOAuthLogin, navigate, t])

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-50 to-orange-50 flex items-center justify-center p-4">
      <div className="card p-8 text-center">
        <Spinner size="lg" />
        <p className="mt-4 text-sm font-semibold text-gray-700">{t('auth.googleCompleting')}</p>
      </div>
    </div>
  )
}
