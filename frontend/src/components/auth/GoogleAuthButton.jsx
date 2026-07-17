import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getGoogleAuthConfig } from '../../api/auth'

export default function GoogleAuthButton({ role = '', next = '/', className = '', onAvailabilityChange }) {
  const { t } = useTranslation()
  const [enabled, setEnabled] = useState(false)

  useEffect(() => {
    let alive = true
    getGoogleAuthConfig()
      .then(({ data }) => {
        if (alive) {
          const isEnabled = Boolean(data.enabled)
          setEnabled(isEnabled)
          onAvailabilityChange?.(isEnabled)
        }
      })
      .catch(() => {
        if (alive) {
          setEnabled(false)
          onAvailabilityChange?.(false)
        }
      })
    return () => { alive = false }
  }, [])

  if (!enabled) return null

  const startGoogleLogin = () => {
    const params = new URLSearchParams()
    if (role) params.set('role', role)
    if (next) params.set('next', next)
    window.location.assign(`/api/v1/auth/google/start/?${params.toString()}`)
  }

  return (
    <button
      type="button"
      onClick={startGoogleLogin}
      className={`w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm font-semibold text-gray-900 shadow-sm transition hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-brand-500 ${className}`}
    >
      <span className="inline-flex items-center justify-center gap-3">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-white text-base font-bold text-blue-600 shadow-sm">
          G
        </span>
        {t('auth.continueWithGoogle')}
      </span>
    </button>
  )
}
