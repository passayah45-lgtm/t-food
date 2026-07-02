import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { Save, ShieldCheck } from 'lucide-react'
import {
  changePassword,
  getPartnerProfile,
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
  useTitle('Account settings')
  const { user, role } = useAuth()
  const [profile, setProfile] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [passwords, setPasswords] = useState({ old_password: '', new_password: '', confirm: '' })
  const [passwordError, setPasswordError] = useState('')

  useEffect(() => {
    if (role === 'customer') {
      setLoading(false)
      return
    }
    const load = role === 'partner' ? getPartnerProfile : getMerchantProfile
    load()
      .then(({ data }) => setProfile(data))
      .catch(() => toast.error('Could not load account details.'))
      .finally(() => setLoading(false))
  }, [role])

  if (role === 'customer') {
    return <Navigate to="/profile" replace />
  }

  const saveProfile = async event => {
    event.preventDefault()
    setSaving(true)
    try {
      const update = role === 'partner' ? updatePartnerProfile : updateMerchantProfile
      const { data } = await update(profile)
      setProfile(data)
      toast.success('Account details updated')
    } catch {
      toast.error('Could not update account details.')
    } finally {
      setSaving(false)
    }
  }

  const savePassword = async event => {
    event.preventDefault()
    setPasswordError('')
    if (passwords.new_password !== passwords.confirm) {
      setPasswordError('Passwords do not match')
      return
    }
    try {
      await changePassword({
        old_password: passwords.old_password,
        new_password: passwords.new_password,
      })
      setPasswords({ old_password: '', new_password: '', confirm: '' })
      toast.success('Password updated')
    } catch (error) {
      const data = error.response?.data
      setPasswordError(data?.old_password || data?.new_password?.[0] || 'Could not update password.')
    }
  }

  if (loading) {
    return <div className="max-w-2xl mx-auto px-4 py-10 text-gray-500">Loading account...</div>
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-10">
      <div className="mb-7">
        <h1 className="text-2xl font-bold text-gray-950">Account settings</h1>
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
                {profile.is_verified ? 'Verified T-Food account' : 'Verification pending'}
              </p>
              <p className={`text-sm mt-1 ${profile.is_verified ? 'text-emerald-800' : 'text-amber-800'}`}>
                {role === 'merchant'
                  ? (profile.is_verified
                    ? 'Your storefront can appear in the marketplace and receive customer orders.'
                    : 'Upload owner identity documents from the merchant dashboard. T-Food operations will approve the account before it becomes public.')
                  : (profile.is_verified
                    ? 'You can go available, claim eligible deliveries, and update delivery progress.'
                    : 'Upload your partner profile photo and identity or license document from the partner dashboard before live delivery work starts.')}
              </p>
            </div>
          </div>
        </section>
      )}

      <form onSubmit={saveProfile} className="card p-6 space-y-4 mb-6">
        <div className="flex items-center justify-between gap-4">
          <h2 className="font-semibold text-gray-950">{role === 'partner' ? 'Delivery profile' : 'Business profile'}</h2>
          {(role === 'merchant' || role === 'partner') && (
            <span className={`inline-flex items-center gap-2 text-sm ${profile.is_verified ? 'text-emerald-700' : 'text-amber-700'}`}>
              <ShieldCheck size={16} /> {profile.is_verified ? 'Verified' : 'Approval pending'}
            </span>
          )}
        </div>
        {role === 'partner' ? (
          <>
            <InputField label="Display name" value={profile.partner_name || ''} onChange={event => setProfile(current => ({ ...current, partner_name: event.target.value }))} />
            <InputField label="Phone" value={profile.partner_phone || ''} onChange={event => setProfile(current => ({ ...current, partner_phone: event.target.value }))} />
            <InputField label="Transport" value={profile.transport_details || ''} onChange={event => setProfile(current => ({ ...current, transport_details: event.target.value }))} />
          </>
        ) : (
          <>
            <InputField label="Business name" value={profile.business_name || ''} onChange={event => setProfile(current => ({ ...current, business_name: event.target.value }))} />
            <InputField label="Phone" value={profile.phone || ''} onChange={event => setProfile(current => ({ ...current, phone: event.target.value }))} />
          </>
        )}
        <button disabled={saving} className="btn-primary inline-flex items-center gap-2">
          <Save size={16} /> {saving ? 'Saving...' : 'Save details'}
        </button>
      </form>

      <form onSubmit={savePassword} className="card p-6 space-y-4">
        <h2 className="font-semibold text-gray-950">Change password</h2>
        <PasswordField required label="Current password" value={passwords.old_password} onChange={event => setPasswords(current => ({ ...current, old_password: event.target.value }))} />
        <PasswordField required label="New password" value={passwords.new_password} onChange={event => setPasswords(current => ({ ...current, new_password: event.target.value }))} error={passwordError} />
        <PasswordField required label="Confirm password" value={passwords.confirm} onChange={event => setPasswords(current => ({ ...current, confirm: event.target.value }))} />
        <button className="btn-primary">Update password</button>
      </form>
    </div>
  )
}
