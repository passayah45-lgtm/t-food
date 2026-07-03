import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { LocateFixed, MapPin, Pencil, Plus, Save, Star, Trash2, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import {
  createAddress,
  deleteAddress,
  listAddresses,
  updateAddress,
} from '../api/auth'

const emptyAddress = {
  label: 'HOME',
  recipient_name: '',
  phone: '',
  address: '',
  instructions: '',
  latitude: null,
  longitude: null,
  is_default: false,
}

export default function AddressBook({ defaultName = '', defaultPhone = '' }) {
  const { t } = useTranslation()
  const [addresses, setAddresses] = useState([])
  const [form, setForm] = useState(emptyAddress)
  const [editingId, setEditingId] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [locating, setLocating] = useState(false)

  const load = () => listAddresses()
    .then(({ data }) => setAddresses(data.results || data))
    .catch(() => toast.error(t('address.loadFailed')))

  useEffect(() => { load() }, [])

  const startCreate = () => {
    setEditingId(null)
    setForm({ ...emptyAddress, recipient_name: defaultName, phone: defaultPhone })
    setShowForm(true)
  }

  const startEdit = address => {
    setEditingId(address.id)
    setForm({
      label: address.label,
      recipient_name: address.recipient_name,
      phone: address.phone,
      address: address.address,
      instructions: address.instructions || '',
      latitude: address.latitude,
      longitude: address.longitude,
      is_default: address.is_default,
    })
    setShowForm(true)
  }

  const locate = () => {
    if (!navigator.geolocation) return toast.error(t('checkout.locationUnsupported'))
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      position => {
        setForm(current => ({
          ...current,
          latitude: position.coords.latitude.toFixed(6),
          longitude: position.coords.longitude.toFixed(6),
        }))
        setLocating(false)
        toast.success(t('address.preciseLocationAdded'))
      },
      () => {
        setLocating(false)
        toast.error(t('checkout.locationFailed'))
      },
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  const submit = async event => {
    event.preventDefault()
    setSaving(true)
    try {
      if (editingId) await updateAddress(editingId, form)
      else await createAddress(form)
      toast.success(editingId ? t('address.updated') : t('address.saved'))
      setShowForm(false)
      setEditingId(null)
      await load()
    } catch (error) {
      const data = error.response?.data
      toast.error(typeof data === 'string' ? data : data?.non_field_errors?.[0] || data?.detail || t('address.saveFailed'))
    } finally {
      setSaving(false)
    }
  }

  const remove = async address => {
    if (!window.confirm(t('address.deleteConfirm', { label: address.label_display }))) return
    try {
      await deleteAddress(address.id)
      toast.success(t('address.deleted'))
      await load()
    } catch {
      toast.error(t('address.deleteFailed'))
    }
  }

  const makeDefault = async address => {
    try {
      await updateAddress(address.id, { is_default: true })
      await load()
    } catch {
      toast.error(t('address.defaultFailed'))
    }
  }

  return (
    <section className="mb-6">
      <div className="flex items-center justify-between gap-4 mb-4">
        <div>
          <h2 className="font-semibold text-gray-950">{t('address.savedAddresses')}</h2>
          <p className="text-sm text-gray-500">{t('address.chooseFaster')}</p>
        </div>
        {!showForm && (
          <button type="button" onClick={startCreate} className="btn-secondary inline-flex items-center gap-2">
            <Plus size={16} /> {t('address.addAddress')}
          </button>
        )}
      </div>

      {showForm && (
        <form onSubmit={submit} className="card p-5 mb-4 grid sm:grid-cols-2 gap-4">
          <select className="input-field" value={form.label} onChange={event => setForm(current => ({ ...current, label: event.target.value }))}>
            <option value="HOME">{t('address.home')}</option>
            <option value="WORK">{t('address.work')}</option>
            <option value="OTHER">{t('address.other')}</option>
          </select>
          <input required maxLength={100} className="input-field" placeholder="T-Food Customer" value={form.recipient_name} onChange={event => setForm(current => ({ ...current, recipient_name: event.target.value }))} />
          <input required type="tel" maxLength={15} className="input-field" placeholder="+224 620 00 00 00" value={form.phone} onChange={event => setForm(current => ({ ...current, phone: event.target.value }))} />
          <button type="button" onClick={locate} disabled={locating} className="btn-secondary inline-flex items-center justify-center gap-2">
            <LocateFixed size={16} /> {locating ? t('address.locating') : form.latitude ? t('checkout.locationAdded') : t('checkout.addPreciseLocation')}
          </button>
          <textarea required maxLength={500} rows={3} className="input-field resize-none sm:col-span-2" placeholder="Camayenne, Kaloum, Conakry" value={form.address} onChange={event => setForm(current => ({ ...current, address: event.target.value }))} />
          <input maxLength={300} className="input-field sm:col-span-2" placeholder="Ask the T-Food rider to call near the gate" value={form.instructions} onChange={event => setForm(current => ({ ...current, instructions: event.target.value }))} />
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input type="checkbox" checked={form.is_default} onChange={event => setForm(current => ({ ...current, is_default: event.target.checked }))} />
            {t('address.useAsDefault')}
          </label>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary inline-flex items-center gap-2"><X size={16} /> {t('common.cancel')}</button>
            <button disabled={saving} className="btn-primary inline-flex items-center gap-2"><Save size={16} /> {saving ? t('account.saving') : t('common.save')}</button>
          </div>
        </form>
      )}

      <div className="grid sm:grid-cols-2 gap-3">
        {addresses.map(address => (
          <article key={address.id} className="card p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-semibold flex items-center gap-2"><MapPin size={16} /> {address.label_display}</p>
                <p className="text-sm text-gray-700 mt-2">{address.recipient_name} · {address.phone}</p>
                <p className="text-sm text-gray-500 mt-1 break-words">{address.address}</p>
                {address.instructions && <p className="text-xs text-gray-500 mt-2">{address.instructions}</p>}
              </div>
              {address.is_default && <Star size={17} className="text-amber-500 fill-amber-500 flex-shrink-0" />}
            </div>
            <div className="flex items-center gap-2 mt-4 border-t border-gray-100 pt-3">
              {!address.is_default && <button type="button" onClick={() => makeDefault(address)} className="text-xs font-medium text-brand-600">{t('address.setDefault')}</button>}
              <button type="button" onClick={() => startEdit(address)} className="ml-auto p-2 text-gray-500 hover:text-gray-900" title={t('address.editAddress')}><Pencil size={16} /></button>
              <button type="button" onClick={() => remove(address)} className="p-2 text-gray-500 hover:text-red-600" title={t('address.deleteAddress')}><Trash2 size={16} /></button>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
