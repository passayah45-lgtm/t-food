import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext'
import GoogleAuthButton from '../components/auth/GoogleAuthButton'
import InputField from '../components/ui/InputField'
import PasswordField from '../components/ui/PasswordField'
import Spinner from '../components/ui/Spinner'
import useTitle from '../hooks/useTitle'

export default function LoginPage() {
  const { t } = useTranslation()
  useTitle(t('auth.loginTitle'))
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname || '/'

  const [form, setForm] = useState({ username: '', password: '' })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const [googleEnabled, setGoogleEnabled] = useState(false)

  const set = field => e => setForm(f => ({ ...f, [field]: e.target.value }))

  const validate = () => {
    const nextErrors = {}
    if (!form.username.trim()) nextErrors.username = t('auth.usernameRequired')
    if (!form.password) nextErrors.password = t('auth.passwordRequired')
    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const handleSubmit = async e => {
    e.preventDefault()
    if (!validate()) return
    setLoading(true)
    try {
      const data = await login(form)
      toast.success(t('auth.welcomeBack', { name: data.user.first_name || data.user.username }))
      const destination = data.role === 'admin'
        ? '/operations'
        : data.role === 'partner'
          ? '/partner/dashboard'
          : data.role === 'merchant' ? '/merchant/dashboard' : from
      navigate(destination, { replace: true })
    } catch (err) {
      const msg = err.response?.data?.detail || t('auth.invalidLogin')
      toast.error(msg)
      setErrors({ password: msg })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-50 to-orange-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center gap-2 text-2xl font-bold text-brand-600">
            T-Food
          </Link>
          <p className="mt-2 text-sm font-medium text-black">{t('auth.signInSubtitle')}</p>
        </div>

        <div className="card p-8">
          <GoogleAuthButton next={from} onAvailabilityChange={setGoogleEnabled} />
          {googleEnabled && (
            <div className="my-5 flex items-center gap-3">
              <div className="h-px flex-1 bg-gray-200" />
              <span className="text-xs font-semibold text-gray-500">{t('auth.orContinueWith')}</span>
              <div className="h-px flex-1 bg-gray-200" />
            </div>
          )}
          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            <InputField
              label={t('auth.username')}
              placeholder="tfood.partner"
              value={form.username}
              onChange={set('username')}
              error={errors.username}
              autoComplete="username"
            />
            <PasswordField
              label={t('auth.password')}
              placeholder="Your T-Food password"
              value={form.password}
              onChange={set('password')}
              error={errors.password}
              autoComplete="current-password"
            />

            <div className="flex justify-end">
              <Link to="/forgot-password" className="text-sm text-brand-600 hover:underline">
                {t('auth.forgotPassword')}
              </Link>
            </div>

            <button type="submit" disabled={loading} className="btn-primary flex items-center justify-center gap-2 w-full py-3 text-base">
              {loading ? <><Spinner size="sm" /> {t('auth.signingIn')}</> : t('common.signIn')}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-gray-500">
            {t('auth.dontHaveAccount')}{' '}
            <Link to="/register" className="text-brand-600 font-medium hover:underline">
              {t('auth.createOne')}
            </Link>
          </div>
        </div>

        <p className="text-center text-xs font-medium text-black mt-6">
          {t('auth.termsPrefix')}{' '}
          <a href="#" className="font-semibold text-black underline">{t('auth.terms')}</a> {t('auth.and')}{' '}
          <a href="#" className="font-semibold text-black underline">{t('auth.privacyPolicy')}</a>
        </p>
      </div>
    </div>
  )
}
