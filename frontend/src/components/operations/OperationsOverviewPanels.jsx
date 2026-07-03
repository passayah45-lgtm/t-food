import { useTranslation } from 'react-i18next'
import { statusLabel } from '../../lib/statusLabels'

const OperationsOverviewPanel = ({ operationsSections, selectedRangeLabel }) => (
  <section className="bg-white border border-gray-200 rounded-lg p-5">
    <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-5">
      <div>
        <h2 className="text-lg font-semibold text-gray-950">Operations sections</h2>
        <p className="text-sm text-gray-500 mt-1">Open one section to work only that section's records.</p>
      </div>
    </div>
    <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
      {operationsSections.map(({ view, label, count, detail, icon: Icon, onClick }) => (
        <button
          key={view}
          type="button"
          onClick={onClick}
          className="border border-gray-200 rounded-lg p-4 text-left transition-colors hover:border-brand-300 hover:bg-brand-50/30"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold text-gray-950">{label}</p>
              <p className="text-sm text-gray-500 mt-1">{detail}</p>
            </div>
            <Icon size={19} className="text-brand-600" />
          </div>
          <p className="text-2xl font-bold text-gray-950 mt-4">{count}</p>
          <p className="text-xs text-gray-500 mt-1">Filtered by: {selectedRangeLabel}</p>
        </button>
      ))}
    </div>
  </section>
)

export const PendingActionQueuesPanel = ({
  activeView,
  pendingActionViews,
  setDashboardView,
}) => (
  <section className="bg-white border border-gray-200 rounded-lg p-4">
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold text-gray-950">Pending action queues</h2>
        <p className="text-sm text-gray-500 mt-1">Choose a queue to work its filtered records directly.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {pendingActionViews.map(item => (
          <button
            key={item.view}
            type="button"
            onClick={() => setDashboardView(item.view)}
            className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${activeView === item.view ? 'border-brand-500 bg-brand-50 text-brand-800' : 'border-gray-200 text-gray-600 hover:border-brand-300 hover:bg-brand-50/30'}`}
          >
            {item.count} {item.label.toLowerCase()}
          </button>
        ))}
      </div>
    </div>
  </section>
)

export const FocusedOverviewPanel = ({
  activeView,
  activeRestaurants,
  openOrders,
  revenue,
  availableMerchantPayouts,
  availablePartnerPayouts,
  customers,
  merchants,
  partners,
  pendingMerchants,
  pendingPartners,
  pendingStaff,
  openPendingMerchants,
  openPendingPartners,
  setDashboardView,
  money,
  formatDateTime,
}) => {
  const { t } = useTranslation()
  return (
  <section className="bg-white border border-gray-200 rounded-lg p-5">
    {activeView === 'restaurants' && (
      <div>
        <h2 className="text-lg font-semibold text-gray-950">Active restaurants</h2>
        <p className="text-sm text-gray-500 mt-1">Restaurants currently active in the marketplace.</p>
        {!activeRestaurants.length ? (
          <p className="mt-5 text-sm text-gray-500">No active restaurants found.</p>
        ) : (
          <div className="mt-5 divide-y divide-gray-200 border-y border-gray-200">
            {activeRestaurants.map(restaurant => (
              <div key={restaurant.id} className="py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                  <p className="font-medium text-gray-950">{restaurant.name}</p>
                  <p className="text-sm text-gray-500">{restaurant.city || restaurant.location || 'Location not set'} · {restaurant.merchant_business_name || 'Merchant not set'} · {restaurant.merchant_verified ? 'verified merchant' : 'merchant pending'}</p>
                  <p className="text-xs text-gray-500 mt-1">Delivery radius: {restaurant.delivery_radius_km} km</p>
                </div>
                <span className={`text-xs font-medium px-2 py-1 rounded-full w-fit ${restaurant.is_open ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-600'}`}>
                  {restaurant.is_open ? 'Open' : 'Closed'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    )}

    {activeView === 'orders' && (
      <div>
        <h2 className="text-lg font-semibold text-gray-950">Open orders</h2>
        <p className="text-sm text-gray-500 mt-1">Orders that have not reached delivered, cancelled, or expired state.</p>
        {!openOrders.length ? (
          <p className="mt-5 text-sm text-gray-500">No open orders found.</p>
        ) : (
          <div className="mt-5 space-y-3">
            {openOrders.map(order => (
              <article key={order.id} className="border border-gray-200 rounded-lg p-4">
                <p className="font-medium text-gray-950">Order #{order.id} · {order.restaurant || 'Restaurant not available'}</p>
                <p className="text-sm text-gray-500 mt-1">{order.customer} - {money(order.total_amount)} - {statusLabel(order.status, t, 'orders')}</p>
                <p className="text-xs text-gray-500 mt-2">{t('operations.paymentDeliveryCreated', { payment: statusLabel(order.payment_status, t, 'payments'), delivery: statusLabel(order.delivery_status, t, 'delivery'), created: formatDateTime(order.created_at) })}</p>
              </article>
            ))}
          </div>
        )}
      </div>
    )}

    {activeView === 'revenue' && (
      <div>
        <h2 className="text-lg font-semibold text-gray-950">Revenue breakdown</h2>
        <p className="text-sm text-gray-500 mt-1">Read-only marketplace revenue and payout totals from delivered successful orders.</p>
        <div className="grid md:grid-cols-3 gap-3 mt-5">
          <div className="border border-gray-200 rounded-lg p-4"><p className="text-sm text-gray-500">Gross sales</p><p className="text-2xl font-bold text-gray-950 mt-1">{money(revenue.gross_sales)}</p></div>
          <div className="border border-gray-200 rounded-lg p-4"><p className="text-sm text-gray-500">Merchant earnings</p><p className="text-2xl font-bold text-gray-950 mt-1">{money(revenue.merchant_earnings)}</p></div>
          <div className="border border-gray-200 rounded-lg p-4"><p className="text-sm text-gray-500">Platform revenue</p><p className="text-2xl font-bold text-gray-950 mt-1">{money(revenue.platform_revenue)}</p></div>
          <div className="border border-gray-200 rounded-lg p-4"><p className="text-sm text-gray-500">Delivery fees</p><p className="text-2xl font-bold text-gray-950 mt-1">{money(revenue.delivery_fees)}</p></div>
          <div className="border border-gray-200 rounded-lg p-4"><p className="text-sm text-gray-500">Pending payouts</p><p className="text-2xl font-bold text-gray-950 mt-1">{money(revenue.pending_payouts)}</p></div>
          <div className="border border-gray-200 rounded-lg p-4"><p className="text-sm text-gray-500">Paid payouts</p><p className="text-2xl font-bold text-gray-950 mt-1">{money(revenue.paid_payouts)}</p></div>
        </div>
        <div className="grid md:grid-cols-4 gap-3 mt-3">
          {[
            ['Today', revenue.today],
            ['Last 7 days', revenue.week],
            ['Current month', revenue.month],
            ['Current year', revenue.year],
          ].map(([label, period]) => (
            <div key={label} className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm font-medium text-gray-950">{label}</p>
              <p className="text-sm text-gray-500 mt-2">Sales: {money(period?.gross_sales)}</p>
              <p className="text-sm text-gray-500">Platform: {money(period?.platform_revenue)}</p>
            </div>
          ))}
        </div>
        <p className="text-sm text-gray-500 mt-4">{availableMerchantPayouts.length} merchant settlements and {availablePartnerPayouts.length} partner payouts are currently available for action.</p>
      </div>
    )}

    {activeView === 'customers' && (
      <div>
        <h2 className="text-lg font-semibold text-gray-950">Customer management</h2>
        <p className="text-sm text-gray-500 mt-1">Safe read-only customer list. Passwords are not exposed.</p>
        {!customers.length ? (
          <p className="mt-5 text-sm text-gray-500">No customers found.</p>
        ) : (
          <div className="mt-5 divide-y divide-gray-200 border-y border-gray-200">
            {customers.map(customer => (
              <div key={customer.id} className="py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                  <p className="font-medium text-gray-950">{customer.name}</p>
                  <p className="text-sm text-gray-500">{customer.email || 'No email'} · {customer.phone || 'No phone'}</p>
                  <p className="text-xs text-gray-500 mt-1">{customer.total_orders} orders · Joined {formatDateTime(customer.created_at)}</p>
                </div>
                <span className={`text-xs font-medium px-2 py-1 rounded-full w-fit ${customer.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
                  {customer.is_active ? statusLabel('ACTIVE', t, 'operations') : statusLabel('INACTIVE', t, 'operations')}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    )}

    {activeView === 'merchants' && (
      <div>
        <h2 className="text-lg font-semibold text-gray-950">Merchant management</h2>
        <p className="text-sm text-gray-500 mt-1">Showing all merchants from the existing operations merchant payload. Passwords are not exposed.</p>
        <div className="mt-5 divide-y divide-gray-200 border-y border-gray-200">
          {merchants.map(merchant => (
            <div key={merchant.id} className="py-4">
              <p className="font-medium text-gray-950">{merchant.business_name || merchant.owner_name || merchant.username}</p>
              <p className="text-sm text-gray-500 mt-1">{merchant.owner_name} · @{merchant.username} · {merchant.email || 'No email'} · {merchant.phone || 'No phone'}</p>
              <p className="text-xs text-gray-500 mt-2">{t('operations.merchantSummaryLine', { count: merchant.restaurants?.length || 0, status: merchant.is_verified ? t('account.verified') : t('account.verificationPending') })}</p>
            </div>
          ))}
        </div>
      </div>
    )}

    {activeView === 'partners' && (
      <div>
        <h2 className="text-lg font-semibold text-gray-950">Delivery partner management</h2>
        <p className="text-sm text-gray-500 mt-1">Showing all delivery partners from the existing operations partner payload. Passwords are not exposed.</p>
        <div className="mt-5 divide-y divide-gray-200 border-y border-gray-200">
          {partners.map(partner => (
            <div key={partner.id} className="py-4">
              <p className="font-medium text-gray-950">{partner.partner_name || partner.owner_name || partner.username}</p>
              <p className="text-sm text-gray-500 mt-1">@{partner.username} · {partner.email || 'No email'} · {partner.partner_phone || 'No phone'}</p>
              <p className="text-xs text-gray-500 mt-2">{t('operations.partnerSummaryLine', { deliveries: partner.delivery_count, verification: partner.is_verified ? t('account.verified') : t('account.verificationPending'), availability: partner.is_available ? t('partner.availableForAssignment') : t('statuses.notAvailable') })}</p>
            </div>
          ))}
        </div>
      </div>
    )}

    {activeView === 'verification' && (
      <div>
        <h2 className="text-lg font-semibold text-gray-950">Verification queue</h2>
        <p className="text-sm text-gray-500 mt-1">Merchant and delivery partner accounts waiting for review.</p>
        <div className="grid md:grid-cols-2 gap-4 mt-5">
          <div className="border border-gray-200 rounded-lg p-4">
            <h3 className="font-semibold text-gray-950">Merchants</h3>
            <p className="text-2xl font-bold text-gray-950 mt-3">{pendingMerchants.length}</p>
            <button type="button" onClick={openPendingMerchants} className="btn-secondary text-sm mt-4">Review merchants</button>
          </div>
          <div className="border border-gray-200 rounded-lg p-4">
            <h3 className="font-semibold text-gray-950">Delivery partners</h3>
            <p className="text-2xl font-bold text-gray-950 mt-3">{pendingPartners.length}</p>
            <button type="button" onClick={openPendingPartners} className="btn-secondary text-sm mt-4">Review partners</button>
          </div>
          <div className="border border-gray-200 rounded-lg p-4">
            <h3 className="font-semibold text-gray-950">Merchant staff</h3>
            <p className="text-2xl font-bold text-gray-950 mt-3">{pendingStaff.length}</p>
            <button type="button" onClick={() => setDashboardView('staff-verification')} className="btn-secondary text-sm mt-4">Review staff</button>
          </div>
        </div>
      </div>
    )}
  </section>
)
}

export default OperationsOverviewPanel
