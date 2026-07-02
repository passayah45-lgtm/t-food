import { RefreshCw, Sparkles } from 'lucide-react'
import { usePreferences } from '../../context/PreferencesContext'
import { formatCurrency, formatNumber } from '../../lib/formatters'

const safeNumber = value => Number(value || 0)

function KpiCard({ label, value, accent = 'text-gray-950' }) {
  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${accent}`}>{value}</p>
    </div>
  )
}

function CompactList({ items = [], emptyLabel, renderItem }) {
  if (!items.length) {
    return <p className="text-sm text-gray-500 border border-dashed border-gray-300 rounded-lg p-4">{emptyLabel}</p>
  }
  return <div className="divide-y divide-gray-200 border-y border-gray-200">{items.map(renderItem)}</div>
}

export default function MerchantInsightsPanel({ insights, merchantInsightsQuery }) {
  const { preferences } = usePreferences()
  const money = value => formatCurrency(value, insights?.currency || insights?.currency_code || 'INR', preferences)
  const percent = value => value === null || value === undefined ? '-' : `${formatNumber(value, preferences, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`
  const minutes = value => value === null || value === undefined ? '-' : `${formatNumber(value, preferences, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} min`

  return (
    <section className="py-8 border-b border-gray-200">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
        <div className="flex items-center gap-2">
          <Sparkles size={20} className="text-brand-600" />
          <h2 className="text-xl font-semibold">Merchant insights</h2>
        </div>
        <button
          type="button"
          onClick={() => merchantInsightsQuery.refetch()}
          disabled={merchantInsightsQuery.isFetching}
          className="btn-secondary inline-flex items-center justify-center gap-2 py-2 px-3 text-sm"
        >
          <RefreshCw size={16} className={merchantInsightsQuery.isFetching ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {merchantInsightsQuery.isLoading && (
        <p className="text-sm text-gray-500">Loading merchant insights...</p>
      )}
      {merchantInsightsQuery.isError && (
        <p className="text-sm text-red-600">Could not load merchant insights.</p>
      )}

      {!merchantInsightsQuery.isLoading && !merchantInsightsQuery.isError && (
        <>
          <div className="grid md:grid-cols-3 gap-3 mb-6">
            <KpiCard
              label="Average order value"
              value={money(insights?.sales_insights?.average_order_value)}
            />
            <KpiCard
              label="Cancellation rate"
              value={percent(insights?.operations_insights?.cancellation_rate)}
              accent={safeNumber(insights?.operations_insights?.cancellation_rate) >= 20 ? 'text-red-600' : 'text-gray-950'}
            />
            <KpiCard
              label="Average rating"
              value={insights?.customer_insights?.rating_summary?.average_rating ?? '-'}
              accent={safeNumber(insights?.customer_insights?.rating_summary?.average_rating) < 3.5 && insights?.customer_insights?.rating_summary?.average_rating ? 'text-amber-700' : 'text-gray-950'}
            />
          </div>

          <div className="grid lg:grid-cols-[1fr_1fr] gap-6 mb-6">
            <div className="border border-gray-200 rounded-lg p-5">
              <h3 className="font-semibold text-gray-950">Suggested actions</h3>
              <div className="mt-4 space-y-3">
                {(insights?.action_recommendations || []).map(action => (
                  <div key={action} className="flex items-start gap-3 rounded-lg bg-brand-50 px-3 py-2">
                    <Sparkles size={16} className="mt-0.5 text-brand-600 flex-shrink-0" />
                    <p className="text-sm text-gray-800">{action}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="border border-gray-200 rounded-lg p-5">
              <h3 className="font-semibold text-gray-950">Sales summary</h3>
              <p className="text-sm text-gray-500 mt-2">
                {insights?.sales_insights?.revenue_trend_summary || 'No sales summary yet.'}
              </p>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <KpiCard
                  label="Avg prep"
                  value={minutes(insights?.operations_insights?.average_prep_minutes)}
                />
                <KpiCard
                  label="Repeat customers"
                  value={insights?.customer_insights?.repeat_customer_signals?.repeat_customers || 0}
                />
              </div>
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-6 mb-6">
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Best sellers</h3>
              <CompactList
                items={insights?.sales_insights?.best_selling_items || []}
                emptyLabel="No best sellers yet."
                renderItem={item => (
                  <div key={item.item_id} className="py-3 flex items-center justify-between gap-3">
                    <span className="text-sm text-gray-700">{item.name}</span>
                    <span className="text-sm font-medium">{formatNumber(item.quantity, preferences, { maximumFractionDigits: 0 })} sold - {money(item.gross_sales)}</span>
                  </div>
                )}
              />
            </div>
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Low performers</h3>
              <CompactList
                items={insights?.sales_insights?.low_performing_items || []}
                emptyLabel="No low-performing items yet."
                renderItem={item => (
                  <div key={item.item_id} className="py-3 flex items-center justify-between gap-3">
                    <span className="text-sm text-gray-700">{item.name}</span>
                    <span className="text-sm font-medium">{formatNumber(item.quantity, preferences, { maximumFractionDigits: 0 })} sold - {money(item.gross_sales)}</span>
                  </div>
                )}
              />
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-6 mb-6">
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Menu opportunities</h3>
              <CompactList
                items={insights?.menu_insights?.items_with_zero_sales || []}
                emptyLabel="No zero-sale menu items."
                renderItem={item => (
                  <div key={item.item_id} className="py-3 flex items-center justify-between gap-3">
                    <span className="text-sm text-gray-700">{item.name}</span>
                    <span className="text-xs font-medium text-amber-700 bg-amber-50 px-2 py-1 rounded-md">Zero sales</span>
                  </div>
                )}
              />
            </div>
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Unavailable items</h3>
              <CompactList
                items={insights?.menu_insights?.unavailable_items || []}
                emptyLabel="No unavailable items."
                renderItem={item => (
                  <div key={item.item_id} className="py-3 flex items-center justify-between gap-3">
                    <span className="text-sm text-gray-700">{item.name}</span>
                    <span className="text-xs text-gray-500">{item.restaurant}</span>
                  </div>
                )}
              />
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Prep and cancellation warnings</h3>
              <CompactList
                items={[
                  ...(insights?.operations_insights?.slow_prep_warnings || []),
                  ...(insights?.operations_insights?.ready_for_pickup_delay_warnings || []),
                ]}
                emptyLabel="No operational warnings right now."
                renderItem={warning => (
                  <div key={warning.code} className="py-3">
                    <p className="text-sm font-medium text-gray-900">{warning.message}</p>
                    <p className="text-xs text-gray-500 mt-1">{warning.code.replaceAll('_', ' ')}</p>
                  </div>
                )}
              />
            </div>
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Rating and review signals</h3>
              <CompactList
                items={insights?.customer_insights?.recent_review_issues || []}
                emptyLabel="No recent low-rating issues."
                renderItem={issue => (
                  <div key={`${issue.restaurant}-${issue.created_at}`} className="py-3">
                    <p className="text-sm font-medium text-gray-900">{issue.restaurant} · {issue.rating} stars</p>
                    <p className="text-sm text-gray-600 mt-1">{issue.comment || 'No comment provided.'}</p>
                  </div>
                )}
              />
            </div>
          </div>
        </>
      )}
    </section>
  )
}
