import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { usePreferences } from '../../context/PreferencesContext'
import { formatCurrency, formatNumber } from '../../lib/formatters'
import TfoodAssistantPanel from '../assistant/TfoodAssistantPanel'

function OverviewStat({ label, value, accent = 'text-gray-950', onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="border border-gray-200 rounded-lg p-4 text-left transition hover:border-brand-300 hover:bg-brand-50/40 focus:outline-none focus:ring-2 focus:ring-brand-500"
    >
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`text-xl font-bold mt-1 ${accent}`}>{value}</p>
    </button>
  )
}

export default function MerchantOverviewPanel({
  summary,
  restaurant,
  unavailableItems,
  merchantNotifications,
  merchantReviews = [],
  toggleStore,
  setActiveTab,
}) {
  const { t } = useTranslation()
  const { preferences } = usePreferences()
  const [showReviews, setShowReviews] = useState(false)
  const money = value => formatCurrency(value, summary?.currency || summary?.currency_code || 'GNF', preferences)
  const integer = value => formatNumber(value, preferences, { maximumFractionDigits: 0 })
  const positiveReviews = merchantReviews.filter(review => Number(review.rating) >= 4)
  const neutralReviews = merchantReviews.filter(review => Number(review.rating) === 3)
  const negativeReviews = merchantReviews.filter(review => Number(review.rating) <= 2)
  const imageReviews = merchantReviews.filter(review => (review.photos || []).length)

  return (
    <section className="grid grid-cols-2 lg:grid-cols-3 gap-3 py-6 border-b border-gray-200">
      <OverviewStat label={t('merchantDashboard.overview.totalOrders')} value={integer(summary?.total_orders || 0)} onClick={() => setActiveTab('orders')} />
      <OverviewStat label={t('merchantDashboard.overview.openOrders')} value={integer(summary?.open_orders || 0)} onClick={() => setActiveTab('orders')} />
      <OverviewStat label={t('operations.grossSales')} value={money(summary?.gross_sales || 0)} onClick={() => setActiveTab('revenue')} />
      <OverviewStat label={t('merchantDashboard.overview.netEarnings')} value={money(summary?.merchant_earnings || 0)} accent="text-emerald-700" onClick={() => setActiveTab('revenue')} />
      <OverviewStat label={t('partner.availablePayout')} value={money(summary?.available_payout || 0)} accent="text-emerald-700" onClick={() => setActiveTab('payouts')} />
      <OverviewStat label={t('operations.paidPayouts')} value={money(summary?.paid_payout || 0)} onClick={() => setActiveTab('payouts')} />
      <div className="border border-gray-200 rounded-lg p-4 lg:col-span-2">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm text-gray-500">{t('merchantDashboard.overview.storeStatus')}</p>
            <p className={`text-xl font-bold mt-1 ${restaurant.is_open ? 'text-emerald-700' : 'text-amber-700'}`}>
              {restaurant.is_open ? t('merchantDashboard.overview.openForOrders') : t('merchantDashboard.overview.paused')}
            </p>
            <p className="text-sm text-gray-500 mt-2">{t('merchantDashboard.overview.prepUnavailable', { minutes: integer(restaurant.estimated_prep_minutes), count: integer(unavailableItems.length) })}</p>
          </div>
          <button onClick={toggleStore} className={restaurant.is_open ? 'btn-secondary' : 'btn-primary'}>
            {restaurant.is_open ? t('merchantDashboard.overview.pause') : t('merchantDashboard.overview.open')}
          </button>
        </div>
        <div className="flex flex-wrap gap-2 mt-4">
          <button type="button" onClick={() => setActiveTab('orders')} className="btn-secondary py-2 px-3 text-sm">{t('merchantDashboard.overview.viewOrders')}</button>
          <button type="button" onClick={() => setShowReviews(current => !current)} className="btn-secondary py-2 px-3 text-sm">
            {showReviews
              ? t('merchantDashboard.overview.hideReviews', { defaultValue: 'Hide reviews' })
              : t('merchantDashboard.overview.viewReviews', { defaultValue: 'View reviews' })}
          </button>
          <button type="button" onClick={() => setActiveTab('menu')} className="btn-secondary py-2 px-3 text-sm">{t('merchantDashboard.overview.manageMenu')}</button>
          <button type="button" onClick={() => setActiveTab('profile')} className="btn-secondary py-2 px-3 text-sm">{t('merchantDashboard.overview.storeSettings')}</button>
        </div>
        {showReviews && (
          <div className="mt-4 rounded-lg border border-gray-200 p-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-gray-950">
                  {t('merchantDashboard.overview.customerReviews', { defaultValue: 'Customer reviews' })}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {t('merchantDashboard.overview.customerReviewsHelp', { defaultValue: 'Recent customer feedback for your store.' })}
                </p>
              </div>
              <span className="text-sm font-semibold">{integer(merchantReviews.length)}</span>
            </div>
            <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-800">
                <p className="font-semibold">{integer(positiveReviews.length)}</p>
                <p>{t('merchantDashboard.overview.positiveReviews', { defaultValue: 'Positive' })}</p>
              </div>
              <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-gray-700">
                <p className="font-semibold">{integer(neutralReviews.length)}</p>
                <p>{t('merchantDashboard.overview.neutralReviews', { defaultValue: 'Neutral' })}</p>
              </div>
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-700">
                <p className="font-semibold">{integer(negativeReviews.length)}</p>
                <p>{t('merchantDashboard.overview.negativeReviews', { defaultValue: 'Negative' })}</p>
              </div>
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-amber-800">
                <p className="font-semibold">{integer(imageReviews.length)}</p>
                <p>{t('merchantDashboard.overview.imageReviews', { defaultValue: 'Image reviews' })}</p>
              </div>
            </div>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {merchantReviews.slice(0, 4).map(review => {
                const pendingPhotoCount = (review.photos || []).filter(photo => photo.status !== 'APPROVED').length
                const approvedPhotos = (review.photos || []).filter(photo => photo.status === 'APPROVED' && photo.image_url)
                return (
                  <article key={review.id} className="rounded-md border border-gray-200 p-3 text-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-gray-950">{review.customer_name}</p>
                        <p className="text-xs text-gray-500">{review.branch_name}</p>
                      </div>
                      <span className="text-amber-600 font-semibold">★ {review.rating}</span>
                    </div>
                    {review.comment && <p className="mt-2 text-gray-700">{review.comment}</p>}
                    {!!approvedPhotos.length && (
                      <div className="mt-3 flex gap-2 overflow-x-auto">
                        {approvedPhotos.map(photo => (
                          <img
                            key={photo.id}
                            src={photo.image_url}
                            alt=""
                            className="h-14 w-14 rounded-md object-cover border border-gray-200"
                          />
                        ))}
                      </div>
                    )}
                    {!!pendingPhotoCount && (
                      <p className="mt-2 text-xs text-amber-700">
                        {t('merchantDashboard.overview.pendingReviewPhotos', {
                          count: pendingPhotoCount,
                          defaultValue: '{{count}} photo pending moderation',
                        })}
                      </p>
                    )}
                  </article>
                )
              })}
              {!merchantReviews.length && (
                <p className="text-sm text-gray-500">{t('merchantDashboard.overview.noCustomerReviews', { defaultValue: 'No customer reviews yet.' })}</p>
              )}
            </div>
          </div>
        )}
      </div>
      <div className="border border-gray-200 rounded-lg p-4 lg:col-span-1">
        <p className="text-sm text-gray-500">{t('merchantDashboard.overview.unreadNotifications')}</p>
        <p className="text-2xl font-bold mt-1">{integer(merchantNotifications?.unread_count || 0)}</p>
        <div className="mt-3 space-y-2">
          {(merchantNotifications?.results || []).slice(0, 3).map(notification => (
            <div key={notification.id} className="text-sm">
              <p className="font-medium text-gray-800 truncate">{notification.title}</p>
              <p className="text-xs text-gray-500 truncate">{notification.message}</p>
            </div>
          ))}
          {!merchantNotifications?.results?.length && <p className="text-sm text-gray-500">{t('merchantDashboard.overview.noNotifications')}</p>}
        </div>
      </div>
      <div className="lg:col-span-3">
        <TfoodAssistantPanel surface="merchant" compact />
      </div>
    </section>
  )
}
