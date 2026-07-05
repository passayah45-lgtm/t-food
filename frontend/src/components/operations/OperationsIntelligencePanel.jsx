import { Sparkles } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import InsightList from './InsightList.jsx'
import { statusLabel } from '../../lib/statusLabels'

export default function OperationsIntelligencePanel({
  operationsInsights,
  operationsInsightsQuery,
}) {
  const { t } = useTranslation()

  return (
    <section className="bg-white border border-gray-200 rounded-lg p-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
        <div>
          <h2 className="text-lg font-semibold text-gray-950 flex items-center gap-2">
            <Sparkles size={19} className="text-brand-600" /> {t('operations.intelligence.title')}
          </h2>
          <p className="text-sm text-gray-500 mt-1">{t('operations.intelligence.description')}</p>
        </div>
        <button
          type="button"
          onClick={() => operationsInsightsQuery.refetch()}
          disabled={operationsInsightsQuery.isFetching}
          className="btn-secondary inline-flex items-center justify-center text-sm"
        >
          {operationsInsightsQuery.isFetching ? t('common.refreshing') : t('common.refresh')}
        </button>
      </div>

      {operationsInsightsQuery.isLoading && <p className="text-sm text-gray-500">{t('operations.intelligence.loading')}</p>}
      {operationsInsightsQuery.isError && <p className="text-sm text-red-600">{t('operations.intelligence.loadFailed')}</p>}

      {!operationsInsightsQuery.isLoading && !operationsInsightsQuery.isError && (
        <div className="space-y-6">
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">{t('operations.activeRestaurants')}</p>
              <p className="text-2xl font-bold mt-1">{operationsInsights?.marketplace_health?.active_restaurants || 0}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">{t('operations.verifiedMerchants')}</p>
              <p className="text-2xl font-bold mt-1">{operationsInsights?.marketplace_health?.verified_merchants || 0}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">{t('operations.verifiedPartners')}</p>
              <p className="text-2xl font-bold mt-1">{operationsInsights?.marketplace_health?.verified_partners || 0}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">{t('operations.activeCustomers')}</p>
              <p className="text-2xl font-bold mt-1">{operationsInsights?.marketplace_health?.active_customers || 0}</p>
            </div>
          </div>

          <div className="border border-brand-100 bg-brand-50 rounded-lg p-4">
            <h3 className="font-semibold text-gray-950">{t('operations.intelligence.recommendedActions')}</h3>
            <div className="mt-3 space-y-2">
              {(operationsInsights?.marketplace_recommendations || []).map(action => (
                <div key={action} className="flex items-start gap-3 rounded-lg bg-white px-3 py-2 border border-brand-100">
                  <Sparkles size={16} className="text-brand-600 mt-0.5 flex-shrink-0" />
                  <p className="text-sm text-gray-800">{action}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">{t('operations.intelligence.orderTitle')}</h3>
              <div className="grid sm:grid-cols-2 gap-3 mb-4">
                <div className="border border-gray-200 rounded-lg p-4">
                  <p className="text-sm text-gray-500">{t('operations.intelligence.unassignedDeliveries')}</p>
                  <p className="text-2xl font-bold mt-1">{operationsInsights?.order_intelligence?.unassigned_delivery_pressure?.unassigned_deliveries || 0}</p>
                </div>
                <div className="border border-gray-200 rounded-lg p-4">
                  <p className="text-sm text-gray-500">{t('operations.intelligence.avgDeliveryTime')}</p>
                  <p className="text-2xl font-bold mt-1">
                    {t('operations.minutesValue', { value: operationsInsights?.order_intelligence?.average_delivery_time ?? '-' })}
                  </p>
                </div>
              </div>
              <InsightList
                items={operationsInsights?.order_intelligence?.delayed_orders || []}
                emptyLabel={t('operations.intelligence.noDelayedOrders')}
                renderItem={order => (
                  <div key={order.order_id} className="py-3">
                    <p className="text-sm font-medium text-gray-950">{t('operations.orderStatusLine', { id: order.order_id, status: statusLabel(order.status, t, 'orders') })}</p>
                    <p className="text-xs text-gray-500 mt-1">{t('operations.intelligence.orderAreaAge', { restaurant: order.restaurant || t('operations.restaurantNotAvailable'), area: order.area, minutes: order.age_minutes })}</p>
                  </div>
                )}
              />
            </div>

            <div>
              <h3 className="font-semibold text-gray-950 mb-3">{t('operations.intelligence.peakDemandTitle')}</h3>
              <InsightList
                items={operationsInsights?.order_intelligence?.peak_ordering_hours || []}
                emptyLabel={t('operations.intelligence.noOrderHourData')}
                renderItem={row => (
                  <div key={row.hour} className="py-3 flex items-center justify-between gap-3">
                    <span className="text-sm text-gray-700">{String(row.hour).padStart(2, '0')}:00</span>
                    <span className="text-sm font-medium">{t('operations.orderCount', { count: row.orders })}</span>
                  </div>
                )}
              />
              <div className="mt-5">
                <InsightList
                  items={operationsInsights?.order_intelligence?.high_cancellation_areas || []}
                  emptyLabel={t('operations.intelligence.noCancellationAreaPressure')}
                  renderItem={area => (
                    <div key={area.area} className="py-3 flex items-center justify-between gap-3">
                      <span className="text-sm text-gray-700">{area.area}</span>
                      <span className="text-sm font-medium">{Number(area.cancellation_rate || 0).toFixed(1)}%</span>
                    </div>
                  )}
                />
              </div>
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">{t('operations.intelligence.merchantTitle')}</h3>
              <InsightList
                items={[
                  ...(operationsInsights?.merchant_intelligence?.high_cancellation_merchants || []),
                  ...(operationsInsights?.merchant_intelligence?.slow_preparation_merchants || []),
                  ...(operationsInsights?.merchant_intelligence?.low_rating_merchants || []),
                ]}
                emptyLabel={t('operations.intelligence.noMerchantRiskSignals')}
                renderItem={(merchant, index) => (
                  <div key={`${merchant.merchant_id}-${index}`} className="py-3">
                    <p className="text-sm font-medium text-gray-950">{merchant.name}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {t('operations.intelligence.merchantRiskLine', {
                        cancellation: Number(merchant.cancellation_rate || 0).toFixed(1),
                        prep: merchant.average_prep_time ?? '-',
                        rating: merchant.average_rating ?? '-',
                      })}
                    </p>
                  </div>
                )}
              />
            </div>
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">{t('operations.intelligence.outstandingMerchants')}</h3>
              <InsightList
                items={operationsInsights?.merchant_intelligence?.outstanding_merchants || []}
                emptyLabel={t('operations.intelligence.noOutstandingMerchantSignal')}
                renderItem={merchant => (
                  <div key={merchant.merchant_id} className="py-3">
                    <p className="text-sm font-medium text-gray-950">{merchant.name}</p>
                    <p className="text-xs text-gray-500 mt-1">{t('operations.intelligence.outstandingMerchantLine', { rating: merchant.average_rating, count: merchant.delivered_orders })}</p>
                  </div>
                )}
              />
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">{t('operations.intelligence.deliveryTitle')}</h3>
              <InsightList
                items={operationsInsights?.delivery_intelligence?.partner_workload || []}
                emptyLabel={t('operations.intelligence.noPartnerWorkload')}
                renderItem={partner => (
                  <div key={partner.partner_id} className="py-3 flex items-center justify-between gap-3">
                    <span className="text-sm text-gray-700">{partner.name}</span>
                    <span className="text-sm font-medium">{t('operations.deliveryCount', { count: partner.deliveries })}</span>
                  </div>
                )}
              />
            </div>
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">{t('operations.intelligence.supportTitle')}</h3>
              <InsightList
                items={operationsInsights?.support_intelligence?.common_complaint_categories || []}
                emptyLabel={t('operations.intelligence.noSupportComplaintData')}
                renderItem={category => (
                  <div key={category.category} className="py-3 flex items-center justify-between gap-3">
                    <span className="text-sm text-gray-700">{statusLabel(category.category, t, 'common')}</span>
                    <span className="text-sm font-medium">{t('operations.ticketCount', { count: category.count })}</span>
                  </div>
                )}
              />
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
