import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  FileText,
  LineChart,
  ImagePlus,
  LocateFixed,
  Pencil,
  Plus,
  ReceiptText,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Sparkles,
  Store,
  Trash2,
  UploadCloud,
  UserPlus,
  Users,
  Utensils,
  XCircle,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { getMerchantInsights } from '../api/intelligence'
import {
  createMerchantItem,
  createMerchantRestaurant,
  deleteMerchantItem,
  getMerchantAnalytics,
  getMerchantNotifications,
  getMerchantPayouts,
  getMerchantProfile,
  getMerchantSummary,
  createMerchantFulfillmentRequest,
  assignMerchantRiderRestaurant,
  assignMerchantStaffBranches,
  createMerchantNetworkRequest,
  inviteMerchantStaff,
  inviteMerchantRider,
  listMerchantFulfillmentRequests,
  listMerchantNetwork,
  listNearbyMerchants,
  listMerchantReviews,
  listMerchantRiders,
  listMerchantOrders,
  listMerchantRestaurants,
  listMerchantStaff,
  removeMerchantStaffBranch,
  updateMerchantRiderStatus,
  updateMerchantStaff,
  updateMerchantFulfillmentRequest,
  updateMerchantNetworkRelationship,
  updateMerchantItem,
  updateMerchantItemOptions,
  updateMerchantOrderStatus,
  updateMerchantOperatingHours,
  updateMerchantProfile,
  updateMerchantRestaurant,
} from '../api/merchant'
import {
  deleteMerchantVerificationDocument,
  listMerchantVerificationDocuments,
  uploadMerchantVerificationDocument,
} from '../api/verifications'
import { openPrivateMedia } from '../api/media'
import { listMarketAreas, listMarketCities } from '../api/markets'
import { usePreferences } from '../context/PreferencesContext'
import { formatCurrency } from '../lib/formatters'
import { statusLabel } from '../lib/statusLabels'
import useRealtime from '../hooks/useRealtime'
import useTitle from '../hooks/useTitle'

const MerchantVerificationPanel = lazy(() => import('../components/merchant/MerchantVerificationPanel.jsx'))
const MerchantOverviewPanel = lazy(() => import('../components/merchant/MerchantOverviewPanel.jsx'))
const MerchantInsightsPanel = lazy(() => import('../components/merchant/MerchantInsightsPanel.jsx'))

const PanelLoading = () => (
  <section className="py-6 border-b border-gray-200 text-sm text-gray-500">
    Loading section...
  </section>
)

const emptyRestaurant = {
  rest_name: '',
  rest_email: '',
  rest_contact: '',
  rest_address: '',
  rest_city: '',
  branch_name: '',
  branch_code: '',
  branch_type: 'FOOD',
  delivery_mode: 'HYBRID',
  country_code: '',
  city_ref: '',
  area_ref: '',
  branch_manager: '',
  delivery_fee: '0.00',
  min_order_amount: '0.00',
  delivery_radius_km: '15.00',
  estimated_prep_minutes: '25',
  cover_image: null,
  is_open: true,
  pickup_latitude: '',
  pickup_longitude: '',
}

const emptyItem = {
  food_name: '',
  food_desc: '',
  food_price: '',
  food_categ: 'Vegetarian',
  image: null,
  is_available: true,
}

const MENU_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const MENU_IMAGE_MAX_BYTES = 5 * 1024 * 1024

const firstApiError = (data, fallback) => {
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (Array.isArray(data)) return data[0] || fallback
  if (data.detail) return firstApiError(data.detail, fallback)
  const firstValue = Object.values(data)[0]
  return firstApiError(firstValue, fallback)
}

const validateMenuImageFile = file => {
  if (!file) return ''
  if (!MENU_IMAGE_TYPES.includes(file.type)) {
    return 'Use a JPEG, PNG, or WebP image.'
  }
  if (file.size > MENU_IMAGE_MAX_BYTES) {
    return 'Menu images must be 5 MB or smaller.'
  }
  return ''
}

const nextActions = {
  CONFIRMED: { status: 'PREPARING', labelKey: 'merchantDashboard.actions.acceptPrepare' },
  PREPARING: { status: 'READY_FOR_PICKUP', labelKey: 'merchantDashboard.actions.readyPickup' },
}
const closedOrderStatuses = new Set(['DELIVERED', 'CANCELLED', 'EXPIRED'])
const orderHistoryRanges = [
  { value: 'today', labelKey: 'merchantDashboard.historyRanges.today' },
  { value: 'yesterday', labelKey: 'merchantDashboard.historyRanges.yesterday' },
  { value: 'last7', labelKey: 'merchantDashboard.historyRanges.last7' },
  { value: 'last30', labelKey: 'merchantDashboard.historyRanges.last30' },
  { value: 'month', labelKey: 'merchantDashboard.historyRanges.month' },
  { value: 'year', labelKey: 'merchantDashboard.historyRanges.year' },
  { value: 'lastYear', labelKey: 'merchantDashboard.historyRanges.lastYear' },
]

const startOfDay = value => {
  const date = new Date(value)
  date.setHours(0, 0, 0, 0)
  return date
}

const addDays = (value, days) => {
  const date = new Date(value)
  date.setDate(date.getDate() + days)
  return date
}

const orderInHistoryRange = (order, range) => {
  const createdAt = new Date(order.created_at)
  if (Number.isNaN(createdAt.getTime())) return true
  const now = new Date()
  const today = startOfDay(now)
  let start = today
  let end = addDays(today, 1)
  if (range === 'yesterday') {
    start = addDays(today, -1)
    end = today
  } else if (range === 'last7') {
    start = addDays(today, -6)
  } else if (range === 'last30') {
    start = addDays(today, -29)
  } else if (range === 'month') {
    start = new Date(today.getFullYear(), today.getMonth(), 1)
  } else if (range === 'year') {
    start = new Date(today.getFullYear(), 0, 1)
  } else if (range === 'lastYear') {
    start = new Date(today.getFullYear() - 1, 0, 1)
    end = new Date(today.getFullYear(), 0, 1)
  }
  return createdAt >= start && createdAt < end
}

const merchantOrderLabel = (order, t) => (
  order.merchant_order_code ? `Order ${order.merchant_order_code}` : t('orders.orderNumber', { id: order.id })
)

const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const defaultHours = dayNames.map((day, index) => ({
  day_of_week: index,
  day_display: day,
  is_closed: false,
  opens_at: '09:00',
  closes_at: '22:00',
}))
const merchantTabs = [
  { id: 'overview', label: 'Overview' },
  { id: 'orders', label: 'Orders' },
  { id: 'branches', label: 'Branches' },
  { id: 'menu', label: 'Menu' },
  { id: 'revenue', label: 'Revenue' },
  { id: 'performance', label: 'Performance' },
  { id: 'insights', label: 'Insights' },
  { id: 'riders', label: 'Riders' },
  { id: 'staff', label: 'Staff' },
  { id: 'network', label: 'Merchant Network' },
  { id: 'payouts', label: 'Payouts' },
  { id: 'profile', label: 'Profile' },
]
const branchTypes = [
  { value: 'FOOD', label: 'Food' },
  { value: 'GROCERY', label: 'Grocery' },
  { value: 'PHARMACY', label: 'Pharmacy' },
  { value: 'RETAIL', label: 'Retail' },
  { value: 'COURIER', label: 'Courier' },
  { value: 'LOCAL_COMMERCE', label: 'Local commerce' },
]
const deliveryModes = [
  {
    value: 'HYBRID',
    label: 'Merchant first, then T-Food',
    hint: 'Merchant riders get priority first. If none accept, T-Food partners can pick it up.',
  },
  {
    value: 'MERCHANT_DELIVERY',
    label: 'Merchant riders only',
    hint: 'Only riders assigned to this merchant can deliver this branch order.',
  },
  {
    value: 'T_FOOD_DELIVERY',
    label: 'T-Food partners only',
    hint: 'Only platform delivery partners can deliver this branch order.',
  },
]
const deliveryModeByValue = Object.fromEntries(deliveryModes.map(mode => [mode.value, mode]))
const merchantRiderScopeLabel = rider => (
  rider.home_restaurant?.id ? 'Branch-assigned rider' : 'Merchant-wide rider'
)
const currencyForCountry = countryCode => ({
  GN: 'GNF',
  IN: 'INR',
  US: 'USD',
  SA: 'SAR',
})[String(countryCode || '').toUpperCase()] || 'GNF'

const formatMoney = (value, currencyCode = 'GNF', preferences = null) => (
  formatCurrency(value, currencyCode, preferences, { fallbackCurrency: currencyCode })
)
const subscriptionPlanLabel = plan => ({
  NOT_CONFIGURED: 'Not configured',
  TRIAL: 'Trial',
  MONTHLY: 'Monthly',
  YEARLY: 'Yearly',
})[String(plan || 'NOT_CONFIGURED').toUpperCase()] || 'Not configured'
const settlementPreviewRows = preview => ([
  ['Order total', preview?.order_total],
  ['Food subtotal', preview?.food_subtotal],
  ['Platform fee', preview?.platform_fee],
  ['Original merchant payout', preview?.original_merchant_payout],
  ['Fulfilling merchant share', preview?.suggested_fulfilling_merchant_share],
  ['Requesting merchant share', preview?.suggested_requesting_merchant_share],
  ['Delivery fee', preview?.delivery_fee],
  ['Delivery partner fee', preview?.delivery_partner_fee],
])

const SettlementPreviewPanel = ({ preview, label }) => {
  if (!preview?.is_preview_only) return null
  return (
    <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
      <p className="text-sm font-semibold text-amber-900">
        {label || preview.preview_label || 'Preview Only — No Financial Settlement Has Been Applied'}
      </p>
      <div className="mt-3 grid sm:grid-cols-2 gap-2">
        {settlementPreviewRows(preview).map(([name, value]) => (
          <div key={name} className="flex items-center justify-between gap-3 rounded-md bg-white/70 px-3 py-2 text-sm">
            <span className="text-gray-600">{name}</span>
            <span className="font-semibold text-gray-950">{formatMoney(value)}</span>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-amber-800">
        Method: {preview.calculation_method || 'Preview'}.
      </p>
    </div>
  )
}

const FulfillmentTimeline = ({ events = [] }) => {
  if (!events.length) return null
  return (
    <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-4">
      <p className="text-sm font-semibold text-gray-950">Audit timeline</p>
      <div className="mt-3 space-y-3">
        {events.map(event => (
          <div key={event.id} className="border-l-2 border-gray-300 pl-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-gray-900">{formatFulfillmentStatus(event.event_type)}</span>
              {(event.from_status || event.to_status) && (
                <span className="text-xs text-gray-500">
                  {event.from_status ? formatFulfillmentStatus(event.from_status) : 'Created'} {'->'} {formatFulfillmentStatus(event.to_status)}
                </span>
              )}
            </div>
            <p className="mt-1 text-xs text-gray-500">
              {event.actor || 'System'} · {formatDateTime(event.created_at)}
            </p>
            {event.note && <p className="mt-1 text-sm text-gray-600">{event.note}</p>}
          </div>
        ))}
      </div>
    </div>
  )
}
const formatPercent = value => value === null || value === undefined ? '-' : `${Number(value || 0).toFixed(1)}%`
const formatMinutes = value => value === null || value === undefined ? '-' : `${Number(value).toFixed(1)} min`
const safeNumber = value => Number(value || 0)
const merchantAnalyticsQueryKey = (range, branchId) => ['merchant-analytics', range, branchId || 'company']
const merchantAnalyticsQueryRoot = ['merchant-analytics']
const merchantDocumentTypes = [
  { value: 'OWNER_PROFILE_PHOTO', label: 'Owner profile photo' },
  { value: 'NATIONAL_ID', label: 'National ID' },
  { value: 'PASSPORT', label: 'Passport' },
  { value: 'VOTER_CARD', label: 'Voter card' },
  { value: 'RESTAURANT_PHOTO', label: 'Restaurant photo' },
  { value: 'BUSINESS_DOCUMENT', label: 'Business document (optional)' },
]
const identityDocumentTypes = ['NATIONAL_ID', 'PASSPORT', 'VOTER_CARD']
const verificationStatusLabels = {
  PENDING: 'Pending',
  SUBMITTED: 'Submitted',
  APPROVED: 'Approved',
  VERIFIED: 'Verified',
  REJECTED: 'Rejected',
  SUSPENDED: 'Suspended',
  MORE_INFO_REQUIRED: 'More info required',
}
const emptyVerificationForm = {
  document_type: 'OWNER_PROFILE_PHOTO',
  file: null,
  notes: '',
}
const emptyRiderInviteForm = {
  name: '',
  phone: '',
  email: '',
  transport_type: '',
  home_restaurant: '',
}
const staffRoles = [
  { value: 'ADMIN', label: 'Admin' },
  { value: 'BRANCH_MANAGER', label: 'Branch Manager' },
  { value: 'KITCHEN_STAFF', label: 'Kitchen Staff' },
  { value: 'CASHIER', label: 'Cashier' },
  { value: 'DISPATCHER', label: 'Dispatcher' },
  { value: 'CUSTOMER_SUPPORT', label: 'Customer Support' },
  { value: 'FINANCE_STAFF', label: 'Finance Staff' },
  { value: 'VIEWER', label: 'Viewer' },
]
const emptyStaffInviteForm = {
  name: '',
  email: '',
  phone: '',
  role: 'BRANCH_MANAGER',
  is_company_wide: true,
  branch_ids: [],
}
const emptyFulfillmentRequestForm = {
  order_id: '',
  fulfilling_merchant_id: '',
  notes: '',
}
const networkStatusClass = status => {
  if (['ACTIVE', 'ACCEPTED', 'RESOLVED', 'READY_FOR_HANDOFF'].includes(status)) return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (['REQUESTED', 'PENDING', 'IN_PROGRESS'].includes(status)) return 'bg-amber-50 text-amber-700 border-amber-200'
  if (['PAUSED'].includes(status)) return 'bg-gray-50 text-gray-700 border-gray-200'
  if (['BLOCKED', 'REJECTED', 'CANCELLED', 'UNABLE_TO_FULFILL'].includes(status)) return 'bg-red-50 text-red-700 border-red-200'
  return 'bg-gray-50 text-gray-700 border-gray-200'
}
const formatFulfillmentStatus = (value, t) => {
  if (!value) return t ? t('statuses.notAvailable') : 'Not available'
  return t ? statusLabel(value, t, 'common') : value.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, letter => letter.toUpperCase())
}
const fulfillmentActionRules = {
  ACCEPT: request => request.direction === 'incoming' && request.status === 'REQUESTED',
  REJECT: request => request.direction === 'incoming' && request.status === 'REQUESTED',
  START_PREPARATION: request => request.direction === 'incoming' && request.status === 'ACCEPTED' && request.internal_status === 'ACCEPTED',
  READY_FOR_HANDOFF: request => request.direction === 'incoming' && request.status === 'ACCEPTED' && request.internal_status === 'IN_PROGRESS',
  UNABLE_TO_FULFILL: request => request.direction === 'incoming' && request.status === 'ACCEPTED' && request.internal_status === 'IN_PROGRESS',
  RESOLVE: request => request.direction === 'incoming' && request.status === 'ACCEPTED' && ['READY_FOR_HANDOFF', 'UNABLE_TO_FULFILL'].includes(request.internal_status),
  CANCEL: request => request.direction === 'outgoing' && ['REQUESTED', 'ACCEPTED'].includes(request.status) && !['CANCELLED', 'REJECTED', 'RESOLVED'].includes(request.internal_status),
}
const fulfillmentActionLabels = {
  ACCEPT: 'Accept',
  REJECT: 'Reject',
  START_PREPARATION: 'Start preparation',
  READY_FOR_HANDOFF: 'Ready for handoff',
  UNABLE_TO_FULFILL: 'Unable to fulfill',
  RESOLVE: 'Resolve',
  CANCEL: 'Cancel',
}

function KpiCard({ label, value, accent = 'text-gray-950', onClick, actionLabel, isActive = false }) {
  const Component = onClick ? 'button' : 'div'
  return (
    <Component
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      className={`w-full border rounded-lg p-4 text-left ${isActive ? 'border-brand-500 bg-brand-50' : 'border-gray-200'} ${onClick ? 'cursor-pointer transition hover:border-brand-300 hover:bg-brand-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500' : ''}`}
    >
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`text-xl font-bold mt-1 ${accent}`}>{value}</p>
      {actionLabel && <p className="mt-3 text-xs font-semibold text-brand-600">{actionLabel}</p>}
    </Component>
  )
}

function TrendChart({ title, data = [], valueKey = 'gross_sales', formatter = value => value, emptyLabel }) {
  const values = data.map(row => safeNumber(row[valueKey]))
  const maxValue = Math.max(...values, 0)
  const width = 520
  const height = 180
  const padding = 20
  const usableWidth = width - padding * 2
  const usableHeight = height - padding * 2
  const points = data.map((row, index) => {
    const x = data.length === 1 ? width / 2 : padding + (index / (data.length - 1)) * usableWidth
    const y = height - padding - (maxValue ? (safeNumber(row[valueKey]) / maxValue) * usableHeight : 0)
    return `${x},${y}`
  }).join(' ')

  return (
    <div>
      <h3 className="font-semibold text-gray-950 mb-3">{title}</h3>
      <div className="border border-gray-200 rounded-lg p-4">
        {data.length ? (
          <>
            <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-44" role="img" aria-label={title}>
              <line x1={padding} y1={padding} x2={padding} y2={height - padding} stroke="#e5e7eb" />
              <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#e5e7eb" />
              <polyline points={points} fill="none" stroke="#16a34a" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
              {data.map((row, index) => {
                const [x, y] = points.split(' ')[index].split(',').map(Number)
                return <circle key={`${row.date || index}-${valueKey}`} cx={x} cy={y} r="4" fill="#0f766e" />
              })}
            </svg>
            <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
              <span>{data[0]?.date || 'Start'}</span>
              <span className="font-medium text-gray-700">Peak {formatter(maxValue)}</span>
              <span>{data[data.length - 1]?.date || 'Now'}</span>
            </div>
          </>
        ) : (
          <p className="py-8 text-center text-sm text-gray-500">{emptyLabel}</p>
        )}
      </div>
    </div>
  )
}

function BarRows({ title, data = [], labelKey = 'name', valueKey = 'gross_sales', formatter = value => value, secondary, emptyLabel }) {
  const maxValue = Math.max(...data.map(row => safeNumber(row[valueKey])), 0)
  return (
    <div>
      <h3 className="font-semibold text-gray-950 mb-3">{title}</h3>
      <div className="border border-gray-200 rounded-lg p-4 space-y-4">
        {data.length ? data.map((row, index) => (
          <div key={row.item_id || row.date || row.rating || index}>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-gray-700 truncate">{row[labelKey]}</span>
              <span className="font-medium text-gray-950">{formatter(row[valueKey])}</span>
            </div>
            <div className="mt-2 h-2 rounded-full bg-gray-100 overflow-hidden">
              <div
                className="h-full rounded-full bg-brand-600"
                style={{ width: `${maxValue ? Math.max((safeNumber(row[valueKey]) / maxValue) * 100, 4) : 0}%` }}
              />
            </div>
            {secondary && <p className="mt-1 text-xs text-gray-500">{secondary(row)}</p>}
          </div>
        )) : (
          <p className="py-8 text-center text-sm text-gray-500">{emptyLabel}</p>
        )}
      </div>
    </div>
  )
}

function ComparisonCard({ label, current, previous, change }) {
  const isPositive = safeNumber(change) >= 0
  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-xl font-bold mt-1">{formatMoney(current?.gross_sales)}</p>
      <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
        <span>Previous {formatMoney(previous?.gross_sales)}</span>
        <span className={change === null ? 'text-gray-500' : isPositive ? 'text-emerald-700' : 'text-red-600'}>
          {change === null ? 'New' : `${isPositive ? '+' : ''}${Number(change).toFixed(1)}%`}
        </span>
      </div>
    </div>
  )
}

function CompactList({ items = [], emptyLabel, renderItem }) {
  return (
    <div className="divide-y divide-gray-200 border-y border-gray-200">
      {items.length ? items.map(renderItem) : (
        <p className="py-4 text-sm text-gray-500">{emptyLabel}</p>
      )}
    </div>
  )
}

const formatDocumentType = value => (
  merchantDocumentTypes.find(type => type.value === value)?.label || value?.replaceAll('_', ' ') || 'Document'
)

const formatDateTime = value => {
  if (!value) return 'Not available'
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

const documentStatusClass = status => {
  if (status === 'APPROVED') return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (status === 'REJECTED') return 'bg-red-50 text-red-700 border-red-200'
  if (status === 'SUBMITTED' || status === 'PENDING') return 'bg-amber-50 text-amber-700 border-amber-200'
  return 'bg-gray-50 text-gray-700 border-gray-200'
}

function ChecklistItem({ done, label, help }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-gray-200 p-3">
      {done
        ? <CheckCircle2 size={18} className="mt-0.5 flex-shrink-0 text-emerald-600" />
        : <XCircle size={18} className="mt-0.5 flex-shrink-0 text-amber-600" />}
      <div>
        <p className="text-sm font-medium text-gray-900">{label}</p>
        <p className="text-xs text-gray-500 mt-1">{help}</p>
      </div>
    </div>
  )
}

function LegacyMerchantVerificationPanel({
  profile,
  documentsQuery,
  form,
  setForm,
  onUpload,
  uploading,
  onDelete,
  deletingId,
}) {
  const documentsPayload = documentsQuery.data
  const documents = documentsPayload?.results || documentsPayload || []
  const summary = documentsPayload?.summary || {}
  const uploadedTypes = new Set(documents.map(document => document.document_type))
  const hasOwnerProfilePhoto = summary.has_owner_profile_photo ?? uploadedTypes.has('OWNER_PROFILE_PHOTO')
  const hasIdentityDocument = summary.has_identity_document ?? identityDocumentTypes.some(type => uploadedTypes.has(type))
  const hasRestaurantPhoto = summary.has_restaurant_photo ?? uploadedTypes.has('RESTAURANT_PHOTO')
  const status = profile?.verification_status || (profile?.is_verified ? 'APPROVED' : 'PENDING')
  const statusLabel = verificationStatusLabels[status] || status?.replaceAll('_', ' ') || 'Pending'
  const missing = [
    !hasOwnerProfilePhoto && 'Owner profile photo',
    !hasIdentityDocument && 'National ID, Passport, or Voter Card',
    !hasRestaurantPhoto && 'Restaurant photo',
  ].filter(Boolean)

  return (
    <section className="py-6 border-b border-gray-200">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5 mb-5">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck size={20} className="text-brand-600" />
            <h2 className="text-xl font-semibold text-gray-950">Merchant verification</h2>
          </div>
          <p className="text-sm text-gray-500 mt-2 max-w-2xl">
            T-Food reviews your owner profile photo, identity document, and restaurant photo before your store becomes visible to customers.
            Upload clear files here; this is how the owner profile photo is handled for merchant verification.
          </p>
        </div>
        <span className={`inline-flex w-fit items-center rounded-full border px-3 py-1 text-sm font-medium ${documentStatusClass(status)}`}>
          {statusLabel}
        </span>
      </div>

      {profile?.verification_rejection_reason && (
        <div className="mb-5 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <p className="font-medium">Review note</p>
          <p className="mt-1">{profile.verification_rejection_reason}</p>
        </div>
      )}

      {!profile?.is_verified && (
        <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <p className="font-medium text-amber-950">What is missing</p>
          {missing.length ? (
            <p className="mt-1">Upload: {missing.join(', ')}.</p>
          ) : (
            <p className="mt-1">Required documents are uploaded. T-Food operations will review them before publishing the storefront.</p>
          )}
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-3 mb-6">
        <ChecklistItem
          done={hasOwnerProfilePhoto}
          label="Owner profile photo"
          help="A clear photo of the restaurant owner."
        />
        <ChecklistItem
          done={hasIdentityDocument}
          label="One identity document"
          help="National ID, Passport, or Voter Card."
        />
        <ChecklistItem
          done={hasRestaurantPhoto}
          label="Restaurant photo"
          help="A real photo of the storefront, kitchen, or counter."
        />
      </div>

      <form onSubmit={onUpload} className="grid lg:grid-cols-[220px_1fr_1fr_auto] gap-3 items-end rounded-lg border border-gray-200 p-4 mb-6">
        <label className="text-sm font-medium text-gray-700">
          Document type
          <select
            className="input-field mt-1"
            value={form.document_type}
            onChange={event => setForm(current => ({ ...current, document_type: event.target.value }))}
          >
            {merchantDocumentTypes.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium text-gray-700">
          Upload file
          <span className="mt-1 flex min-h-[42px] items-center gap-2 rounded-lg border border-dashed border-gray-300 px-3 text-sm text-gray-600 cursor-pointer hover:bg-gray-50">
            <UploadCloud size={16} className="text-brand-600" />
            <span className="truncate">{form.file?.name || 'Choose image or document'}</span>
            <input
              required
              type="file"
              accept="image/*,.pdf"
              className="hidden"
              onChange={event => setForm(current => ({ ...current, file: event.target.files?.[0] || null }))}
            />
          </span>
        </label>
        <label className="text-sm font-medium text-gray-700">
          Note for reviewer
          <input
            className="input-field mt-1"
            placeholder="T-Food verification note"
            value={form.notes}
            onChange={event => setForm(current => ({ ...current, notes: event.target.value }))}
          />
        </label>
        <button type="submit" disabled={uploading} className="btn-primary inline-flex items-center justify-center gap-2">
          <UploadCloud size={16} /> {uploading ? 'Uploading...' : 'Upload'}
        </button>
      </form>

      <div className="rounded-lg border border-gray-200 divide-y divide-gray-200">
        {documentsQuery.isLoading && <p className="p-4 text-sm text-gray-500">Loading verification documents...</p>}
        {documentsQuery.isError && <p className="p-4 text-sm text-red-600">Could not load verification documents.</p>}
        {!documentsQuery.isLoading && !documents.length && (
          <p className="p-4 text-sm text-gray-500">No verification documents uploaded yet.</p>
        )}
        {documents.map(document => {
          const canDelete = document.status === 'PENDING' || document.status === 'REJECTED'
          return (
            <div key={document.id} className="p-4 flex flex-col md:flex-row md:items-start md:justify-between gap-3">
              <div className="flex items-start gap-3">
                <FileText size={18} className="mt-1 flex-shrink-0 text-brand-600" />
                <div>
                  <p className="font-medium text-gray-950">{formatDocumentType(document.document_type)}</p>
                  <p className="text-xs text-gray-500 mt-1">Uploaded {formatDateTime(document.created_at)}</p>
                  {document.rejection_reason && (
                    <p className="mt-2 text-sm text-red-600">Rejected: {document.rejection_reason}</p>
                  )}
                  {document.file_url && (
                    <button type="button" onClick={() => openPrivateMedia(document.file_url)} className="mt-2 inline-block text-left text-sm font-medium text-brand-700 hover:underline">
                      View uploaded file
                    </button>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${documentStatusClass(document.status)}`}>
                  {document.status?.replaceAll('_', ' ') || 'PENDING'}
                </span>
                {canDelete && (
                  <button
                    type="button"
                    onClick={() => onDelete(document)}
                    disabled={deletingId === document.id}
                    className="p-2 text-red-500 hover:bg-red-50 rounded-lg"
                    title="Delete document"
                  >
                    <Trash2 size={16} />
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

export default function MerchantDashboardPage() {
  const { t } = useTranslation()
  const { preferences } = usePreferences()
  useTitle(t('nav.merchantDashboard'))
  const queryClient = useQueryClient()
  const [restaurantForm, setRestaurantForm] = useState(emptyRestaurant)
  const [branchEditingId, setBranchEditingId] = useState(null)
  const [branchFormOpen, setBranchFormOpen] = useState(false)
  const [itemForm, setItemForm] = useState(emptyItem)
  const [itemEditingId, setItemEditingId] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [selectedRestaurantId, setSelectedRestaurantId] = useState('')
  const [analyticsRange, setAnalyticsRange] = useState('7d')
  const [analyticsBranchId, setAnalyticsBranchId] = useState('')
  const [menuFilter, setMenuFilter] = useState('all')
  const [branchTableFilter, setBranchTableFilter] = useState('all')
  const [orderHistoryRange, setOrderHistoryRange] = useState('today')
  const [saving, setSaving] = useState(false)
  const [hoursDraft, setHoursDraft] = useState(defaultHours)
  const [savingHours, setSavingHours] = useState(false)
  const [editingOptionsFor, setEditingOptionsFor] = useState(null)
  const [optionGroups, setOptionGroups] = useState([])
  const [savingOptions, setSavingOptions] = useState(false)
  const [verificationForm, setVerificationForm] = useState(emptyVerificationForm)
  const [uploadingVerification, setUploadingVerification] = useState(false)
  const [deletingVerificationId, setDeletingVerificationId] = useState(null)
  const [riderInviteForm, setRiderInviteForm] = useState(emptyRiderInviteForm)
  const [lastRiderInvite, setLastRiderInvite] = useState(null)
  const [riderActionId, setRiderActionId] = useState(null)
  const [assigningRiderId, setAssigningRiderId] = useState(null)
  const [expandedRiderId, setExpandedRiderId] = useState(null)
  const [riderBranchFilter, setRiderBranchFilter] = useState('all')
  const [staffInviteForm, setStaffInviteForm] = useState(emptyStaffInviteForm)
  const [lastStaffInvite, setLastStaffInvite] = useState(null)
  const [staffActionId, setStaffActionId] = useState(null)
  const [expandedStaffId, setExpandedStaffId] = useState(null)
  const [networkRadius, setNetworkRadius] = useState('5')
  const [networkActionId, setNetworkActionId] = useState(null)
  const [fulfillmentRequestForm, setFulfillmentRequestForm] = useState(emptyFulfillmentRequestForm)
  const [fulfillmentActionId, setFulfillmentActionId] = useState(null)
  const [profileForm, setProfileForm] = useState({ business_name: '', phone: '' })
  const [savingProfile, setSavingProfile] = useState(false)
  const branchFormRef = useRef(null)

  const profileQuery = useQuery({
    queryKey: ['merchant-profile'],
    queryFn: async () => (await getMerchantProfile()).data,
  })
  const restaurantsQuery = useQuery({
    queryKey: ['merchant-restaurants'],
    queryFn: async () => (await listMerchantRestaurants()).data,
  })
  const restaurantsForQueryGating = restaurantsQuery.data?.results || restaurantsQuery.data || []
  const needsBranchSetupData = activeTab === 'branches' || (!restaurantsForQueryGating.length && activeTab === 'overview')
  const needsAnalyticsData = ['branches', 'revenue', 'performance'].includes(activeTab)
  const needsOrdersData = ['orders', 'network'].includes(activeTab)
  const needsPayoutData = activeTab === 'payouts'
  const needsNotificationsData = activeTab === 'overview'
  const needsReviewData = activeTab === 'overview'
  const needsInsightsData = activeTab === 'insights'
  const needsRiderData = activeTab === 'riders'
  const needsStaffData = activeTab === 'staff'
  const needsNetworkData = activeTab === 'network'
  const needsVerificationData = activeTab === 'profile'
  const citiesQuery = useQuery({
    queryKey: ['market-cities'],
    queryFn: async () => (await listMarketCities()).data,
    enabled: needsBranchSetupData,
    staleTime: 1000 * 60 * 5,
  })
  const areasQuery = useQuery({
    queryKey: ['market-areas', restaurantForm.city_ref],
    queryFn: async () => (await listMarketAreas(restaurantForm.city_ref ? { city: restaurantForm.city_ref } : {})).data,
    enabled: needsBranchSetupData,
    staleTime: 1000 * 60 * 5,
  })
  const summaryQuery = useQuery({
    queryKey: ['merchant-summary'],
    queryFn: async () => (await getMerchantSummary()).data,
  })
  const analyticsQuery = useQuery({
    queryKey: merchantAnalyticsQueryKey(analyticsRange, analyticsBranchId),
    queryFn: async () => (await getMerchantAnalytics(analyticsRange, analyticsBranchId)).data,
    enabled: needsAnalyticsData,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const payoutsQuery = useQuery({
    queryKey: ['merchant-payouts'],
    queryFn: async () => (await getMerchantPayouts()).data,
    enabled: needsPayoutData,
    keepPreviousData: true,
    staleTime: 1000 * 60,
  })
  const merchantNotificationsQuery = useQuery({
    queryKey: ['merchant-notifications'],
    queryFn: async () => (await getMerchantNotifications(5)).data,
    enabled: needsNotificationsData,
    staleTime: 1000 * 30,
  })
  const merchantReviewsQuery = useQuery({
    queryKey: ['merchant-reviews'],
    queryFn: async () => (await listMerchantReviews()).data,
    enabled: needsReviewData,
    staleTime: 1000 * 30,
  })
  const merchantInsightsQuery = useQuery({
    queryKey: ['merchant-insights'],
    queryFn: async () => (await getMerchantInsights()).data,
    enabled: needsInsightsData,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const ordersQuery = useQuery({
    queryKey: ['merchant-orders'],
    queryFn: async () => (await listMerchantOrders()).data,
    enabled: needsOrdersData,
    keepPreviousData: true,
    staleTime: 1000 * 15,
  })
  const merchantRidersQuery = useQuery({
    queryKey: ['merchant-riders'],
    queryFn: async () => (await listMerchantRiders()).data,
    enabled: needsRiderData,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const merchantStaffQuery = useQuery({
    queryKey: ['merchant-staff'],
    queryFn: async () => (await listMerchantStaff()).data,
    enabled: needsStaffData,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const nearbyMerchantsQuery = useQuery({
    queryKey: ['merchant-network-nearby', networkRadius],
    queryFn: async () => (await listNearbyMerchants({ radius_km: networkRadius })).data,
    enabled: needsNetworkData,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const merchantNetworkQuery = useQuery({
    queryKey: ['merchant-network'],
    queryFn: async () => (await listMerchantNetwork()).data,
    enabled: needsNetworkData,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const fulfillmentRequestsQuery = useQuery({
    queryKey: ['merchant-fulfillment-requests'],
    queryFn: async () => (await listMerchantFulfillmentRequests()).data,
    enabled: needsNetworkData,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const merchantVerificationQuery = useQuery({
    queryKey: ['merchant-verification-documents'],
    queryFn: async () => (await listMerchantVerificationDocuments()).data,
    enabled: profileQuery.isSuccess && needsVerificationData,
  })

  const restaurants = restaurantsQuery.data?.results || restaurantsQuery.data || []
  const cities = citiesQuery.data?.results || citiesQuery.data || []
  const areas = areasQuery.data?.results || areasQuery.data || []
  const orders = ordersQuery.data?.results || ordersQuery.data || []
  const activeOrders = orders.filter(order => !closedOrderStatuses.has(order.status))
  const historyOrders = orders.filter(order => (
    closedOrderStatuses.has(order.status) && orderInHistoryRange(order, orderHistoryRange)
  ))
  const restaurant = restaurants.find(branch => String(branch.id) === String(selectedRestaurantId)) || restaurants[0]
  const restaurantCurrency = restaurant?.currency_code || restaurant?.currency || currencyForCountry(restaurant?.country_code)
  const money = (value, currencyCode = restaurantCurrency) => formatMoney(value, currencyCode, preferences)
  const merchantProfile = profileQuery.data
  const summary = summaryQuery.data
  const analytics = analyticsQuery.data
  const insights = merchantInsightsQuery.data
  const payouts = payoutsQuery.data
  const merchantNotifications = merchantNotificationsQuery.data
  const merchantReviews = merchantReviewsQuery.data?.results || merchantReviewsQuery.data || []
  const riderPayload = merchantRidersQuery.data || {}
  const merchantRiders = riderPayload.results || []
  const riderInvites = riderPayload.invites || []
  const staffPayload = merchantStaffQuery.data || {}
  const merchantStaff = staffPayload.results || []
  const staffInvites = staffPayload.invites || []
  const visibleMerchantRiders = merchantRiders.filter(rider => {
    if (riderBranchFilter === 'all') return true
    if (riderBranchFilter === 'unassigned') return !rider.home_restaurant?.id
    return String(rider.home_restaurant?.id || '') === String(riderBranchFilter)
  })
  const nearbyMerchants = nearbyMerchantsQuery.data?.results || []
  const merchantNetwork = merchantNetworkQuery.data || {}
  const fulfillmentRequests = fulfillmentRequestsQuery.data || {}
  const activeCollaborators = (merchantNetwork.active || []).map(relationship => (
    relationship.direction === 'incoming' ? relationship.from_merchant : relationship.to_merchant
  )).filter(Boolean)
  const riderSummary = {
    total: merchantRiders.length,
    active: merchantRiders.filter(rider => rider.status === 'ACTIVE').length,
    pending: merchantRiders.filter(rider => !rider.partner_is_verified || ['INVITED', 'PENDING_APPROVAL'].includes(rider.status)).length,
    inactive: merchantRiders.filter(rider => ['INACTIVE', 'REMOVED'].includes(rider.status)).length,
  }
  const staffSummary = {
    total: merchantStaff.length,
    active: merchantStaff.filter(staff => staff.membership_status === 'ACTIVE').length,
    pending: merchantStaff.filter(staff => ['PENDING', 'SUBMITTED', 'MORE_INFO_REQUIRED'].includes(staff.verification_status)).length,
    rejected: merchantStaff.filter(staff => staff.verification_status === 'REJECTED').length,
    suspended: merchantStaff.filter(staff => staff.verification_status === 'SUSPENDED').length,
    removed: merchantStaff.filter(staff => staff.membership_status === 'REMOVED').length,
  }
  const branchRiderCounts = merchantRiders.reduce((counts, rider) => {
    const branchId = rider.home_restaurant?.id
    if (!branchId) return counts
    counts[branchId] = (counts[branchId] || 0) + 1
    return counts
  }, {})
  const activeBranchRiderCounts = merchantRiders.reduce((counts, rider) => {
    const branchId = rider.home_restaurant?.id
    if (!branchId || rider.status !== 'ACTIVE' || !rider.partner_is_verified) return counts
    counts[branchId] = (counts[branchId] || 0) + 1
    return counts
  }, {})
  const filteredBranches = restaurants.filter(branch => {
    if (branchTableFilter === 'open') return branch.is_open
    if (branchTableFilter === 'active') return branch.is_active
    if (branchTableFilter === 'with-riders') return (branchRiderCounts[branch.id] || 0) > 0
    return true
  })
  const menuItems = restaurant?.menu_items || []
  const unavailableItems = menuItems.filter(item => !item.is_available)
  const visibleMenuItems = menuItems.filter(item => {
    if (menuFilter === 'available') return item.is_available
    if (menuFilter === 'unavailable') return !item.is_available
    return true
  })

  useEffect(() => {
    if (!restaurants.length) return
    const selectedStillExists = restaurants.some(branch => String(branch.id) === String(selectedRestaurantId))
    if (!selectedRestaurantId || !selectedStillExists) {
      setSelectedRestaurantId(String(restaurants[0].id))
    }
  }, [restaurants, selectedRestaurantId])

  useEffect(() => {
    if (!merchantProfile) return
    setProfileForm({
      business_name: merchantProfile.business_name || '',
      phone: merchantProfile.phone || '',
    })
  }, [merchantProfile?.business_name, merchantProfile?.phone])

  useEffect(() => {
    if (!restaurant) return
    const saved = restaurant.operating_hours || []
    setHoursDraft(saved.length === 7 ? saved : defaultHours)
  }, [restaurant?.id, restaurant?.operating_hours])

  const refreshRestaurants = () => queryClient.invalidateQueries({ queryKey: ['merchant-restaurants'] })
  const refreshOrders = () => queryClient.invalidateQueries({ queryKey: ['merchant-orders'] })
  const refreshSummary = () => queryClient.invalidateQueries({ queryKey: ['merchant-summary'] })
  const refreshAnalytics = () => queryClient.invalidateQueries({ queryKey: merchantAnalyticsQueryRoot })
  const refreshInsights = () => queryClient.invalidateQueries({ queryKey: ['merchant-insights'] })
  const refreshMerchantNotifications = () => queryClient.invalidateQueries({ queryKey: ['merchant-notifications'] })
  const refreshRiders = () => queryClient.invalidateQueries({ queryKey: ['merchant-riders'] })
  const refreshStaff = () => queryClient.invalidateQueries({ queryKey: ['merchant-staff'] })
  const refreshNetwork = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: ['merchant-network'] }),
    queryClient.invalidateQueries({ queryKey: ['merchant-network-nearby'] }),
  ])
  const refreshFulfillmentRequests = () => queryClient.invalidateQueries({ queryKey: ['merchant-fulfillment-requests'] })
  const refreshVerification = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: ['merchant-verification-documents'] }),
    queryClient.invalidateQueries({ queryKey: ['merchant-profile'] }),
  ])
  const saveMerchantProfile = async event => {
    event.preventDefault()
    const businessName = profileForm.business_name.trim()
    const phone = profileForm.phone.trim()
    if (!phone) {
      toast.error('Add the merchant owner phone number before approval.')
      return
    }
    setSavingProfile(true)
    try {
      await updateMerchantProfile({ business_name: businessName, phone })
      await queryClient.invalidateQueries({ queryKey: ['merchant-profile'] })
      toast.success('Merchant contact saved')
    } catch (error) {
      toast.error(error.response?.data?.phone?.[0] || error.response?.data?.business_name?.[0] || 'Could not save merchant contact.')
    } finally {
      setSavingProfile(false)
    }
  }
  const branchPayload = form => {
    const payload = { ...form }
    ;['city_ref', 'area_ref', 'branch_manager'].forEach(field => {
      if (!payload[field]) delete payload[field]
    })
    if (!payload.country_code) delete payload.country_code
    if (!payload.branch_code) delete payload.branch_code
    return payload
  }
  const resetBranchForm = () => {
    setBranchEditingId(null)
    setRestaurantForm(emptyRestaurant)
    setBranchFormOpen(false)
  }
  const openNewBranchForm = () => {
    setBranchEditingId(null)
    setRestaurantForm(emptyRestaurant)
    setBranchFormOpen(true)
    window.requestAnimationFrame(() => {
      branchFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }
  const editBranch = branch => {
    setBranchEditingId(branch.id)
    setRestaurantForm({
      rest_name: branch.rest_name || '',
      rest_email: branch.rest_email || '',
      rest_contact: branch.rest_contact || '',
      rest_address: branch.rest_address || '',
      rest_city: branch.rest_city || '',
      branch_name: branch.branch_name || '',
      branch_code: branch.branch_code || '',
      branch_type: branch.branch_type || 'FOOD',
      delivery_mode: branch.delivery_mode || 'HYBRID',
      country_code: branch.country_code || '',
      city_ref: branch.city_ref || '',
      area_ref: branch.area_ref || '',
      branch_manager: branch.branch_manager || '',
      delivery_fee: branch.delivery_fee || '0.00',
      min_order_amount: branch.min_order_amount || '0.00',
      delivery_radius_km: branch.delivery_radius_km || '15.00',
      estimated_prep_minutes: branch.estimated_prep_minutes || '25',
      cover_image: null,
      is_open: branch.is_open,
      pickup_latitude: branch.pickup_latitude || '',
      pickup_longitude: branch.pickup_longitude || '',
    })
    setBranchFormOpen(true)
    setActiveTab('branches')
    window.requestAnimationFrame(() => {
      branchFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  }
  const realtime = useRealtime({
    onMessage: message => {
      if (['order.created', 'order.status_changed'].includes(message?.type)) {
        refreshOrders()
        refreshSummary()
        refreshAnalytics()
        refreshInsights()
        refreshMerchantNotifications()
      }
    },
  })
  const analyticsLastUpdated = analyticsQuery.dataUpdatedAt
    ? new Intl.DateTimeFormat(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }).format(new Date(analyticsQuery.dataUpdatedAt))
    : 'Not loaded yet'
  const refreshAnalyticsNow = () => analyticsQuery.refetch()
  const selectedAnalyticsBranch = restaurants.find(branch => String(branch.id) === String(analyticsBranchId))
  const analyticsScopeLabel = analyticsBranchId
    ? `Branch View: ${selectedAnalyticsBranch?.branch_name || selectedAnalyticsBranch?.rest_name || analytics?.branch?.name || 'Selected branch'}`
    : 'Company View: all branches'
  const openBranchAnalytics = branch => {
    setAnalyticsBranchId(String(branch.id))
    setActiveTab('revenue')
  }
  const analyticsScopeControl = (
    <select
      value={analyticsBranchId}
      onChange={event => setAnalyticsBranchId(event.target.value)}
      className="input-field sm:w-64"
      aria-label="Analytics scope"
    >
      <option value="">Company View - all branches</option>
      {restaurants.map(branch => (
        <option key={branch.id} value={branch.id}>
          Branch View - {branch.branch_name || branch.rest_name}
        </option>
      ))}
    </select>
  )

  const uploadVerification = async event => {
    event.preventDefault()
    if (!verificationForm.file) {
      toast.error('Choose a verification file to upload.')
      return
    }
    setUploadingVerification(true)
    try {
      const form = new FormData()
      form.append('document_type', verificationForm.document_type)
      form.append('file', verificationForm.file)
      if (verificationForm.notes) form.append('notes', verificationForm.notes)
      await uploadMerchantVerificationDocument(form)
      setVerificationForm(emptyVerificationForm)
      await refreshVerification()
      toast.success('Verification document uploaded')
    } catch (error) {
      toast.error(error.response?.data?.document_type?.[0] || error.response?.data?.file?.[0] || 'Could not upload verification document.')
    } finally {
      setUploadingVerification(false)
    }
  }

  const deleteVerification = async document => {
    setDeletingVerificationId(document.id)
    try {
      await deleteMerchantVerificationDocument(document.id)
      await refreshVerification()
      toast.success('Verification document removed')
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not delete verification document.')
    } finally {
      setDeletingVerificationId(null)
    }
  }

  const inviteRider = async event => {
    event.preventDefault()
    if (!riderInviteForm.name.trim()) {
      toast.error('Add the rider name.')
      return
    }
    setRiderActionId('invite')
    try {
      const payload = {
        ...riderInviteForm,
        home_restaurant: riderInviteForm.home_restaurant || null,
      }
      const response = await inviteMerchantRider(payload)
      setLastRiderInvite(response.data)
      setRiderInviteForm(emptyRiderInviteForm)
      await refreshRiders()
      toast.success('Rider invite created')
    } catch (error) {
      toast.error(error.response?.data?.home_restaurant?.[0] || error.response?.data?.name?.[0] || 'Could not create rider invite.')
    } finally {
      setRiderActionId(null)
    }
  }

  const setRiderStatus = async (rider, status) => {
    setRiderActionId(`${rider.id}-${status}`)
    try {
      await updateMerchantRiderStatus(rider.id, status)
      await refreshRiders()
      toast.success(`Rider marked ${status.toLowerCase().replaceAll('_', ' ')}`)
    } catch (error) {
      toast.error(error.response?.data?.status?.[0] || error.response?.data?.detail || 'Could not update rider.')
    } finally {
      setRiderActionId(null)
    }
  }

  const assignRiderRestaurant = async (rider, homeRestaurant) => {
    setAssigningRiderId(rider.id)
    try {
      await assignMerchantRiderRestaurant(rider.id, homeRestaurant)
      await refreshRiders()
      toast.success('Rider restaurant assignment updated')
    } catch (error) {
      toast.error(error.response?.data?.home_restaurant?.[0] || error.response?.data?.detail || 'Could not assign restaurant.')
    } finally {
      setAssigningRiderId(null)
    }
  }

  const inviteStaff = async event => {
    event.preventDefault()
    if (!staffInviteForm.name.trim()) {
      toast.error('Add the staff member name.')
      return
    }
    if (!staffInviteForm.is_company_wide && !staffInviteForm.branch_ids.length) {
      toast.error('Choose at least one branch or use company-wide access.')
      return
    }
    setStaffActionId('invite')
    try {
      const payload = {
        ...staffInviteForm,
        branch_ids: staffInviteForm.is_company_wide ? [] : staffInviteForm.branch_ids,
      }
      const response = await inviteMerchantStaff(payload)
      setLastStaffInvite(response.data)
      setStaffInviteForm(emptyStaffInviteForm)
      await refreshStaff()
      toast.success('Staff invite created')
    } catch (error) {
      toast.error(error.response?.data?.branch_ids?.[0] || error.response?.data?.name?.[0] || error.response?.data?.detail || 'Could not create staff invite.')
    } finally {
      setStaffActionId(null)
    }
  }

  const updateStaff = async (staff, payload, successMessage) => {
    setStaffActionId(`${staff.id}-${Object.keys(payload).join('-')}`)
    try {
      await updateMerchantStaff(staff.id, payload)
      await refreshStaff()
      toast.success(successMessage)
    } catch (error) {
      toast.error(error.response?.data?.membership_status?.[0] || error.response?.data?.role?.[0] || error.response?.data?.detail || 'Could not update staff member.')
    } finally {
      setStaffActionId(null)
    }
  }

  const assignStaffBranches = async (staff, branchIds) => {
    setStaffActionId(`${staff.id}-branches`)
    try {
      await assignMerchantStaffBranches(staff.id, branchIds)
      await refreshStaff()
      toast.success('Staff branch access updated')
    } catch (error) {
      toast.error(error.response?.data?.branch_ids?.[0] || error.response?.data?.detail || 'Could not assign branches.')
    } finally {
      setStaffActionId(null)
    }
  }

  const removeStaffBranch = async (staff, branchId) => {
    setStaffActionId(`${staff.id}-remove-${branchId}`)
    try {
      await removeMerchantStaffBranch(staff.id, branchId)
      await refreshStaff()
      toast.success('Branch access removed')
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not remove branch access.')
    } finally {
      setStaffActionId(null)
    }
  }

  const sendNetworkRequest = async merchant => {
    setNetworkActionId(`request-${merchant.id}`)
    try {
      await createMerchantNetworkRequest({ to_merchant: merchant.id })
      await refreshNetwork()
      toast.success('Collaboration request sent')
    } catch (error) {
      toast.error(error.response?.data?.detail || error.response?.data?.to_merchant?.[0] || 'Could not send collaboration request.')
    } finally {
      setNetworkActionId(null)
    }
  }

  const updateNetworkRelationship = async (relationship, action) => {
    setNetworkActionId(`${relationship.id}-${action}`)
    try {
      await updateMerchantNetworkRelationship(relationship.id, action)
      await refreshNetwork()
      toast.success(`Collaboration ${action.toLowerCase()} action saved`)
    } catch (error) {
      toast.error(error.response?.data?.action?.[0] || error.response?.data?.detail || 'Could not update collaboration.')
    } finally {
      setNetworkActionId(null)
    }
  }

  const createFulfillmentRequest = async event => {
    event.preventDefault()
    if (!fulfillmentRequestForm.order_id || !fulfillmentRequestForm.fulfilling_merchant_id) {
      toast.error('Choose an order and a collaboration merchant.')
      return
    }
    setFulfillmentActionId('create')
    try {
      await createMerchantFulfillmentRequest({
        order_id: fulfillmentRequestForm.order_id,
        fulfilling_merchant_id: fulfillmentRequestForm.fulfilling_merchant_id,
        notes: fulfillmentRequestForm.notes,
      })
      setFulfillmentRequestForm(emptyFulfillmentRequestForm)
      await refreshFulfillmentRequests()
      toast.success('Fulfillment help request sent')
    } catch (error) {
      toast.error(error.response?.data?.order_id?.[0] || error.response?.data?.fulfilling_merchant_id?.[0] || error.response?.data?.detail || 'Could not create fulfillment request.')
    } finally {
      setFulfillmentActionId(null)
    }
  }

  const respondToFulfillmentRequest = async (request, action) => {
    setFulfillmentActionId(`${request.id}-${action}`)
    try {
      await updateMerchantFulfillmentRequest(request.id, action)
      await refreshFulfillmentRequests()
      toast.success(`Fulfillment request ${action.toLowerCase()} saved`)
    } catch (error) {
      toast.error(error.response?.data?.action?.[0] || error.response?.data?.detail || 'Could not update fulfillment request.')
    } finally {
      setFulfillmentActionId(null)
    }
  }

  const createRestaurant = async event => {
    event.preventDefault()
    setSaving(true)
    try {
      await createMerchantRestaurant(branchPayload(restaurantForm))
      setRestaurantForm(emptyRestaurant)
      await refreshRestaurants()
      toast.success('Storefront created')
    } catch (error) {
      toast.error(error.response?.data?.rest_email?.[0] || 'Could not create storefront.')
    } finally {
      setSaving(false)
    }
  }

  const saveBranch = async event => {
    event.preventDefault()
    setSaving(true)
    try {
      if (branchEditingId) {
        await updateMerchantRestaurant(branchEditingId, branchPayload(restaurantForm))
        toast.success('Branch updated')
      } else {
        await createMerchantRestaurant(branchPayload(restaurantForm))
        toast.success('Branch created')
      }
      resetBranchForm()
      await refreshRestaurants()
      await refreshSummary()
    } catch (error) {
      toast.error(error.response?.data?.rest_email?.[0] || error.response?.data?.area_ref?.[0] || 'Could not save branch.')
    } finally {
      setSaving(false)
    }
  }

  const resetItemForm = () => {
    setItemForm(emptyItem)
    setItemEditingId(null)
  }

  const openBranchMenu = branch => {
    setSelectedRestaurantId(String(branch.id))
    setMenuFilter('all')
    resetItemForm()
    setActiveTab('menu')
  }

  const handleMenuImageChange = event => {
    const file = event.target.files?.[0] || null
    const error = validateMenuImageFile(file)
    if (error) {
      toast.error(error)
      event.target.value = ''
      setItemForm(form => ({ ...form, image: null }))
      return
    }
    setItemForm(form => ({ ...form, image: file }))
  }

  const saveItem = async event => {
    event.preventDefault()
    setSaving(true)
    try {
      if (itemEditingId) {
        await updateMerchantItem(restaurant.id, itemEditingId, itemForm)
        toast.success('Menu item updated')
      } else {
        await createMerchantItem(restaurant.id, itemForm)
        toast.success('Menu item added')
      }
      resetItemForm()
      await refreshRestaurants()
    } catch (error) {
      toast.error(firstApiError(
        error.response?.data,
        itemEditingId ? 'Could not update menu item.' : 'Could not add menu item.',
      ))
    } finally {
      setSaving(false)
    }
  }

  const toggleStore = async () => {
    try {
      await updateMerchantRestaurant(restaurant.id, { is_open: !restaurant.is_open })
      await refreshRestaurants()
      toast.success(restaurant.is_open ? 'Store paused' : 'Store opened')
    } catch {
      toast.error('Could not update store status.')
    }
  }

  const toggleBranchOpen = async branch => {
    try {
      await updateMerchantRestaurant(branch.id, { is_open: !branch.is_open })
      await refreshRestaurants()
      toast.success(branch.is_open ? 'Branch closed' : 'Branch opened')
    } catch {
      toast.error('Could not update branch status.')
    }
  }

  const updateServiceSetting = async (field, value) => {
    if (String(value) === String(restaurant[field])) return
    try {
      await updateMerchantRestaurant(restaurant.id, { [field]: value })
      await refreshRestaurants()
      toast.success('Delivery settings updated')
    } catch (error) {
      toast.error(error.response?.data?.[field]?.[0] || 'Could not update delivery settings.')
    }
  }

  const saveOperatingHours = async () => {
    setSavingHours(true)
    try {
      await updateMerchantOperatingHours(restaurant.id, hoursDraft.map(entry => ({
        day_of_week: entry.day_of_week,
        is_closed: entry.is_closed,
        opens_at: entry.opens_at,
        closes_at: entry.closes_at,
      })))
      await refreshRestaurants()
      toast.success('Weekly operating hours saved')
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not save operating hours.')
    } finally {
      setSavingHours(false)
    }
  }

  const updateCover = async event => {
    const file = event.target.files?.[0]
    if (!file) return
    try {
      await updateMerchantRestaurant(restaurant.id, { cover_image: file })
      await refreshRestaurants()
      toast.success('Store cover updated')
    } catch {
      toast.error('Could not upload cover image.')
    }
  }

  const capturePickupLocation = existingRestaurant => {
    if (!navigator.geolocation) {
      toast.error('Location is not supported by this browser.')
      return
    }
    navigator.geolocation.getCurrentPosition(
      async position => {
        const location = {
          pickup_latitude: position.coords.latitude,
          pickup_longitude: position.coords.longitude,
        }
        if (!existingRestaurant) {
          setRestaurantForm(current => ({ ...current, ...location }))
          toast.success('Pickup location pinned')
          return
        }
        try {
          await updateMerchantRestaurant(existingRestaurant.id, location)
          await refreshRestaurants()
          toast.success('Pickup location updated')
        } catch {
          toast.error('Could not update pickup location.')
        }
      },
      () => toast.error('Could not access your location.'),
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  const toggleItem = async item => {
    try {
      await updateMerchantItem(restaurant.id, item.id, { is_available: !item.is_available })
      await refreshRestaurants()
      toast.success(item.is_available ? 'Item marked unavailable' : 'Item marked available')
    } catch {
      toast.error('Could not update item availability.')
    }
  }

  const removeItem = async itemId => {
    const item = restaurant.menu_items.find(current => current.id === itemId)
    const confirmed = window.confirm(`Delete ${item?.food_name || 'this menu item'}?`)
    if (!confirmed) return
    try {
      await deleteMerchantItem(restaurant.id, itemId)
      if (itemEditingId === itemId) resetItemForm()
      await refreshRestaurants()
      toast.success('Menu item removed')
    } catch (error) {
      toast.error(firstApiError(error.response?.data, 'Could not delete menu item.'))
    }
  }

  const startEditItem = item => {
    setItemEditingId(item.id)
    setItemForm({
      food_name: item.food_name || '',
      food_desc: item.food_desc || '',
      food_price: item.food_price || '',
      food_categ: item.food_categ || 'Vegetarian',
      image: null,
      is_available: item.is_available,
    })
  }

  const editOptions = item => {
    setEditingOptionsFor(item)
    setOptionGroups((item.option_groups || []).map(group => ({
      ...group,
      options: group.options.map(option => ({ ...option })),
    })))
  }

  const addOptionGroup = () => setOptionGroups(current => [...current, {
    name: '', min_select: 0, max_select: 1, options: [],
  }])

  const updateOptionGroup = (index, patch) => setOptionGroups(current => current.map(
    (group, groupIndex) => groupIndex === index ? { ...group, ...patch } : group,
  ))

  const addOption = groupIndex => setOptionGroups(current => current.map(
    (group, index) => index === groupIndex
      ? { ...group, options: [...group.options, { name: '', price_delta: '0.00', is_available: true }] }
      : group,
  ))

  const updateOption = (groupIndex, optionIndex, patch) => setOptionGroups(current => current.map(
    (group, index) => index === groupIndex
      ? { ...group, options: group.options.map((option, currentOptionIndex) => currentOptionIndex === optionIndex ? { ...option, ...patch } : option) }
      : group,
  ))

  const saveOptions = async () => {
    setSavingOptions(true)
    try {
      await updateMerchantItemOptions(restaurant.id, editingOptionsFor.id, optionGroups)
      await refreshRestaurants()
      setEditingOptionsFor(null)
      toast.success('Item options saved')
    } catch (error) {
      const details = error.response?.data
      toast.error(details?.detail || details?.[0]?.non_field_errors?.[0] || 'Could not save item options.')
    } finally {
      setSavingOptions(false)
    }
  }

  const advanceOrder = async (orderId, status) => {
    try {
      await updateMerchantOrderStatus(orderId, status)
      await refreshOrders()
      await refreshSummary()
      await refreshAnalytics()
      toast.success('Order status updated')
    } catch (error) {
      toast.error(error.response?.data?.status?.[0] || 'Could not update order.')
    }
  }

  const renderNetworkRelationship = relationship => {
    const otherMerchant = relationship.direction === 'incoming'
      ? relationship.from_merchant
      : relationship.to_merchant
    const canAccept = relationship.status === 'REQUESTED' && relationship.direction === 'incoming'
    return (
      <div key={relationship.id} className="rounded-lg border border-gray-200 p-4">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h4 className="font-semibold text-gray-950">{otherMerchant?.business_name || otherMerchant?.username || 'Merchant'}</h4>
                  <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${networkStatusClass(relationship.status)}`}>
                {statusLabel(relationship.status, t, 'operations')}
              </span>
              {otherMerchant?.is_verified && (
                <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                  Verified
                </span>
              )}
            </div>
            <p className="mt-1 text-sm text-gray-500">
              {relationship.direction === 'incoming' ? 'Incoming request' : 'Outgoing request'}
              {relationship.distance_km ? ` · ${relationship.distance_km} km away` : ''}
            </p>
            {relationship.notes && <p className="mt-2 text-sm text-gray-600">{relationship.notes}</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            {canAccept && (
              <button
                type="button"
                disabled={networkActionId === `${relationship.id}-ACCEPT`}
                onClick={() => updateNetworkRelationship(relationship, 'ACCEPT')}
                className="btn-secondary px-3 py-2 text-sm"
              >
                Accept
              </button>
            )}
            <button
              type="button"
              disabled={networkActionId === `${relationship.id}-PAUSE`}
              onClick={() => updateNetworkRelationship(relationship, 'PAUSE')}
              className="btn-secondary px-3 py-2 text-sm"
            >
              Pause
            </button>
            <button
              type="button"
              disabled={networkActionId === `${relationship.id}-BLOCK`}
              onClick={() => updateNetworkRelationship(relationship, 'BLOCK')}
              className="btn-secondary px-3 py-2 text-sm text-red-600"
            >
              Block
            </button>
          </div>
        </div>
      </div>
    )
  }

  const renderStaffSection = () => (
    <section className="py-8 border-b border-gray-200">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-5">
        <div className="flex items-start gap-2">
          <Users size={21} className="text-brand-600 mt-0.5" />
          <div>
            <h2 className="text-xl font-semibold text-gray-950">Staff management</h2>
            <p className="text-sm text-gray-500 mt-1">
              Invite and manage company staff. T-Food Operations remains responsible for identity verification.
            </p>
          </div>
        </div>
        <button type="button" onClick={() => document.getElementById('invite-staff-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} className="btn-primary py-2 px-3 text-sm inline-flex items-center justify-center gap-2">
          <UserPlus size={16} /> Invite Staff
        </button>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-6 gap-3 mb-6">
        <KpiCard label="Total staff" value={staffSummary.total} />
        <KpiCard label="Active staff" value={staffSummary.active} accent="text-emerald-700" />
        <KpiCard label="Pending verification" value={staffSummary.pending} accent="text-amber-700" />
        <KpiCard label="Rejected" value={staffSummary.rejected} accent="text-red-600" />
        <KpiCard label="Suspended" value={staffSummary.suspended} accent="text-red-600" />
        <KpiCard label="Removed" value={staffSummary.removed} accent="text-gray-700" />
      </div>

      {!restaurants.length && (
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          No branches configured yet. You can still invite company-wide staff, or create a branch first.
        </div>
      )}

      {!merchantStaff.length && (
        <div className="mb-6 border border-dashed border-gray-300 rounded-lg p-6 text-center">
          <p className="font-semibold text-gray-950">Invite your first staff member.</p>
          <p className="text-sm text-gray-500 mt-2">Staff accounts must complete T-Food identity verification before they can become active.</p>
          <button type="button" onClick={() => document.getElementById('invite-staff-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} className="btn-primary mt-4 px-4 py-2">
            Invite Staff
          </button>
        </div>
      )}

      <div id="invite-staff-form" className="grid lg:grid-cols-[1fr_360px] gap-6 mb-6 scroll-mt-24">
        <form onSubmit={inviteStaff} className="border border-gray-200 rounded-lg p-5">
          <h3 className="font-semibold text-gray-950">Invite staff</h3>
          <p className="text-sm text-gray-500 mt-1">Create an invite token now. Email or SMS sending is not active yet.</p>
          <div className="grid sm:grid-cols-2 gap-4 mt-4">
            <input required className="input-field" placeholder="T-Food Branch Manager" value={staffInviteForm.name} onChange={event => setStaffInviteForm(form => ({ ...form, name: event.target.value }))} />
            <input type="email" className="input-field" placeholder="branch.manager@t-food.gn" value={staffInviteForm.email} onChange={event => setStaffInviteForm(form => ({ ...form, email: event.target.value }))} />
            <input className="input-field" placeholder="+224 620 00 00 00" value={staffInviteForm.phone} onChange={event => setStaffInviteForm(form => ({ ...form, phone: event.target.value }))} />
            <select className="input-field bg-white" value={staffInviteForm.role} onChange={event => setStaffInviteForm(form => ({ ...form, role: event.target.value }))}>
              {staffRoles.map(role => <option key={role.value} value={role.value}>{role.label}</option>)}
            </select>
            <label className="sm:col-span-2 flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-3 text-sm font-medium text-gray-700">
              <input
                type="checkbox"
                checked={staffInviteForm.is_company_wide}
                onChange={event => setStaffInviteForm(form => ({
                  ...form,
                  is_company_wide: event.target.checked,
                  branch_ids: event.target.checked ? [] : form.branch_ids,
                }))}
              />
              Company-wide access
            </label>
            {!staffInviteForm.is_company_wide && (
              <label className="sm:col-span-2 text-sm font-medium text-gray-700">
                Branch assignments
                <select
                  multiple
                  disabled={!restaurants.length}
                  className="input-field mt-1 min-h-[120px] bg-white"
                  value={staffInviteForm.branch_ids}
                  onChange={event => setStaffInviteForm(form => ({
                    ...form,
                    branch_ids: Array.from(event.target.selectedOptions).map(option => option.value),
                  }))}
                >
                  {restaurants.map(branch => (
                    <option key={branch.id} value={branch.id} disabled={!branch.is_active}>
                      {branch.branch_name || branch.rest_name}{branch.is_active ? '' : ' (inactive)'}
                    </option>
                  ))}
                </select>
                {!restaurants.length && <span className="mt-1 block text-xs text-amber-700">Create a branch before inviting branch-specific staff.</span>}
              </label>
            )}
          </div>
          <button
            type="submit"
            disabled={staffActionId === 'invite' || (!staffInviteForm.is_company_wide && !restaurants.length)}
            className="btn-primary mt-4 px-4 py-2"
          >
            {staffActionId === 'invite' ? 'Creating invite...' : 'Create invite'}
          </button>
        </form>

        <div className="border border-gray-200 rounded-lg p-5">
          <h3 className="font-semibold text-gray-950">Latest invite</h3>
          {lastStaffInvite ? (
            <div className="mt-4 space-y-3 text-sm">
              <p><span className="text-gray-500">Name:</span> <strong>{lastStaffInvite.name}</strong></p>
              <p><span className="text-gray-500">{t('statuses.status')}:</span> <strong>{statusLabel(lastStaffInvite.status, t, 'staff')}</strong></p>
              <p><span className="text-gray-500">Role:</span> <strong>{formatFulfillmentStatus(lastStaffInvite.role)}</strong></p>
              <div>
                <p className="text-gray-500">Invite token</p>
                <p className="mt-1 break-all rounded-lg bg-gray-50 border border-gray-200 p-3 font-mono text-xs">{lastStaffInvite.invite_token}</p>
              </div>
              <p className="text-xs text-gray-500">Share this token manually for now. Staff must upload official verification documents before activation.</p>
            </div>
          ) : (
            <p className="mt-4 text-sm text-gray-500">Create an invite to see the token and invite status here.</p>
          )}
        </div>
      </div>

      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-3">Staff</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Membership</th>
                <th className="px-4 py-3">Verification</th>
                <th className="px-4 py-3">Access</th>
                <th className="px-4 py-3">Dates</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {merchantStaff.map(staff => {
                const isVerified = staff.verification_status === 'VERIFIED'
                const assignedBranches = staff.assigned_branches || []
                return (
                  <tr key={staff.id} className="align-top">
                    <td className="px-4 py-4">
                      <p className="font-medium text-gray-950">{staff.name}</p>
                      <p className="text-xs text-gray-500">{staff.email || 'No email'}{staff.phone ? ` · ${staff.phone}` : ''}</p>
                      {expandedStaffId === staff.id && (
                        <div className="mt-3 rounded-lg bg-gray-50 border border-gray-200 p-3 text-xs text-gray-600">
                          {staff.verification_status === 'PENDING' && <p>Waiting for T-Food Operations verification.</p>}
                          {staff.verification_status === 'SUBMITTED' && <p>Documents submitted. Waiting for T-Food Operations review.</p>}
                          {staff.verification_status === 'REJECTED' && <p className="text-red-700">Verification rejected. Staff must submit valid official documents.</p>}
                          {staff.verification_status === 'MORE_INFO_REQUIRED' && <p className="text-amber-700">T-Food Operations requested more information.</p>}
                          {isVerified && staff.membership_status !== 'ACTIVE' && <p className="text-emerald-700">Verified. You may activate this staff member.</p>}
                          {staff.verification_rejection_reason && <p className="mt-2">Reason: {staff.verification_rejection_reason}</p>}
                          <p className="mt-2">Verification status is read-only. Only T-Food Operations can approve, reject, suspend, or request more information.</p>
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-4 min-w-[190px]">
                      <select
                        className="input-field py-2 bg-white text-sm"
                        value={staff.role}
                        onChange={event => updateStaff(staff, { role: event.target.value }, 'Staff role updated')}
                      >
                        {staffRoles.map(role => <option key={role.value} value={role.value}>{role.label}</option>)}
                      </select>
                    </td>
                    <td className="px-4 py-4">
                      <span className={`inline-flex rounded-full border px-2 py-1 text-xs font-medium ${networkStatusClass(staff.membership_status)}`}>
                        {statusLabel(staff.membership_status, t, 'staff')}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <span className={`inline-flex rounded-full border px-2 py-1 text-xs font-medium ${networkStatusClass(staff.verification_status)}`}>
                        {verificationStatusLabels[staff.verification_status] || statusLabel(staff.verification_status, t, 'verification')}
                      </span>
                    </td>
                    <td className="px-4 py-4 min-w-[260px]">
                      <label className="flex items-center gap-2 text-sm text-gray-700">
                        <input
                          type="checkbox"
                          checked={staff.is_company_wide}
                          onChange={event => updateStaff(staff, { is_company_wide: event.target.checked }, 'Staff access scope updated')}
                        />
                        Company-wide
                      </label>
                      {!staff.is_company_wide && (
                        <div className="mt-3">
                          <select
                            multiple
                            className="input-field min-h-[92px] bg-white text-sm"
                            value={assignedBranches.map(branch => String(branch.id))}
                            disabled={!restaurants.length || staff.membership_status === 'REMOVED'}
                            onChange={event => assignStaffBranches(
                              staff,
                              Array.from(event.target.selectedOptions).map(option => option.value),
                            )}
                          >
                            {restaurants.map(branch => (
                              <option key={branch.id} value={branch.id} disabled={!branch.is_active}>
                                {branch.branch_name || branch.rest_name}{branch.is_active ? '' : ' (inactive)'}
                              </option>
                            ))}
                          </select>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {assignedBranches.map(branch => (
                              <button
                                key={branch.id}
                                type="button"
                                onClick={() => removeStaffBranch(staff, branch.id)}
                                className="rounded-full border border-gray-200 px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
                              >
                                {branch.branch_name || branch.name} x
                              </button>
                            ))}
                          </div>
                          {!assignedBranches.length && <p className="mt-2 text-xs text-amber-700">Branch-specific staff require at least one branch assignment.</p>}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-4 text-xs text-gray-500">
                      <p>Created {formatDateTime(staff.created_at)}</p>
                      <p className="mt-1">Updated {formatDateTime(staff.updated_at)}</p>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex flex-wrap gap-2">
                        <button type="button" onClick={() => setExpandedStaffId(current => current === staff.id ? null : staff.id)} className="btn-secondary px-2 py-1 text-xs">
                          {expandedStaffId === staff.id ? 'Hide' : 'View'}
                        </button>
                        <button
                          type="button"
                          disabled={!isVerified || staff.membership_status === 'ACTIVE'}
                          onClick={() => updateStaff(staff, { membership_status: 'ACTIVE' }, 'Staff activated')}
                          className="btn-secondary px-2 py-1 text-xs"
                        >
                          Activate
                        </button>
                        <button
                          type="button"
                          disabled={staff.membership_status === 'INACTIVE'}
                          onClick={() => updateStaff(staff, { membership_status: 'INACTIVE' }, 'Staff deactivated')}
                          className="btn-secondary px-2 py-1 text-xs"
                        >
                          Deactivate
                        </button>
                        <button
                          type="button"
                          disabled={staff.membership_status === 'REMOVED'}
                          onClick={() => updateStaff(staff, { membership_status: 'REMOVED' }, 'Staff removed')}
                          className="btn-secondary px-2 py-1 text-xs text-red-600"
                        >
                          Remove
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
              {!merchantStaff.length && (
                <tr>
                  <td colSpan="7" className="px-4 py-8 text-center text-sm text-gray-500">
                    Invite your first staff member.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {!!staffInvites.length && (
        <div className="mt-6">
          <h3 className="font-semibold text-gray-950 mb-3">Recent staff invites</h3>
          <div className="divide-y divide-gray-200 border-y border-gray-200">
            {staffInvites.slice(0, 5).map(invite => (
              <div key={invite.id} className="py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                  <p className="font-medium text-gray-950">{invite.name}</p>
                  <p className="text-xs text-gray-500">{invite.email || invite.phone || 'No contact provided'} · {formatFulfillmentStatus(invite.role)}</p>
                </div>
                <div className="sm:text-right">
                  <p className="text-sm font-medium">{invite.status}</p>
                  <p className="text-xs text-gray-500 break-all">{invite.invite_token}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )

  const renderMerchantContactSection = () => (
    <section className="mb-6 rounded-lg border border-gray-200 bg-white p-5">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-950">Merchant owner contact</h2>
          <p className="mt-1 max-w-2xl text-sm text-gray-500">
            Add the company name and merchant owner phone number T-Food Operations should use during approval.
            Branch/storefront phone numbers can be different.
          </p>
          {!merchantProfile?.phone && (
            <p className="mt-2 text-sm text-amber-700">Merchant phone number is required before approval.</p>
          )}
        </div>
        <span className={`inline-flex w-fit rounded-full border px-3 py-1 text-sm font-medium ${merchantProfile?.phone ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
          {merchantProfile?.phone ? 'Contact ready' : 'Phone missing'}
        </span>
      </div>
      <form onSubmit={saveMerchantProfile} className="mt-4 grid md:grid-cols-[1fr_1fr_auto] gap-3 items-end">
        <label className="text-sm font-medium text-gray-700">
          Company name
          <input
            className="input-field mt-1"
            placeholder="T-Food merchant company"
            value={profileForm.business_name}
            onChange={event => setProfileForm(current => ({ ...current, business_name: event.target.value }))}
          />
        </label>
        <label className="text-sm font-medium text-gray-700">
          Merchant owner phone
          <input
            required
            className="input-field mt-1"
            placeholder="+224 620 00 00 00"
            value={profileForm.phone}
            onChange={event => setProfileForm(current => ({ ...current, phone: event.target.value }))}
          />
        </label>
        <button type="submit" disabled={savingProfile} className="btn-primary">
          {savingProfile ? 'Saving...' : 'Save contact'}
        </button>
      </form>
    </section>
  )

  if (
    profileQuery.isLoading ||
    restaurantsQuery.isLoading ||
    summaryQuery.isLoading
  ) {
    return <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10 text-gray-500">Loading merchant workspace...</div>
  }

  if (!restaurant) {
    const onboardingTabs = [
      { id: 'branches', label: 'Branches' },
      { id: 'staff', label: 'Staff' },
      { id: 'profile', label: 'Profile' },
    ]
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-10">
        {!merchantProfile?.is_verified && (
          <div className="mb-6 border border-amber-200 bg-amber-50 rounded-lg px-4 py-3">
            <p className="font-medium text-amber-900">Application received</p>
            <p className="text-sm text-amber-800 mt-1">Your company can complete onboarding before creating a branch. Branch creation is optional until you are ready to operate.</p>
          </div>
        )}
        <div className="mb-7">
          <Store size={30} className="text-brand-600 mb-3" />
          <h1 className="text-2xl font-bold text-gray-950">{merchantProfile?.business_name || 'Merchant company'}</h1>
          <p className="text-gray-500 mt-2">{t('merchantDashboard.onboardingSubtitle')}</p>
        </div>
        {renderMerchantContactSection()}
        <div className="py-4 border-y border-gray-200 flex gap-2 overflow-x-auto">
          {onboardingTabs.map(tab => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap ${activeTab === tab.id || (activeTab === 'overview' && tab.id === 'branches') ? 'bg-brand-600 text-white' : 'text-gray-600 hover:bg-gray-100'}`}
            >
              {t(`dashboard.${tab.id}`, { defaultValue: tab.label })}
            </button>
          ))}
        </div>
        {activeTab === 'staff' ? renderStaffSection() : (
          <>
            {activeTab === 'profile' && (
              <Suspense fallback={<PanelLoading />}>
                <MerchantVerificationPanel
                  profile={merchantProfile}
                  documentsQuery={merchantVerificationQuery}
                  form={verificationForm}
                  setForm={setVerificationForm}
                  onUpload={uploadVerification}
                  uploading={uploadingVerification}
                  onDelete={deleteVerification}
                  deletingId={deletingVerificationId}
                  identityDocumentTypes={identityDocumentTypes}
                  merchantDocumentTypes={merchantDocumentTypes}
                  verificationStatusLabels={verificationStatusLabels}
                  documentStatusClass={documentStatusClass}
                  formatDocumentType={formatDocumentType}
                  formatDateTime={formatDateTime}
                />
              </Suspense>
            )}
            {(activeTab === 'overview' || activeTab === 'branches') && (
              <section className="py-8">
                <div className="mb-5 rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
                  No branches configured yet. You can keep onboarding the company, invite company-wide staff, or create the first branch below.
                </div>
                <form onSubmit={createRestaurant} className="grid sm:grid-cols-2 gap-4">
                  <input required className="input-field" placeholder="T-Food Conakry Kitchen" value={restaurantForm.rest_name} onChange={e => setRestaurantForm(f => ({ ...f, rest_name: e.target.value }))} />
                  <input required type="email" className="input-field" placeholder="conakry@t-food.gn" value={restaurantForm.rest_email} onChange={e => setRestaurantForm(f => ({ ...f, rest_email: e.target.value }))} />
                  <input required className="input-field" placeholder="+224 620 00 00 00" value={restaurantForm.rest_contact} onChange={e => setRestaurantForm(f => ({ ...f, rest_contact: e.target.value }))} />
                  <input required className="input-field" placeholder="Conakry" value={restaurantForm.rest_city} onChange={e => setRestaurantForm(f => ({ ...f, rest_city: e.target.value }))} />
                  <textarea required className="input-field resize-none sm:col-span-2" rows={3} placeholder="Kaloum, Conakry" value={restaurantForm.rest_address} onChange={e => setRestaurantForm(f => ({ ...f, rest_address: e.target.value }))} />
                  <button type="button" onClick={() => capturePickupLocation(null)} className="btn-secondary sm:col-span-2 inline-flex items-center justify-center gap-2">
                    <LocateFixed size={16} /> {restaurantForm.pickup_latitude ? 'Pickup location pinned' : 'Pin pickup location'}
                  </button>
                  <label className="sm:col-span-2 border border-dashed border-gray-300 rounded-lg p-4 flex items-center gap-3 cursor-pointer hover:bg-gray-50">
                    <ImagePlus size={20} className="text-brand-600" />
                    <span className="text-sm text-gray-600">{restaurantForm.cover_image?.name || 'Choose storefront cover image'}</span>
                    <input type="file" accept="image/*" className="hidden" onChange={e => setRestaurantForm(f => ({ ...f, cover_image: e.target.files?.[0] || null }))} />
                  </label>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Delivery fee</label>
                    <input required min="0" step="0.01" type="number" className="input-field mt-1" value={restaurantForm.delivery_fee} onChange={e => setRestaurantForm(f => ({ ...f, delivery_fee: e.target.value }))} />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Minimum order</label>
                    <input required min="0" step="0.01" type="number" className="input-field mt-1" value={restaurantForm.min_order_amount} onChange={e => setRestaurantForm(f => ({ ...f, min_order_amount: e.target.value }))} />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Delivery radius (km)</label>
                    <input required min="1" max="50" step="0.5" type="number" className="input-field mt-1" value={restaurantForm.delivery_radius_km} onChange={e => setRestaurantForm(f => ({ ...f, delivery_radius_km: e.target.value }))} />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Preparation time (minutes)</label>
                    <input required min="5" max="180" step="5" type="number" className="input-field mt-1" value={restaurantForm.estimated_prep_minutes} onChange={e => setRestaurantForm(f => ({ ...f, estimated_prep_minutes: e.target.value }))} />
                  </div>
                  <button disabled={saving} className="btn-primary self-end">{saving ? 'Creating...' : 'Create branch / storefront'}</button>
                </form>
              </section>
            )}
          </>
        )}
      </div>
    )
  }

  return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
      {!merchantProfile?.is_verified && (
        <div className="mb-6 border border-amber-200 bg-amber-50 rounded-lg px-4 py-3">
          <p className="font-medium text-amber-900">Awaiting T-Food approval</p>
          <p className="text-sm text-amber-800 mt-1">You can prepare your storefront and menu. Customers will see it after an admin verifies your business.</p>
        </div>
      )}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 pb-7 border-b border-gray-200">
        <div>
          <p className="text-sm font-medium text-brand-600">
            {merchantProfile?.is_verified ? 'Verified merchant' : 'Merchant workspace'}
          </p>
          <h1 className="text-2xl font-bold text-gray-950 mt-1">{restaurant.rest_name}</h1>
          <p className="text-xs text-gray-400 mt-2">
            {realtime.isConnected ? 'Live updates connected' : 'Auto refresh active'}
          </p>
          <p className="text-gray-500 mt-1">
            {restaurant.rest_city || restaurant.city || 'No city'} · Delivery {money(restaurant.delivery_fee)} · Plan {subscriptionPlanLabel(merchantProfile?.subscription_plan)}
          </p>
          <p className={`text-sm font-medium mt-2 ${(restaurant.accepting_orders ?? restaurant.is_open) ? 'text-emerald-700' : 'text-amber-700'}`}>
            {restaurant.is_open
              ? (restaurant.accepting_orders ?? true) ? 'Accepting customer orders now' : 'Orders enabled, but closed by operating hours'
              : 'Orders paused by merchant'}
          </p>
        </div>
        <button onClick={toggleStore} className={restaurant.is_open ? 'btn-secondary' : 'btn-primary'}>
          {restaurant.is_open ? 'Pause orders' : 'Open store'}
        </button>
      </div>

      <div className="py-4 border-b border-gray-200 flex gap-2 overflow-x-auto">
        {merchantTabs.map(tab => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap ${activeTab === tab.id ? 'bg-brand-600 text-white' : 'text-gray-600 hover:bg-gray-100'}`}
          >
            {t(`dashboard.${tab.id}`, { defaultValue: tab.label })}
          </button>
        ))}
      </div>

      {activeTab === 'profile' && (
        <>
      {renderMerchantContactSection()}
      <Suspense fallback={<PanelLoading />}>
        <MerchantVerificationPanel
          profile={merchantProfile}
          documentsQuery={merchantVerificationQuery}
          form={verificationForm}
          setForm={setVerificationForm}
          onUpload={uploadVerification}
          uploading={uploadingVerification}
          onDelete={deleteVerification}
          deletingId={deletingVerificationId}
          identityDocumentTypes={identityDocumentTypes}
          merchantDocumentTypes={merchantDocumentTypes}
          verificationStatusLabels={verificationStatusLabels}
          documentStatusClass={documentStatusClass}
          formatDocumentType={formatDocumentType}
          formatDateTime={formatDateTime}
        />
      </Suspense>

      <div className="py-5 border-b border-gray-200 flex items-center gap-4">
        <div className="h-20 w-32 rounded-lg overflow-hidden bg-gray-100 flex items-center justify-center">
          {restaurant.cover_image
            ? <img src={restaurant.cover_image} alt="" className="h-full w-full object-cover" />
            : <Store size={24} className="text-gray-400" />}
        </div>
        <label className="btn-secondary inline-flex items-center gap-2 cursor-pointer">
          <ImagePlus size={16} /> Update cover
          <input type="file" accept="image/*" className="hidden" onChange={updateCover} />
        </label>
        <button type="button" onClick={() => capturePickupLocation(restaurant)} className="btn-secondary inline-flex items-center gap-2">
          <LocateFixed size={16} /> {restaurant.pickup_latitude ? 'Update pickup pin' : 'Pin pickup location'}
        </button>
      </div>

      <div className="py-5 border-b border-gray-200 grid sm:grid-cols-2 gap-4">
        <label className="text-sm font-medium text-gray-700">
          Delivery radius (km)
          <input key={`radius-${restaurant.delivery_radius_km}`} type="number" min="1" max="50" step="0.5" defaultValue={restaurant.delivery_radius_km} onBlur={event => updateServiceSetting('delivery_radius_km', event.target.value)} className="input-field mt-1" />
        </label>
        <label className="text-sm font-medium text-gray-700">
          Preparation time (minutes)
          <input key={`prep-${restaurant.estimated_prep_minutes}`} type="number" min="5" max="180" step="5" defaultValue={restaurant.estimated_prep_minutes} onBlur={event => updateServiceSetting('estimated_prep_minutes', event.target.value)} className="input-field mt-1" />
        </label>
      </div>

      <section className="py-6 border-b border-gray-200">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 mb-4">
          <div>
            <h2 className="font-semibold text-gray-950">Weekly operating hours</h2>
            <p className="text-sm text-gray-500 mt-1">Overnight hours such as 18:00–02:00 are supported.</p>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            <label className="text-sm font-medium text-gray-700">
              Branch
              <select
                className="input-field mt-1 min-w-[260px] bg-white"
                value={selectedRestaurantId || restaurant?.id || ''}
                onChange={event => setSelectedRestaurantId(event.target.value)}
              >
                {restaurants.map(branch => (
                  <option key={branch.id} value={branch.id}>
                    {branch.branch_name || branch.rest_name}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex flex-wrap items-center gap-2 sm:self-end">
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${restaurant?.accepting_orders ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                {restaurant?.accepting_orders ? 'Currently open' : 'Currently closed'}
              </span>
              <button type="button" onClick={saveOperatingHours} disabled={savingHours || !restaurant} className="btn-primary">
                {savingHours ? 'Saving...' : 'Save hours'}
              </button>
            </div>
          </div>
        </div>
        <div className="divide-y divide-gray-200 border-y border-gray-200">
          {hoursDraft.map((entry, index) => (
            <div key={entry.day_of_week} className="py-3 grid grid-cols-[90px_1fr] sm:grid-cols-[110px_100px_1fr_1fr] items-center gap-3">
              <span className="text-sm font-medium text-gray-800">{entry.day_display || dayNames[index]}</span>
              <label className="flex items-center gap-2 text-sm text-gray-600">
                <input type="checkbox" checked={entry.is_closed} onChange={event => setHoursDraft(current => current.map((item, itemIndex) => itemIndex === index ? { ...item, is_closed: event.target.checked } : item))} />
                {entry.is_closed ? 'Closed all day' : 'Open this day'}
              </label>
              <input aria-label={`${dayNames[index]} opening time`} type="time" disabled={entry.is_closed} value={entry.opens_at.slice(0, 5)} onChange={event => setHoursDraft(current => current.map((item, itemIndex) => itemIndex === index ? { ...item, opens_at: event.target.value } : item))} className="input-field" />
              <input aria-label={`${dayNames[index]} closing time`} type="time" disabled={entry.is_closed} value={entry.closes_at.slice(0, 5)} onChange={event => setHoursDraft(current => current.map((item, itemIndex) => itemIndex === index ? { ...item, closes_at: event.target.value } : item))} className="input-field" />
            </div>
          ))}
        </div>
      </section>
        </>
      )}
      {activeTab === 'overview' && (
        <Suspense fallback={<PanelLoading />}>
          <MerchantOverviewPanel
            summary={summary}
            restaurant={restaurant}
            unavailableItems={unavailableItems}
            merchantNotifications={merchantNotifications}
            merchantReviews={merchantReviews}
            toggleStore={toggleStore}
            setActiveTab={setActiveTab}
          />
        </Suspense>
      )}

      {activeTab === 'orders' && (
      <section className="py-8 border-b border-gray-200">
        <div className="flex items-center gap-2 mb-5">
          <Clock3 size={20} className="text-brand-600" />
          <h2 className="text-xl font-semibold">{t('merchantDashboard.incomingOrders')}</h2>
          <span className="text-sm text-gray-500">({activeOrders.length})</span>
        </div>
        {!activeOrders.length && <p className="text-gray-500">{t('merchantDashboard.ordersEmpty')}</p>}
        <div className="grid lg:grid-cols-2 gap-4">
          {activeOrders.map(order => {
            const action = nextActions[order.status]
            return (
              <article key={order.id} className="card p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="font-semibold">{merchantOrderLabel(order, t)}</h3>
                    <p className="text-sm text-gray-500 mt-1">{order.customer_name} · {order.customer_phone}</p>
                  </div>
                  <span className="text-xs font-medium bg-gray-100 px-2 py-1 rounded-md">{statusLabel(order.status, t, 'orders')}</span>
                </div>
                <div className="text-sm text-gray-600 mt-3 space-y-1">{order.items.map(item => <p key={item.id}>{item.name} x {item.quantity}{item.selected_options?.length ? ` · ${item.selected_options.map(option => option.name).join(', ')}` : ''}</p>)}</div>
                <p className={`text-sm mt-2 ${order.payment_status === 'PENDING' ? 'text-amber-700' : 'text-emerald-700'}`}>
                  {order.payment_method === 'COD' ? t('payment.methods.cod') : statusLabel(order.payment_method, t, 'payments')} - {statusLabel(order.payment_status, t, 'payments')}
                </p>
                <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm">
                  <p className="font-medium text-gray-950">{t('merchantDashboard.assignedPartner')}</p>
                  {order.delivery_partner_name ? (
                    <div className="mt-1 space-y-1 text-gray-600">
                      <p>{order.delivery_partner_name}</p>
                      <p>{order.delivery_partner_phone || t('merchantDashboard.partnerPhoneMissing')}</p>
                      <p>{order.delivery_partner_transport || t('merchantDashboard.partnerTransportMissing')}</p>
                    </div>
                  ) : (
                    <p className="mt-1 text-amber-700">{t('merchantDashboard.waitingForDriver')}</p>
                  )}
                </div>
                <div className="flex items-center justify-between gap-3 mt-4 pt-4 border-t border-gray-100">
                  <span className="font-semibold flex items-center gap-2"><CircleDollarSign size={16} /> {money(order.total_amount)}</span>
                  <div className="flex gap-2">
                    {order.status === 'CONFIRMED' && <button onClick={() => advanceOrder(order.id, 'CANCELLED')} className="btn-secondary py-2 px-3 text-sm text-red-600">{t('merchantDashboard.actions.reject')}</button>}
                    {action && <button onClick={() => advanceOrder(order.id, action.status)} className="btn-primary py-2 px-3 text-sm">{t(action.labelKey)}</button>}
                  </div>
                  {order.status === 'READY_FOR_PICKUP' && <span className="text-sm text-emerald-700 flex items-center gap-2"><CheckCircle2 size={16} /> {t('merchantDashboard.waitingForDriver')}</span>}
                </div>
                <p className="text-xs text-gray-500 mt-3">{t('merchantDashboard.yourPayout', { amount: Number(order.merchant_payout).toFixed(2) })}</p>
                <p className="text-xs text-gray-500 mt-1">{t('merchantDashboard.settlement', { status: statusLabel(order.merchant_payout_status, t, 'payouts') })}</p>
              </article>
            )
          })}
        </div>
        <div className="mt-10 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
          <div className="flex items-center gap-2">
            <ReceiptText size={20} className="text-brand-600" />
            <h2 className="text-xl font-semibold">{t('merchantDashboard.orderHistory')}</h2>
            <span className="text-sm text-gray-500">({historyOrders.length})</span>
          </div>
          <label className="text-sm font-medium text-gray-700">
            {t('merchantDashboard.historyRange')}
            <select
              className="input-field mt-1 bg-white min-w-[220px]"
              value={orderHistoryRange}
              onChange={event => setOrderHistoryRange(event.target.value)}
            >
              {orderHistoryRanges.map(range => (
                <option key={range.value} value={range.value}>{t(range.labelKey)}</option>
              ))}
            </select>
          </label>
        </div>
        {!historyOrders.length && (
          <p className="mt-4 text-gray-500">{t('merchantDashboard.orderHistoryEmpty')}</p>
        )}
        <div className="mt-5 grid lg:grid-cols-2 gap-4">
          {historyOrders.map(order => (
            <article key={order.id} className="card p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="font-semibold">{merchantOrderLabel(order, t)}</h3>
                  <p className="text-sm text-gray-500 mt-1">{order.customer_name} · {order.customer_phone}</p>
                </div>
                <span className="text-xs font-medium bg-gray-100 px-2 py-1 rounded-md">{statusLabel(order.status, t, 'orders')}</span>
              </div>
              <div className="text-sm text-gray-600 mt-3 space-y-1">{order.items.map(item => <p key={item.id}>{item.name} x {item.quantity}{item.selected_options?.length ? ` · ${item.selected_options.map(option => option.name).join(', ')}` : ''}</p>)}</div>
              <p className={`text-sm mt-2 ${order.payment_status === 'PENDING' ? 'text-amber-700' : 'text-emerald-700'}`}>
                {order.payment_method === 'COD' ? t('payment.methods.cod') : statusLabel(order.payment_method, t, 'payments')} - {statusLabel(order.payment_status, t, 'payments')}
              </p>
              <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm">
                <p className="font-medium text-gray-950">{t('merchantDashboard.assignedPartner')}</p>
                {order.delivery_partner_name ? (
                  <div className="mt-1 space-y-1 text-gray-600">
                    <p>{order.delivery_partner_name}</p>
                    <p>{order.delivery_partner_phone || t('merchantDashboard.partnerPhoneMissing')}</p>
                    <p>{order.delivery_partner_transport || t('merchantDashboard.partnerTransportMissing')}</p>
                  </div>
                ) : (
                  <p className="mt-1 text-amber-700">{t('merchantDashboard.waitingForDriver')}</p>
                )}
              </div>
              <div className="flex items-center justify-between gap-3 mt-4 pt-4 border-t border-gray-100">
                <span className="font-semibold flex items-center gap-2"><CircleDollarSign size={16} /> {money(order.total_amount)}</span>
              </div>
              <p className="text-xs text-gray-500 mt-3">{t('merchantDashboard.yourPayout', { amount: Number(order.merchant_payout).toFixed(2) })}</p>
              <p className="text-xs text-gray-500 mt-1">{t('merchantDashboard.settlement', { status: statusLabel(order.merchant_payout_status, t, 'payouts') })}</p>
            </article>
          ))}
        </div>
      </section>
      )}

      {activeTab === 'branches' && (
        <section className="py-8 border-b border-gray-200">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 mb-6">
            <div>
              <div className="flex items-center gap-2">
                <Store size={20} className="text-brand-600" />
                <h2 className="text-xl font-semibold text-gray-950">Branches / Storefronts</h2>
              </div>
              <p className="mt-2 max-w-3xl text-sm text-gray-500">
                Manage each commerce location your company operates. A branch can represent food, grocery, pharmacy, retail, courier, or other local commerce storefronts while old restaurant fields remain supported.
              </p>
            </div>
            <button type="button" onClick={openNewBranchForm} className="btn-secondary inline-flex items-center justify-center gap-2">
              <Plus size={16} /> New branch
            </button>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <KpiCard label="Total Branches" value={restaurants.length} actionLabel="Show all branches" isActive={branchTableFilter === 'all'} onClick={() => setBranchTableFilter('all')} />
            <KpiCard label="Open Branches" value={restaurants.filter(branch => branch.is_open).length} accent="text-emerald-700" actionLabel="Show open branches" isActive={branchTableFilter === 'open'} onClick={() => setBranchTableFilter('open')} />
            <KpiCard label="Active Branches" value={restaurants.filter(branch => branch.is_active).length} accent="text-brand-700" actionLabel="Show active branches" isActive={branchTableFilter === 'active'} onClick={() => setBranchTableFilter('active')} />
            <KpiCard label="Assigned Riders" value={Object.values(branchRiderCounts).reduce((total, count) => total + count, 0)} actionLabel="Open rider assignments" onClick={() => setActiveTab('riders')} />
          </div>

          <div className="mb-6 rounded-lg border border-gray-200 bg-white p-5">
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
              <div>
                <h3 className="font-semibold text-gray-950">Company vs Branch analytics</h3>
                <p className="mt-1 text-sm text-gray-500">
                  Review all branches together or isolate one storefront before opening revenue and performance analytics.
                </p>
              </div>
              <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                {analyticsScopeControl}
                <button type="button" onClick={() => setActiveTab('revenue')} className="btn-primary text-sm">
                  Open analytics
                </button>
              </div>
            </div>
            <div className="mt-4 grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
              <KpiCard label="Analytics scope" value={analytics?.scope === 'branch' ? 'Branch' : 'Company'} onClick={() => setActiveTab('revenue')} />
              <KpiCard label="Orders" value={analytics?.sales?.delivered_orders ?? 0} onClick={() => setActiveTab('orders')} />
              <KpiCard label="Revenue" value={money(analytics?.sales?.gross_sales)} onClick={() => setActiveTab('revenue')} />
              <KpiCard label="Active riders" value={analytics?.kpis?.active_riders ?? 0} accent="text-emerald-700" onClick={() => setActiveTab('riders')} />
            </div>
          </div>

          {(citiesQuery.isError || areasQuery.isError) && (
            <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              City/area records could not be loaded. You can still use the city text field.
            </div>
          )}
          {!cities.length && !citiesQuery.isLoading && (
            <div className="mb-5 rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
              No city/area records configured yet.
            </div>
          )}

          <div className="mb-3 flex items-center justify-between gap-3 text-sm text-gray-500">
            <p>
              Showing {filteredBranches.length} of {restaurants.length} branches
              {branchTableFilter !== 'all' ? ` (${branchTableFilter.replace('-', ' ')})` : ''}
            </p>
            {branchTableFilter !== 'all' && (
              <button type="button" onClick={() => setBranchTableFilter('all')} className="text-brand-600 font-medium">
                Show all branches
              </button>
            )}
          </div>

          <div className="mb-8 overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-4 py-3">Branch</th>
                  <th className="px-4 py-3">Location</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Delivery</th>
                  <th className="px-4 py-3">Radius</th>
                  <th className="px-4 py-3">Menu</th>
                  <th className="px-4 py-3">Riders</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {filteredBranches.map(branch => {
                  const branchTypeLabel = branchTypes.find(type => type.value === branch.branch_type)?.label || branch.branch_type || 'Food'
                  const deliveryMode = deliveryModeByValue[branch.delivery_mode] || deliveryModeByValue.HYBRID
                  const assignedRiderCount = branchRiderCounts[branch.id] || 0
                  const activeAssignedRiderCount = activeBranchRiderCounts[branch.id] || 0
                  return (
                    <tr key={branch.id} className="align-top">
                      <td className="px-4 py-4">
                        <p className="font-semibold text-gray-950">{branch.branch_name || branch.rest_name}</p>
                        <p className="text-xs text-gray-500">{branch.rest_name}</p>
                        <p className="mt-1 text-xs text-gray-400">{branch.branch_code || 'No branch code'} · {branchTypeLabel}</p>
                      </td>
                      <td className="px-4 py-4">
                        <p className="text-gray-800">Country: {branch.country_code || 'Not set'} · City: {branch.city || branch.rest_city || 'Not set'}</p>
                        <p className="text-xs text-gray-500">Market: {branch.market_name || branch.market_slug || 'Not set'}{branch.area ? ` · Area: ${branch.area}` : ''}</p>
                        <p className="mt-1 max-w-xs text-xs text-gray-400">{branch.rest_address}</p>
                      </td>
                      <td className="px-4 py-4">
                        <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${branch.is_open ? 'border-blue-200 bg-blue-50 text-blue-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
                          {branch.is_open ? 'Orders enabled' : 'Orders paused'}
                        </span>
                        <p className={`mt-2 text-xs font-medium ${(branch.accepting_orders ?? branch.is_open) ? 'text-emerald-700' : 'text-red-600'}`}>
                          {(branch.accepting_orders ?? branch.is_open) ? 'Accepting now' : 'Closed now'}
                        </p>
                        <p className="mt-1 text-xs text-gray-500">{branch.is_active ? 'Active' : 'Inactive'}</p>
                      </td>
                      <td className="px-4 py-4 min-w-[190px]">
                        <p className="text-sm font-medium text-gray-800">{deliveryMode.label}</p>
                        <p className="mt-1 text-xs text-gray-500">{deliveryMode.hint}</p>
                        {branch.delivery_mode === 'MERCHANT_DELIVERY' && activeAssignedRiderCount === 0 && (
                          <p className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-800">
                            Merchant delivery is enabled, but no active riders are assigned.
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-4 text-gray-700">{branch.delivery_radius_km} km</td>
                      <td className="px-4 py-4 text-gray-700">{branch.item_count ?? branch.menu_items?.length ?? 0}</td>
                      <td className="px-4 py-4 text-gray-700">{assignedRiderCount}</td>
                      <td className="px-4 py-4">
                        <div className="flex flex-wrap gap-2">
                          <button type="button" onClick={() => toggleBranchOpen(branch)} className="btn-secondary px-3 py-2 text-xs">
                            {branch.is_open ? 'Close branch' : 'Open branch'}
                          </button>
                          <button type="button" onClick={() => editBranch(branch)} className="btn-secondary px-3 py-2 text-xs">Edit</button>
                          <button type="button" onClick={() => openBranchMenu(branch)} className="btn-secondary px-3 py-2 text-xs">View menu</button>
                          <button
                            type="button"
                            onClick={() => {
                              setRiderBranchFilter(String(branch.id))
                              setActiveTab('riders')
                            }}
                            className="btn-secondary px-3 py-2 text-xs"
                          >
                            View riders
                          </button>
                          <button type="button" onClick={() => openBranchAnalytics(branch)} className="btn-secondary px-3 py-2 text-xs">View analytics</button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <section ref={branchFormRef} className="scroll-mt-24 rounded-lg border border-gray-200 p-5">
            <div className="mb-5 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-gray-950">{branchEditingId ? 'Edit branch / storefront' : 'Create branch / storefront'}</h3>
                <p className="mt-1 text-sm text-gray-500">Use restaurant fields for backward compatibility and branch fields for the multi-country commerce model.</p>
              </div>
              <button
                type="button"
                onClick={branchFormOpen ? resetBranchForm : openNewBranchForm}
                className="btn-secondary inline-flex items-center justify-center gap-2 px-3 py-2 text-sm"
              >
                {branchFormOpen ? (branchEditingId ? 'Cancel edit' : 'Hide form') : (
                  <>
                    <Plus size={16} /> New branch
                  </>
                )}
              </button>
            </div>

            {!branchFormOpen ? (
              <p className="text-sm text-gray-500">
                Open this card when you want to add another storefront or edit an existing branch.
              </p>
            ) : (
              <form onSubmit={saveBranch}>
                <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
              <label className="text-sm font-medium text-gray-700">
                Storefront name
                <input required className="input-field mt-1" value={restaurantForm.rest_name} onChange={event => setRestaurantForm(form => ({ ...form, rest_name: event.target.value }))} />
              </label>
              <label className="text-sm font-medium text-gray-700">
                Branch name
                <input className="input-field mt-1" placeholder="T-Food Conakry Branch" value={restaurantForm.branch_name} onChange={event => setRestaurantForm(form => ({ ...form, branch_name: event.target.value }))} />
              </label>
              <label className="text-sm font-medium text-gray-700">
                Branch code
                <input className="input-field mt-1" placeholder="TF-CONAKRY-01" value={restaurantForm.branch_code} onChange={event => setRestaurantForm(form => ({ ...form, branch_code: event.target.value }))} />
              </label>
              <label className="text-sm font-medium text-gray-700">
                Business email
                <input required type="email" className="input-field mt-1" value={restaurantForm.rest_email} onChange={event => setRestaurantForm(form => ({ ...form, rest_email: event.target.value }))} />
              </label>
              <label className="text-sm font-medium text-gray-700">
                Contact phone
                <input required className="input-field mt-1" value={restaurantForm.rest_contact} onChange={event => setRestaurantForm(form => ({ ...form, rest_contact: event.target.value }))} />
              </label>
              <label className="text-sm font-medium text-gray-700">
                Branch type
                <select className="input-field mt-1 bg-white" value={restaurantForm.branch_type} onChange={event => setRestaurantForm(form => ({ ...form, branch_type: event.target.value }))}>
                  {branchTypes.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}
                </select>
              </label>
              <label className="text-sm font-medium text-gray-700">
                Delivery assignment
                <select className="input-field mt-1 bg-white" value={restaurantForm.delivery_mode} onChange={event => setRestaurantForm(form => ({ ...form, delivery_mode: event.target.value }))}>
                  {deliveryModes.map(mode => <option key={mode.value} value={mode.value}>{mode.label}</option>)}
                </select>
                <span className="mt-1 block text-xs font-normal text-gray-500">
                  {deliveryModeByValue[restaurantForm.delivery_mode]?.hint}
                </span>
              </label>
              <label className="text-sm font-medium text-gray-700">
                Country code
                <input className="input-field mt-1 uppercase" maxLength={2} placeholder="GN" value={restaurantForm.country_code} onChange={event => setRestaurantForm(form => ({ ...form, country_code: event.target.value.toUpperCase() }))} />
              </label>
              <label className="text-sm font-medium text-gray-700">
                City record
                <select
                  className="input-field mt-1 bg-white"
                  value={restaurantForm.city_ref}
                  onChange={event => {
                    const city = cities.find(item => String(item.id) === event.target.value)
                    setRestaurantForm(form => ({
                      ...form,
                      city_ref: event.target.value,
                      area_ref: '',
                      rest_city: city?.name || form.rest_city,
                      country_code: city?.country_code || form.country_code,
                    }))
                  }}
                >
                  <option value="">Use text city only</option>
                  {cities.map(city => <option key={city.id} value={city.id}>{city.name} · {city.country_code}</option>)}
                </select>
              </label>
              <label className="text-sm font-medium text-gray-700">
                Area record
                <select className="input-field mt-1 bg-white" value={restaurantForm.area_ref} onChange={event => setRestaurantForm(form => ({ ...form, area_ref: event.target.value }))}>
                  <option value="">No area record</option>
                  {areas.map(area => <option key={area.id} value={area.id}>{area.name}</option>)}
                </select>
              </label>
              <label className="text-sm font-medium text-gray-700">
                City text fallback
                <input required className="input-field mt-1" value={restaurantForm.rest_city} onChange={event => setRestaurantForm(form => ({ ...form, rest_city: event.target.value }))} />
              </label>
              <label className="text-sm font-medium text-gray-700 xl:col-span-2">
                Address
                <input required className="input-field mt-1" value={restaurantForm.rest_address} onChange={event => setRestaurantForm(form => ({ ...form, rest_address: event.target.value }))} />
              </label>
              <label className="text-sm font-medium text-gray-700">
                Delivery radius (km)
                <input required min="1" max="50" step="0.5" type="number" className="input-field mt-1" value={restaurantForm.delivery_radius_km} onChange={event => setRestaurantForm(form => ({ ...form, delivery_radius_km: event.target.value }))} />
              </label>
              <label className="text-sm font-medium text-gray-700">
                Pickup latitude
                <input type="number" step="0.000001" className="input-field mt-1" value={restaurantForm.pickup_latitude} onChange={event => setRestaurantForm(form => ({ ...form, pickup_latitude: event.target.value }))} />
              </label>
              <label className="text-sm font-medium text-gray-700">
                Pickup longitude
                <input type="number" step="0.000001" className="input-field mt-1" value={restaurantForm.pickup_longitude} onChange={event => setRestaurantForm(form => ({ ...form, pickup_longitude: event.target.value }))} />
              </label>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
                <input type="checkbox" checked={restaurantForm.is_open} onChange={event => setRestaurantForm(form => ({ ...form, is_open: event.target.checked }))} />
                Branch open for orders
              </label>
                </div>

                <div className="mt-5 flex flex-wrap items-center gap-3">
                  <button type="button" onClick={() => capturePickupLocation(null)} className="btn-secondary inline-flex items-center gap-2">
                    <LocateFixed size={16} /> {restaurantForm.pickup_latitude ? 'Pickup location pinned' : 'Pin pickup location'}
                  </button>
                  <button disabled={saving} className="btn-primary">
                    {saving ? 'Saving...' : branchEditingId ? 'Save branch' : 'Create branch'}
                  </button>
                </div>
              </form>
            )}
          </section>
        </section>
      )}

      {activeTab === 'menu' && (
      <section className="py-8">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
          <div className="flex items-center gap-2">
            <Utensils size={20} className="text-brand-600" />
            <div>
              <h2 className="text-xl font-semibold">Menu</h2>
              {restaurant && (
                <p className="text-sm text-gray-500">
                  Branch: {restaurant.branch_name || restaurant.rest_name}
                </p>
              )}
            </div>
          </div>
          <div className="flex gap-2 overflow-x-auto">
            {[
              ['all', `All (${menuItems.length})`],
              ['available', `Available (${menuItems.length - unavailableItems.length})`],
              ['unavailable', `Unavailable (${unavailableItems.length})`],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setMenuFilter(value)}
                className={`px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap ${menuFilter === value ? 'bg-brand-600 text-white' : 'text-gray-600 hover:bg-gray-100'}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <form onSubmit={saveItem} className="grid md:grid-cols-[1fr_1fr_140px_170px_auto] gap-3 mb-3">
          <input required className="input-field" placeholder="T-Food Jollof Rice" value={itemForm.food_name} onChange={e => setItemForm(f => ({ ...f, food_name: e.target.value }))} />
          <input className="input-field" placeholder="Conakry-style T-Food meal" value={itemForm.food_desc} onChange={e => setItemForm(f => ({ ...f, food_desc: e.target.value }))} />
          <input required min="0.01" step="0.01" type="number" className="input-field" placeholder="50000" value={itemForm.food_price} onChange={e => setItemForm(f => ({ ...f, food_price: e.target.value }))} />
          <select className="input-field" value={itemForm.food_categ} onChange={e => setItemForm(f => ({ ...f, food_categ: e.target.value }))}>
            <option>Vegetarian</option>
            <option>Non-Vegetarian</option>
            <option>Beverages</option>
            <option>Desserts</option>
          </select>
          <button disabled={saving} className="btn-primary inline-flex items-center justify-center gap-2">
            {itemEditingId ? <Pencil size={16} /> : <Plus size={16} />}
            {itemEditingId ? 'Save item' : 'Add'}
          </button>
        </form>
        <div className="mb-6 flex flex-wrap items-center gap-3">
          <label className="inline-flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <ImagePlus size={16} className="text-brand-600" />
            {itemForm.image?.name || (itemEditingId ? 'Replace item image' : 'Add item image')}
            <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={handleMenuImageChange} />
          </label>
          <span className="text-xs text-gray-500">JPEG, PNG, or WebP. 5 MB max.</span>
          {itemEditingId && (
            <button type="button" onClick={resetItemForm} className="btn-secondary py-1.5 px-3 text-sm">
              Cancel edit
            </button>
          )}
        </div>
        <div className="divide-y divide-gray-200 border-y border-gray-200">
          {visibleMenuItems.map(item => (
            <div key={item.id} className="py-4 flex flex-col gap-4 lg:flex-row lg:items-center">
              <div className="h-12 w-12 rounded-lg overflow-hidden bg-gray-100 flex items-center justify-center flex-shrink-0">
                {item.image
                  ? <img src={item.image} alt="" className="h-full w-full object-cover" />
                  : <Utensils size={18} className="text-gray-400" />}
              </div>
              <div className="flex-1">
                <p className="font-medium text-gray-950">{item.food_name}</p>
                <p className="text-sm text-gray-500">{item.food_categ} · {money(item.food_price)}</p>
              </div>
              <label className="flex items-center gap-2 text-sm text-gray-600">
                <input type="checkbox" checked={item.is_available} onChange={() => toggleItem(item)} />
                Available
              </label>
              <div className="flex flex-wrap items-center gap-2">
                <button type="button" onClick={() => startEditItem(item)} className="btn-secondary inline-flex items-center gap-2 py-2 px-3 text-sm">
                  <Pencil size={16} /> Edit
                </button>
                <button type="button" onClick={() => editOptions(item)} className="btn-secondary inline-flex items-center gap-2 py-2 px-3 text-sm">
                  <Settings2 size={16} /> Options
                </button>
                <button type="button" onClick={() => removeItem(item.id)} className="inline-flex items-center gap-2 rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50">
                  <Trash2 size={16} /> Delete
                </button>
              </div>
            </div>
          ))}
          {!visibleMenuItems.length && <p className="py-4 text-sm text-gray-500">No menu items match this filter.</p>}
        </div>
      </section>
      )}

      {activeTab === 'revenue' && (
        <section className="py-8 border-b border-gray-200">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
            <div className="flex items-center gap-2">
              <LineChart size={20} className="text-brand-600" />
              <div>
                <h2 className="text-xl font-semibold">Revenue</h2>
                <p className="text-xs text-gray-500">{analyticsScopeLabel}</p>
              </div>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center gap-2">
              <p className="text-xs text-gray-500">Last updated at {analyticsLastUpdated}</p>
              {analyticsScopeControl}
              <select value={analyticsRange} onChange={event => setAnalyticsRange(event.target.value)} className="input-field sm:w-40">
                <option value="today">Today</option>
                <option value="yesterday">Yesterday</option>
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
                <option value="month">This month</option>
                <option value="year">This year</option>
              </select>
              <button
                type="button"
                onClick={refreshAnalyticsNow}
                disabled={analyticsQuery.isFetching}
                className="btn-secondary inline-flex items-center justify-center gap-2 py-2 px-3 text-sm"
              >
                <RefreshCw size={16} className={analyticsQuery.isFetching ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <KpiCard label="Gross sales" value={money(analytics?.kpis?.gross_sales ?? analytics?.sales?.gross_sales)} />
            <KpiCard label="Net earnings" value={money(analytics?.kpis?.net_earnings ?? analytics?.sales?.merchant_earnings)} accent="text-emerald-700" />
            <KpiCard label="Average order value" value={money(analytics?.kpis?.average_order_value ?? analytics?.sales?.average_order_value)} />
            <KpiCard label="Delivered orders" value={analytics?.kpis?.delivered_orders ?? analytics?.sales?.delivered_orders ?? 0} />
          </div>
          {analytics?.scope === 'branch' && (
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
              <KpiCard label="Branch status" value={analytics?.branch_status?.is_open ? 'Open' : 'Closed'} accent={analytics?.branch_status?.is_open ? 'text-emerald-700' : 'text-amber-700'} />
              <KpiCard label="Branch active" value={analytics?.branch_status?.is_active ? 'Active' : 'Inactive'} />
              <KpiCard label="Riders" value={analytics?.branch_status?.rider_count ?? 0} />
              <KpiCard label="Active riders" value={analytics?.branch_status?.active_riders ?? 0} accent="text-emerald-700" />
            </div>
          )}
          <div className="grid lg:grid-cols-2 gap-6 mb-6">
            <TrendChart
              title="Revenue trend"
              data={analytics?.charts?.revenue_line || analytics?.order_volume || []}
              formatter={formatMoney}
              emptyLabel="No delivered sales in this range."
            />
            <BarRows
              title="Order volume"
              data={analytics?.charts?.order_volume || analytics?.order_volume || []}
              labelKey="date"
              valueKey="orders"
              formatter={value => `${Number(value || 0)} orders`}
              secondary={row => money(row.gross_sales)}
              emptyLabel="No delivered orders in this range."
            />
          </div>
          <div className="grid lg:grid-cols-2 gap-6 mb-6">
            <BarRows
              title="Top-selling items"
              data={analytics?.charts?.top_items || analytics?.top_items || []}
              valueKey="quantity"
              formatter={value => `${Number(value || 0)} sold`}
              secondary={row => money(row.gross_sales)}
              emptyLabel="No item sales yet."
            />
            <BarRows
              title="Cancellations"
              data={analytics?.charts?.cancellations || []}
              labelKey="date"
              valueKey="cancelled_orders"
              formatter={value => `${Number(value || 0)} cancelled`}
              emptyLabel="No cancellations in this range."
            />
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
            {(analytics?.revenue_trends || []).map(row => (
              <KpiCard key={row.key} label={row.label} value={money(row.gross_sales)} />
            ))}
          </div>
          <div className="grid md:grid-cols-2 gap-3 mb-6">
            <ComparisonCard
              label="This week vs last week"
              current={analytics?.comparison?.this_week_vs_last_week?.current}
              previous={analytics?.comparison?.this_week_vs_last_week?.previous}
              change={analytics?.comparison?.this_week_vs_last_week?.gross_sales_change_percent}
            />
            <ComparisonCard
              label="This month vs last month"
              current={analytics?.comparison?.this_month_vs_last_month?.current}
              previous={analytics?.comparison?.this_month_vs_last_month?.previous}
              change={analytics?.comparison?.this_month_vs_last_month?.gross_sales_change_percent}
            />
          </div>
          <div className="grid lg:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Sales by day</h3>
              <div className="divide-y divide-gray-200 border-y border-gray-200">
                {(analytics?.order_volume || []).map(row => (
                  <div key={row.date} className="py-3 flex items-center justify-between gap-3">
                    <span className="text-sm text-gray-600">{row.date}</span>
                    <span className="text-sm font-medium">{row.orders} orders · {money(row.gross_sales)}</span>
                  </div>
                ))}
                {!analytics?.order_volume?.length && <p className="py-4 text-sm text-gray-500">No delivered sales in this range.</p>}
              </div>
            </div>
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Top-selling items</h3>
              <div className="divide-y divide-gray-200 border-y border-gray-200">
                {(analytics?.top_items || []).map(item => (
                  <div key={item.item_id} className="py-3 flex items-center justify-between gap-3">
                    <span className="text-sm text-gray-700">{item.name}</span>
                    <span className="text-sm font-medium">{item.quantity} sold · {money(item.gross_sales)}</span>
                  </div>
                ))}
                {!analytics?.top_items?.length && <p className="py-4 text-sm text-gray-500">No item sales yet.</p>}
              </div>
            </div>
          </div>
        </section>
      )}

      {activeTab === 'performance' && (
        <section className="py-8 border-b border-gray-200">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
            <div className="flex items-center gap-2">
              <Clock3 size={20} className="text-brand-600" />
              <div>
                <h2 className="text-xl font-semibold">Performance</h2>
                <p className="text-xs text-gray-500">{analyticsScopeLabel}</p>
              </div>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center gap-2">
              <p className="text-xs text-gray-500">Last updated at {analyticsLastUpdated}</p>
              {analyticsScopeControl}
              <button
                type="button"
                onClick={refreshAnalyticsNow}
                disabled={analyticsQuery.isFetching}
                className="btn-secondary inline-flex items-center justify-center gap-2 py-2 px-3 text-sm"
              >
                <RefreshCw size={16} className={analyticsQuery.isFetching ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <KpiCard label="Cancellation rate" value={formatPercent(analytics?.kpis?.cancellation_rate ?? analytics?.sales?.cancellation_rate)} />
            <KpiCard label="Average prep time" value={formatMinutes(analytics?.kpis?.average_prep_time ?? analytics?.prep?.average_ready_minutes)} />
            <KpiCard label="Average acceptance time" value={formatMinutes(analytics?.kpis?.average_acceptance_time ?? analytics?.prep?.average_accept_minutes)} />
            <KpiCard label="Average rating" value={analytics?.kpis?.average_rating ?? analytics?.ratings?.average_rating ?? '-'} />
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <KpiCard label="Best day" value={analytics?.performance?.best_day ? money(analytics.performance.best_day.gross_sales) : '-'} />
            <KpiCard label="Worst day" value={analytics?.performance?.worst_day ? money(analytics.performance.worst_day.gross_sales) : '-'} />
            <KpiCard label="Fastest prep" value={formatMinutes(analytics?.performance?.fastest_prep_time?.minutes)} />
            <KpiCard label="Slowest prep" value={formatMinutes(analytics?.performance?.slowest_prep_time?.minutes)} />
          </div>
          <div className="grid lg:grid-cols-2 gap-6 mb-6">
            <BarRows
              title="Low-performing items"
              data={analytics?.low_items || []}
              valueKey="gross_sales"
              formatter={formatMoney}
              secondary={row => `${row.quantity} sold`}
              emptyLabel="No low-performing items yet."
            />
            <BarRows
              title="Rating distribution"
              data={analytics?.charts?.rating_distribution || analytics?.ratings?.distribution || []}
              labelKey="rating"
              valueKey="count"
              formatter={value => `${Number(value || 0)} reviews`}
              secondary={row => `${row.rating} star`}
              emptyLabel="No ratings yet."
            />
          </div>
          <div className="grid md:grid-cols-2 gap-3 mb-6">
            <KpiCard
              label="Most profitable item"
              value={analytics?.performance?.most_profitable_item?.name || '-'}
              accent="text-emerald-700"
            />
            <KpiCard
              label="Lowest performing item"
              value={analytics?.performance?.lowest_performing_item?.name || '-'}
              accent="text-amber-700"
            />
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Delivered orders</p>
              <p className="text-2xl font-bold mt-1">{analytics?.sales?.delivered_orders || 0}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Cancellation rate</p>
              <p className="text-2xl font-bold mt-1">{Number(analytics?.sales?.cancellation_rate || 0).toFixed(1)}%</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Accept time</p>
              <p className="text-2xl font-bold mt-1">{analytics?.prep?.average_accept_minutes ?? '-'} min</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Ready time</p>
              <p className="text-2xl font-bold mt-1">{analytics?.prep?.average_ready_minutes ?? '-'} min</p>
            </div>
          </div>
          <div className="grid lg:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Low-performing items</h3>
              <div className="divide-y divide-gray-200 border-y border-gray-200">
                {(analytics?.low_items || []).map(item => (
                  <div key={item.item_id} className="py-3 flex items-center justify-between gap-3">
                    <span className="text-sm text-gray-700">{item.name}</span>
                    <span className="text-sm font-medium">{item.quantity} sold · {money(item.gross_sales)}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Customer ratings</h3>
              <div className="border-y border-gray-200 py-4">
                <p className="text-3xl font-bold">{analytics?.ratings?.average_rating ?? '-'}</p>
                <p className="text-sm text-gray-500 mt-1">{analytics?.ratings?.review_count || 0} reviews</p>
                <p className="text-sm text-gray-500 mt-3">Estimated prep time: {analytics?.prep?.estimated_prep_minutes ?? restaurant.estimated_prep_minutes} minutes</p>
              </div>
            </div>
          </div>
        </section>
      )}
      {activeTab === 'insights' && (
        <Suspense fallback={<PanelLoading />}>
          <MerchantInsightsPanel
            insights={insights}
            merchantInsightsQuery={merchantInsightsQuery}
          />
        </Suspense>
      )}

      {activeTab === 'riders' && (
        <section className="py-8 border-b border-gray-200">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
            <div className="flex items-center gap-2">
              <ShieldCheck size={20} className="text-brand-600" />
              <div>
                <h2 className="text-xl font-semibold">Rider management</h2>
                <p className="text-sm text-gray-500 mt-1">Manage your business rider relationships. T-Food Operations still controls verification approval.</p>
              </div>
            </div>
            <button type="button" onClick={() => document.getElementById('invite-rider-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} className="btn-primary py-2 px-3 text-sm">
              Invite Rider
            </button>
          </div>

          <div className="grid sm:grid-cols-4 gap-3 mb-6">
            <KpiCard label="Total Riders" value={riderSummary.total} />
            <KpiCard label="Active Riders" value={riderSummary.active} accent="text-emerald-700" />
            <KpiCard label="Pending Approval" value={riderSummary.pending} accent="text-amber-700" />
            <KpiCard label="Inactive Riders" value={riderSummary.inactive} accent="text-gray-700" />
          </div>

          <div className="mb-5 rounded-lg border border-gray-200 bg-white p-4">
            <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
              <div>
                <h3 className="font-semibold text-gray-950">Rider branch filter</h3>
                <p className="text-sm text-gray-500 mt-1">
                  View all riders or focus on one home branch / storefront.
                </p>
              </div>
              <label className="text-sm font-medium text-gray-700 md:min-w-[280px]">
                Branch
                <select
                  className="input-field mt-1 bg-white"
                  value={riderBranchFilter}
                  onChange={event => setRiderBranchFilter(event.target.value)}
                >
                  <option value="all">All riders</option>
                  <option value="unassigned">No home branch</option>
                  {restaurants.map(store => (
                    <option key={store.id} value={store.id}>
                      {store.branch_name || store.rest_name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="mt-3 text-xs text-gray-500">
              Showing {visibleMerchantRiders.length} of {merchantRiders.length} riders.
            </p>
          </div>

          {!merchantRiders.length && (
            <div className="mb-6 border border-dashed border-gray-300 rounded-lg p-6 text-center">
              <p className="font-semibold text-gray-950">Invite your first delivery rider.</p>
              <p className="text-sm text-gray-500 mt-2">Merchant-owned riders help you build a reliable local delivery network while T-Food keeps verification centralized.</p>
              <button type="button" onClick={() => document.getElementById('invite-rider-form')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} className="btn-primary mt-4 px-4 py-2">
                Invite Rider
              </button>
            </div>
          )}

          <div id="invite-rider-form" className="grid lg:grid-cols-[1fr_360px] gap-6 mb-6 scroll-mt-24">
            <form onSubmit={inviteRider} className="border border-gray-200 rounded-lg p-5">
              <h3 className="font-semibold text-gray-950">Invite rider</h3>
              <p className="text-sm text-gray-500 mt-1">Create an invite token now. Email or SMS sending will be added later.</p>
              <div className="grid sm:grid-cols-2 gap-4 mt-4">
                <label className="text-sm font-medium text-gray-700">
                  Rider name
                  <input required className="input-field mt-1" placeholder="T-Food Express Rider" value={riderInviteForm.name} onChange={event => setRiderInviteForm(form => ({ ...form, name: event.target.value }))} />
                </label>
                <label className="text-sm font-medium text-gray-700">
                  Phone number
                  <input className="input-field mt-1" placeholder="+224 620 00 00 00" value={riderInviteForm.phone} onChange={event => setRiderInviteForm(form => ({ ...form, phone: event.target.value }))} />
                </label>
                <label className="text-sm font-medium text-gray-700">
                  Email address
                  <input type="email" className="input-field mt-1" placeholder="rider@t-food.gn" value={riderInviteForm.email} onChange={event => setRiderInviteForm(form => ({ ...form, email: event.target.value }))} />
                </label>
                <label className="text-sm font-medium text-gray-700">
                  Transport type
                  <input className="input-field mt-1" placeholder="Bike, scooter, car, or walking" value={riderInviteForm.transport_type} onChange={event => setRiderInviteForm(form => ({ ...form, transport_type: event.target.value }))} />
                </label>
                <label className="sm:col-span-2 text-sm font-medium text-gray-700">
                  Home branch / storefront
                  <select className="input-field mt-1 bg-white" value={riderInviteForm.home_restaurant} onChange={event => setRiderInviteForm(form => ({ ...form, home_restaurant: event.target.value }))}>
                    <option value="">No home branch yet</option>
                    {restaurants.map(store => (
                      <option key={store.id} value={store.id} disabled={!store.is_active}>
                        {store.branch_name || store.rest_name}{store.is_active ? '' : ' (inactive)'}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <button type="submit" disabled={riderActionId === 'invite'} className="btn-primary mt-4 px-4 py-2">
                {riderActionId === 'invite' ? 'Creating invite...' : 'Create invite'}
              </button>
            </form>

            <div className="border border-gray-200 rounded-lg p-5">
              <h3 className="font-semibold text-gray-950">Latest invite</h3>
              {lastRiderInvite ? (
                <div className="mt-4 space-y-3 text-sm">
                  <p><span className="text-gray-500">Name:</span> <strong>{lastRiderInvite.name}</strong></p>
                  <p><span className="text-gray-500">{t('statuses.status')}:</span> <strong>{statusLabel(lastRiderInvite.status, t, 'staff')}</strong></p>
                  <div>
                    <p className="text-gray-500">Invite token</p>
                    <p className="mt-1 break-all rounded-lg bg-gray-50 border border-gray-200 p-3 font-mono text-xs">{lastRiderInvite.invite_token}</p>
                  </div>
                  <p className="text-xs text-gray-500">Share this token manually with the rider for now. Verification still requires T-Food Operations approval.</p>
                </div>
              ) : (
                <p className="mt-4 text-sm text-gray-500">Create an invite to see the token and invite status here.</p>
              )}
            </div>
          </div>

          <div className="border border-gray-200 rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
                  <tr>
                    <th className="px-4 py-3">Photo</th>
                    <th className="px-4 py-3">Rider</th>
                    <th className="px-4 py-3">Phone</th>
                    <th className="px-4 py-3">Transport</th>
                    <th className="px-4 py-3">Home Branch / Storefront</th>
                    <th className="px-4 py-3">Verification</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Availability</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 bg-white">
                  {visibleMerchantRiders.map(rider => (
                    <tr key={rider.id} className="align-top">
                      <td className="px-4 py-4">
                        <div className="h-10 w-10 rounded-full bg-brand-50 text-brand-700 flex items-center justify-center font-semibold">
                          {(rider.rider_name || 'R').slice(0, 1).toUpperCase()}
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <p className="font-medium text-gray-950">{rider.rider_name}</p>
                        <span className="mt-1 inline-flex rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs font-medium text-gray-600">
                          {merchantRiderScopeLabel(rider)}
                        </span>
                        <p className="text-xs text-gray-500">{rider.partner_account?.username || 'Partner account pending'}</p>
                        {expandedRiderId === rider.id && (
                          <div className="mt-3 rounded-lg bg-gray-50 border border-gray-200 p-3 text-xs text-gray-600">
                            <p>Email: {rider.partner_account?.email || 'Not provided'}</p>
                            <p>Invite state: {rider.invitation_state || 'No invite linked'}</p>
                            {!rider.partner_is_verified && <p className="mt-2 text-amber-700">Upload required documents before activation.</p>}
                            {rider.status === 'PENDING_APPROVAL' && <p className="mt-2 text-amber-700">Waiting for T-Food Operations verification.</p>}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-4">{rider.rider_phone || '-'}</td>
                      <td className="px-4 py-4">{rider.transport_type || '-'}</td>
                      <td className="px-4 py-4 min-w-[190px]">
                        <select
                          className="input-field py-2 bg-white text-sm"
                          value={rider.home_restaurant?.id || ''}
                          disabled={assigningRiderId === rider.id}
                          onChange={event => assignRiderRestaurant(rider, event.target.value)}
                        >
                          <option value="">No home branch</option>
                          {restaurants.map(store => (
                            <option key={store.id} value={store.id} disabled={!store.is_active}>
                              {store.branch_name || store.rest_name}{store.is_active ? '' : ' (inactive)'}
                            </option>
                          ))}
                        </select>
                        {rider.home_restaurant ? (
                          <div className="mt-2 text-xs text-gray-500">
                            <p>{rider.home_restaurant.branch_type?.replaceAll('_', ' ') || 'Branch'} · {rider.home_restaurant.is_active ? 'Active' : 'Inactive'} · {rider.home_restaurant.is_open ? 'Open' : 'Closed'}</p>
                            <p>{rider.home_restaurant.market?.name || 'Market not set'} · {rider.home_restaurant.city || 'City not set'}{rider.home_restaurant.area ? ` · ${rider.home_restaurant.area}` : ''}</p>
                          </div>
                        ) : (
                          <p className="mt-2 text-xs text-amber-700">No home branch assigned.</p>
                        )}
                      </td>
                      <td className="px-4 py-4">
                        <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${rider.partner_is_verified ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                          {statusLabel(rider.verification_status || 'PENDING', t, 'verification')}
                        </span>
                      </td>
                      <td className="px-4 py-4">{statusLabel(rider.status, t, 'staff')}</td>
                      <td className="px-4 py-4">{rider.availability ? 'Available' : 'Unavailable'}</td>
                      <td className="px-4 py-4">
                        <div className="flex flex-wrap gap-2">
                          <button type="button" onClick={() => setExpandedRiderId(current => current === rider.id ? null : rider.id)} className="btn-secondary px-2 py-1 text-xs">
                            {expandedRiderId === rider.id ? 'Hide' : 'View'}
                          </button>
                          <button type="button" disabled={riderActionId === `${rider.id}-ACTIVE` || !rider.partner_is_verified} onClick={() => setRiderStatus(rider, 'ACTIVE')} className="btn-secondary px-2 py-1 text-xs">
                            Activate
                          </button>
                          <button type="button" disabled={riderActionId === `${rider.id}-INACTIVE`} onClick={() => setRiderStatus(rider, 'INACTIVE')} className="btn-secondary px-2 py-1 text-xs">
                            Deactivate
                          </button>
                          <button type="button" disabled={riderActionId === `${rider.id}-REMOVED`} onClick={() => setRiderStatus(rider, 'REMOVED')} className="btn-secondary px-2 py-1 text-xs text-red-600">
                            Remove
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {!visibleMerchantRiders.length && (
                    <tr>
                      <td colSpan="9" className="px-4 py-8 text-center text-sm text-gray-500">
                        {merchantRiders.length ? 'No riders match this branch filter.' : 'Invite your first delivery rider.'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {!!riderInvites.length && (
            <div className="mt-6">
              <h3 className="font-semibold text-gray-950 mb-3">Recent invites</h3>
              <div className="divide-y divide-gray-200 border-y border-gray-200">
                {riderInvites.slice(0, 5).map(invite => (
                  <div key={invite.id} className="py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                    <div>
                      <p className="font-medium text-gray-950">{invite.name}</p>
                      <p className="text-xs text-gray-500">{invite.email || invite.phone || 'No contact provided'} · {invite.transport_type || 'Transport not set'}</p>
                    </div>
                    <div className="sm:text-right">
                      <p className="text-sm font-medium">{invite.status}</p>
                      <p className="text-xs text-gray-500 break-all">{invite.invite_token}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {activeTab === 'staff' && renderStaffSection()}

      {activeTab === 'network' && (
        <section className="py-8 border-b border-gray-200">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 mb-6">
            <div>
              <div className="flex items-center gap-2">
                <Store size={20} className="text-brand-600" />
                <h2 className="text-xl font-semibold text-gray-950">Merchant Network</h2>
              </div>
              <p className="text-sm text-gray-500 mt-2 max-w-2xl">
                Discover nearby verified merchants and build collaboration relationships. Order transfer, fulfillment sharing, and revenue sharing are not enabled yet.
              </p>
            </div>
            <label className="text-sm font-medium text-gray-700">
              Discovery radius
              <select
                className="input-field mt-1 bg-white min-w-[180px]"
                value={networkRadius}
                onChange={event => setNetworkRadius(event.target.value)}
              >
                <option value="2">2 km</option>
                <option value="5">5 km</option>
                <option value="10">10 km</option>
                <option value="20">20 km</option>
              </select>
            </label>
          </div>

          <div className="grid md:grid-cols-4 gap-3 mb-6">
            <KpiCard label="Nearby Merchants" value={nearbyMerchants.length} />
            <KpiCard label="Requested" value={(merchantNetwork.requested || []).length} accent="text-amber-700" />
            <KpiCard label="Active" value={(merchantNetwork.active || []).length} accent="text-emerald-700" />
            <KpiCard label="Paused / Blocked" value={(merchantNetwork.paused || []).length + (merchantNetwork.blocked || []).length} accent="text-gray-700" />
          </div>

          <div className="grid xl:grid-cols-[1.15fr_0.85fr] gap-6">
            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Nearby merchants</h3>
              <div className="space-y-3">
                {nearbyMerchantsQuery.isLoading && <p className="rounded-lg border border-gray-200 p-4 text-sm text-gray-500">Finding nearby merchants...</p>}
                {nearbyMerchantsQuery.isError && <p className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">Could not load nearby merchants.</p>}
                {!nearbyMerchantsQuery.isLoading && !nearbyMerchants.length && (
                  <p className="rounded-lg border border-gray-200 p-4 text-sm text-gray-500">No nearby merchants found within {networkRadius} km.</p>
                )}
                {nearbyMerchants.map(merchant => (
                  <div key={merchant.id} className="rounded-lg border border-gray-200 p-4">
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h4 className="font-semibold text-gray-950">{merchant.business_name || merchant.username}</h4>
                          {merchant.is_verified && (
                            <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                              Verified
                            </span>
                          )}
                          {merchant.relationship_status && (
                            <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${networkStatusClass(merchant.relationship_status)}`}>
                              {statusLabel(merchant.relationship_status, t, 'operations')}
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-sm text-gray-500">
                          {merchant.distance_km ? `${merchant.distance_km} km away` : 'Distance unavailable'}
                        </p>
                        <p className="mt-1 text-xs text-gray-400">
                          {t('merchantDashboard.verificationLabel')}: {statusLabel(merchant.verification_status || (merchant.is_verified ? 'APPROVED' : 'PENDING'), t, 'verification')}
                        </p>
                      </div>
                      <button
                        type="button"
                        disabled={!!merchant.relationship_status || networkActionId === `request-${merchant.id}`}
                        onClick={() => sendNetworkRequest(merchant)}
                        className="btn-primary px-3 py-2 text-sm disabled:opacity-50"
                      >
                        {merchant.relationship_status ? 'Already connected' : 'Send request'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <h3 className="font-semibold text-gray-950 mb-3">Collaboration requests</h3>
              {merchantNetworkQuery.isLoading && <p className="rounded-lg border border-gray-200 p-4 text-sm text-gray-500">Loading collaboration requests...</p>}
              {merchantNetworkQuery.isError && <p className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">Could not load collaboration requests.</p>}
              {!merchantNetworkQuery.isLoading && ['requested', 'active', 'paused', 'blocked'].map(group => (
                <div key={group} className="mb-5">
                  <div className="mb-2 flex items-center justify-between">
                    <h4 className="text-sm font-semibold uppercase tracking-wide text-gray-500">{group}</h4>
                    <span className="text-xs text-gray-400">{(merchantNetwork[group] || []).length}</span>
                  </div>
                  <div className="space-y-3">
                    {(merchantNetwork[group] || []).length
                      ? (merchantNetwork[group] || []).map(renderNetworkRelationship)
                      : <p className="rounded-lg border border-gray-200 p-4 text-sm text-gray-500">No {group} collaborations.</p>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-8 border-t border-gray-200 pt-8">
            <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 mb-5">
              <div>
                <h3 className="text-lg font-semibold text-gray-950">Fulfillment Requests</h3>
                <p className="text-sm text-gray-500 mt-1 max-w-2xl">
                  Accepted requests do not yet transfer payout or preparation responsibility. This is a coordination workflow for asking an active collaborator for help before preparation starts, without changing dispatch or showing anything to customers.
                </p>
              </div>
            </div>

            <form onSubmit={createFulfillmentRequest} className="grid lg:grid-cols-[160px_1fr_1fr_auto] gap-3 items-end rounded-lg border border-gray-200 p-4 mb-6">
              <label className="text-sm font-medium text-gray-700">
                Order ID
                <select
                  className="input-field mt-1 bg-white"
                  value={fulfillmentRequestForm.order_id}
                  onChange={event => setFulfillmentRequestForm(form => ({ ...form, order_id: event.target.value }))}
                >
                  <option value="">Choose order</option>
                  {orders.filter(order => ['PLACED', 'CONFIRMED'].includes(order.status)).map(order => (
                    <option key={order.id} value={order.id}>#{order.id} - {statusLabel(order.status, t, 'orders')}</option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-medium text-gray-700">
                Collaborator
                <select
                  className="input-field mt-1 bg-white"
                  value={fulfillmentRequestForm.fulfilling_merchant_id}
                  onChange={event => setFulfillmentRequestForm(form => ({ ...form, fulfilling_merchant_id: event.target.value }))}
                >
                  <option value="">Choose active collaborator</option>
                  {activeCollaborators.map(merchant => (
                    <option key={merchant.id} value={merchant.id}>{merchant.business_name || merchant.username}</option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-medium text-gray-700">
                Notes
                <input
                  className="input-field mt-1"
                  placeholder="T-Food fulfillment note"
                  value={fulfillmentRequestForm.notes}
                  onChange={event => setFulfillmentRequestForm(form => ({ ...form, notes: event.target.value }))}
                />
              </label>
              <button type="submit" disabled={fulfillmentActionId === 'create'} className="btn-primary px-4 py-2">
                {fulfillmentActionId === 'create' ? 'Sending...' : 'Request help'}
              </button>
            </form>

            <div className="grid xl:grid-cols-2 gap-6">
              {[
                ['Incoming requests', fulfillmentRequests.incoming || []],
                ['Outgoing requests', fulfillmentRequests.outgoing || []],
              ].map(([title, requests]) => (
                <div key={title}>
                  <div className="mb-3 flex items-center justify-between">
                    <h4 className="font-semibold text-gray-950">{title}</h4>
                    <span className="text-xs text-gray-400">{requests.length}</span>
                  </div>
                  <div className="space-y-3">
                    {requests.length ? requests.map(request => {
                      const availableActions = (
                        request.direction === 'incoming'
                          ? ['ACCEPT', 'REJECT', 'START_PREPARATION', 'READY_FOR_HANDOFF', 'UNABLE_TO_FULFILL', 'RESOLVE']
                          : ['CANCEL']
                      )
                      const actorLabel = request.direction === 'incoming' ? 'Requesting merchant' : 'Fulfilling merchant'
                      const actorMerchant = request.direction === 'incoming' ? request.requesting_merchant : request.fulfilling_merchant
                      const enabledActions = availableActions.filter(action => fulfillmentActionRules[action]?.(request))
                      return (
                      <div key={request.id} className="rounded-lg border border-gray-200 p-4">
                        <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4">
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-semibold text-gray-950">Order #{request.order_id}</p>
                              <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${networkStatusClass(request.status)}`}>
                                Request: {formatFulfillmentStatus(request.status)}
                              </span>
                              <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${networkStatusClass(request.internal_status)}`}>
                                Internal: {formatFulfillmentStatus(request.internal_status)}
                              </span>
                              <span className="rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs font-medium text-gray-600">
                                Customer order: {formatFulfillmentStatus(request.order_status)}
                              </span>
                            </div>
                            <p className="mt-2 text-sm text-gray-500">
                              {actorLabel}: {actorMerchant?.business_name || actorMerchant?.username || 'Not available'}
                            </p>
                            {request.direction === 'outgoing' && (
                              <p className="mt-2 text-sm text-gray-600">
                                View progress: {formatFulfillmentStatus(request.internal_status)}
                              </p>
                            )}
                            {request.notes && <p className="mt-2 text-sm text-gray-600">{request.notes}</p>}
                            <div className="mt-3 grid gap-2 text-xs text-amber-800">
                              <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2">Merchant A remains customer-facing.</p>
                              <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2">This does not change customer order status.</p>
                            </div>
                            <SettlementPreviewPanel
                              preview={request.settlement_preview}
                              label={request.settlement_preview_label}
                            />
                            <FulfillmentTimeline events={request.events || []} />
                          </div>
                          <div className="xl:w-52 flex flex-wrap xl:flex-col gap-2">
                            {availableActions.map(action => {
                              const enabled = fulfillmentActionRules[action]?.(request)
                              return (
                                <button
                                  key={action}
                                  type="button"
                                  disabled={!enabled || fulfillmentActionId === `${request.id}-${action}`}
                                  onClick={() => respondToFulfillmentRequest(request, action)}
                                  className={`btn-secondary px-3 py-2 text-sm ${['REJECT', 'CANCEL', 'UNABLE_TO_FULFILL'].includes(action) ? 'text-red-600' : ''}`}
                                  title={enabled ? fulfillmentActionLabels[action] : `Not available while request is ${formatFulfillmentStatus(request.status)} and internal status is ${formatFulfillmentStatus(request.internal_status)}`}
                                >
                                  {fulfillmentActionId === `${request.id}-${action}` ? 'Saving...' : fulfillmentActionLabels[action]}
                                </button>
                              )
                            })}
                            {!enabledActions.length && (
                              <p className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-500">
                                No actions available in this state.
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                      )
                    }) : (
                      <p className="rounded-lg border border-gray-200 p-4 text-sm text-gray-500">No {title.toLowerCase()}.</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {activeTab === 'payouts' && (
        <section className="py-8 border-b border-gray-200">
          <div className="flex items-center gap-2 mb-5">
            <ReceiptText size={20} className="text-brand-600" />
            <h2 className="text-xl font-semibold">Payouts</h2>
          </div>
          <div className="grid sm:grid-cols-4 gap-3 mb-6">
            {['PENDING', 'AVAILABLE', 'PAID', 'CANCELLED'].map(status => (
              <div key={status} className="border border-gray-200 rounded-lg p-4">
                <p className="text-sm text-gray-500">{status.replaceAll('_', ' ')}</p>
                <p className="text-xl font-bold mt-1">{money(payouts?.totals?.[status])}</p>
              </div>
            ))}
          </div>
          <div className="divide-y divide-gray-200 border-y border-gray-200">
            {(payouts?.results || []).map(payout => (
              <div key={payout.order_id} className="py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                  <p className="font-medium text-gray-950">Order #{payout.order_id}</p>
                  <p className="text-sm text-gray-500">{payout.customer_name} · {payout.payment_method} · {payout.payment_status}</p>
                </div>
                <div className="sm:text-right">
                  <p className="font-semibold">{money(payout.merchant_payout)}</p>
                  <p className="text-xs text-gray-500">{payout.merchant_payout_status}</p>
                </div>
              </div>
            ))}
            {!payouts?.results?.length && <p className="py-4 text-sm text-gray-500">No payout records yet.</p>}
          </div>
        </section>
      )}

      {editingOptionsFor && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-0 sm:p-4" role="dialog" aria-modal="true" aria-label={`Options for ${editingOptionsFor.food_name}`}>
          <div className="bg-white w-full sm:max-w-2xl max-h-[92vh] overflow-y-auto rounded-t-lg sm:rounded-lg">
            <div className="sticky top-0 z-10 bg-white border-b border-gray-200 p-5 flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">Options for {editingOptionsFor.food_name}</h2>
                <p className="text-sm text-gray-500 mt-1">Set sizes, spice levels, add-ons, and selection rules.</p>
              </div>
              <button type="button" onClick={() => setEditingOptionsFor(null)} className="btn-secondary">Close</button>
            </div>
            <div className="p-5 space-y-5">
              {!optionGroups.length && <p className="text-sm text-gray-500">This item has no customization groups yet.</p>}
              {optionGroups.map((group, groupIndex) => (
                <section key={group.id || `new-${groupIndex}`} className="border border-gray-200 rounded-lg p-4">
                  <div className="grid sm:grid-cols-[1fr_110px_110px_auto] gap-3">
                    <input required className="input-field" placeholder="T-Food meal size" value={group.name} onChange={event => updateOptionGroup(groupIndex, { name: event.target.value })} />
                    <label className="text-xs text-gray-600">Minimum<input type="number" min="0" max="20" className="input-field mt-1" value={group.min_select} onChange={event => updateOptionGroup(groupIndex, { min_select: Number(event.target.value) })} /></label>
                    <label className="text-xs text-gray-600">Maximum<input type="number" min="1" max="20" className="input-field mt-1" value={group.max_select} onChange={event => updateOptionGroup(groupIndex, { max_select: Number(event.target.value) })} /></label>
                    <button type="button" onClick={() => setOptionGroups(current => current.filter((_, index) => index !== groupIndex))} className="p-2 text-red-500 self-end rounded-lg hover:bg-red-50" title="Remove group"><Trash2 size={17} /></button>
                  </div>
                  <div className="mt-4 space-y-2">
                    {group.options.map((option, optionIndex) => (
                      <div key={option.id || `new-option-${optionIndex}`} className="grid grid-cols-[1fr_120px_auto_auto] items-center gap-2">
                        <input className="input-field" placeholder="T-Food large" value={option.name} onChange={event => updateOption(groupIndex, optionIndex, { name: event.target.value })} />
                        <input type="number" min="0" step="0.01" className="input-field" aria-label="Additional price" value={option.price_delta} onChange={event => updateOption(groupIndex, optionIndex, { price_delta: event.target.value })} />
                        <input type="checkbox" checked={option.is_available} onChange={event => updateOption(groupIndex, optionIndex, { is_available: event.target.checked })} title="Available" />
                        <button type="button" onClick={() => updateOptionGroup(groupIndex, { options: group.options.filter((_, index) => index !== optionIndex) })} className="p-2 text-red-500 rounded-lg hover:bg-red-50" title="Remove option"><Trash2 size={16} /></button>
                      </div>
                    ))}
                  </div>
                  <button type="button" onClick={() => addOption(groupIndex)} className="btn-secondary mt-3 inline-flex items-center gap-2 text-sm"><Plus size={15} /> Add option</button>
                </section>
              ))}
              <button type="button" onClick={addOptionGroup} className="btn-secondary inline-flex items-center gap-2"><Plus size={16} /> Add group</button>
            </div>
            <div className="sticky bottom-0 bg-white border-t border-gray-200 p-4 flex justify-end">
              <button type="button" onClick={saveOptions} disabled={savingOptions} className="btn-primary">{savingOptions ? 'Saving...' : 'Save options'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
