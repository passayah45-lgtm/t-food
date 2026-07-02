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
  const { preferences } = usePreferences()
  const money = value => formatCurrency(value, summary?.currency || summary?.currency_code || 'INR', preferences)
  const integer = value => formatNumber(value, preferences, { maximumFractionDigits: 0 })

  return (
    <section className="grid grid-cols-2 lg:grid-cols-3 gap-3 py-6 border-b border-gray-200">
      <div className="border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-500">Total orders</p>
        <p className="text-2xl font-bold mt-1">{integer(summary?.total_orders || 0)}</p>
      </div>
      <div className="border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-500">Open orders</p>
        <p className="text-2xl font-bold mt-1">{integer(summary?.open_orders || 0)}</p>
      </div>
      <div className="border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-500">Gross sales</p>
        <p className="text-xl font-bold mt-1">{money(summary?.gross_sales || 0)}</p>
      </div>
      <div className="border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-500">Net earnings</p>
        <p className="text-xl font-bold mt-1 text-emerald-700">{money(summary?.merchant_earnings || 0)}</p>
      </div>
      <div className="border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-500">Available payout</p>
        <p className="text-xl font-bold mt-1 text-emerald-700">{money(summary?.available_payout || 0)}</p>
      </div>
      <div className="border border-gray-200 rounded-lg p-4">
        <p className="text-sm text-gray-500">Paid payouts</p>
        <p className="text-xl font-bold mt-1">{money(summary?.paid_payout || 0)}</p>
      </div>
      <div className="border border-gray-200 rounded-lg p-4 lg:col-span-2">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm text-gray-500">Store status</p>
            <p className={`text-xl font-bold mt-1 ${restaurant.is_open ? 'text-emerald-700' : 'text-amber-700'}`}>
              {restaurant.is_open ? 'Open for orders' : 'Paused'}
            </p>
            <p className="text-sm text-gray-500 mt-2">{integer(restaurant.estimated_prep_minutes)} min prep - {integer(unavailableItems.length)} unavailable items</p>
          </div>
          <button onClick={toggleStore} className={restaurant.is_open ? 'btn-secondary' : 'btn-primary'}>
            {restaurant.is_open ? 'Pause' : 'Open'}
          </button>
        </div>
        <div className="flex flex-wrap gap-2 mt-4">
          <button type="button" onClick={() => setActiveTab('orders')} className="btn-secondary py-2 px-3 text-sm">View orders</button>
          <button type="button" onClick={() => setActiveTab('menu')} className="btn-secondary py-2 px-3 text-sm">Manage menu</button>
          <button type="button" onClick={() => setActiveTab('profile')} className="btn-secondary py-2 px-3 text-sm">Store settings</button>
        </div>
      </div>
      <div className="border border-gray-200 rounded-lg p-4 lg:col-span-1">
        <p className="text-sm text-gray-500">Unread notifications</p>
        <p className="text-2xl font-bold mt-1">{integer(merchantNotifications?.unread_count || 0)}</p>
        <div className="mt-3 space-y-2">
          {(merchantNotifications?.results || []).slice(0, 3).map(notification => (
            <div key={notification.id} className="text-sm">
              <p className="font-medium text-gray-800 truncate">{notification.title}</p>
              <p className="text-xs text-gray-500 truncate">{notification.message}</p>
            </div>
          ))}
          {!merchantNotifications?.results?.length && <p className="text-sm text-gray-500">No notifications yet.</p>}
        </div>
      </div>
    </section>
  )
}
