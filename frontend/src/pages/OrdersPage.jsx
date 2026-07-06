import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Bike, Clock, CreditCard, Phone, MapPinned, MessageSquarePlus, Package, ReceiptText, ShoppingCart, Store, XCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { cancelOrder, getReorderPreview, listOrders } from '../api/orders'
import { useCart } from '../context/CartContext'
import { usePreferences } from '../context/PreferencesContext'
import { formatCurrency } from '../lib/formatters'
import { statusLabel } from '../lib/statusLabels'
import useTitle from '../hooks/useTitle'

const formatDate = value => new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium',
  timeStyle: 'short',
}).format(new Date(value))

export default function OrdersPage() {
  const { t } = useTranslation()
  useTitle(t('orders.title'))
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { items: cartItems, replaceCart } = useCart()
  const { preferences } = usePreferences()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['orders'],
    queryFn: async () => (await listOrders()).data,
  })

  const orders = data?.results || data || []
  const money = (value, currency = 'GNF') => formatCurrency(value, currency, preferences)

  const cancel = async id => {
    try {
      await cancelOrder(id)
      await queryClient.invalidateQueries({ queryKey: ['orders'] })
      toast.success(t('orders.cancelled'))
    } catch (error) {
      toast.error(error.response?.data?.detail || t('orders.cancelFailed'))
    }
  }

  const reorder = async order => {
    if (cartItems.length && !window.confirm(t('orders.replaceCartConfirm'))) return
    try {
      const { data: preview } = await getReorderPreview(order.id)
      replaceCart(preview.items, preview.restaurant_id)
      if (preview.unavailable_items.length) {
        toast(t('orders.unavailableItems', { items: preview.unavailable_items.join(', ') }))
      } else {
        toast.success(t('orders.cartRebuilt', { id: order.id }))
      }
      navigate('/cart')
    } catch (error) {
      toast.error(error.response?.data?.detail || t('orders.reorderFailed'))
    }
  }

  if (isLoading) {
    return <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 text-gray-500">{t('orders.loading')}</div>
  }
  if (isError) {
    return <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 text-red-500">{t('orders.loadFailed')}</div>
  }

  if (!orders.length) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center">
        <Package size={42} className="text-gray-300 mx-auto mb-4" />
        <h1 className="text-2xl font-bold text-gray-950">{t('orders.emptyTitle')}</h1>
        <p className="text-gray-500 mt-2">{t('orders.emptyBody')}</p>
        <Link to="/search" className="btn-primary inline-flex mt-6">{t('cart.browseRestaurants')}</Link>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-950">{t('orders.title')}</h1>
        <p className="text-gray-500 mt-1">{t('orders.subtitle')}</p>
      </div>

      <div className="space-y-4">
        {orders.map(order => (
          <article key={order.id} className="card p-5">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <ReceiptText size={18} className="text-brand-600" />
                  <h2 className="font-semibold text-gray-950">{t('orders.orderNumber', { id: order.id })}</h2>
                </div>
                <p className="text-sm text-gray-500 mt-2 flex items-center gap-2">
                  <Clock size={15} /> {formatDate(order.created_at)}
                </p>
                <div className="mt-3 space-y-2 text-sm text-gray-600">
                  {order.restaurant && (
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                      <span className="flex items-center gap-2">
                        <Store size={15} className="text-brand-600" />
                        {t('orders.restaurant')}: {order.restaurant.name}
                      </span>
                      {order.restaurant.phone && (
                        <span className="flex items-center gap-2">
                          <Phone size={14} className="text-gray-400" />
                          {order.restaurant.phone}
                        </span>
                      )}
                    </div>
                  )}
                  {order.delivery && (
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                      <span className="flex items-center gap-2">
                        <Bike size={15} className="text-brand-600" />
                        {order.delivery.partner_name || t('orders.findingPartner')}
                      </span>
                      {order.delivery.partner_phone && (
                        <span className="flex items-center gap-2">
                          <Phone size={14} className="text-gray-400" />
                          {order.delivery.partner_phone}
                        </span>
                      )}
                      <span>{t('orders.deliveryStatus', { status: statusLabel(order.delivery.status, t, 'delivery') })}</span>
                    </div>
                  )}
                </div>
              </div>
              <div className="text-left sm:text-right">
                <span className="inline-flex px-3 py-1 rounded-lg bg-brand-50 text-brand-700 text-sm font-medium">
                  {statusLabel(order.status, t, 'orders')}
                </span>
                <p className="font-semibold text-gray-950 mt-2">
                  {money(order.total_amount, order.currency || order.currency_code || 'GNF')}
                </p>
                {order.status === 'PLACED' && (
                  <Link
                    to={`/orders/${order.id}/payment`}
                    className="btn-primary inline-flex items-center gap-2 py-2 px-3 text-sm mt-3"
                  >
                    <CreditCard size={15} /> {t('orders.payNow')}
                  </Link>
                )}
                {order.payment && order.status !== 'CANCELLED' && (
                  <Link
                    to={`/orders/${order.id}`}
                    className="btn-secondary inline-flex items-center gap-2 py-2 px-3 text-sm mt-3"
                  >
                    <MapPinned size={15} /> {t('orders.trackOrder')}
                  </Link>
                )}
                {['PLACED', 'CONFIRMED'].includes(order.status) && (
                  <button onClick={() => cancel(order.id)} className="btn-secondary inline-flex items-center gap-2 py-2 px-3 text-sm mt-3 ml-2 text-red-600">
                    <XCircle size={15} /> {t('common.cancel')}
                  </button>
                )}
                {order.payment?.status === 'REFUNDED' && (
                  <p className="text-sm text-emerald-700 mt-2">{t('orders.paymentRefunded')}</p>
                )}
                {order.status === 'EXPIRED' && (
                  <p className="text-sm text-red-600 mt-2">{t('orders.paymentExpired')}</p>
                )}
                {order.payment?.method === 'COD' && order.payment?.status === 'PENDING' && (
                  <p className="text-sm text-amber-700 mt-2">{t('orders.cashDue')}</p>
                )}
                {order.status === 'DELIVERED' && !order.review && (
                  <Link
                    to={`/restaurants/${order.items[0]?.food.restaurant_id}?reviewOrder=${order.id}`}
                    className="btn-secondary inline-flex items-center gap-2 py-2 px-3 text-sm mt-3 ml-2"
                  >
                    <MessageSquarePlus size={15} /> {t('orders.review')}
                  </Link>
                )}
                <button
                  type="button"
                  onClick={() => reorder(order)}
                  className="btn-secondary inline-flex items-center gap-2 py-2 px-3 text-sm mt-3 ml-2"
                >
                  <ShoppingCart size={15} /> {t('orders.reorder')}
                </button>
              </div>
            </div>

            <div className="mt-4 border-t border-gray-100 pt-4 space-y-2">
              {order.items.map(item => (
                <div key={item.id} className="flex items-center justify-between gap-4 text-sm">
                  <span className="text-gray-700">
                    {item.food.food_name} x {item.quantity}
                    {!!item.selected_options?.length && <small className="block text-gray-500">{item.selected_options.map(option => `${option.group}: ${option.name}`).join(' · ')}</small>}
                  </span>
                  <span className="text-gray-500">
                    {money(item.subtotal, item.currency || item.currency_code || order.currency || order.currency_code || 'GNF')}
                  </span>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>

      <Link to="/search" className="btn-secondary inline-flex items-center gap-2 mt-6">
        <ShoppingCart size={16} /> {t('orders.orderAgain')}
      </Link>
    </div>
  )
}
