import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { CircleHelp, Clock3, MessageSquareText, ReceiptText } from 'lucide-react'
import { listOrders } from '../api/orders'
import { createSupportTicket, listSupportTickets } from '../api/support'
import useTitle from '../hooks/useTitle'

const categories = [
  ['MISSING_ITEMS', 'Missing items'],
  ['QUALITY', 'Food quality'],
  ['DELIVERY', 'Delivery issue'],
  ['PAYMENT', 'Payment issue'],
  ['OTHER', 'Other'],
]

export default function SupportPage() {
  useTitle('Help and support')
  const queryClient = useQueryClient()
  const [form, setForm] = useState({ order: '', category: 'MISSING_ITEMS', description: '', request_refund: false })
  const [saving, setSaving] = useState(false)
  const ordersQuery = useQuery({ queryKey: ['orders'], queryFn: async () => (await listOrders()).data })
  const ticketsQuery = useQuery({ queryKey: ['support-tickets'], queryFn: async () => (await listSupportTickets()).data })
  const orders = ordersQuery.data?.results || ordersQuery.data || []
  const tickets = ticketsQuery.data?.results || ticketsQuery.data || []

  const submit = async event => {
    event.preventDefault()
    setSaving(true)
    try {
      await createSupportTicket({ ...form, order: Number(form.order) })
      setForm({ order: '', category: 'MISSING_ITEMS', description: '', request_refund: false })
      await queryClient.invalidateQueries({ queryKey: ['support-tickets'] })
      toast.success('Support ticket created')
    } catch (error) {
      const data = error.response?.data
      toast.error(data?.non_field_errors?.[0] || data?.order?.[0] || 'Could not create support ticket.')
    } finally {
      setSaving(false)
    }
  }

  if (ordersQuery.isLoading || ticketsQuery.isLoading) return <div className="max-w-5xl mx-auto px-4 py-10 text-gray-500">Loading support...</div>

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 grid lg:grid-cols-[0.9fr_1.1fr] gap-8 items-start">
      <section>
        <div className="mb-6">
          <div className="flex items-center gap-2 text-brand-600 text-sm font-medium"><CircleHelp size={18} /> Customer care</div>
          <h1 className="text-2xl font-bold text-gray-950 mt-2">Help with an order</h1>
          <p className="text-gray-500 mt-1">Send the issue directly to T-Food operations.</p>
        </div>
        <form onSubmit={submit} className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
          <label className="block text-sm font-medium text-gray-700">Order
            <select required value={form.order} onChange={event => setForm(current => ({ ...current, order: event.target.value }))} className="input-field mt-1.5">
              <option value="">Select an order</option>
              {orders.map(order => <option key={order.id} value={order.id}>Order #{order.id} · Rs. {Number(order.total_amount).toFixed(2)} · {order.status}</option>)}
            </select>
          </label>
          <label className="block text-sm font-medium text-gray-700">Issue
            <select value={form.category} onChange={event => setForm(current => ({ ...current, category: event.target.value }))} className="input-field mt-1.5">
              {categories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="block text-sm font-medium text-gray-700">What happened?
            <textarea required minLength={10} maxLength={2000} rows={5} value={form.description} onChange={event => setForm(current => ({ ...current, description: event.target.value }))} className="input-field resize-none mt-1.5" />
          </label>
          <label className="flex items-start gap-3 text-sm text-gray-700">
            <input type="checkbox" checked={form.request_refund} onChange={event => setForm(current => ({ ...current, request_refund: event.target.checked }))} className="mt-1" />
            Request a full refund for this order
          </label>
          <button disabled={saving || !orders.length} className="btn-primary w-full">{saving ? 'Sending...' : 'Submit ticket'}</button>
        </form>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-gray-950 mb-4">Your support tickets</h2>
        {!tickets.length ? (
          <div className="border border-dashed border-gray-300 rounded-lg py-12 text-center text-gray-500"><MessageSquareText className="mx-auto mb-3 text-gray-300" />No support tickets yet.</div>
        ) : (
          <div className="space-y-3">
            {tickets.map(ticket => (
              <article key={ticket.id} className="bg-white border border-gray-200 rounded-lg p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-semibold text-gray-950">Ticket #{ticket.id} · Order #{ticket.order}</p>
                    <p className="text-sm text-gray-500 mt-1 flex items-center gap-2"><ReceiptText size={14} /> {ticket.category.replaceAll('_', ' ')}</p>
                  </div>
                  <span className="text-xs font-medium bg-gray-100 text-gray-700 px-2 py-1 rounded-md">{ticket.status.replaceAll('_', ' ')}</span>
                </div>
                <p className="text-sm text-gray-700 mt-4">{ticket.description}</p>
                <div className="flex flex-wrap gap-3 mt-4 text-sm">
                  <span className="flex items-center gap-1 text-gray-500"><Clock3 size={14} /> {new Date(ticket.created_at).toLocaleDateString('en-IN')}</span>
                  {ticket.refund_status !== 'NONE' && <span className="text-amber-700">Refund: {ticket.refund_status}</span>}
                  {Number(ticket.refunded_amount) > 0 && <span className="text-emerald-700">Rs. {Number(ticket.refunded_amount).toFixed(2)} refunded</span>}
                </div>
                {ticket.resolution && <div className="mt-4 border-l-2 border-brand-400 pl-3 text-sm text-gray-700"><strong>T-Food response:</strong> {ticket.resolution}</div>}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
