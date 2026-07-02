import { useEffect, useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Banknote, CreditCard, Smartphone, Wallet } from 'lucide-react'
import { getOrder } from '../api/orders'
import { getPaymentConfig, payForOrder, verifyPayment } from '../api/payments'
import useTitle from '../hooks/useTitle'

const methods = [
  { value: 'COD', label: 'Cash on delivery', icon: Banknote },
  { value: 'UPI', label: 'UPI', icon: Smartphone },
  { value: 'CARD', label: 'Credit or debit card', icon: CreditCard },
  { value: 'WALLET', label: 'Wallet', icon: Wallet },
]

const loadRazorpay = () => new Promise((resolve, reject) => {
  if (window.Razorpay) {
    resolve()
    return
  }
  const script = document.createElement('script')
  script.src = 'https://checkout.razorpay.com/v1/checkout.js'
  script.onload = resolve
  script.onerror = () => reject(new Error('Could not load the secure payment window.'))
  document.body.appendChild(script)
})

export default function PaymentPage() {
  useTitle('Payment')
  const { id } = useParams()
  const navigate = useNavigate()
  const [method, setMethod] = useState('COD')
  const [isPaying, setIsPaying] = useState(false)
  const [secondsRemaining, setSecondsRemaining] = useState(null)
  const { data: order, isLoading, isError } = useQuery({
    queryKey: ['order', id],
    queryFn: async () => (await getOrder(id)).data,
  })
  const { data: paymentConfig } = useQuery({
    queryKey: ['payment-config'],
    queryFn: async () => (await getPaymentConfig()).data,
  })

  useEffect(() => {
    if (!order?.payment_expires_at) return undefined
    const update = () => {
      const remaining = Math.max(
        0,
        Math.ceil((new Date(order.payment_expires_at).getTime() - Date.now()) / 1000),
      )
      setSecondsRemaining(remaining)
    }
    update()
    const timer = window.setInterval(update, 1000)
    return () => window.clearInterval(timer)
  }, [order?.payment_expires_at])

  const handlePayment = async () => {
    setIsPaying(true)
    let paymentWindowOpened = false
    try {
      const { data } = await payForOrder(id, method)
      if (method === 'COD') {
        toast.success('Order confirmed for cash on delivery')
        navigate('/orders')
        return
      }

      await loadRazorpay()
      const checkout = new window.Razorpay({
        key: data.key_id,
        amount: data.amount,
        currency: data.currency,
        name: 'T-Food',
        description: `Order #${data.order_id}`,
        order_id: data.provider_order_id,
        prefill: data.customer,
        handler: async response => {
          setIsPaying(true)
          try {
            await verifyPayment(id, response)
            toast.success('Payment verified and order confirmed')
            navigate('/orders')
          } catch (error) {
            toast.error(error.response?.data?.detail || 'Payment verification failed.')
          } finally {
            setIsPaying(false)
          }
        },
        modal: {
          ondismiss: () => setIsPaying(false),
        },
        theme: { color: '#e11d48' },
      })
      paymentWindowOpened = true
      checkout.open()
    } catch (error) {
      const message = error.response?.data?.method?.[0]
        || error.response?.data?.detail
        || error.message
        || 'Could not start payment.'
      toast.error(message)
    } finally {
      if (!paymentWindowOpened) setIsPaying(false)
    }
  }

  if (isLoading) {
    return <div className="max-w-2xl mx-auto px-4 py-10 text-gray-500">Loading order...</div>
  }
  if (isError || !order) {
    return <div className="max-w-2xl mx-auto px-4 py-10 text-red-500">Could not load this order.</div>
  }
  if (order.status !== 'PLACED' || order.payment?.status === 'SUCCESS') {
    return <Navigate to="/orders" replace />
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-10">
      <div className="mb-6">
        <p className="text-sm font-medium text-brand-600">Order #{order.id}</p>
        <h1 className="text-2xl font-bold text-gray-950 mt-1">Choose payment method</h1>
        <p className="text-gray-500 mt-2">Your order is confirmed only after secure payment verification.</p>
        {secondsRemaining !== null && (
          <p className={`text-sm mt-2 ${secondsRemaining > 120 ? 'text-gray-600' : 'text-red-600 font-medium'}`}>
            Payment window: {Math.floor(secondsRemaining / 60)}:{String(secondsRemaining % 60).padStart(2, '0')}
          </p>
        )}
      </div>

      <div className="space-y-3">
        {methods.map(({ value, label, icon: Icon }) => {
          const disabled = value !== 'COD' && paymentConfig?.online_payments_enabled === false
          return (
          <label
            key={value}
            className={`card p-4 flex items-center gap-4 border-2 ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'} ${method === value ? 'border-brand-500' : 'border-transparent'}`}
          >
            <Icon size={22} className="text-brand-600" />
            <span className="flex-1 font-medium text-gray-800">{label}</span>
            <input
              type="radio"
              name="payment-method"
              value={value}
              checked={method === value}
              disabled={disabled}
              onChange={() => setMethod(value)}
              className="h-4 w-4 accent-brand-500"
            />
            {disabled && <span className="text-xs text-gray-500">Unavailable</span>}
          </label>
          )
        })}
      </div>

      <div className="mt-6 border-t border-gray-200 pt-5 flex items-center justify-between gap-4">
        <div>
          {Number(order.discount_amount) > 0 && (
            <p className="text-sm text-emerald-700 mb-1">
              {order.offer_code}: saved Rs. {Number(order.discount_amount).toFixed(2)}
            </p>
          )}
          <p className="text-sm text-gray-500">Amount</p>
          <p className="text-xl font-bold text-gray-950">Rs. {Number(order.total_amount).toFixed(2)}</p>
        </div>
        <button onClick={handlePayment} disabled={isPaying || secondsRemaining === 0} className="btn-primary">
          {isPaying ? 'Confirming...' : method === 'COD' ? 'Place COD order' : 'Confirm payment'}
        </button>
      </div>
    </div>
  )
}
