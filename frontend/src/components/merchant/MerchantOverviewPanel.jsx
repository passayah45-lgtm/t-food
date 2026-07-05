import { useTranslation } from 'react-i18next'
import { usePreferences } from '../../context/PreferencesContext'
import { formatCurrency, formatNumber } from '../../lib/formatters'

export default function MerchantOverviewPanel({
  summary,
  restaurant,
  unavailableItems,
  merchantNotifications,
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
    </section>
  )
}
