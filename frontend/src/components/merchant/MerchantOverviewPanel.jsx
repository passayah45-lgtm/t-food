import { useTranslation } from 'react-i18next'
import { usePreferences } from '../../context/PreferencesContext'
import { formatCurrency, formatNumber } from '../../lib/formatters'

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
  const money = value => formatCurrency(value, summary?.currency || summary?.currency_code || 'GNF', preferences)
  const integer = value => formatNumber(value, preferences, { maximumFractionDigits: 0 })

  return (
    <section className="grid grid-cols-2 lg:grid-cols-3 gap-3 py-6 border-b border-gray-200">
      <div className="border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-500">{t('merchantDashboard.overview.totalOrders')}</p>
        <p className="text-2xl font-bold mt-1">{integer(summary?.total_orders || 0)}</p>
      </div>
      <div className="border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-500">{t('merchantDashboard.overview.openOrders')}</p>
        <p className="text-2xl font-bold mt-1">{integer(summary?.open_orders || 0)}</p>
      </div>
      <div className="border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-500">{t('operations.grossSales')}</p>
        <p className="text-xl font-bold mt-1">{money(summary?.gross_sales || 0)}</p>
      </div>
      <div className="border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-500">{t('merchantDashboard.overview.netEarnings')}</p>
        <p className="text-xl font-bold mt-1 text-emerald-700">{money(summary?.merchant_earnings || 0)}</p>
      </div>
      <div className="border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-500">{t('partner.availablePayout')}</p>
        <p className="text-xl font-bold mt-1 text-emerald-700">{money(summary?.available_payout || 0)}</p>
      </div>
      <div className="border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-500">{t('operations.paidPayouts')}</p>
        <p className="text-xl font-bold mt-1">{money(summary?.paid_payout || 0)}</p>
      </div>
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
          <button type="button" onClick={() => setActiveTab('menu')} className="btn-secondary py-2 px-3 text-sm">{t('merchantDashboard.overview.manageMenu')}</button>
          <button type="button" onClick={() => setActiveTab('profile')} className="btn-secondary py-2 px-3 text-sm">{t('merchantDashboard.overview.storeSettings')}</button>
        </div>
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
      <div className="border border-gray-200 rounded-lg p-4 lg:col-span-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm text-gray-500">{t('merchantDashboard.overview.customerReviews', { defaultValue: 'Customer reviews' })}</p>
            <p className="text-xs text-gray-500 mt-1">{t('merchantDashboard.overview.customerReviewsHelp', { defaultValue: 'Recent customer feedback for your store.' })}</p>
          </div>
          <span className="text-sm font-semibold">{integer(merchantReviews.length)}</span>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {merchantReviews.slice(0, 4).map(review => {
            const pendingPhotoCount = (review.photos || []).filter(photo => photo.status !== 'APPROVED').length
            const approvedPhotos = (review.photos || []).filter(photo => photo.status === 'APPROVED' && photo.image_url)
            return (
              <article key={review.id} className="rounded-lg border border-gray-200 p-3 text-sm">
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
                        className="h-16 w-16 rounded-md object-cover border border-gray-200"
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
    </section>
  )
}
