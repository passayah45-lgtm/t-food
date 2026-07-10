import { useTranslation } from 'react-i18next'
import { statusLabel } from '../../lib/statusLabels'
import TfoodAssistantPanel from '../assistant/TfoodAssistantPanel'

const joinDetails = details => details.filter(Boolean).join(' - ')

const contactGap = (t, profileType) => t('operations.contactGap', { profileType })

const merchantContactLine = (merchant, t) => joinDetails([
  merchant.owner_name || t('operations.ownerNameNotSet'),
  merchant.username ? `@${merchant.username}` : t('operations.usernameNotSet'),
  merchant.email || t('operations.emailNotProvided'),
  merchant.phone || contactGap(t, t('operations.merchantProfile')),
])

const partnerContactLine = (partner, t) => joinDetails([
  `@${partner.username || t('operations.unknown')}`,
  partner.email || t('operations.emailNotProvided'),
  partner.partner_phone || contactGap(t, t('operations.partnerProfile')),
])

const partnerTransportLine = (partner, t) => joinDetails([
  partner.transport_details ? t('operations.transportValue', { value: partner.transport_details }) : t('operations.transportSetupGap'),
  t('operations.deliveryCount', { count: partner.delivery_count || 0 }),
  partner.is_available ? t('partner.availableForAssignment') : t('statuses.notAvailable'),
])

const partnerScopeLabel = partner => {
  if (partner.rider_scope === 'MERCHANT_BRANCH') return 'Branch-assigned merchant rider'
  if (partner.rider_scope === 'MERCHANT') return 'Merchant-wide rider'
  return 'Platform rider'
}

const partnerScopeTone = partner => {
  if (partner.rider_scope === 'MERCHANT_BRANCH') return 'border-blue-200 bg-blue-50 text-blue-700'
  if (partner.rider_scope === 'MERCHANT') return 'border-purple-200 bg-purple-50 text-purple-700'
  return 'border-emerald-200 bg-emerald-50 text-emerald-700'
}

const partnerScopeLine = partner => {
  if (partner.linked_branch) {
    return joinDetails([
      partner.linked_merchant?.name ? `Merchant: ${partner.linked_merchant.name}` : '',
      `Branch: ${partner.linked_branch.name}`,
      partner.linked_branch.area || partner.linked_branch.city,
    ])
  }
  if (partner.linked_merchant) return `Merchant: ${partner.linked_merchant.name}`
  return 'Can receive eligible T-Food platform deliveries.'
}

const OperationsOverviewPanel = ({ operationsSections, selectedRangeLabel }) => {
  const { t } = useTranslation()

  return (
    <section className="bg-white border border-gray-200 rounded-lg p-5">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 mb-5">
        <div>
          <h2 className="text-lg font-semibold text-gray-950">{t('operations.sectionsTitle')}</h2>
          <p className="text-sm text-gray-500 mt-1">{t('operations.sectionsDescription')}</p>
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
            <p className="text-xs text-gray-500 mt-1">{t('operations.filteredBy', { range: selectedRangeLabel })}</p>
          </button>
        ))}
      </div>
      <div className="mt-4">
        <TfoodAssistantPanel surface="operations" compact />
      </div>
    </section>
  )
}

export const PendingActionQueuesPanel = ({
  activeView,
  pendingActionViews,
  setDashboardView,
}) => {
  const { t } = useTranslation()

  return (
    <section className="bg-white border border-gray-200 rounded-lg p-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-950">{t('operations.pendingQueues')}</h2>
          <p className="text-sm text-gray-500 mt-1">{t('operations.pendingQueuesDescription')}</p>
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
}

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
          <h2 className="text-lg font-semibold text-gray-950">{t('operations.activeRestaurants')}</h2>
          <p className="text-sm text-gray-500 mt-1">{t('operations.activeRestaurantsDescription')}</p>
          {!activeRestaurants.length ? (
            <p className="mt-5 text-sm text-gray-500">{t('operations.noActiveRestaurants')}</p>
          ) : (
            <div className="mt-5 divide-y divide-gray-200 border-y border-gray-200">
              {activeRestaurants.map(restaurant => (
                <div key={restaurant.id} className="py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div>
                    <p className="font-medium text-gray-950">{restaurant.name}</p>
                    <p className="text-sm text-gray-500">{joinDetails([
                      restaurant.city || restaurant.location || t('operations.locationNotSet'),
                      restaurant.merchant_business_name || t('operations.merchantNotSet'),
                      restaurant.merchant_verified ? t('operations.verifiedMerchant') : t('operations.merchantPending'),
                    ])}</p>
                    <p className="text-xs text-gray-500 mt-1">{t('operations.deliveryRadius', { radius: restaurant.delivery_radius_km })}</p>
                  </div>
                  <span className={`text-xs font-medium px-2 py-1 rounded-full w-fit ${restaurant.is_open ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-600'}`}>
                    {restaurant.is_open ? statusLabel('OPEN', t, 'operations') : statusLabel('CLOSED', t, 'operations')}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeView === 'orders' && (
        <div>
          <h2 className="text-lg font-semibold text-gray-950">{t('operations.openOrders')}</h2>
          <p className="text-sm text-gray-500 mt-1">{t('operations.openOrdersDescription')}</p>
          {!openOrders.length ? (
            <p className="mt-5 text-sm text-gray-500">{t('operations.noOpenOrders')}</p>
          ) : (
            <div className="mt-5 space-y-3">
              {openOrders.map(order => (
                <article key={order.id} className="border border-gray-200 rounded-lg p-4">
                  <p className="font-medium text-gray-950">{t('operations.orderWithRestaurant', { id: order.id, restaurant: order.restaurant || t('operations.restaurantNotAvailable') })}</p>
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
          <h2 className="text-lg font-semibold text-gray-950">{t('operations.revenueBreakdown')}</h2>
          <p className="text-sm text-gray-500 mt-1">{t('operations.revenueBreakdownDescription')}</p>
          <div className="grid md:grid-cols-3 gap-3 mt-5">
            <div className="border border-gray-200 rounded-lg p-4"><p className="text-sm text-gray-500">{t('operations.grossSales')}</p><p className="text-2xl font-bold text-gray-950 mt-1">{money(revenue.gross_sales)}</p></div>
            <div className="border border-gray-200 rounded-lg p-4"><p className="text-sm text-gray-500">{t('operations.merchantEarnings')}</p><p className="text-2xl font-bold text-gray-950 mt-1">{money(revenue.merchant_earnings)}</p></div>
            <div className="border border-gray-200 rounded-lg p-4"><p className="text-sm text-gray-500">{t('operations.platformRevenue')}</p><p className="text-2xl font-bold text-gray-950 mt-1">{money(revenue.platform_revenue)}</p></div>
            <div className="border border-gray-200 rounded-lg p-4"><p className="text-sm text-gray-500">{t('operations.deliveryFees')}</p><p className="text-2xl font-bold text-gray-950 mt-1">{money(revenue.delivery_fees)}</p></div>
            <div className="border border-gray-200 rounded-lg p-4"><p className="text-sm text-gray-500">{t('operations.pendingPayouts')}</p><p className="text-2xl font-bold text-gray-950 mt-1">{money(revenue.pending_payouts)}</p></div>
            <div className="border border-gray-200 rounded-lg p-4"><p className="text-sm text-gray-500">{t('operations.paidPayouts')}</p><p className="text-2xl font-bold text-gray-950 mt-1">{money(revenue.paid_payouts)}</p></div>
          </div>
          <div className="grid md:grid-cols-4 gap-3 mt-3">
            {[
              [t('operations.today'), revenue.today],
              [t('operations.last7Days'), revenue.week],
              [t('operations.currentMonth'), revenue.month],
              [t('operations.currentYear'), revenue.year],
            ].map(([label, period]) => (
              <div key={label} className="border border-gray-200 rounded-lg p-4">
                <p className="text-sm font-medium text-gray-950">{label}</p>
                <p className="text-sm text-gray-500 mt-2">{t('operations.salesValue', { value: money(period?.gross_sales) })}</p>
                <p className="text-sm text-gray-500">{t('operations.platformValue', { value: money(period?.platform_revenue) })}</p>
              </div>
            ))}
          </div>
          <p className="text-sm text-gray-500 mt-4">{t('operations.availablePayoutActions', { merchantCount: availableMerchantPayouts.length, partnerCount: availablePartnerPayouts.length })}</p>
        </div>
      )}

      {activeView === 'customers' && (
        <div>
          <h2 className="text-lg font-semibold text-gray-950">{t('operations.customerManagement')}</h2>
          <p className="text-sm text-gray-500 mt-1">{t('operations.customerManagementDescription')}</p>
          {!customers.length ? (
            <p className="mt-5 text-sm text-gray-500">{t('operations.noCustomers')}</p>
          ) : (
            <div className="mt-5 divide-y divide-gray-200 border-y border-gray-200">
              {customers.map(customer => (
                <div key={customer.id} className="py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div>
                    <p className="font-medium text-gray-950">{customer.name}</p>
                    <p className="text-sm text-gray-500">{customer.email || t('operations.emailNotProvided')} - {customer.phone || contactGap(t, t('operations.customerProfile'))}</p>
                    <p className="text-xs text-gray-500 mt-1">{t('operations.customerOrderJoined', { count: customer.total_orders, date: formatDateTime(customer.created_at) })}</p>
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
          <h2 className="text-lg font-semibold text-gray-950">{t('operations.merchantManagement')}</h2>
          <p className="text-sm text-gray-500 mt-1">{t('operations.merchantManagementDescription')}</p>
          <div className="mt-5 divide-y divide-gray-200 border-y border-gray-200">
            {merchants.map(merchant => (
              <div key={merchant.id} className="py-4">
                <p className="font-medium text-gray-950">{merchant.business_name || merchant.owner_name || merchant.username}</p>
                <p className="text-sm text-gray-500 mt-1">{merchantContactLine(merchant, t)}</p>
                <p className="text-xs text-gray-500 mt-2">
                  {t('operations.profileBranchCount', { status: merchant.is_verified ? t('account.verified') : t('account.verificationPending'), count: merchant.restaurants?.length || 0 })}
                </p>
                <p className="text-xs text-gray-500 mt-2">{t('operations.merchantSummaryLine', { count: merchant.restaurants?.length || 0, status: merchant.is_verified ? t('account.verified') : t('account.verificationPending') })}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeView === 'partners' && (
        <div>
          <h2 className="text-lg font-semibold text-gray-950">{t('operations.deliveryPartnerManagement')}</h2>
          <p className="text-sm text-gray-500 mt-1">{t('operations.deliveryPartnerManagementDescription')}</p>
          <div className="mt-5 divide-y divide-gray-200 border-y border-gray-200">
            {partners.map(partner => (
              <div key={partner.id} className="py-4">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium text-gray-950">{partner.partner_name || partner.owner_name || partner.username}</p>
                  <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${partnerScopeTone(partner)}`}>
                    {partnerScopeLabel(partner)}
                  </span>
                </div>
                <p className="text-sm text-gray-500 mt-1">{partnerContactLine(partner, t)}</p>
                <p className="text-xs text-gray-500 mt-2">{partnerTransportLine(partner, t)}</p>
                <p className="text-xs text-gray-600 mt-1">{partnerScopeLine(partner)}</p>
                {partner.merchant_rider_status && (
                  <p className="text-xs text-gray-500 mt-1">Merchant rider status: {statusLabel(partner.merchant_rider_status, t, 'staff')}</p>
                )}
                <p className="text-xs text-gray-500 mt-1">{t('operations.partnerSummaryLine', { deliveries: partner.delivery_count, verification: partner.is_verified ? t('account.verified') : t('account.verificationPending'), availability: partner.is_available ? t('partner.availableForAssignment') : t('statuses.notAvailable') })}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeView === 'verification' && (
        <div>
          <h2 className="text-lg font-semibold text-gray-950">{t('operations.verificationQueue')}</h2>
          <p className="text-sm text-gray-500 mt-1">{t('operations.verificationQueueDescription')}</p>
          <div className="grid md:grid-cols-2 gap-4 mt-5">
            <div className="border border-gray-200 rounded-lg p-4">
              <h3 className="font-semibold text-gray-950">{t('dashboard.merchants')}</h3>
              <p className="text-2xl font-bold text-gray-950 mt-3">{pendingMerchants.length}</p>
              <button type="button" onClick={openPendingMerchants} className="btn-secondary text-sm mt-4">{t('operations.reviewMerchants')}</button>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <h3 className="font-semibold text-gray-950">{t('operations.deliveryPartners')}</h3>
              <p className="text-2xl font-bold text-gray-950 mt-3">{pendingPartners.length}</p>
              <button type="button" onClick={openPendingPartners} className="btn-secondary text-sm mt-4">{t('operations.reviewPartners')}</button>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <h3 className="font-semibold text-gray-950">{t('operations.merchantStaff')}</h3>
              <p className="text-2xl font-bold text-gray-950 mt-3">{pendingStaff.length}</p>
              <button type="button" onClick={() => setDashboardView('staff-verification')} className="btn-secondary text-sm mt-4">{t('operations.reviewStaff')}</button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

export default OperationsOverviewPanel
