import { useEffect, useRef, useState } from 'react'
import { Navigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { Camera, Save, ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import {
  changePassword,
  getAccountAvatar,
  getPartnerProfile,
  updateAccountAvatar,
  updatePartnerProfile,
} from '../api/auth'
import {
  getMerchantProfile,
  updateMerchantProfile,
} from '../api/merchant'
import { useAuth } from '../context/AuthContext'
import InputField from '../components/ui/InputField'
import PasswordField from '../components/ui/PasswordField'
import useTitle from '../hooks/useTitle'

export default function AccountPage() {
  const { t } = useTranslation()
  useTitle(t('account.title'))
  const { user, role } = useAuth()
  const fileRef = useRef()
  const [profile, setProfile] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [avatarFile, setAvatarFile] = useState(null)
  const [avatarPreview, setAvatarPreview] = useState(null)
  const [savingAvatar, setSavingAvatar] = useState(false)
  const [passwords, setPasswords] = useState({ old_password: '', new_password: '', confirm: '' })
  const [passwordError, setPasswordError] = useState('')
  const [hasUsablePassword, setHasUsablePassword] = useState(Boolean(user?.has_usable_password))
  const hasBusinessProfile = role === 'merchant' || role === 'partner'

  useEffect(() => {
    setHasUsablePassword(Boolean(user?.has_usable_password))
  }, [user?.has_usable_password])

  useEffect(() => {
    let alive = true

    if (role === 'customer') {
      setLoading(false)
      return () => { alive = false }
    }

    const loadProfile = hasBusinessProfile
      ? (role === 'partner' ? getPartnerProfile : getMerchantProfile)
      : async () => ({ data: {} })

    Promise.all([getAccountAvatar(), loadProfile()])
      .then(([avatarResponse, profileResponse]) => {
        if (!alive) return
        setAvatarPreview(avatarResponse.data.avatar || null)
        setProfile(profileResponse.data)
      })
      .catch(() => toast.error(t('account.loadFailed')))
      .finally(() => {
        if (alive) setLoading(false)
      })

    return () => { alive = false }
  }, [hasBusinessProfile, role, t])

  if (role === 'customer') {
    return <Navigate to="/profile" replace />
  }

  const saveProfile = async event => {
    event.preventDefault()
    if (!hasBusinessProfile) return
    setSaving(true)
    try {
      const update = role === 'partner' ? updatePartnerProfile : updateMerchantProfile
      const { data } = await update(profile)
      setProfile(data)
      toast.success(t('account.updated'))
    } catch {
      toast.error(t('account.updateFailed'))
    } finally {
      setSaving(false)
    }
  }

  const handleAvatarChange = event => {
    const file = event.target.files?.[0]
    if (!file) return
    setAvatarFile(file)
    setAvatarPreview(URL.createObjectURL(file))
  }

  const saveAvatar = async event => {
    event.preventDefault()
    if (!avatarFile) return
    setSavingAvatar(true)
    try {
      const data = new FormData()
      data.append('avatar', avatarFile)
      const response = await updateAccountAvatar(data)
      setAvatarFile(null)
      setAvatarPreview(response.data.avatar || null)
      toast.success(t('account.photoUpdated'))
    } catch {
      toast.error(t('account.photoUpdateFailed'))
    } finally {
      setSavingAvatar(false)
    }
  }

  const savePassword = async event => {
    event.preventDefault()
    setPasswordError('')
    if (passwords.new_password !== passwords.confirm) {
      setPasswordError(t('auth.passwordsDoNotMatch'))
      return
    }
    try {
      await changePassword({
        old_password: hasUsablePassword ? passwords.old_password : '',
        new_password: passwords.new_password,
      })
      setHasUsablePassword(true)
      setPasswords({ old_password: '', new_password: '', confirm: '' })
      toast.success(t('account.passwordUpdated'))
    } catch (error) {
      const data = error.response?.data
      setPasswordError(data?.old_password || data?.new_password?.[0] || t('account.passwordUpdateFailed'))
    }
  }

  if (loading) {
    return <div className="max-w-2xl mx-auto px-4 py-10 text-gray-500">{t('account.loading')}</div>
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-10">
      <div className="mb-7">
        <h1 className="text-2xl font-bold text-gray-950">{t('account.title')}</h1>
        <p className="text-gray-500 mt-1">{user?.email} · @{user?.username}</p>
      </div>

      {(role === 'merchant' || role === 'partner') && (
        <section className={`mb-6 border rounded-lg p-5 ${profile.is_verified ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'}`}>
          <div className="flex items-start gap-3">
            <div className={`h-10 w-10 rounded-lg flex items-center justify-center ${profile.is_verified ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
              <ShieldCheck size={20} />
            </div>
            <div>
              <p className={`font-semibold ${profile.is_verified ? 'text-emerald-950' : 'text-amber-950'}`}>
                {profile.is_verified ? t('account.verifiedTfoodAccount') : t('account.verificationPending')}
              </p>
              <p className={`text-sm mt-1 ${profile.is_verified ? 'text-emerald-800' : 'text-amber-800'}`}>
                {role === 'merchant'
                  ? (profile.is_verified
                    ? t('account.merchantVerifiedBody')
                    : t('account.merchantPendingBody'))
                  : (profile.is_verified
                    ? t('account.partnerVerifiedBody')
                    : t('account.partnerPendingBody'))}
              </p>
            </div>
          </div>
        </section>
      )}

      <section className="card p-6 mb-6">
        <div className="flex flex-col sm:flex-row sm:items-start gap-5">
          <div className="relative flex-shrink-0">
            <div className="h-20 w-20 rounded-full bg-brand-100 flex items-center justify-center overflow-hidden border-2 border-brand-200">
              {avatarPreview
                ? <img src={avatarPreview} alt="avatar" className="h-full w-full object-cover" />
                : <span className="text-3xl font-bold text-brand-600">{user?.first_name?.[0] || user?.username?.[0]}</span>
              }
            </div>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="absolute -bottom-1 -right-1 bg-brand-500 text-white p-1.5 rounded-full hover:bg-brand-600 transition-colors"
              aria-label={t('account.choosePhoto')}
            >
              <Camera size={12} />
            </button>
            <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={handleAvatarChange} />
          </div>
          <div className="flex-1">
            <h2 className="font-semibold text-lg text-gray-950">{t('account.accountPhoto')}</h2>
            <p className="text-sm text-gray-500 mt-1">{t('account.accountPhotoHelp')}</p>
            {avatarFile && (
              <form onSubmit={saveAvatar} className="mt-4">
                <button disabled={savingAvatar} className="btn-primary inline-flex items-center gap-2">
                  <Save size={16} /> {savingAvatar ? t('account.saving') : t('account.savePhoto')}
                </button>
              </form>
            )}
          </div>
        </div>
      </section>

      {hasBusinessProfile && (
      <form onSubmit={saveProfile} className="card p-6 space-y-4 mb-6">
        <div className="flex items-center justify-between gap-4">
          <h2 className="font-semibold text-gray-950">{role === 'partner' ? t('account.deliveryProfile') : t('account.businessProfile')}</h2>
          {(role === 'merchant' || role === 'partner') && (
            <span className={`inline-flex items-center gap-2 text-sm ${profile.is_verified ? 'text-emerald-700' : 'text-amber-700'}`}>
              <ShieldCheck size={16} /> {profile.is_verified ? t('account.verified') : t('account.approvalPending')}
            </span>
          )}
        </div>
        {role === 'partner' ? (
          <>
            <InputField label={t('account.displayName')} value={profile.partner_name || ''} onChange={event => setProfile(current => ({ ...current, partner_name: event.target.value }))} />
            <InputField label={t('account.phone')} value={profile.partner_phone || ''} onChange={event => setProfile(current => ({ ...current, partner_phone: event.target.value }))} />
            <InputField label={t('account.transport')} value={profile.transport_details || ''} onChange={event => setProfile(current => ({ ...current, transport_details: event.target.value }))} />
          </>
        ) : (
          <>
            <InputField label={t('account.businessName')} value={profile.business_name || ''} onChange={event => setProfile(current => ({ ...current, business_name: event.target.value }))} />
            <InputField label={t('account.phone')} value={profile.phone || ''} onChange={event => setProfile(current => ({ ...current, phone: event.target.value }))} />
          </>
        )}
        <button disabled={saving} className="btn-primary inline-flex items-center gap-2">
          <Save size={16} /> {saving ? t('account.saving') : t('account.saveDetails')}
        </button>
      </form>
      )}

      <form onSubmit={savePassword} className="card p-6 space-y-4">
        <h2 className="font-semibold text-gray-950">{hasUsablePassword ? t('account.changePassword') : t('account.setPassword')}</h2>
        {!hasUsablePassword && (
          <p className="text-sm text-gray-500">{t('account.setPasswordHelp')}</p>
        )}
        {hasUsablePassword && (
          <PasswordField required label={t('account.currentPassword')} value={passwords.old_password} onChange={event => setPasswords(current => ({ ...current, old_password: event.target.value }))} />
        )}
        <PasswordField required label={t('account.newPassword')} value={passwords.new_password} onChange={event => setPasswords(current => ({ ...current, new_password: event.target.value }))} error={passwordError} />
        <PasswordField required label={t('auth.confirmPassword')} value={passwords.confirm} onChange={event => setPasswords(current => ({ ...current, confirm: event.target.value }))} />
        <button className="btn-primary">{t('account.updatePassword')}</button>
      </form>
    </div>
  )
}
