import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { CircleHelp, Clock3, MessageSquareText, ReceiptText } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { listOrders } from '../api/orders'
import { createSupportTicket, listSupportTickets } from '../api/support'
import TfoodAssistantPanel from '../components/assistant/TfoodAssistantPanel'
import { usePreferences } from '../context/PreferencesContext'
import { formatCurrency } from '../lib/formatters'
import { statusLabel } from '../lib/statusLabels'
import useTitle from '../hooks/useTitle'

const categories = ['MISSING_ITEMS', 'QUALITY', 'DELIVERY', 'PAYMENT', 'OTHER']

export default function SupportPage() {
  const { t } = useTranslation()
  useTitle(t('support.title'))
  const queryClient = useQueryClient()
  const { preferences } = usePreferences()
  const [form, setForm] = useState({ order: '', category: 'MISSING_ITEMS', description: '', request_refund: false })
  const [saving, setSaving] = useState(false)
  const ordersQuery = useQuery({ queryKey: ['orders'], queryFn: async () => (await listOrders()).data })
  const ticketsQuery = useQuery({ queryKey: ['support-tickets'], queryFn: async () => (await listSupportTickets()).data })
  const orders = ordersQuery.data?.results || ordersQuery.data || []
  const tickets = ticketsQuery.data?.results || ticketsQuery.data || []
  const money = (value, currency = 'GNF') => formatCurrency(value, currency, preferences)

  const submit = async event => {
    event.preventDefault()
    setSaving(true)
    try {
      await createSupportTicket({ ...form, order: Number(form.order) })
      setForm({ order: '', category: 'MISSING_ITEMS', description: '', request_refund: false })
      await queryClient.invalidateQueries({ queryKey: ['support-tickets'] })
      toast.success(t('support.created'))
    } catch (error) {
      const data = error.response?.data
      toast.error(data?.non_field_errors?.[0] || data?.order?.[0] || t('support.createFailed'))
    } finally {
      setSaving(false)
    }
  }

  if (ordersQuery.isLoading || ticketsQuery.isLoading) {
    return <div className="max-w-5xl mx-auto px-4 py-10 text-gray-500">{t('support.loading')}</div>
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 grid lg:grid-cols-[0.9fr_1.1fr] gap-8 items-start">
      <section>
        <div className="mb-6">
          <div className="flex items-center gap-2 text-brand-600 text-sm font-medium"><CircleHelp size={18} /> {t('support.customerCare')}</div>
          <h1 className="text-2xl font-bold text-gray-950 mt-2">{t('support.orderHelp')}</h1>
          <p className="text-gray-500 mt-1">{t('support.subtitle')}</p>
        </div>
        <form onSubmit={submit} className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
          <label className="block text-sm font-medium text-gray-700">
            {t('support.order')}
            <select required value={form.order} onChange={event => setForm(current => ({ ...current, order: event.target.value }))} className="input-field mt-1.5">
              <option value="">{t('support.selectOrder')}</option>
              {orders.map(order => <option key={order.id} value={order.id}>{t('orders.orderNumber', { id: order.id })} - {money(order.total_amount, order.currency || order.currency_code || 'GNF')} - {statusLabel(order.status, t, 'orders')}</option>)}
            </select>
          </label>
          <label className="block text-sm font-medium text-gray-700">
            {t('support.issue')}
            <select value={form.category} onChange={event => setForm(current => ({ ...current, category: event.target.value }))} className="input-field mt-1.5">
              {categories.map(value => <option key={value} value={value}>{t(`support.categories.${value}`)}</option>)}
            </select>
          </label>
          <label className="block text-sm font-medium text-gray-700">
            {t('support.whatHappened')}
            <textarea required minLength={10} maxLength={2000} rows={5} value={form.description} onChange={event => setForm(current => ({ ...current, description: event.target.value }))} className="input-field resize-none mt-1.5" />
          </label>
          <label className="flex items-start gap-3 text-sm text-gray-700">
            <input type="checkbox" checked={form.request_refund} onChange={event => setForm(current => ({ ...current, request_refund: event.target.checked }))} className="mt-1" />
            {t('support.requestRefund')}
          </label>
          <button disabled={saving || !orders.length} className="btn-primary w-full">{saving ? t('support.sending') : t('support.submitTicket')}</button>
        </form>
      </section>

      <section>
        <div className="mb-5">
          <TfoodAssistantPanel surface="support" compact />
        </div>
        <h2 className="text-lg font-semibold text-gray-950 mb-4">{t('support.yourTickets')}</h2>
        {!tickets.length ? (
          <div className="border border-dashed border-gray-300 rounded-lg py-12 text-center text-gray-500"><MessageSquareText className="mx-auto mb-3 text-gray-300" />{t('support.noTickets')}</div>
        ) : (
          <div className="space-y-3">
            {tickets.map(ticket => (
              <article key={ticket.id} className="bg-white border border-gray-200 rounded-lg p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-semibold text-gray-950">{t('support.ticketNumber', { id: ticket.id })} - {t('orders.orderNumber', { id: ticket.order })}</p>
                    <p className="text-sm text-gray-500 mt-1 flex items-center gap-2"><ReceiptText size={14} /> {t(`support.categories.${ticket.category}`, { defaultValue: statusLabel(ticket.category, t) })}</p>
                  </div>
                  <span className="text-xs font-medium bg-gray-100 text-gray-700 px-2 py-1 rounded-md">{statusLabel(ticket.status, t, 'operations')}</span>
                </div>
                <p className="text-sm text-gray-700 mt-4">{ticket.description}</p>
                <div className="flex flex-wrap gap-3 mt-4 text-sm">
                  <span className="flex items-center gap-1 text-gray-500"><Clock3 size={14} /> {new Date(ticket.created_at).toLocaleDateString('en-IN')}</span>
                  {ticket.refund_status !== 'NONE' && <span className="text-amber-700">{t('support.refundStatus', { status: statusLabel(ticket.refund_status, t, 'payments') })}</span>}
                  {Number(ticket.refunded_amount) > 0 && <span className="text-emerald-700">{t('support.refundedAmount', { amount: Number(ticket.refunded_amount).toFixed(2) })}</span>}
                </div>
                {ticket.resolution && <div className="mt-4 border-l-2 border-brand-400 pl-3 text-sm text-gray-700"><strong>{t('support.tfoodResponse')}:</strong> {ticket.resolution}</div>}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
