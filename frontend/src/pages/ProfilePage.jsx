import { useEffect, useState, useRef } from 'react'
import { toast } from 'react-hot-toast'
import { Award, Camera, Save } from 'lucide-react'
import { getProfile, updateProfile, changePassword } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import InputField from '../components/ui/InputField'
import PasswordField from '../components/ui/PasswordField'
import Spinner from '../components/ui/Spinner'
import AddressBook from '../components/AddressBook'
import useTitle from '../hooks/useTitle'

export default function ProfilePage() {
  useTitle('My profile')
  const { user } = useAuth()
  const fileRef = useRef()

  const [profile, setProfile] = useState({ phone: '', address: '', avatar: null, loyalty_points: 0 })
  const [preview, setPreview] = useState(null)
  const [saving, setSaving] = useState(false)
  const [loadingProfile, setLoadingProfile] = useState(true)

  const [pwForm, setPwForm] = useState({ old_password: '', new_password: '', confirm: '' })
  const [pwErrors, setPwErrors] = useState({})
  const [pwSaving, setPwSaving] = useState(false)

  useEffect(() => {
    let alive = true

    const loadProfile = async () => {
      try {
        const { data } = await getProfile()
        if (!alive) return
        setProfile({
          phone: data.phone || '',
          address: data.address || '',
          avatar: null,
          loyalty_points: data.loyalty_points || 0,
        })
        setPreview(data.avatar || null)
      } catch {
        toast.error('Failed to load profile')
      } finally {
        if (alive) setLoadingProfile(false)
      }
    }

    loadProfile()
    return () => { alive = false }
  }, [])

  const handleAvatarChange = e => {
    const file = e.target.files[0]
    if (!file) return
    setProfile(p => ({ ...p, avatar: file }))
    setPreview(URL.createObjectURL(file))
  }

  const handleSaveProfile = async e => {
    e.preventDefault()
    setSaving(true)
    try {
      const fd = new FormData()
      fd.append('phone', profile.phone)
      fd.append('address', profile.address)
      if (profile.avatar instanceof File) fd.append('avatar', profile.avatar)
      await updateProfile(fd)
      toast.success('Profile updated!')
    } catch {
      toast.error('Failed to update profile')
    } finally {
      setSaving(false)
    }
  }

  const handleChangePassword = async e => {
    e.preventDefault()
    const nextErrors = {}
    if (!pwForm.old_password) nextErrors.old_password = 'Required'
    if (!pwForm.new_password || pwForm.new_password.length < 8) nextErrors.new_password = 'At least 8 characters'
    if (pwForm.new_password !== pwForm.confirm) nextErrors.confirm = 'Passwords do not match'
    setPwErrors(nextErrors)
    if (Object.keys(nextErrors).length) return

    setPwSaving(true)
    try {
      await changePassword({ old_password: pwForm.old_password, new_password: pwForm.new_password })
      toast.success('Password changed!')
      setPwForm({ old_password: '', new_password: '', confirm: '' })
    } catch (err) {
      const msg = err.response?.data?.old_password || 'Failed to change password'
      setPwErrors({ old_password: msg })
      toast.error(msg)
    } finally {
      setPwSaving(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold mb-8">My profile</h1>

      {loadingProfile && (
        <div className="mb-6 flex items-center gap-2 text-sm text-gray-500">
          <Spinner size="sm" /> Loading profile...
        </div>
      )}

      <div className="bg-emerald-50 border border-emerald-100 rounded-lg p-4 mb-6 flex items-center gap-4">
        <div className="h-10 w-10 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center">
          <Award size={21} />
        </div>
        <div>
          <p className="text-sm text-emerald-700">Loyalty balance</p>
          <p className="text-xl font-bold text-emerald-950">{profile.loyalty_points} points</p>
        </div>
      </div>

      <div className="card p-6 mb-6">
        <div className="flex items-start gap-5 mb-6">
          <div className="relative flex-shrink-0">
            <div className="h-20 w-20 rounded-full bg-brand-100 flex items-center justify-center overflow-hidden border-2 border-brand-200">
              {preview
                ? <img src={preview} alt="avatar" className="h-full w-full object-cover" />
                : <span className="text-3xl font-bold text-brand-600">{user?.first_name?.[0] || user?.username?.[0]}</span>
              }
            </div>
            <button
              type="button"
              onClick={() => fileRef.current.click()}
              className="absolute -bottom-1 -right-1 bg-brand-500 text-white p-1.5 rounded-full hover:bg-brand-600 transition-colors"
              aria-label="Choose avatar"
            >
              <Camera size={12} />
            </button>
            <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleAvatarChange} />
          </div>
          <div>
            <h2 className="font-semibold text-lg">{user?.first_name} {user?.last_name}</h2>
            <p className="text-sm text-gray-500">{user?.email}</p>
            <p className="text-xs text-gray-400 mt-1">@{user?.username}</p>
            <p className="text-xs text-gray-500 mt-3 max-w-sm">
              Your customer photo is optional. It helps support recognize your account faster, but T-Food does not require customer identity documents.
            </p>
            {profile.avatar instanceof File && (
              <p className="text-xs text-emerald-700 mt-2">Preview ready. Save changes to upload this photo.</p>
            )}
          </div>
        </div>

        <form onSubmit={handleSaveProfile} className="flex flex-col gap-4">
          <InputField
            label="Phone number"
            placeholder="+224 620 00 00 00"
            value={profile.phone}
            onChange={e => setProfile(p => ({ ...p, phone: e.target.value }))}
            type="tel"
          />
          <button type="submit" disabled={saving} className="btn-primary self-start flex items-center gap-2">
            {saving ? <Spinner size="sm" /> : <Save size={15} />}
            {saving ? 'Saving...' : 'Save changes'}
          </button>
        </form>
      </div>

      <AddressBook
        defaultName={`${user?.first_name || ''} ${user?.last_name || ''}`.trim() || user?.username}
        defaultPhone={profile.phone}
      />

      <div className="card p-6">
        <h3 className="font-semibold mb-4">Change password</h3>
        <form onSubmit={handleChangePassword} className="flex flex-col gap-4">
          <PasswordField
            label="Current password"
            value={pwForm.old_password}
            onChange={e => setPwForm(f => ({ ...f, old_password: e.target.value }))}
            error={pwErrors.old_password}
          />
          <PasswordField
            label="New password"
            value={pwForm.new_password}
            onChange={e => setPwForm(f => ({ ...f, new_password: e.target.value }))}
            error={pwErrors.new_password}
          />
          <PasswordField
            label="Confirm new password"
            value={pwForm.confirm}
            onChange={e => setPwForm(f => ({ ...f, confirm: e.target.value }))}
            error={pwErrors.confirm}
          />
          <button type="submit" disabled={pwSaving} className="btn-primary self-start flex items-center gap-2">
            {pwSaving ? <Spinner size="sm" /> : null}
            {pwSaving ? 'Updating...' : 'Update password'}
          </button>
        </form>
      </div>
    </div>
  )
}
