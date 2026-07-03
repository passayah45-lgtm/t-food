import { useState } from 'react'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { ArrowLeft, Mail } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { requestPasswordReset } from '../api/auth'
import InputField from '../components/ui/InputField'
import useTitle from '../hooks/useTitle'

export default function ForgotPasswordPage() {
  const { t } = useTranslation()
  useTitle(t('passwordReset.resetTitle'))
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)

  const submit = async event => {
    event.preventDefault()
    setLoading(true)
    try {
      await requestPasswordReset(email)
      setSent(true)
      toast.success(t('passwordReset.requestReceived'))
    } catch {
      toast.error(t('passwordReset.requestFailed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <Link to="/login" className="inline-flex items-center gap-2 text-sm text-brand-600 mb-6">
          <ArrowLeft size={16} /> {t('passwordReset.backToSignIn')}
        </Link>
        <div className="card p-7">
          <Mail className="text-brand-600 mb-4" />
          <h1 className="text-2xl font-bold text-gray-950">{t('passwordReset.resetHeading')}</h1>
          {sent ? (
            <p className="text-gray-600 mt-3">{t('passwordReset.checkEmail')}</p>
          ) : (
            <form onSubmit={submit} className="mt-6 space-y-4">
              <InputField required type="email" label={t('passwordReset.accountEmail')} value={email} onChange={event => setEmail(event.target.value)} />
              <button disabled={loading} className="btn-primary w-full">
                {loading ? t('passwordReset.sending') : t('passwordReset.sendLink')}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
