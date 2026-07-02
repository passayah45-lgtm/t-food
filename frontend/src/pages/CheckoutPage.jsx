import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { ArrowLeft, BadgePercent, LocateFixed, MapPin, Phone } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { getProfile, listAddresses } from '../api/auth'
import { createOrder, validateOffer } from '../api/orders'
import { useCart } from '../context/CartContext'
import useTitle from '../hooks/useTitle'

export default function CheckoutPage() {
  const { t } = useTranslation()
  useTitle(t('checkout.title'))
  const navigate = useNavigate()
  const { items, totalAmount, clearCart } = useCart()
  const [clientOrderId] = useState(() => {
    const signature = items
      .map(item => `${item.lineId}:${item.qty}`)
      .sort()
      .join('|')
    try {
      const saved = JSON.parse(sessionStorage.getItem('tfood_checkout') || 'null')
      if (saved?.signature === signature && saved?.id) return saved.id
    } catch {
      // Replace malformed checkout state with a fresh identifier.
    }
    const id = crypto.randomUUID()
    sessionStorage.setItem('tfood_checkout', JSON.stringify({ id, signature }))
    return id
  })
  const [form, setForm] = useState({
    delivery_address: '',
    delivery_instructions: '',
    contact_phone: '',
    latitude: null,
    longitude: null,
  })
  const [loadingProfile, setLoadingProfile] = useState(true)
  const [addresses, setAddresses] = useState([])
  const [selectedAddressId, setSelectedAddressId] = useState(null)
  const [locating, setLocating] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [offerCode, setOfferCode] = useState('')
  const [offer, setOffer] = useState(null)
  const [applyingOffer, setApplyingOffer] = useState(false)

  useEffect(() => {
    Promise.all([getProfile(), listAddresses()])
      .then(([profileResponse, addressResponse]) => {
        const profile = profileResponse.data
        const saved = addressResponse.data.results || addressResponse.data
        const selected = saved.find(address => address.is_default) || saved[0]
        setAddresses(saved)
        setSelectedAddressId(selected?.id || null)
        setForm(current => ({
          ...current,
          delivery_address: selected?.address || profile.address || '',
          delivery_instructions: selected?.instructions || '',
          contact_phone: selected?.phone || profile.phone || '',
          latitude: selected?.latitude || null,
          longitude: selected?.longitude || null,
        }))
      })
      .catch(() => toast.error(t('checkout.loadDetailsFailed')))
      .finally(() => setLoadingProfile(false))
  }, [])

  const selectAddress = address => {
    setSelectedAddressId(address?.id || null)
    if (!address) return
    setForm(current => ({
      ...current,
      delivery_address: address.address,
      delivery_instructions: address.instructions || '',
      contact_phone: address.phone,
      latitude: address.latitude,
      longitude: address.longitude,
    }))
  }

  useEffect(() => {
    if (!items.length) return
    validateOffer({
      offer_code: '',
      items: items.map(item => ({ food_id: item.id, quantity: item.qty, option_ids: item.optionIds || [] })),
    })
      .then(({ data }) => setOffer(data))
      .catch(() => setOffer(null))
  }, [items])

  const useCurrentLocation = () => {
    if (!navigator.geolocation) {
      toast.error(t('checkout.locationUnsupported'))
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      position => {
        setForm(current => ({
          ...current,
          latitude: position.coords.latitude.toFixed(6),
          longitude: position.coords.longitude.toFixed(6),
        }))
        setLocating(false)
        toast.success(t('checkout.locationAdded'))
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
    setSubmitting(true)
    try {
      const { data } = await createOrder({
        ...form,
        client_order_id: clientOrderId,
        offer_code: offer?.offer_code || '',
        items: items.map(item => ({ food_id: item.id, quantity: item.qty, option_ids: item.optionIds || [] })),
      })
      sessionStorage.removeItem('tfood_checkout')
      clearCart()
      toast.success(t('checkout.orderCreated', { id: data.id }))
      navigate(`/orders/${data.id}/payment`)
    } catch (error) {
      const response = error.response?.data
      const firstError = response && Object.values(response).flat()[0]
      toast.error(firstError || t('checkout.createOrderFailed'))
    } finally {
      setSubmitting(false)
    }
  }

  const applyOffer = async () => {
    if (!offerCode.trim()) return
    setApplyingOffer(true)
    try {
      const { data } = await validateOffer({
        offer_code: offerCode.trim(),
        items: items.map(item => ({ food_id: item.id, quantity: item.qty, option_ids: item.optionIds || [] })),
      })
      setOffer(data)
      setOfferCode(data.offer_code)
      toast.success(t('checkout.discountApplied', { percent: data.discount_percent }))
    } catch (error) {
      setOffer(null)
      toast.error(error.response?.data?.offer_code?.[0] || t('checkout.offerFailed'))
    } finally {
      setApplyingOffer(false)
    }
  }

  if (!items.length) return <Navigate to="/cart" replace />

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-10">
      <Link to="/cart" className="inline-flex items-center gap-2 text-sm font-medium text-brand-600 mb-6">
        <ArrowLeft size={16} /> {t('checkout.backToCart')}
      </Link>
      <div className="grid lg:grid-cols-[1fr_300px] gap-6">
        <form onSubmit={submit}>
          <h1 className="text-2xl font-bold text-gray-950">{t('checkout.deliveryDetails')}</h1>
          <p className="text-gray-500 mt-1 mb-6">{t('checkout.deliveryDetailsBody')}</p>

          <div className="space-y-4">
            {addresses.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">{t('checkout.savedAddresses')}</p>
                <div className="grid sm:grid-cols-2 gap-2">
                  {addresses.map(address => (
                    <button
                      key={address.id}
                      type="button"
                      onClick={() => selectAddress(address)}
                      className={`text-left border p-3 rounded-lg ${selectedAddressId === address.id ? 'border-brand-500 bg-brand-50' : 'border-gray-200 bg-white'}`}
                    >
                      <span className="text-sm font-semibold">{address.label_display}</span>
                      <span className="block text-xs text-gray-500 mt-1 line-clamp-2">{address.address}</span>
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => setSelectedAddressId(null)}
                    className={`text-left border p-3 rounded-lg ${selectedAddressId === null ? 'border-brand-500 bg-brand-50' : 'border-gray-200 bg-white'}`}
                  >
                    <span className="text-sm font-semibold">{t('checkout.useAnotherAddress')}</span>
                    <span className="block text-xs text-gray-500 mt-1">{t('checkout.enterDetailsBelow')}</span>
                  </button>
                </div>
              </div>
            )}
            <div>
              <label className="text-sm font-medium text-gray-700 flex items-center gap-2 mb-1">
                <MapPin size={15} /> {t('checkout.deliveryAddress')}
              </label>
              <textarea
                required
                rows={4}
                maxLength={500}
                disabled={loadingProfile}
                className="input-field resize-none"
                value={form.delivery_address}
                onChange={event => {
                  setSelectedAddressId(null)
                  setForm(current => ({ ...current, delivery_address: event.target.value }))
                }}
                placeholder="Camayenne, Kaloum, Conakry"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 flex items-center gap-2 mb-1">
                <Phone size={15} /> {t('checkout.contactPhone')}
              </label>
              <input
                required
                type="tel"
                maxLength={15}
                disabled={loadingProfile}
                className="input-field"
                value={form.contact_phone}
                onChange={event => setForm(current => ({ ...current, contact_phone: event.target.value }))}
                placeholder="+224 620 00 00 00"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">{t('checkout.deliveryInstructions')}</label>
              <input
                maxLength={300}
                className="input-field"
                value={form.delivery_instructions}
                onChange={event => setForm(current => ({ ...current, delivery_instructions: event.target.value }))}
                placeholder="Ask the T-Food rider to call near the gate"
              />
            </div>
            <button type="button" onClick={useCurrentLocation} disabled={locating} className="btn-secondary inline-flex items-center gap-2">
              <LocateFixed size={16} />
              {locating ? t('checkout.findingLocation') : form.latitude ? t('checkout.locationAdded') : t('checkout.addPreciseLocation')}
            </button>
            <div>
              <label className="text-sm font-medium text-gray-700 flex items-center gap-2 mb-1">
                <BadgePercent size={15} /> {t('checkout.promoCode')}
              </label>
              <div className="flex gap-2">
                <input
                  value={offerCode}
                  onChange={event => {
                    setOfferCode(event.target.value.toUpperCase())
                    setOffer(null)
                  }}
                  className="input-field"
                  placeholder={t('checkout.promoPlaceholder')}
                />
                <button type="button" onClick={applyOffer} disabled={applyingOffer} className="btn-secondary">
                  {applyingOffer ? t('checkout.checking') : t('checkout.apply')}
                </button>
              </div>
            </div>
          </div>

          <button type="submit" disabled={submitting || loadingProfile} className="btn-primary mt-7">
            {submitting ? t('checkout.creatingOrder') : t('checkout.continueToPayment')}
          </button>
        </form>

        <aside className="card p-5 h-fit">
          <h2 className="font-semibold text-gray-950 mb-4">{t('checkout.orderSummary')}</h2>
          <div className="space-y-3">
            {items.map(item => (
              <div key={item.lineId} className="flex justify-between gap-4 text-sm">
                <span className="text-gray-600">{item.name} x {item.qty}{item.options?.length ? <small className="block">{item.options.map(option => option.name).join(', ')}</small> : null}</span>
                <span>Rs. {(item.price * item.qty).toFixed(2)}</span>
              </div>
            ))}
          </div>
          <div className="border-t border-gray-100 mt-4 pt-4 flex justify-between font-semibold">
            <span>{t('cart.subtotal')}</span>
            <span>Rs. {totalAmount.toFixed(2)}</span>
          </div>
          {offer?.offer_code && (
            <div className="flex justify-between text-sm text-emerald-700 mt-2">
              <span>{offer.offer_code}</span>
              <span>- Rs. {Number(offer.discount_amount).toFixed(2)}</span>
            </div>
          )}
          <div className="flex justify-between text-sm text-gray-600 mt-2">
            <span>{t('checkout.deliveryFee')}</span>
            <span>Rs. {Number(offer?.delivery_fee || 0).toFixed(2)}</span>
          </div>
          <div className="flex justify-between font-semibold text-lg mt-3">
            <span>{t('cart.total')}</span>
            <span>Rs. {Number(offer?.total_amount ?? totalAmount).toFixed(2)}</span>
          </div>
        </aside>
      </div>
    </div>
  )
}
