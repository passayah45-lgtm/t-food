import { Link, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Check, Clock, MapPin, Phone, UserRound } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { getOrder } from '../api/orders'
import useRealtime from '../hooks/useRealtime'
import useTitle from '../hooks/useTitle'

const steps = [
  { status: 'PLACED', labelKey: 'tracking.steps.placed' },
  { status: 'CONFIRMED', labelKey: 'tracking.steps.confirmed' },
  { status: 'PREPARING', labelKey: 'tracking.steps.preparing' },
  { status: 'READY_FOR_PICKUP', labelKey: 'tracking.steps.ready' },
  { status: 'ON_THE_WAY', labelKey: 'tracking.steps.onTheWay' },
  { status: 'DELIVERED', labelKey: 'tracking.steps.delivered' },
]

const formatTime = value => new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium',
  timeStyle: 'short',
}).format(new Date(value))

export default function OrderTrackingPage() {
  const { t } = useTranslation()
  useTitle(t('tracking.title'))
  const { id } = useParams()
  const queryClient = useQueryClient()
  const { data: order, isLoading, isError } = useQuery({
    queryKey: ['order', id],
    queryFn: async () => (await getOrder(id)).data,
    refetchInterval: query => (
      query.state.data?.status === 'DELIVERED' ? false : 5000
    ),
  })
  const realtime = useRealtime({
    onMessage: message => {
      if (
        ['order.status_changed', 'delivery.status_changed'].includes(message?.type)
        && String(message.order_id) === String(id)
      ) {
        queryClient.invalidateQueries({ queryKey: ['order', id] })
      }
    },
  })

  if (isLoading) {
    return <div className="max-w-3xl mx-auto px-4 py-10 text-gray-500">{t('tracking.loading')}</div>
  }
  if (isError || !order) {
    return <div className="max-w-3xl mx-auto px-4 py-10 text-red-500">{t('tracking.loadFailed')}</div>
  }

  const activeIndex = steps.findIndex(step => step.status === order.status)
  const timeline = order.timeline || []
  const location = order.delivery?.current_latitude != null
    ? `${Number(order.delivery.current_latitude).toFixed(5)}, ${Number(order.delivery.current_longitude).toFixed(5)}`
    : null
  const latitude = Number(order.delivery?.current_latitude)
  const longitude = Number(order.delivery?.current_longitude)
  const mapUrl = location
    ? `https://www.openstreetmap.org/export/embed.html?bbox=${longitude - 0.01}%2C${latitude - 0.01}%2C${longitude + 0.01}%2C${latitude + 0.01}&layer=mapnik&marker=${latitude}%2C${longitude}`
    : null

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
      <Link to="/orders" className="inline-flex items-center gap-2 text-sm font-medium text-brand-600 mb-6">
        <ArrowLeft size={16} /> {t('orders.title')}
      </Link>
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-8">
        <div>
          <p className="text-sm font-medium text-brand-600">{t('orders.orderNumber', { id: order.id })}</p>
          <h1 className="text-2xl font-bold text-gray-950 mt-1">{t('tracking.trackDelivery')}</h1>
        </div>
        <div className="flex flex-col sm:items-end gap-2">
          <span className="inline-flex items-center gap-2 bg-gray-100 text-gray-700 px-3 py-2 rounded-lg text-sm">
            <Clock size={15} /> {order.estimated_delivery_at ? t('tracking.estimated', { time: formatTime(order.estimated_delivery_at) }) : t('tracking.updatesEvery')}
          </span>
          <span className="text-xs text-gray-400">
            {realtime.isConnected ? t('tracking.liveConnected') : t('tracking.autoRefresh')}
          </span>
        </div>
      </div>

      <div className="mb-8">
        {steps.map((step, index) => {
          const complete = index <= activeIndex
          const event = [...timeline].reverse().find(item => item.status === step.status)
          return (
            <div key={step.status} className="flex gap-4 min-h-16">
              <div className="flex flex-col items-center">
                <div className={`h-8 w-8 rounded-full flex items-center justify-center border-2 ${complete ? 'bg-brand-500 border-brand-500 text-white' : 'bg-white border-gray-200 text-gray-400'}`}>
                  {complete ? <Check size={16} /> : index + 1}
                </div>
                {index < steps.length - 1 && (
                  <div className={`w-0.5 flex-1 ${index < activeIndex ? 'bg-brand-500' : 'bg-gray-200'}`} />
                )}
              </div>
              <div className="pt-1">
                <p className={`font-medium ${complete ? 'text-gray-950' : 'text-gray-400'}`}>{t(step.labelKey)}</p>
                {step.status === order.status && <p className="text-sm text-brand-600 mt-1">{t('tracking.currentStatus')}</p>}
                {event && (
                  <>
                    <p className="text-sm text-gray-500 mt-1">{formatTime(event.created_at)}</p>
                    <p className="text-xs text-gray-500 mt-1">{event.description}</p>
                  </>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {['CANCELLED', 'EXPIRED'].includes(order.status) && (
        <div className="border border-red-200 bg-red-50 rounded-lg p-4 mb-6">
          <p className="font-medium text-red-800">{order.status === 'EXPIRED' ? t('orders.paymentExpired') : t('orders.cancelled')}</p>
          <p className="text-sm text-red-700 mt-1">{timeline.at(-1)?.description}</p>
        </div>
      )}

      {order.delivery?.confirmation_code && (
        <div className="border border-amber-200 bg-amber-50 rounded-lg p-4 mb-6">
          <p className="text-sm font-medium text-amber-800">{t('tracking.handoffCode')}</p>
          <p className="text-3xl font-bold tracking-widest text-amber-950 mt-1">{order.delivery.confirmation_code}</p>
          <p className="text-sm text-amber-800 mt-2">{t('tracking.handoffHelp')}</p>
        </div>
      )}

      <div className="border-t border-gray-200 pt-6 grid sm:grid-cols-2 gap-5">
        <div>
          <p className="text-sm font-medium text-gray-500 mb-2">{t('checkout.deliveryDetails')}</p>
          <p className="text-sm text-gray-800 flex items-start gap-2"><MapPin size={16} className="mt-0.5 flex-shrink-0" /> {order.delivery_address}</p>
          <p className="text-sm text-gray-800 flex items-center gap-2 mt-2"><Phone size={16} /> {order.contact_phone}</p>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-500 mb-2">{t('tracking.deliveryPartner')}</p>
          <p className="text-sm text-gray-800 flex items-center gap-2"><UserRound size={16} /> {order.delivery?.partner_name || t('tracking.assignmentPending')}</p>
          {location && <p className="text-sm text-gray-500 mt-2">{t('tracking.lastLocation', { location })}</p>}
        </div>
      </div>
      <div className="mt-6 border border-gray-200 rounded-lg overflow-hidden bg-white">
        {mapUrl ? (
          <>
            <iframe title={t('tracking.liveLocationTitle')} src={mapUrl} className="w-full h-72 border-0" />
            <div className="px-4 py-3 flex items-center justify-between gap-3 text-sm">
              <span className="text-emerald-700 font-medium">{t('tracking.livePartnerLocation')}</span>
              <span className="text-gray-500">{location}</span>
            </div>
          </>
        ) : (
          <div className="p-5">
            <p className="font-medium text-gray-900">
              {order.delivery?.partner_name ? t('tracking.partnerAssigned') : t('tracking.searchingPartner')}
            </p>
            <p className="text-sm text-gray-500 mt-1">
              {order.delivery?.partner_name
                ? t('tracking.mapWillAppear')
                : t('tracking.dispatchQueue')}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
