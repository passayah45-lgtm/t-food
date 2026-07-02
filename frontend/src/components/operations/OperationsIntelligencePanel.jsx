import { Sparkles } from 'lucide-react'
import InsightList from './InsightList.jsx'

export default function OperationsIntelligencePanel({
  operationsInsights,
  operationsInsightsQuery,
}) {
  return (
    <section className="bg-white border border-gray-200 rounded-lg p-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
        <div>
          <h2 className="text-lg font-semibold text-gray-950 flex items-center gap-2">
            <Sparkles size={19} className="text-brand-600" /> Marketplace Intelligence
          </h2>
          <p className="text-sm text-gray-500 mt-1">Deterministic business insights from current marketplace activity.</p>
        </div>
        <button
          type="button"
          onClick={() => operationsInsightsQuery.refetch()}
          disabled={operationsInsightsQuery.isFetching}
          className="btn-secondary inline-flex items-center justify-center text-sm"
        >
          {operationsInsightsQuery.isFetching ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {operationsInsightsQuery.isLoading && <p className="text-sm text-gray-500">Loading marketplace intelligence...</p>}
      {operationsInsightsQuery.isError && <p className="text-sm text-red-600">Marketplace intelligence could not be loaded.</p>}

      {!operationsInsightsQuery.isLoading && !operationsInsightsQuery.isError && (
        <div className="space-y-6">
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Active restaurants</p>
              <p className="text-2xl font-bold mt-1">{operationsInsights?.marketplace_health?.active_restaurants || 0}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Verified merchants</p>
              <p className="text-2xl font-bold mt-1">{operationsInsights?.marketplace_health?.verified_merchants || 0}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Verified partners</p>
              <p className="text-2xl font-bold mt-1">{operationsInsights?.marketplace_health?.verified_partners || 0}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Active customers</p>
              <p className="text-2xl font-bold mt-1">{operationsInsights?.marketplace_health?.active_customers || 0}</p>
            </div>
          </div>

          <div className="border border-brand-100 bg-brand-50 rounded-lg p-4">
            <h3 className="font-semibold text-gray-950">Recommended actions</h3>
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
              <h3 className="font-semibold text-gray-950 mb-3">Order intelligence</h3>
              <div className="grid sm:grid-cols-2 gap-3 mb-4">
                <div className="border border-gray-200 rounded-lg p-4">
                  <p className="text-sm text-gray-500">Unassigned deliveries</p>
                  <p className="text-2xl font-bold mt-1">{operationsInsights?.order_intelligence?.unassigned_delivery_pressure?.unassigned_deliveries || 0}</p>
                </div>
                <div className="border border-gray-200 rounded-lg p-4">
                  <p className="text-sm text-gray-500">Avg delivery time</p>
                  <p className="text-2xl font-bold mt-1">
                    {operationsInsights?.order_intelligence?.average_delivery_time ?? '-'} min
                  </p>
                </div>
              </div>
              <InsightList
                items={operationsInsights?.order_intelligence?.delayed_orders || []}
                emptyLabel="No delayed orders detected."
                renderItem={order => (
                  <div key={order.order_id} className="py-3">
                    <p className="text-sm font-medium text-gray-950">Order #{order.order_id} · {order.status}</p>
                    <p className="text-xs text-gray-500 mt-1">{order.restaurant || 'Restaurant unavailable'} · {order.area} · {order.age_minutes} min old</p>
                  </div>
                )}
              />
            </div>

            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Peak demand and cancellation areas</h3>
              <InsightList
                items={operationsInsights?.order_intelligence?.peak_ordering_hours || []}
                emptyLabel="No order hour data yet."
                renderItem={row => (
                  <div key={row.hour} className="py-3 flex items-center justify-between gap-3">
                    <span className="text-sm text-gray-700">{String(row.hour).padStart(2, '0')}:00</span>
                    <span className="text-sm font-medium">{row.orders} orders</span>
                  </div>
                )}
              />
              <div className="mt-5">
                <InsightList
                  items={operationsInsights?.order_intelligence?.high_cancellation_areas || []}
                  emptyLabel="No cancellation area pressure detected."
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
              <h3 className="font-semibold text-gray-950 mb-3">Merchant intelligence</h3>
              <InsightList
                items={[
                  ...(operationsInsights?.merchant_intelligence?.high_cancellation_merchants || []),
                  ...(operationsInsights?.merchant_intelligence?.slow_preparation_merchants || []),
                  ...(operationsInsights?.merchant_intelligence?.low_rating_merchants || []),
                ]}
                emptyLabel="No merchant risk signals detected."
                renderItem={(merchant, index) => (
                  <div key={`${merchant.merchant_id}-${index}`} className="py-3">
                    <p className="text-sm font-medium text-gray-950">{merchant.name}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      Cancellation {Number(merchant.cancellation_rate || 0).toFixed(1)}% · Prep {merchant.average_prep_time ?? '-'} min · Rating {merchant.average_rating ?? '-'}
                    </p>
                  </div>
                )}
              />
            </div>
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Outstanding merchants</h3>
              <InsightList
                items={operationsInsights?.merchant_intelligence?.outstanding_merchants || []}
                emptyLabel="No outstanding merchant signal yet."
                renderItem={merchant => (
                  <div key={merchant.merchant_id} className="py-3">
                    <p className="text-sm font-medium text-gray-950">{merchant.name}</p>
                    <p className="text-xs text-gray-500 mt-1">{merchant.average_rating} rating · {merchant.delivered_orders} delivered orders</p>
                  </div>
                )}
              />
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Delivery intelligence</h3>
              <InsightList
                items={operationsInsights?.delivery_intelligence?.partner_workload || []}
                emptyLabel="No partner workload yet."
                renderItem={partner => (
                  <div key={partner.partner_id} className="py-3 flex items-center justify-between gap-3">
                    <span className="text-sm text-gray-700">{partner.name}</span>
                    <span className="text-sm font-medium">{partner.deliveries} deliveries</span>
                  </div>
                )}
              />
            </div>
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Support intelligence</h3>
              <InsightList
                items={operationsInsights?.support_intelligence?.common_complaint_categories || []}
                emptyLabel="No support complaint data yet."
                renderItem={category => (
                  <div key={category.category} className="py-3 flex items-center justify-between gap-3">
                    <span className="text-sm text-gray-700">{category.category?.replaceAll('_', ' ')}</span>
                    <span className="text-sm font-medium">{category.count} tickets</span>
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
