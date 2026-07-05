import { CircleDollarSign } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { usePreferences } from '../../context/PreferencesContext'
import { formatCurrency, formatNumber } from '../../lib/formatters'
import { statusLabel } from '../../lib/statusLabels'

const maxBreakdownAmount = rows => Math.max(...(rows || []).map(row => Number(row.amount || 0)), 1)

export default function OperationsLedgerPanel({ ledger, ledgerQuery, formatDateTime }) {
  const { t } = useTranslation()
  const { preferences } = usePreferences()
  const ledgerMoney = (value, currency = 'GNF') => formatCurrency(value, currency || 'GNF', preferences)
  const integer = value => formatNumber(value, preferences, { maximumFractionDigits: 0 })

  return (
    <section className="bg-white border border-gray-200 rounded-lg p-5">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
        <div>
          <h2 className="text-lg font-semibold text-gray-950 flex items-center gap-2">
            <CircleDollarSign size={19} className="text-brand-600" /> Ledger
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Read-only finance dashboard powered by immutable ledger transactions.
          </p>
        </div>
        <button
          type="button"
          onClick={() => ledgerQuery.refetch()}
          disabled={ledgerQuery.isFetching}
          className="btn-secondary inline-flex items-center justify-center text-sm"
        >
          {ledgerQuery.isFetching ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {ledgerQuery.isLoading && <p className="text-sm text-gray-500">Loading ledger dashboard...</p>}
      {ledgerQuery.isError && <p className="text-sm text-red-600">Ledger dashboard could not be loaded.</p>}

      {!ledgerQuery.isLoading && !ledgerQuery.isError && (
        <div className="space-y-6">
          <div className={`rounded-lg border p-4 ${ledger.financial_health?.unbalanced_transactions ? 'border-red-200 bg-red-50 text-red-900' : 'border-emerald-200 bg-emerald-50 text-emerald-900'}`}>
            <p className="font-semibold">
              {ledger.financial_health?.unbalanced_transactions ? 'Financial Integrity Warning' : 'Ledger Verified'}
            </p>
            <p className="text-sm mt-1">
              {integer(ledger.financial_health?.balanced_transactions || 0)} balanced transactions, {integer(ledger.financial_health?.unbalanced_transactions || 0)} unbalanced transactions, {integer(ledger.financial_health?.failed_financial_events || 0)} failed financial events.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {[
              ['Gross revenue', ledger.platform_summary?.total_gross_revenue],
              ['Platform fees', ledger.platform_summary?.total_platform_fees],
              ['Merchant payouts', ledger.platform_summary?.total_merchant_payouts],
              ['Partner payouts', ledger.platform_summary?.total_partner_payouts],
              ['Refunds', ledger.platform_summary?.total_refunds],
            ].map(([label, value]) => (
              <div key={label} className="border border-gray-200 rounded-lg p-4">
                <p className="text-sm text-gray-500">{label}</p>
                <p className="text-2xl font-bold text-gray-950 mt-1">{ledgerMoney(value)}</p>
              </div>
            ))}
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Settlement preview amount</p>
              <p className="text-xl font-bold text-gray-950 mt-1">{ledgerMoney(ledger.platform_summary?.total_settlement_preview_amount)}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Ledger transactions</p>
              <p className="text-xl font-bold text-gray-950 mt-1">{integer(ledger.platform_summary?.ledger_transaction_count || 0)}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Ledger entries</p>
              <p className="text-xl font-bold text-gray-950 mt-1">{integer(ledger.platform_summary?.ledger_entry_count || 0)}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Idempotency</p>
              <p className="text-xl font-bold text-gray-950 mt-1">{integer(ledger.financial_health?.duplicate_idempotency_attempts_prevented || 0)}</p>
              <p className="text-xs text-gray-500 mt-1">Duplicate ledger rows detected</p>
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-5">
            {[
              ['Revenue by Country', ledger.breakdowns?.by_country],
              ['Revenue by Currency', ledger.breakdowns?.by_currency],
              ['Revenue by Provider', ledger.breakdowns?.by_provider],
              ['Transaction Types', ledger.breakdowns?.by_transaction_type],
            ].map(([title, rows]) => {
              const maxAmount = maxBreakdownAmount(rows)
              return (
                <div key={title} className="border border-gray-200 rounded-lg p-4">
                  <h3 className="font-semibold text-gray-950">{title}</h3>
                  <div className="mt-4 space-y-3">
                    {(rows || []).length ? rows.map(row => (
                      <div key={row.key}>
                        <div className="flex items-center justify-between gap-3 text-sm">
                          <span className="font-medium text-gray-800">{row.key}</span>
                          <span className="text-gray-500">{ledgerMoney(row.amount, row.currency || 'GNF')} ({integer(row.count)})</span>
                        </div>
                        <div className="mt-1 h-2 rounded-full bg-gray-100 overflow-hidden">
                          <div
                            className="h-full bg-brand-500"
                            style={{ width: `${Math.max((Number(row.amount || 0) / maxAmount) * 100, 4)}%` }}
                          />
                        </div>
                      </div>
                    )) : <p className="text-sm text-gray-500">No ledger data yet.</p>}
                  </div>
                </div>
              )
            })}
          </div>

          <div className="grid xl:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Recent Ledger Transactions</h3>
              <div className="divide-y divide-gray-200 border-y border-gray-200">
                {(ledger.recent_activity?.ledger_transactions || []).length ? ledger.recent_activity.ledger_transactions.map(transaction => (
                  <div key={transaction.id} className="py-3">
                    <p className="text-sm font-medium text-gray-950">{transaction.type} - {ledgerMoney(transaction.amount, transaction.currency)}</p>
                    <p className="text-xs text-gray-500 mt-1">{transaction.provider} - {transaction.market} - {formatDateTime(transaction.created_at)}</p>
                  </div>
                )) : <p className="py-4 text-sm text-gray-500">No ledger transactions yet.</p>}
              </div>
            </div>

            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Recent Fulfillment Preview Ledger Entries</h3>
              <div className="divide-y divide-gray-200 border-y border-gray-200">
                {(ledger.recent_activity?.fulfillment_preview_ledger_entries || []).length ? ledger.recent_activity.fulfillment_preview_ledger_entries.map(transaction => (
                  <div key={transaction.id} className="py-3">
                    <p className="text-sm font-medium text-gray-950">Preview #{transaction.id} - {ledgerMoney(transaction.amount, transaction.currency)}</p>
                    <p className="text-xs text-amber-700 mt-1">Preview Only - No Financial Settlement Has Been Applied.</p>
                  </div>
                )) : <p className="py-4 text-sm text-gray-500">No fulfillment preview ledger entries yet.</p>}
              </div>
            </div>
          </div>

          <div className="grid xl:grid-cols-3 gap-6">
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Recent Refund Audits</h3>
              <div className="divide-y divide-gray-200 border-y border-gray-200">
                {(ledger.recent_activity?.refund_audits || []).length ? ledger.recent_activity.refund_audits.map(audit => (
                  <div key={audit.id} className="py-3">
                    <p className="text-sm font-medium text-gray-950">Order #{audit.order_id} - {ledgerMoney(audit.amount, audit.currency)}</p>
                    <p className="text-xs text-gray-500 mt-1">{statusLabel(audit.status, t, 'payments')} - {audit.provider_code}</p>
                  </div>
                )) : <p className="py-4 text-sm text-gray-500">No refund audits yet.</p>}
              </div>
            </div>

            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Recent Merchant Payout Audits</h3>
              <div className="divide-y divide-gray-200 border-y border-gray-200">
                {(ledger.recent_activity?.merchant_payout_audits || []).length ? ledger.recent_activity.merchant_payout_audits.map(audit => (
                  <div key={audit.id} className="py-3">
                    <p className="text-sm font-medium text-gray-950">{audit.merchant} - {ledgerMoney(audit.amount, audit.currency)}</p>
                    <p className="text-xs text-gray-500 mt-1">Order #{audit.order_id} - {statusLabel(audit.status, t, 'payouts')}</p>
                  </div>
                )) : <p className="py-4 text-sm text-gray-500">No merchant payout audits yet.</p>}
              </div>
            </div>

            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Recent Partner Payout Audits</h3>
              <div className="divide-y divide-gray-200 border-y border-gray-200">
                {(ledger.recent_activity?.partner_payout_audits || []).length ? ledger.recent_activity.partner_payout_audits.map(audit => (
                  <div key={audit.id} className="py-3">
                    <p className="text-sm font-medium text-gray-950">{audit.partner} - {ledgerMoney(audit.amount, audit.currency)}</p>
                    <p className="text-xs text-gray-500 mt-1">Delivery #{audit.delivery_id} - {statusLabel(audit.status, t, 'payouts')}</p>
                  </div>
                )) : <p className="py-4 text-sm text-gray-500">No partner payout audits yet.</p>}
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
