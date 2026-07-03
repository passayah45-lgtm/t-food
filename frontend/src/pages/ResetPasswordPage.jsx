import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import { KeyRound } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { confirmPasswordReset } from '../api/auth'
import PasswordField from '../components/ui/PasswordField'
import useTitle from '../hooks/useTitle'

export default function ResetPasswordPage() {
  const { t } = useTranslation()
  useTitle(t('passwordReset.chooseTitle'))
  const { uid, token } = useParams()
  const navigate = useNavigate()
  const [form, setForm] = useState({ password: '', confirm: '' })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)

  const submit = async event => {
    event.preventDefault()
    if (form.password !== form.confirm) {
      setErrors({ confirm: t('auth.passwordsDoNotMatch') })
      return
    }
    setLoading(true)
    try {
      await confirmPasswordReset({ uid, token, password: form.password })
      toast.success(t('passwordReset.resetSuccess'))
      navigate('/login', { replace: true })
    } catch (error) {
      setErrors({
        password: error.response?.data?.password?.[0]
          || error.response?.data?.detail
          || t('passwordReset.resetFailed'),
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="card p-7 w-full max-w-md">
        <KeyRound className="text-brand-600 mb-4" />
        <h1 className="text-2xl font-bold text-gray-950">{t('passwordReset.chooseHeading')}</h1>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <PasswordField required label={t('account.newPassword')} value={form.password} onChange={event => setForm(current => ({ ...current, password: event.target.value }))} error={errors.password} />
          <PasswordField required label={t('auth.confirmPassword')} value={form.confirm} onChange={event => setForm(current => ({ ...current, confirm: event.target.value }))} error={errors.confirm} />
          <button disabled={loading} className="btn-primary w-full">{loading ? t('account.updating') : t('account.updatePassword')}</button>
        </form>
        <Link to="/login" className="block text-center text-sm text-brand-600 mt-5">{t('passwordReset.returnToSignIn')}</Link>
      </div>
    </div>
  )
}
