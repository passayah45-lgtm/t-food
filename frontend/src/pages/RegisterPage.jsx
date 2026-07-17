import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext'
import GoogleAuthButton from '../components/auth/GoogleAuthButton'
import InputField from '../components/ui/InputField'
import PasswordField from '../components/ui/PasswordField'
import Spinner from '../components/ui/Spinner'
import useTitle from '../hooks/useTitle'

const ROLES = [
  { value: 'customer', labelKey: 'auth.customer', descKey: 'auth.customerDesc', icon: 'C' },
  { value: 'partner', labelKey: 'auth.partner', descKey: 'auth.partnerDesc', icon: 'P' },
  { value: 'merchant', labelKey: 'auth.merchant', descKey: 'auth.merchantDesc', icon: 'M' },
]

export default function RegisterPage() {
  const { t } = useTranslation()
  useTitle(t('common.createAccount'))
  const { register } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const googleRoleMode = searchParams.get('google') === '1'
  const requestedRole = searchParams.get('role')
  const initialRole = ROLES.some(role => role.value === requestedRole)
    ? requestedRole
    : ''

  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    username: '',
    email: '',
    password: '',
    password2: '',
    role: initialRole,
  })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState(googleRoleMode ? 2 : 1)
  const [googleEnabled, setGoogleEnabled] = useState(false)

  const set = field => e => setForm(f => ({ ...f, [field]: e.target.value }))

  const validateStep1 = () => {
    const nextErrors = {}
    if (!form.first_name.trim()) nextErrors.first_name = t('auth.required')
    if (!form.last_name.trim()) nextErrors.last_name = t('auth.required')
    if (!form.username.trim()) nextErrors.username = t('auth.required')
    if (!form.email.trim()) nextErrors.email = t('auth.required')
    else if (!/\S+@\S+\.\S+/.test(form.email)) nextErrors.email = t('auth.invalidEmail')
    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const validateStep2 = () => {
    const nextErrors = {}
    if (!googleRoleMode) {
      if (!form.password) nextErrors.password = t('auth.required')
      else if (form.password.length < 8) nextErrors.password = t('auth.atLeast8')
      if (form.password !== form.password2) nextErrors.password2 = t('auth.passwordsDoNotMatch')
    }
    if (!form.role) nextErrors.role = t('auth.required')
    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const nextStep = () => {
    if (validateStep1()) setStep(2)
  }

  const handleSubmit = async e => {
    e.preventDefault()
    if (googleRoleMode) return
    if (!validateStep2()) return
    setLoading(true)
    try {
      const data = await register(form)
      toast.success(t('auth.welcomeTo', { name: data.user.first_name }))
      const destination = data.role === 'partner'
        ? '/partner/dashboard'
        : data.role === 'merchant' ? '/merchant/dashboard' : '/'
      navigate(destination, { replace: true })
    } catch (err) {
      const errs = err.response?.data || {}
      setErrors(errs)
      if (errs.username || errs.email) setStep(1)
      toast.error(t('auth.fixErrors'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-50 to-orange-50 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center gap-2 text-2xl font-bold text-brand-600">
            T-Food
          </Link>
          <p className="text-gray-500 mt-2 text-sm">{t('auth.createFreeAccount')}</p>
        </div>

        <div className="card p-8">
          <div className="flex items-center gap-3 mb-7">
            {[1, 2].map(n => (
              <div key={n} className="flex items-center gap-2 flex-1">
                <div className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-medium transition-colors
                  ${step >= n ? 'bg-brand-500 text-white' : 'bg-gray-100 text-gray-400'}`}>
                  {n}
                </div>
                <span className={`text-xs font-medium ${step >= n ? 'text-brand-600' : 'text-gray-400'}`}>
                  {n === 1 ? t('auth.yourDetails') : t('auth.passwordAndRole')}
                </span>
                {n < 2 && <div className={`flex-1 h-px ${step > n ? 'bg-brand-300' : 'bg-gray-200'}`} />}
              </div>
            ))}
          </div>

          <form onSubmit={handleSubmit}>
            {step === 1 && (
              <div className="flex flex-col gap-4">
                <div className="grid grid-cols-2 gap-3">
                  <InputField label={t('auth.firstName')} placeholder="T-Food" value={form.first_name} onChange={set('first_name')} error={errors.first_name} />
                  <InputField label={t('auth.lastName')} placeholder="Partner" value={form.last_name} onChange={set('last_name')} error={errors.last_name} />
                </div>
                <InputField label={t('auth.username')} placeholder="tfood.partner" value={form.username} onChange={set('username')} error={errors.username} autoComplete="username" />
                <InputField label={t('auth.email')} placeholder="partner@t-food.gn" value={form.email} onChange={set('email')} error={errors.email} type="email" />
                <button type="button" onClick={nextStep} className="btn-primary w-full py-3 mt-1">{t('common.continue')}</button>
              </div>
            )}

            {step === 2 && (
              <div className="flex flex-col gap-4">
                {!googleRoleMode && (
                  <>
                    <PasswordField label={t('auth.password')} placeholder="Create your T-Food password" value={form.password} onChange={set('password')} error={errors.password} autoComplete="new-password" />
                    <PasswordField label={t('auth.confirmPassword')} placeholder="Repeat your T-Food password" value={form.password2} onChange={set('password2')} error={errors.password2} autoComplete="new-password" />
                  </>
                )}

                <div className="mt-1">
                  <p className="text-sm font-medium text-gray-700 mb-2">{t('auth.wantTo')}</p>
                  {googleRoleMode && (
                    <p className="mb-3 text-sm text-gray-500">{t('auth.googleChooseRole')}</p>
                  )}
                  <div className="grid sm:grid-cols-3 gap-3">
                    {ROLES.map(r => (
                      <button
                        key={r.value}
                        type="button"
                        onClick={() => setForm(f => ({ ...f, role: r.value }))}
                        className={`p-4 rounded-xl border-2 text-left transition-all
                          ${form.role === r.value ? 'border-brand-500 bg-brand-50' : 'border-gray-200 hover:border-gray-300'}`}
                      >
                        <div className="text-sm font-bold mb-1 h-7 w-7 rounded-full bg-gray-100 flex items-center justify-center">{r.icon}</div>
                        <div className="text-sm font-medium">{t(r.labelKey)}</div>
                        <div className="text-xs text-gray-500 mt-0.5">{t(r.descKey)}</div>
                      </button>
                    ))}
                  </div>
                  {errors.role && <p className="mt-2 text-xs text-red-600">{errors.role}</p>}
                </div>

                <div className={`rounded-xl border border-gray-200 p-4 ${googleEnabled && form.role ? '' : 'hidden'}`}>
                  <p className="mb-3 text-sm font-medium text-gray-700">
                    {t('auth.continueWithGoogle')} {form.role === 'partner' ? t('auth.partner') : form.role === 'merchant' ? t('auth.merchant') : t('auth.customer')}
                  </p>
                  <GoogleAuthButton role={form.role} onAvailabilityChange={setGoogleEnabled} />
                  <div className="mt-4 flex items-center gap-3">
                    <div className="h-px flex-1 bg-gray-200" />
                    <span className="text-xs font-semibold text-gray-500">{t('auth.orContinueWith')}</span>
                    <div className="h-px flex-1 bg-gray-200" />
                  </div>
                </div>

                <div className="flex gap-3 mt-1">
                  <button
                    type="button"
                    onClick={() => (googleRoleMode ? navigate('/register', { replace: true }) : setStep(1))}
                    className="btn-secondary flex-1 py-3"
                  >
                    {t('common.back')}
                  </button>
                  {!googleRoleMode && (
                    <button type="submit" disabled={loading} className="btn-primary flex-1 py-3 flex items-center justify-center gap-2">
                      {loading ? <><Spinner size="sm" /> {t('auth.creating')}</> : t('common.createAccount')}
                    </button>
                  )}
                </div>
              </div>
            )}
          </form>

          <div className="mt-6 text-center text-sm text-gray-500">
            {t('auth.alreadyHaveAccount')}{' '}
            <Link to="/login" className="text-brand-600 font-medium hover:underline">{t('common.signIn')}</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
