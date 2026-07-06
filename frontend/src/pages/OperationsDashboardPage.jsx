import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  BadgePercent,
  Bike,
  Banknote,
  Bell,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  FileText,
  Headphones,
  ImagePlus,
  PackageCheck,
  Route,
  ShieldCheck,
  Sparkles,
  Store,
  Users,
  XCircle,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { getOperationsInsights } from '../api/intelligence'
import {
  createOperationsOffer,
  createPaymentProviderConfig,
  createOperationsAccessStaff,
  getOperationsSummary,
  getOperationsAccessMe,
  assignOperationsDelivery,
  assignOperationsAccessArea,
  assignOperationsAccessCity,
  assignOperationsAccessMarket,
  archiveOperationsNotification,
  getOperationsLedger,
  getOperationsRevenue,
  dismissOperationsNotification,
  listOperationsAccessStaff,
  listPaymentProviderConfigs,
  listOperationsBranches,
  listOperationsCustomers,
  listOperationsDispatch,
  listOperationsFulfillmentRequests,
  listOperationsNotifications,
  listOperationsOffers,
  listOperationsOrders,
  listOperationsPartners,
  listOperationsReviewPhotos,
  listOperationsRestaurants,
  listOperationsMerchantDocuments,
  listOperationsPartnerDocuments,
  listOperationsStaff,
  listOperationsStaffDocuments,
  listPartnerPayouts,
  listMerchantPayouts,
  listOperationsMerchants,
  listOperationsSupportTickets,
  updatePartnerVerification,
  updateMerchantVerification,
  updateOperationsStaffVerification,
  updateOperationsFulfillmentRequest,
  reviewOperationsStaffDocument,
  reviewOperationsVerificationDocument,
  updateSupportTicket,
  markPartnerPayoutPaid,
  markMerchantPayoutPaid,
  markAllOperationsNotificationsRead,
  markOperationsNotificationRead,
  moderateOperationsReviewPhoto,
  removeOperationsAccessArea,
  removeOperationsAccessCity,
  removeOperationsAccessMarket,
  updateOperationsAccessStaff,
  updateOperationsOffer,
  updatePaymentProviderConfig,
  updateOperationsBranchStatus,
} from '../api/operations'
import {
  createCurrency,
  createMarket,
  createMarketArea,
  createMarketCity,
  listCurrencies,
  listMarketAreas,
  listMarketCities,
  listMarkets,
} from '../api/markets'
import { openPrivateMedia } from '../api/media'
import PrivateImage from '../components/PrivateImage.jsx'
import { usePreferences } from '../context/PreferencesContext'
import { formatCurrency, formatDateTime as formatPreferenceDateTime } from '../lib/formatters'
import useTitle from '../hooks/useTitle'

const OperationsOverviewPanel = lazy(() => import('../components/operations/OperationsOverviewPanels.jsx'))
const PendingActionQueuesPanel = lazy(() => import('../components/operations/OperationsOverviewPanels.jsx').then(module => ({ default: module.PendingActionQueuesPanel })))
const FocusedOverviewPanel = lazy(() => import('../components/operations/OperationsOverviewPanels.jsx').then(module => ({ default: module.FocusedOverviewPanel })))
const OperationsIntelligencePanel = lazy(() => import('../components/operations/OperationsIntelligencePanel.jsx'))
const OperationsLedgerPanel = lazy(() => import('../components/operations/OperationsLedgerPanel.jsx'))

const PanelLoading = () => (
  <section className="bg-white border border-gray-200 rounded-lg p-5 text-sm text-gray-500">
    Loading section...
  </section>
)

const money = (value, currency = 'GNF') => formatCurrency(value, currency)
const ledgerMoney = (value, currency = 'GNF') => formatCurrency(value, currency)
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
      <div className="mt-3 grid sm:grid-cols-2 lg:grid-cols-4 gap-2">
        {settlementPreviewRows(preview).map(([name, value]) => (
          <div key={name} className="rounded-md bg-white/70 px-3 py-2 text-sm">
            <p className="text-xs text-gray-500">{name}</p>
            <p className="font-semibold text-gray-950">{money(value)}</p>
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
              {event.actor?.name || event.actor?.username || 'System'} · {formatDateTime(event.created_at)}
            </p>
            {event.note && <p className="mt-1 text-sm text-gray-600">{event.note}</p>}
          </div>
        ))}
      </div>
    </div>
  )
}
const rangeOptions = [
  { value: 'today', labelKey: 'operations.ranges.today' },
  { value: 'yesterday', labelKey: 'operations.ranges.yesterday' },
  { value: 'last_7_days', labelKey: 'operations.ranges.last7' },
  { value: 'last_30_days', labelKey: 'operations.ranges.last30' },
  { value: 'this_month', labelKey: 'operations.ranges.thisMonth' },
  { value: 'this_year', labelKey: 'operations.ranges.thisYear' },
]
const defaultProviderForm = {
  market: '',
  provider_code: 'orange_money',
  payment_method: 'MOBILE_MONEY',
  is_active: false,
  is_preferred: false,
  priority: 1,
  supports_refund: true,
  supports_webhook: true,
  supports_partial_refund: false,
  credentials_present: false,
}
const defaultOfferForm = {
  market: '',
  code: 'TFOOD10',
  discount_percent: 10,
  min_order_amount: '0.00',
  max_uses_total: '',
  max_uses_per_customer: '1',
  first_order_only: false,
  is_active: true,
}
const defaultOperationsUserForm = {
  username: '',
  email: '',
  first_name: '',
  last_name: '',
  role: 'VIEWER',
  status: 'ACTIVE',
}
const defaultCurrencySetupForm = {
  code: 'GNF',
  name: 'Guinean Franc',
  symbol: 'GNF',
  numeric_code: '324',
  minor_unit: 0,
  is_active: true,
}
const defaultMarketSetupForm = {
  name: 'Guinea',
  slug: 'guinea',
  country_code: 'GN',
  default_currency: 'GNF',
  timezone: 'Africa/Conakry',
  phone_country_code: '+224',
  is_active: true,
}
const defaultCitySetupForm = {
  market: '',
  name: 'Conakry',
  slug: 'conakry',
  is_active: true,
}
const defaultAreaSetupForm = {
  city: '',
  name: 'Kaloum',
  slug: 'kaloum',
  service_radius_km: '5.00',
  is_active: true,
}
const operationsRoleOptions = [
  'GLOBAL_ADMIN',
  'COUNTRY_ADMIN',
  'CITY_ADMIN',
  'AREA_ADMIN',
  'OPERATIONS_STAFF',
  'SUPPORT_STAFF',
  'FINANCE_STAFF',
  'VERIFICATION_REVIEWER',
  'DISPATCH_OPERATOR',
  'VIEWER',
]
const operationsStatusOptions = ['ACTIVE', 'INACTIVE', 'SUSPENDED']
const defaultDashboardScope = { type: 'global', value: '' }
const documentLabels = {
  OWNER_PROFILE_PHOTO: 'Owner profile photo',
  PARTNER_PROFILE_PHOTO: 'Partner profile photo',
  AADHAAR: 'Aadhaar',
  NATIONAL_ID: 'National ID',
  PASSPORT: 'Passport',
  VOTER_CARD: 'Voter card',
  DRIVING_LICENSE: 'Driving license',
  RESTAURANT_PHOTO: 'Restaurant photo',
  BUSINESS_DOCUMENT: 'Business document',
  VEHICLE_DOCUMENT: 'Vehicle document',
}
const verificationStatusLabels = {
  PENDING: 'Pending',
  SUBMITTED: 'Submitted',
  APPROVED: 'Approved',
  VERIFIED: 'Verified',
  REJECTED: 'Rejected',
  SUSPENDED: 'Suspended',
  MORE_INFO_REQUIRED: 'More info required',
}
const documentStatusClass = status => {
  if (status === 'APPROVED') return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (status === 'REJECTED') return 'bg-red-50 text-red-700 border-red-200'
  return 'bg-amber-50 text-amber-700 border-amber-200'
}
const fulfillmentStatusClass = status => {
  if (['ACCEPTED', 'RESOLVED', 'READY_FOR_HANDOFF'].includes(status)) return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (['REJECTED', 'CANCELLED', 'UNABLE_TO_FULFILL'].includes(status)) return 'bg-red-50 text-red-700 border-red-200'
  if (['IN_PROGRESS', 'REQUESTED', 'PENDING'].includes(status)) return 'bg-amber-50 text-amber-700 border-amber-200'
  return 'bg-amber-50 text-amber-700 border-amber-200'
}
const formatFulfillmentStatus = value => value?.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, letter => letter.toUpperCase()) || 'Not available'
const joinProfileDetails = details => details.filter(Boolean).join(' · ')
const contactSetupGap = profileType => `Phone not set (${profileType} setup gap)`
const formatMerchantContact = merchant => joinProfileDetails([
  merchant.owner_name || 'Owner name not set',
  merchant.username ? `@${merchant.username}` : 'Username not set',
  merchant.email || 'Email not provided',
  merchant.phone || contactSetupGap('merchant profile'),
])
const formatPartnerContact = partner => ([
  `@${partner.username || 'unknown'}`,
  partner.email || 'Email not provided',
  partner.partner_phone || contactSetupGap('partner profile'),
]).join(' · ')
const formatPartnerTransport = partner => ([
  partner.transport_details ? `Transport: ${partner.transport_details}` : 'Transport type not set (partner profile setup gap)',
  `${partner.delivery_count || 0} deliveries`,
  partner.is_available ? 'Available for assignment' : 'Not available for assignment',
]).join(' · ')
const formatStaffContact = staff => joinProfileDetails([
  staff.user?.username ? `@${staff.user.username}` : null,
  staff.email || staff.user?.email || 'Email not provided',
  staff.phone || contactSetupGap('staff profile'),
])
const formatStaffProfile = staff => joinProfileDetails([
  `Role: ${formatFulfillmentStatus(staff.role)}`,
  `Membership: ${formatFulfillmentStatus(staff.membership_status)}`,
  `Scope: ${staff.is_company_wide ? 'Company-wide' : 'Branch-specific'}`,
])
const countryCodesForProfile = profile => new Set([
  ...(profile.assigned_markets || []).map(market => market.country_code).filter(Boolean),
  ...(profile.assigned_countries || []).map(country => country.country_code || country.code || country).filter(Boolean),
])
const marketIdsForProfile = profile => new Set((profile.assigned_markets || []).map(market => String(market.id)))
const scopedOptionsForProfile = (scopeType, profile, options) => {
  if (scopeType === 'market') return options
  const countryCodes = countryCodesForProfile(profile)
  const marketIds = marketIdsForProfile(profile)
  if (!countryCodes.size && !marketIds.size) return options
  return options.filter(option => {
    const optionMarketId = option.market || option.market_id
    const optionCountry = option.country_code || option.market_country_code
    return (
      (optionMarketId && marketIds.has(String(optionMarketId)))
      || (optionCountry && countryCodes.has(optionCountry))
    )
  })
}
const operationsFulfillmentStatuses = [
  'REQUESTED',
  'ACCEPTED',
  'IN_PROGRESS',
  'READY_FOR_HANDOFF',
  'UNABLE_TO_FULFILL',
  'RESOLVED',
  'CANCELLED',
]
const operationsFulfillmentActionEnabled = (request, action) => {
  if (action === 'ADD_NOTE') return true
  if (action === 'OVERRIDE_STATUS') return true
  if (action === 'CANCEL') return !['REJECTED', 'CANCELLED', 'RESOLVED'].includes(request.internal_status)
  if (action === 'RESOLVE') return ['READY_FOR_HANDOFF', 'UNABLE_TO_FULFILL'].includes(request.internal_status)
  return false
}
const formatDocumentType = value => documentLabels[value] || value?.replaceAll('_', ' ') || 'Document'
const staffDocumentRequirements = staff => {
  const countryCode = staff?.merchant_company?.market?.country_code
  if (countryCode === 'GN') return ['National ID', 'Passport', 'Voter Card']
  if (countryCode === 'IN') return ['Passport', 'Voter ID', 'Driving License', 'Aadhaar where configured']
  return ['Market-specific staff document rules are not configured. Use the active global identity requirements.']
}
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
const merchantRequirementsMet = summary => Boolean(
  summary?.has_owner_profile_photo && summary?.has_identity_document && summary?.has_restaurant_photo
)
const partnerRequirementsMet = summary => Boolean(
  summary?.has_partner_profile_photo && summary?.has_identity_document
)
const maxBreakdownAmount = rows => Math.max(...(rows || []).map(row => Number(row.amount || 0)), 1)

function RequirementPill({ done, label, optional = false }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${done ? 'bg-emerald-50 text-emerald-700' : optional ? 'bg-gray-100 text-gray-600' : 'bg-amber-50 text-amber-700'}`}>
      {done ? <CheckCircle2 size={13} /> : optional ? <Clock3 size={13} /> : <XCircle size={13} />}
      {label}
    </span>
  )
}

function VerificationDocuments({ documentsPayload, isLoading, isError, onReview, updatingId, rejectionReasons, setRejectionReasons }) {
  const documents = documentsPayload?.results || documentsPayload || []
  return (
    <div className="mt-4 rounded-lg border border-gray-200 divide-y divide-gray-200">
      {isLoading && <p className="p-4 text-sm text-gray-500">Loading documents...</p>}
      {isError && <p className="p-4 text-sm text-red-600">Could not load documents.</p>}
      {!isLoading && !documents.length && <p className="p-4 text-sm text-gray-500">No documents uploaded yet.</p>}
      {documents.map(document => (
        <div key={document.id} className="p-4">
          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
            <div className="flex items-start gap-3">
              <FileText size={18} className="mt-1 flex-shrink-0 text-brand-600" />
              <div>
                <p className="font-medium text-gray-950">{formatDocumentType(document.document_type)}</p>
                <p className="text-xs text-gray-500 mt-1">Uploaded {formatDateTime(document.created_at)}</p>
                {document.rejection_reason && (
                  <p className="text-sm text-red-600 mt-2"><strong>Rejection reason:</strong> {document.rejection_reason}</p>
                )}
                {document.file_url && (
                  <button type="button" onClick={() => openPrivateMedia(document.file_url)} className="mt-2 inline-block text-left text-sm font-medium text-brand-700 hover:underline">
                    View or download file
                  </button>
                )}
              </div>
            </div>
            <span className={`w-fit rounded-full border px-2.5 py-1 text-xs font-medium ${documentStatusClass(document.status)}`}>
              {document.status?.replaceAll('_', ' ') || 'PENDING'}
            </span>
          </div>
          <div className="mt-3 grid md:grid-cols-[1fr_auto_auto] gap-2">
            <input
              className="input-field"
              placeholder="T-Food document rejection reason"
              value={rejectionReasons[document.id] || ''}
              onChange={event => setRejectionReasons(current => ({ ...current, [document.id]: event.target.value }))}
            />
            <button
              type="button"
              disabled={updatingId === `document-${document.id}` || document.status === 'APPROVED'}
              onClick={() => onReview(document, 'APPROVED')}
              className="btn-secondary inline-flex items-center justify-center gap-2 text-sm"
            >
              <CheckCircle2 size={16} /> Approve document
            </button>
            <button
              type="button"
              disabled={updatingId === `document-${document.id}`}
              onClick={() => onReview(document, 'REJECTED')}
              className="btn-secondary inline-flex items-center justify-center gap-2 text-sm text-red-600"
            >
              <XCircle size={16} /> Reject document
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

export default function OperationsDashboardPage() {
  const { t } = useTranslation()
  useTitle(t('nav.operationsDashboard'))
  const { preferences } = usePreferences()
  const money = value => formatCurrency(value, 'GNF', preferences)
  const formatDateTime = value => formatPreferenceDateTime(value, preferences, { fallback: 'Not available' })
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedView = searchParams.get('view') || 'overview'
  const activeView = requestedView === 'pending' ? 'pending-merchants' : requestedView
  const [selectedRange, setSelectedRange] = useState('today')
  const [filter, setFilter] = useState('pending')
  const [partnerFilter, setPartnerFilter] = useState('pending')
  const [updatingId, setUpdatingId] = useState(null)
  const [ticketNotes, setTicketNotes] = useState({})
  const [dispatchSelections, setDispatchSelections] = useState({})
  const [fulfillmentNotes, setFulfillmentNotes] = useState({})
  const [fulfillmentOverrideStatuses, setFulfillmentOverrideStatuses] = useState({})
  const [merchantRejectionReasons, setMerchantRejectionReasons] = useState({})
  const [partnerRejectionReasons, setPartnerRejectionReasons] = useState({})
  const [staffDecisionReasons, setStaffDecisionReasons] = useState({})
  const [documentRejectionReasons, setDocumentRejectionReasons] = useState({})
  const [providerForm, setProviderForm] = useState(defaultProviderForm)
  const [offerForm, setOfferForm] = useState(defaultOfferForm)
  const [operationsUserForm, setOperationsUserForm] = useState(defaultOperationsUserForm)
  const [currencySetupForm, setCurrencySetupForm] = useState(defaultCurrencySetupForm)
  const [marketSetupForm, setMarketSetupForm] = useState(defaultMarketSetupForm)
  const [citySetupForm, setCitySetupForm] = useState(defaultCitySetupForm)
  const [areaSetupForm, setAreaSetupForm] = useState(defaultAreaSetupForm)
  const [marketplaceSetupOpen, setMarketplaceSetupOpen] = useState(false)
  const [operationsScopeSelections, setOperationsScopeSelections] = useState({})
  const [dashboardScope, setDashboardScope] = useState(defaultDashboardScope)
  const [branchFilters, setBranchFilters] = useState({
    country_code: '',
    market: '',
    city: '',
    area: '',
    branch_type: '',
    status: '',
    merchant_id: '',
    branch_id: '',
  })
  const [notificationFilters, setNotificationFilters] = useState({
    status: '',
    category: '',
    priority: '',
    event_type: '',
    unread: '',
  })
  const [reviewPhotoFilters, setReviewPhotoFilters] = useState({
    status: 'PENDING',
    restaurant: '',
    customer: '',
    date_from: '',
    date_to: '',
  })
  const [reviewPhotoReasons, setReviewPhotoReasons] = useState({})
  const operationsAccessQuery = useQuery({
    queryKey: ['operations-access-me'],
    queryFn: async () => (await getOperationsAccessMe()).data,
    staleTime: 1000 * 60,
  })
  const rangeParams = { range: selectedRange }
  const selectedRangeLabel = t(rangeOptions.find(option => option.value === selectedRange)?.labelKey || 'operations.ranges.today')
  const dashboardScopeParams = dashboardScope.type === 'market' && dashboardScope.value
    ? { market: dashboardScope.value }
    : dashboardScope.type === 'country' && dashboardScope.value
      ? { country_code: dashboardScope.value }
      : dashboardScope.type === 'city' && dashboardScope.value
        ? { city: dashboardScope.value }
        : dashboardScope.type === 'area' && dashboardScope.value
          ? { area: dashboardScope.value }
          : {}
  const scopedRangeParams = { ...rangeParams, ...dashboardScopeParams }
  const dashboardScopeKey = `${dashboardScope.type}:${dashboardScope.value || 'all'}`
  const recordViews = [
    'pending-merchants',
    'pending-partners',
    'open-support',
    'unassigned-deliveries',
    'merchant-settlements',
    'partner-payouts',
    'dispatch',
    'support',
    'fulfillment-requests',
    'branches',
    'merchant-applications',
    'partner-applications',
    'ledger',
    'payment-providers',
    'promo-codes',
    'notifications',
    'operations-users',
    'marketplace-intelligence',
    'staff-verification',
    'review-photo-moderation',
  ]
  const showFocusedOverview = activeView !== 'overview' && !recordViews.includes(activeView)
  const showMerchantSettlements = activeView === 'merchant-settlements'
  const showPartnerPayouts = activeView === 'partner-payouts'
  const showDispatchSection = ['dispatch', 'unassigned-deliveries'].includes(activeView)
  const showSupportSection = ['support', 'open-support'].includes(activeView)
  const showFulfillmentRequests = activeView === 'fulfillment-requests'
  const showBranches = activeView === 'branches'
  const showLedger = activeView === 'ledger'
  const showPaymentProviders = activeView === 'payment-providers'
  const showPromoCodes = activeView === 'promo-codes'
  const showOperationsNotifications = activeView === 'notifications'
  const showOperationsUsers = activeView === 'operations-users'
  const showReviewPhotoModeration = activeView === 'review-photo-moderation'
  const showMerchantApplications = ['pending-merchants', 'merchant-applications'].includes(activeView)
  const showPartnerApplications = ['pending-partners', 'partner-applications'].includes(activeView)
  const showMarketplaceIntelligence = activeView === 'marketplace-intelligence'
  const showStaffVerification = activeView === 'staff-verification'
  const needsMerchants = ['merchants', 'verification', 'pending-merchants', 'merchant-applications'].includes(activeView)
  const needsPartners = ['partners', 'verification', 'pending-partners', 'partner-applications', 'dispatch', 'unassigned-deliveries'].includes(activeView)
  const needsStaff = ['verification', 'staff-verification'].includes(activeView)
  const needsSupport = showSupportSection
  const needsDispatch = showDispatchSection
  const needsFulfillmentRequests = showFulfillmentRequests
  const needsPartnerPayouts = showPartnerPayouts
  const needsMerchantPayouts = showMerchantSettlements
  const needsCustomers = activeView === 'customers'
  const needsRestaurants = activeView === 'restaurants'
  const needsBranches = showBranches
  const needsGeographyOptions = showBranches || showPaymentProviders || showOperationsUsers || showMarketplaceIntelligence
  const needsOpenOrders = activeView === 'orders'
  const needsRevenue = activeView === 'revenue'
  const needsLedger = showLedger
  const needsOperationsNotifications = showOperationsNotifications
  const needsReviewPhotos = showReviewPhotoModeration
  const needsPaymentProviders = showPaymentProviders || showOperationsUsers || showMarketplaceIntelligence
  const needsOperationsInsights = showMarketplaceIntelligence
  const needsOperationsUsers = showOperationsUsers
  const needsMerchantDocuments = ['verification', 'pending-merchants', 'merchant-applications'].includes(activeView)
  const needsPartnerDocuments = ['verification', 'pending-partners', 'partner-applications'].includes(activeView)
  const needsStaffDocuments = ['verification', 'staff-verification'].includes(activeView)
  const summaryQuery = useQuery({
    queryKey: ['operations-summary', dashboardScopeKey],
    queryFn: async () => (await getOperationsSummary(dashboardScopeParams)).data,
    staleTime: 1000 * 30,
  })
  const merchantsQuery = useQuery({
    queryKey: ['operations-merchants', selectedRange, dashboardScopeKey],
    queryFn: async () => (await listOperationsMerchants(scopedRangeParams)).data,
    enabled: needsMerchants,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const partnersQuery = useQuery({
    queryKey: ['operations-partners', selectedRange, dashboardScopeKey],
    queryFn: async () => (await listOperationsPartners(scopedRangeParams)).data,
    enabled: needsPartners,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const staffQuery = useQuery({
    queryKey: ['operations-staff', selectedRange, dashboardScopeKey],
    queryFn: async () => (await listOperationsStaff(scopedRangeParams)).data,
    enabled: needsStaff,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const supportQuery = useQuery({
    queryKey: ['operations-support', selectedRange, dashboardScopeKey],
    queryFn: async () => (await listOperationsSupportTickets(scopedRangeParams)).data,
    enabled: needsSupport,
    keepPreviousData: true,
    staleTime: 1000 * 15,
  })
  const dispatchQuery = useQuery({
    queryKey: ['operations-dispatch', selectedRange, dashboardScopeKey],
    queryFn: async () => (await listOperationsDispatch(scopedRangeParams)).data,
    enabled: needsDispatch,
    keepPreviousData: true,
    staleTime: 1000 * 5,
    refetchInterval: needsDispatch ? 5000 : false,
  })
  const fulfillmentRequestsQuery = useQuery({
    queryKey: ['operations-fulfillment-requests', selectedRange, dashboardScopeKey],
    queryFn: async () => (await listOperationsFulfillmentRequests(scopedRangeParams)).data,
    enabled: needsFulfillmentRequests,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const payoutsQuery = useQuery({
    queryKey: ['partner-payouts', selectedRange, dashboardScopeKey],
    queryFn: async () => (await listPartnerPayouts(scopedRangeParams)).data,
    enabled: needsPartnerPayouts,
    keepPreviousData: true,
    staleTime: 1000 * 60,
  })
  const merchantPayoutsQuery = useQuery({
    queryKey: ['merchant-payouts', selectedRange, dashboardScopeKey],
    queryFn: async () => (await listMerchantPayouts(scopedRangeParams)).data,
    enabled: needsMerchantPayouts,
    keepPreviousData: true,
    staleTime: 1000 * 60,
  })
  const customersQuery = useQuery({
    queryKey: ['operations-customers', selectedRange, dashboardScopeKey],
    queryFn: async () => (await listOperationsCustomers(scopedRangeParams)).data,
    enabled: needsCustomers,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const restaurantsQuery = useQuery({
    queryKey: ['operations-restaurants', 'active', dashboardScopeKey],
    queryFn: async () => (await listOperationsRestaurants({ status: 'active', ...dashboardScopeParams })).data,
    enabled: needsRestaurants,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const branchQueryParams = {
    country_code: branchFilters.country_code || dashboardScopeParams.country_code || undefined,
    market: branchFilters.market || dashboardScopeParams.market || undefined,
    city: branchFilters.city || dashboardScopeParams.city || undefined,
    area: branchFilters.area || dashboardScopeParams.area || undefined,
    branch_type: branchFilters.branch_type || undefined,
    merchant_id: branchFilters.merchant_id || undefined,
    branch_id: branchFilters.branch_id || undefined,
    is_active: branchFilters.status === 'active'
      ? 'true'
      : branchFilters.status === 'inactive'
        ? 'false'
        : undefined,
    is_open: branchFilters.status === 'open'
      ? 'true'
      : branchFilters.status === 'closed'
        ? 'false'
        : undefined,
  }
  const branchesQuery = useQuery({
    queryKey: ['operations-branches', branchFilters, dashboardScopeKey],
    queryFn: async () => (await listOperationsBranches(branchQueryParams)).data,
    enabled: needsBranches,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const citiesQuery = useQuery({
    queryKey: ['market-cities', branchFilters.market, branchFilters.country_code],
    queryFn: async () => (await listMarketCities({
      market: branchFilters.market || undefined,
      country_code: branchFilters.country_code || undefined,
    })).data,
    enabled: needsBranches,
    staleTime: 1000 * 60,
  })
  const areasQuery = useQuery({
    queryKey: ['market-areas', branchFilters.city, branchFilters.country_code],
    queryFn: async () => (await listMarketAreas({
      city: branchFilters.city || undefined,
      country_code: branchFilters.country_code || undefined,
    })).data,
    enabled: needsBranches,
    staleTime: 1000 * 60,
  })
  const allCitiesQuery = useQuery({
    queryKey: ['market-cities', 'operations-access-all'],
    queryFn: async () => (await listMarketCities()).data,
    enabled: needsGeographyOptions,
    staleTime: 1000 * 60,
  })
  const allAreasQuery = useQuery({
    queryKey: ['market-areas', 'operations-access-all'],
    queryFn: async () => (await listMarketAreas()).data,
    enabled: needsGeographyOptions,
    staleTime: 1000 * 60,
  })
  const setupMarketsQuery = useQuery({
    queryKey: ['markets', 'operations-setup'],
    queryFn: async () => (await listMarkets()).data,
    staleTime: 1000 * 60,
  })
  const setupCurrenciesQuery = useQuery({
    queryKey: ['currencies', 'operations-setup'],
    queryFn: async () => (await listCurrencies()).data,
    staleTime: 1000 * 60,
  })
  const refreshGeographySetup = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['markets'] }),
      queryClient.invalidateQueries({ queryKey: ['currencies'] }),
      queryClient.invalidateQueries({ queryKey: ['market-cities'] }),
      queryClient.invalidateQueries({ queryKey: ['market-areas'] }),
      queryClient.invalidateQueries({ queryKey: ['operations-payment-providers'] }),
    ])
  }
  const currencySetupMutation = useMutation({
    mutationFn: payload => createCurrency(payload),
    onSuccess: async response => {
      await refreshGeographySetup()
      setMarketSetupForm(current => ({ ...current, default_currency: response.data.code }))
      toast.success('Currency saved.')
    },
    onError: error => toast.error(error.response?.data?.detail || 'Could not save currency.'),
  })
  const marketSetupMutation = useMutation({
    mutationFn: payload => createMarket(payload),
    onSuccess: async response => {
      await refreshGeographySetup()
      setCitySetupForm(current => ({ ...current, market: String(response.data.id) }))
      toast.success('Market saved.')
    },
    onError: error => toast.error(error.response?.data?.detail || 'Could not save market.'),
  })
  const citySetupMutation = useMutation({
    mutationFn: payload => createMarketCity(payload),
    onSuccess: async response => {
      await refreshGeographySetup()
      setAreaSetupForm(current => ({ ...current, city: String(response.data.id) }))
      toast.success('City saved.')
    },
    onError: error => toast.error(error.response?.data?.detail || 'Could not save city.'),
  })
  const areaSetupMutation = useMutation({
    mutationFn: payload => createMarketArea(payload),
    onSuccess: async () => {
      await refreshGeographySetup()
      toast.success('Area saved.')
    },
    onError: error => toast.error(error.response?.data?.detail || 'Could not save area.'),
  })
  const currencySetupSaving = currencySetupMutation.isPending || currencySetupMutation.isLoading
  const marketSetupSaving = marketSetupMutation.isPending || marketSetupMutation.isLoading
  const citySetupSaving = citySetupMutation.isPending || citySetupMutation.isLoading
  const areaSetupSaving = areaSetupMutation.isPending || areaSetupMutation.isLoading
  const openOrdersQuery = useQuery({
    queryKey: ['operations-orders', 'open', selectedRange, dashboardScopeKey],
    queryFn: async () => (await listOperationsOrders({ status: 'open', ...scopedRangeParams })).data,
    enabled: needsOpenOrders,
    keepPreviousData: true,
    staleTime: 1000 * 15,
  })
  const revenueQuery = useQuery({
    queryKey: ['operations-revenue', selectedRange, dashboardScopeKey],
    queryFn: async () => (await getOperationsRevenue(scopedRangeParams)).data,
    enabled: needsRevenue,
    keepPreviousData: true,
    staleTime: 1000 * 60,
  })
  const ledgerQuery = useQuery({
    queryKey: ['operations-ledger', dashboardScopeKey],
    queryFn: async () => (await getOperationsLedger(dashboardScopeParams)).data,
    enabled: needsLedger,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const notificationQueryParams = {
    ...dashboardScopeParams,
    status: notificationFilters.status || undefined,
    category: notificationFilters.category || undefined,
    priority: notificationFilters.priority || undefined,
    event_type: notificationFilters.event_type || undefined,
    unread: notificationFilters.unread || undefined,
  }
  const operationsNotificationsQuery = useQuery({
    queryKey: ['operations-notifications', dashboardScopeKey, notificationFilters],
    queryFn: async () => (await listOperationsNotifications(notificationQueryParams)).data,
    enabled: needsOperationsNotifications,
    keepPreviousData: true,
    staleTime: 1000 * 10,
    refetchInterval: needsOperationsNotifications ? 15000 : false,
  })
  const reviewPhotoQueryParams = {
    ...dashboardScopeParams,
    status: reviewPhotoFilters.status || undefined,
    restaurant: reviewPhotoFilters.restaurant || undefined,
    customer: reviewPhotoFilters.customer || undefined,
    date_from: reviewPhotoFilters.date_from || undefined,
    date_to: reviewPhotoFilters.date_to || undefined,
  }
  const reviewPhotosQuery = useQuery({
    queryKey: ['operations-review-photos', dashboardScopeKey, reviewPhotoFilters],
    queryFn: async () => (await listOperationsReviewPhotos(reviewPhotoQueryParams)).data,
    enabled: needsReviewPhotos,
    keepPreviousData: true,
    staleTime: 1000 * 15,
  })
  const paymentProvidersQuery = useQuery({
    queryKey: ['operations-payment-providers', dashboardScopeKey],
    queryFn: async () => (await listPaymentProviderConfigs(dashboardScopeParams)).data,
    enabled: needsPaymentProviders,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const operationsOffersQuery = useQuery({
    queryKey: ['operations-offers', dashboardScopeKey],
    queryFn: async () => (await listOperationsOffers(dashboardScopeParams)).data,
    enabled: showPaymentProviders || showPromoCodes,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const operationsInsightsQuery = useQuery({
    queryKey: ['operations-intelligence', dashboardScopeKey],
    queryFn: async () => (await getOperationsInsights(dashboardScopeParams)).data,
    enabled: needsOperationsInsights,
    keepPreviousData: true,
    staleTime: 1000 * 30,
  })
  const operationsActor = operationsAccessQuery.data || {}
  const canManageOperationsUsers = Boolean(operationsActor.permissions?.includes('MANAGE_OPERATIONS_USERS'))
  const showLegacyCompatibilityWarning = Boolean(
    operationsActor.legacy_compatibility_enabled
    && operationsActor.is_global_scope
    && (operationsActor.role === 'GLOBAL_ADMIN' || operationsActor.is_superuser)
  )
  const operationsUsersQuery = useQuery({
    queryKey: ['operations-access-staff'],
    queryFn: async () => (await listOperationsAccessStaff()).data,
    enabled: canManageOperationsUsers && needsOperationsUsers,
    staleTime: 1000 * 30,
  })
  const operationsNotifications = operationsNotificationsQuery.data?.results || []
  const operationsNotificationUnreadCount = operationsNotificationsQuery.data?.unread_count || 0
  const reviewPhotos = reviewPhotosQuery.data || []
  const pendingReviewPhotos = reviewPhotos.filter(photo => photo.status === 'PENDING')

  const merchants = merchantsQuery.data || []
  const partners = partnersQuery.data || []
  const staffMembers = staffQuery.data || []
  const paymentProviderPayload = paymentProvidersQuery.data || {}
  const paymentProviderConfigs = paymentProviderPayload.results || []
  const operationsOfferPayload = operationsOffersQuery.data || {}
  const operationsOffers = operationsOfferPayload.results || []
  const setupMarkets = setupMarketsQuery.data?.results || setupMarketsQuery.data || []
  const setupCurrencies = setupCurrenciesQuery.data?.results || setupCurrenciesQuery.data || []
  const paymentProviderMarkets = setupMarkets.length ? setupMarkets : (paymentProviderPayload.markets || operationsOfferPayload.markets || [])
  const paymentProviderCapabilities = paymentProviderPayload.providers || []
  const paymentProviderMethods = paymentProviderPayload.payment_methods || []
  useEffect(() => {
    if (!citySetupForm.market && paymentProviderMarkets.length) {
      setCitySetupForm(current => ({ ...current, market: String(paymentProviderMarkets[0].id) }))
    }
  }, [citySetupForm.market, paymentProviderMarkets])
  useEffect(() => {
    if (!areaSetupForm.city && operationsCities.length) {
      setAreaSetupForm(current => ({ ...current, city: String(operationsCities[0].id) }))
    }
  }, [areaSetupForm.city, operationsCities])
  const isPendingApplicant = applicant => {
    const status = applicant.verification_status || (applicant.is_verified ? 'APPROVED' : 'PENDING')
    return !applicant.is_verified && ['PENDING', 'SUBMITTED'].includes(status)
  }
  const pendingMerchants = merchants.filter(isPendingApplicant)
  const pendingPartners = partners.filter(isPendingApplicant)
  const pendingStaff = staffMembers.filter(staff => (
    ['PENDING', 'SUBMITTED', 'MORE_INFO_REQUIRED'].includes(staff.verification_status)
  ))
  const applicantMatchesFilter = (applicant, selectedFilter) => {
    const status = applicant.verification_status || (applicant.is_verified ? 'APPROVED' : 'PENDING')
    if (selectedFilter === 'all') return true
    if (selectedFilter === 'pending') return isPendingApplicant(applicant)
    if (selectedFilter === 'verified') return applicant.is_verified || status === 'APPROVED'
    return status === selectedFilter.toUpperCase()
  }
  const visibleMerchants = useMemo(() => {
    if (activeView === 'pending-merchants') return pendingMerchants
    return merchants.filter(merchant => applicantMatchesFilter(merchant, filter))
  }, [activeView, filter, merchants, pendingMerchants])
  const visiblePartners = useMemo(() => {
    if (activeView === 'pending-partners') return pendingPartners
    return partners.filter(partner => applicantMatchesFilter(partner, partnerFilter))
  }, [activeView, partnerFilter, partners, pendingPartners])
  const merchantDocumentsQuery = useQuery({
    queryKey: ['operations-merchant-documents', visibleMerchants.map(merchant => merchant.id).join(',')],
    queryFn: async () => {
      const entries = await Promise.all(visibleMerchants.map(async merchant => ([
        merchant.id,
        (await listOperationsMerchantDocuments(merchant.id)).data,
      ])))
      return Object.fromEntries(entries)
    },
    enabled: needsMerchantDocuments && merchantsQuery.isSuccess && visibleMerchants.length > 0,
  })
  const partnerDocumentsQuery = useQuery({
    queryKey: ['operations-partner-documents', visiblePartners.map(partner => partner.id).join(',')],
    queryFn: async () => {
      const entries = await Promise.all(visiblePartners.map(async partner => ([
        partner.id,
        (await listOperationsPartnerDocuments(partner.id)).data,
      ])))
      return Object.fromEntries(entries)
    },
    enabled: needsPartnerDocuments && partnersQuery.isSuccess && visiblePartners.length > 0,
  })
  const staffDocumentsQuery = useQuery({
    queryKey: ['operations-staff-documents', staffMembers.map(staff => staff.id).join(',')],
    queryFn: async () => {
      const entries = await Promise.all(staffMembers.map(async staff => ([
        staff.id,
        (await listOperationsStaffDocuments(staff.id)).data,
      ])))
      return Object.fromEntries(entries)
    },
    enabled: needsStaffDocuments && staffQuery.isSuccess && staffMembers.length > 0,
  })
  const tickets = supportQuery.data || []
  const dispatches = dispatchQuery.data || []
  const fulfillmentRequests = fulfillmentRequestsQuery.data || []
  const partnerPayouts = payoutsQuery.data || []
  const merchantPayouts = merchantPayoutsQuery.data || []
  const customers = customersQuery.data || []
  const activeRestaurants = restaurantsQuery.data || []
  const branches = branchesQuery.data || []
  const cities = citiesQuery.data?.results || citiesQuery.data || []
  const areas = areasQuery.data?.results || areasQuery.data || []
  const operationsCities = allCitiesQuery.data?.results || allCitiesQuery.data || []
  const operationsAreas = allAreasQuery.data?.results || allAreasQuery.data || []
  const operationsUsers = operationsUsersQuery.data || []
  const countryOptions = Array.from(
    new Map(
      paymentProviderMarkets
        .filter(market => market.country_code)
        .map(market => [market.country_code, {
          code: market.country_code,
          name: market.name,
        }])
    ).values()
  )
  const dashboardScopeOptions = [
    { key: 'global:', type: 'global', value: '', label: 'Global' },
    ...paymentProviderMarkets.map(market => ({
      key: `market:${market.id}`,
      type: 'market',
      value: String(market.id),
      label: `Market: ${market.name}`,
    })),
    ...countryOptions.map(country => ({
      key: `country:${country.code}`,
      type: 'country',
      value: country.code,
      label: `Country: ${country.name || country.code}`,
    })),
    ...operationsCities.map(city => ({
      key: `city:${city.id}`,
      type: 'city',
      value: String(city.id),
      label: `City: ${city.name}`,
    })),
    ...operationsAreas.map(area => ({
      key: `area:${area.id}`,
      type: 'area',
      value: String(area.id),
      label: `Area: ${area.name}`,
    })),
  ]
  const selectedDashboardScopeKey = `${dashboardScope.type}:${dashboardScope.value || ''}`
  const selectedDashboardScopeLabel = dashboardScopeOptions.find(option => option.key === selectedDashboardScopeKey)?.label || 'Global'
  const actorScopeLabel = operationsActor.is_global_scope
    ? selectedDashboardScopeLabel
    : operationsActor.assigned_area_ids?.length
      ? `Assigned areas: ${operationsAreas.filter(area => operationsActor.assigned_area_ids.includes(area.id)).map(area => area.name).join(', ') || operationsActor.assigned_area_ids.join(', ')}`
      : operationsActor.assigned_city_ids?.length
        ? `Assigned cities: ${operationsCities.filter(city => operationsActor.assigned_city_ids.includes(city.id)).map(city => city.name).join(', ') || operationsActor.assigned_city_ids.join(', ')}`
        : operationsActor.assigned_country_codes?.length
          ? `Assigned countries: ${operationsActor.assigned_country_codes.join(', ')}`
          : operationsActor.assigned_market_ids?.length
            ? `Assigned markets: ${paymentProviderMarkets.filter(market => operationsActor.assigned_market_ids.includes(market.id)).map(market => market.name).join(', ') || operationsActor.assigned_market_ids.join(', ')}`
            : 'Assigned scope has no configured markets, cities, or areas'
  const hasConfiguredGeography = Boolean(paymentProviderMarkets.length || operationsCities.length || operationsAreas.length)
  const showGeographyFilters = Boolean(operationsActor.is_global_scope)
  const geographySetupMessage = !countryOptions.length
    ? 'No country/market is configured yet. Start with country, currency, timezone, and market setup.'
    : !operationsCities.length
      ? 'Country/market is configured, but no cities exist yet. Add cities before assigning city or area scopes.'
      : !operationsAreas.length
        ? 'Country and city records exist, but no areas are configured yet. Add areas before assigning area scopes.'
        : ''
  const selectedBranchCountry = branchFilters.country_code || dashboardScopeParams.country_code || ''
  const branchCountryHasConfiguredCities = cities.length > 0
  const branchCityHasConfiguredAreas = branchFilters.city
    ? areas.length > 0
    : true
  const branchGeographyMessage = !paymentProviderMarkets.length && !cities.length && !areas.length
    ? 'No country, market, city, or area records are configured yet. Create geography first, then branches will use those records automatically.'
    : selectedBranchCountry && !branchCountryHasConfiguredCities
      ? `No cities are configured for ${selectedBranchCountry} yet. Branches that only have text city values can still appear.`
      : branchFilters.city && !branchCityHasConfiguredAreas
        ? 'No areas are configured for the selected city yet. Branches that only have text area values can still appear.'
        : ''
  const openOrders = openOrdersQuery.data || []
  const revenue = revenueQuery.data || {}
  const ledger = ledgerQuery.data || {}
  const operationsInsights = operationsInsightsQuery.data
  const pendingTickets = tickets.filter(ticket => ['OPEN', 'IN_REVIEW'].includes(ticket.status))
  const pendingDispatches = dispatches.filter(delivery => !delivery.partner_id)
  const activeBranches = branches.filter(branch => branch.is_active)
  const openBranches = branches.filter(branch => branch.is_open)
  const branchFilterOptions = branches.map(branch => ({
    id: branch.branch_id,
    name: branch.branch_name || branch.rest_name,
  }))
  const branchMarketOptions = selectedBranchCountry
    ? paymentProviderMarkets.filter(market => market.country_code === selectedBranchCountry)
    : paymentProviderMarkets
  const branchAnalytics = {
    orders: branches.reduce((total, branch) => total + Number(branch.analytics?.orders ?? branch.order_count ?? 0), 0),
    revenue: branches.reduce((total, branch) => total + Number(branch.analytics?.revenue ?? branch.revenue_summary?.gross_sales ?? 0), 0),
    riders: branches.reduce((total, branch) => total + Number(branch.analytics?.rider_count ?? branch.rider_count ?? 0), 0),
    availableRiders: branches.reduce((total, branch) => total + Number(branch.analytics?.available_riders ?? branch.available_rider_count ?? 0), 0),
  }
  const branchRiderUtilization = branchAnalytics.riders
    ? Math.round((branchAnalytics.availableRiders / branchAnalytics.riders) * 100)
    : 0
  const topBranches = [...branches]
    .sort((left, right) => Number(right.analytics?.revenue ?? right.revenue_summary?.gross_sales ?? 0) - Number(left.analytics?.revenue ?? left.revenue_summary?.gross_sales ?? 0))
    .slice(0, 3)
  const underperformingBranches = branches
    .filter(branch => Number(branch.analytics?.orders ?? branch.order_count ?? 0) === 0 || !branch.is_active || !branch.is_open)
    .slice(0, 3)
  const visibleTickets = activeView === 'open-support' ? pendingTickets : tickets
  const visibleDispatches = activeView === 'unassigned-deliveries' ? pendingDispatches : dispatches
  const availableMerchantPayouts = merchantPayouts.filter(payout => payout.merchant_payout_status === 'AVAILABLE')
  const availablePartnerPayouts = partnerPayouts.filter(payout => payout.payout_status === 'AVAILABLE')
  const availableMerchantPayoutTotal = availableMerchantPayouts.reduce(
    (total, payout) => total + Number(payout.merchant_payout || 0),
    0
  )
  const availablePartnerPayoutTotal = availablePartnerPayouts.reduce(
    (total, payout) => total + Number(payout.partner_fee || 0),
    0
  )

  const setDashboardView = view => {
    setSearchParams(view === 'overview' ? {} : { view })
  }

  const openPendingMerchants = () => {
    setFilter('pending')
    setDashboardView('pending-merchants')
  }

  const openPendingPartners = () => {
    setPartnerFilter('pending')
    setDashboardView('pending-partners')
  }

  const openMerchantApplications = () => {
    setFilter('pending')
    setDashboardView('merchant-applications')
  }

  const openPartnerApplications = () => {
    setPartnerFilter('pending')
    setDashboardView('partner-applications')
  }

  const refreshMerchantReview = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: ['operations-summary'] }),
    queryClient.invalidateQueries({ queryKey: ['operations-merchants'] }),
    queryClient.invalidateQueries({ queryKey: ['operations-merchant-documents'] }),
  ])

  const refreshPartnerReview = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: ['operations-summary'] }),
    queryClient.invalidateQueries({ queryKey: ['operations-partners'] }),
    queryClient.invalidateQueries({ queryKey: ['operations-partner-documents'] }),
  ])

  const refreshStaffReview = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: ['operations-summary'] }),
    queryClient.invalidateQueries({ queryKey: ['operations-staff'] }),
    queryClient.invalidateQueries({ queryKey: ['operations-staff-documents'] }),
  ])

  const setVerification = async (merchant, isVerified) => {
    const reason = merchantRejectionReasons[merchant.id]?.trim() || ''
    if (!isVerified && !merchant.is_verified && !reason) {
      toast.error('Add a rejection reason before rejecting this merchant.')
      return
    }
    setUpdatingId(merchant.id)
    try {
      await updateMerchantVerification(merchant.id, { is_verified: isVerified, rejection_reason: reason })
      await refreshMerchantReview()
      toast.success(isVerified ? `${merchant.business_name || merchant.username} approved` : merchant.is_verified ? 'Merchant suspended' : 'Merchant rejected')
    } catch (error) {
      toast.error(error.response?.data?.documents?.[0] || error.response?.data?.detail || 'Could not update merchant.')
    } finally {
      setUpdatingId(null)
    }
  }

  const setPartnerVerification = async (partner, isVerified) => {
    const reason = partnerRejectionReasons[partner.id]?.trim() || ''
    if (!isVerified && !partner.is_verified && !reason) {
      toast.error('Add a rejection reason before rejecting this delivery partner.')
      return
    }
    setUpdatingId(`partner-${partner.id}`)
    try {
      await updatePartnerVerification(partner.id, { is_verified: isVerified, rejection_reason: reason })
      await refreshPartnerReview()
      toast.success(isVerified ? `${partner.partner_name || partner.username} approved` : partner.is_verified ? 'Delivery partner suspended' : 'Delivery partner rejected')
    } catch (error) {
      toast.error(error.response?.data?.documents?.[0] || error.response?.data?.detail || 'Could not update delivery partner.')
    } finally {
      setUpdatingId(null)
    }
  }

  const reviewDocument = async (document, status) => {
    const reason = documentRejectionReasons[document.id]?.trim() || ''
    if (status === 'REJECTED' && !reason) {
      toast.error('Add a rejection reason before rejecting this document.')
      return
    }
    setUpdatingId(`document-${document.id}`)
    try {
      await reviewOperationsVerificationDocument(document.id, { status, rejection_reason: reason })
      await Promise.all([refreshMerchantReview(), refreshPartnerReview()])
      toast.success(status === 'APPROVED' ? 'Document approved' : 'Document rejected')
    } catch (error) {
      toast.error(error.response?.data?.rejection_reason?.[0] || error.response?.data?.status?.[0] || 'Could not review document.')
    } finally {
      setUpdatingId(null)
    }
  }

  const reviewStaffDocument = async (document, status) => {
    const reason = documentRejectionReasons[document.id]?.trim() || ''
    if (status === 'REJECTED' && !reason) {
      toast.error('Add a rejection reason before rejecting this staff document.')
      return
    }
    setUpdatingId(`staff-document-${document.id}`)
    try {
      await reviewOperationsStaffDocument(document.id, { status, rejection_reason: reason })
      await refreshStaffReview()
      toast.success(status === 'APPROVED' ? 'Staff document approved' : 'Staff document rejected')
    } catch (error) {
      toast.error(error.response?.data?.rejection_reason?.[0] || error.response?.data?.status?.[0] || 'Could not review staff document.')
    } finally {
      setUpdatingId(null)
    }
  }

  const setStaffVerification = async (staff, action) => {
    const reason = staffDecisionReasons[staff.id]?.trim() || ''
    if (['REJECT', 'SUSPEND', 'REQUEST_MORE_INFO'].includes(action) && !reason) {
      toast.error('Add a reason or note before saving this staff verification decision.')
      return
    }
    setUpdatingId(`staff-${staff.id}-${action}`)
    try {
      await updateOperationsStaffVerification(staff.id, {
        action,
        rejection_reason: reason,
      })
      await refreshStaffReview()
      toast.success(`Staff verification ${formatFulfillmentStatus(action).toLowerCase()} saved`)
    } catch (error) {
      toast.error(
        error.response?.data?.documents?.[0]
        || error.response?.data?.rejection_reason?.[0]
        || error.response?.data?.action?.[0]
        || error.response?.data?.detail
        || 'Could not update staff verification.'
      )
    } finally {
      setUpdatingId(null)
    }
  }

  const refreshOperationsNotifications = () => queryClient.invalidateQueries({ queryKey: ['operations-notifications'] })

  const updateOperationNotification = async (notification, action) => {
    setUpdatingId(`operations-notification-${notification.id}-${action}`)
    try {
      if (action === 'read') await markOperationsNotificationRead(notification.id)
      if (action === 'archive') await archiveOperationsNotification(notification.id)
      if (action === 'dismiss') await dismissOperationsNotification(notification.id)
      await refreshOperationsNotifications()
      const actionLabel = action === 'read' ? 'marked read' : action === 'archive' ? 'archived' : 'dismissed'
      toast.success(`Notification ${actionLabel}`)
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not update notification.')
    } finally {
      setUpdatingId(null)
    }
  }

  const readAllOperationNotifications = async () => {
    setUpdatingId('operations-notifications-read-all')
    try {
      await markAllOperationsNotificationsRead()
      await refreshOperationsNotifications()
      toast.success('Operations notifications marked read')
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not mark notifications read.')
    } finally {
      setUpdatingId(null)
    }
  }

  const updateReviewPhotoModeration = async (photo, action) => {
    const reason = reviewPhotoReasons[photo.id]?.trim() || ''
    if (['REJECT', 'HIDE'].includes(action) && !reason) {
      toast.error('Add a reason before rejecting or hiding this review photo.')
      return
    }
    setUpdatingId(`review-photo-${photo.id}-${action}`)
    try {
      await moderateOperationsReviewPhoto(photo.id, { action, reason })
      await queryClient.invalidateQueries({ queryKey: ['operations-review-photos'] })
      if (action === 'APPROVE') {
        setReviewPhotoReasons(current => ({ ...current, [photo.id]: '' }))
      }
      toast.success(`Review photo ${formatFulfillmentStatus(action).toLowerCase()} saved`)
    } catch (error) {
      toast.error(
        error.response?.data?.reason?.[0]
        || error.response?.data?.action?.[0]
        || error.response?.data?.detail
        || 'Could not moderate review photo.'
      )
    } finally {
      setUpdatingId(null)
    }
  }

  const resolveTicket = async (ticket, status, issueRefund = false) => {
    const resolution = ticketNotes[ticket.id]?.trim() || ''
    if (status !== 'IN_REVIEW' && !resolution) {
      toast.error('Add a response for the customer first.')
      return
    }
    if (issueRefund && !window.confirm(`Issue a full refund of ${money(ticket.order_total)}?`)) return
    setUpdatingId(`ticket-${ticket.id}`)
    try {
      await updateSupportTicket(ticket.id, { status, resolution, issue_refund: issueRefund })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['operations-support'] }),
        queryClient.invalidateQueries({ queryKey: ['operations-summary'] }),
      ])
      toast.success(issueRefund ? 'Ticket resolved and refund issued' : 'Support ticket updated')
    } catch (error) {
      toast.error(error.response?.data?.issue_refund?.[0] || error.response?.data?.detail || 'Could not update support ticket.')
    } finally {
      setUpdatingId(null)
    }
  }

  const assignDelivery = async delivery => {
    const partnerId = Number(dispatchSelections[delivery.id])
    if (!partnerId) {
      toast.error('Choose an available delivery partner.')
      return
    }
    setUpdatingId(`dispatch-${delivery.id}`)
    try {
      await assignOperationsDelivery(delivery.id, partnerId)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['operations-dispatch'] }),
        queryClient.invalidateQueries({ queryKey: ['operations-partners'] }),
        queryClient.invalidateQueries({ queryKey: ['operations-summary'] }),
      ])
      toast.success('Delivery partner assigned')
    } catch (error) {
      toast.error(error.response?.data?.partner_id?.[0] || error.response?.data?.detail || 'Could not assign delivery.')
    } finally {
      setUpdatingId(null)
    }
  }

  const updateBranchStatus = async (branch, payload) => {
    setUpdatingId(`branch-${branch.branch_id}`)
    try {
      await updateOperationsBranchStatus(branch.branch_id, payload)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['operations-branches'] }),
        queryClient.invalidateQueries({ queryKey: ['operations-restaurants'] }),
        queryClient.invalidateQueries({ queryKey: ['operations-summary'] }),
      ])
      toast.success('Branch status updated')
    } catch (error) {
      toast.error(
        error.response?.data?.is_active?.[0]
        || error.response?.data?.is_open?.[0]
        || error.response?.data?.detail
        || 'Could not update branch status.'
      )
    } finally {
      setUpdatingId(null)
    }
  }

  const refreshFulfillmentControls = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: ['operations-fulfillment-requests'] }),
    queryClient.invalidateQueries({ queryKey: ['operations-summary'] }),
  ])

  const updateFulfillmentRequest = async (request, action) => {
    const note = fulfillmentNotes[request.id]?.trim() || ''
    const overrideStatus = fulfillmentOverrideStatuses[request.id] || request.internal_status || 'REQUESTED'
    if (action === 'ADD_NOTE' && !note) {
      toast.error('Add an operations note first.')
      return
    }
    const payload = { action }
    if (note) payload.note = note
    if (action === 'OVERRIDE_STATUS') payload.internal_status = overrideStatus
    setUpdatingId(`fulfillment-${request.id}-${action}`)
    try {
      await updateOperationsFulfillmentRequest(request.id, payload)
      await refreshFulfillmentControls()
      if (action === 'ADD_NOTE') {
        setFulfillmentNotes(current => ({ ...current, [request.id]: '' }))
      }
      toast.success(`Fulfillment ${formatFulfillmentStatus(action).toLowerCase()} saved`)
    } catch (error) {
      toast.error(
        error.response?.data?.action?.[0]
        || error.response?.data?.internal_status?.[0]
        || error.response?.data?.note?.[0]
        || error.response?.data?.detail
        || 'Could not update fulfillment request.'
      )
    } finally {
      setUpdatingId(null)
    }
  }

  const payPartner = async payout => {
    if (!window.confirm(`Mark ${money(payout.partner_fee)} paid to ${payout.partner_name}?`)) return
    setUpdatingId(`payout-${payout.id}`)
    try {
      await markPartnerPayoutPaid(payout.id)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['partner-payouts'] }),
        queryClient.invalidateQueries({ queryKey: ['operations-summary'] }),
      ])
      toast.success('Partner payout marked paid')
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not process partner payout.')
    } finally {
      setUpdatingId(null)
    }
  }

  const payMerchant = async payout => {
    if (!window.confirm(`Mark ${money(payout.merchant_payout)} paid to ${payout.merchant_name}?`)) return
    setUpdatingId(`merchant-payout-${payout.id}`)
    try {
      await markMerchantPayoutPaid(payout.id)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['merchant-payouts'] }),
        queryClient.invalidateQueries({ queryKey: ['operations-summary'] }),
      ])
      toast.success('Merchant payout marked paid')
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not process merchant payout.')
    } finally {
      setUpdatingId(null)
    }
  }

  const selectedProviderMarket = paymentProviderMarkets.find(
    market => String(market.id) === String(providerForm.market)
  )
  const selectedOfferMarket = paymentProviderMarkets.find(
    market => String(market.id) === String(offerForm.market)
  )

  const providerCapability = code => (
    paymentProviderCapabilities.find(provider => provider.code === code) || {}
  )

  const saveProviderConfig = async event => {
    event.preventDefault()
    if (!selectedProviderMarket) {
      toast.error('Choose a market first.')
      return
    }
    setUpdatingId('payment-provider-create')
    try {
      await createPaymentProviderConfig({
        ...providerForm,
        market: Number(providerForm.market),
        country_code: selectedProviderMarket.country_code,
        currency: selectedProviderMarket.currency,
        priority: Number(providerForm.priority || 1),
        config_metadata: {},
      })
      await queryClient.invalidateQueries({ queryKey: ['operations-payment-providers'] })
      setProviderForm(current => ({
        ...defaultProviderForm,
        market: current.market,
      }))
      toast.success('Payment provider config saved')
    } catch (error) {
      toast.error(
        error.response?.data?.non_field_errors?.[0]
        || error.response?.data?.detail
        || error.response?.data?.provider_code?.[0]
        || 'Could not save payment provider config.'
      )
    } finally {
      setUpdatingId(null)
    }
  }

  const patchProviderConfig = async (config, payload) => {
    setUpdatingId(`payment-provider-${config.id}`)
    try {
      await updatePaymentProviderConfig(config.id, payload)
      await queryClient.invalidateQueries({ queryKey: ['operations-payment-providers'] })
      toast.success('Payment provider config updated')
    } catch (error) {
      toast.error(error.response?.data?.detail || error.response?.data?.non_field_errors?.[0] || 'Could not update provider config.')
    } finally {
      setUpdatingId(null)
    }
  }

  const saveOffer = async event => {
    event.preventDefault()
    setUpdatingId('offer-create')
    try {
      await createOperationsOffer({
        ...offerForm,
        market: offerForm.market ? Number(offerForm.market) : null,
        code: offerForm.code.trim().toUpperCase(),
        discount_percent: Number(offerForm.discount_percent || 0),
        min_order_amount: offerForm.min_order_amount || '0.00',
        max_uses_total: offerForm.max_uses_total ? Number(offerForm.max_uses_total) : null,
        max_uses_per_customer: offerForm.max_uses_per_customer ? Number(offerForm.max_uses_per_customer) : null,
      })
      await queryClient.invalidateQueries({ queryKey: ['operations-offers'] })
      setOfferForm(current => ({
        ...defaultOfferForm,
        market: current.market,
      }))
      toast.success('Promo code saved')
    } catch (error) {
      toast.error(
        error.response?.data?.code?.[0]
        || error.response?.data?.market?.[0]
        || error.response?.data?.discount_percent?.[0]
        || error.response?.data?.detail
        || 'Could not save promo code.'
      )
    } finally {
      setUpdatingId(null)
    }
  }

  const patchOffer = async (offer, payload) => {
    setUpdatingId(`offer-${offer.id}`)
    try {
      await updateOperationsOffer(offer.id, payload)
      await queryClient.invalidateQueries({ queryKey: ['operations-offers'] })
      toast.success('Promo code updated')
    } catch (error) {
      toast.error(error.response?.data?.detail || error.response?.data?.market?.[0] || 'Could not update promo code.')
    } finally {
      setUpdatingId(null)
    }
  }

  const refreshOperationsUsers = () => queryClient.invalidateQueries({ queryKey: ['operations-access-staff'] })

  const createOperationsUser = async event => {
    event.preventDefault()
    setUpdatingId('operations-user-create')
    try {
      await createOperationsAccessStaff({
        ...operationsUserForm,
        permissions: [],
      })
      setOperationsUserForm(defaultOperationsUserForm)
      await refreshOperationsUsers()
      toast.success('Operations profile created')
    } catch (error) {
      toast.error(
        error.response?.data?.username?.[0]
        || error.response?.data?.role?.[0]
        || error.response?.data?.detail
        || error.response?.data?.non_field_errors?.[0]
        || 'Could not create operations profile.'
      )
    } finally {
      setUpdatingId(null)
    }
  }

  const patchOperationsUser = async (profile, payload) => {
    setUpdatingId(`operations-user-${profile.id}`)
    try {
      await updateOperationsAccessStaff(profile.id, payload)
      await refreshOperationsUsers()
      toast.success('Operations profile updated')
    } catch (error) {
      toast.error(error.response?.data?.detail || error.response?.data?.role?.[0] || 'Could not update operations profile.')
    } finally {
      setUpdatingId(null)
    }
  }

  const assignOperationsScope = async (profile, scopeType) => {
    const selection = operationsScopeSelections[profile.id] || {}
    const value = selection[scopeType]
    if (!value) {
      toast.error(`Choose a ${scopeType} first.`)
      return
    }
    setUpdatingId(`operations-user-${profile.id}-${scopeType}`)
    try {
      if (scopeType === 'market') await assignOperationsAccessMarket(profile.id, value)
      if (scopeType === 'city') await assignOperationsAccessCity(profile.id, value)
      if (scopeType === 'area') await assignOperationsAccessArea(profile.id, value)
      setOperationsScopeSelections(current => ({
        ...current,
        [profile.id]: { ...(current[profile.id] || {}), [scopeType]: '' },
      }))
      await refreshOperationsUsers()
      toast.success(`${formatFulfillmentStatus(scopeType)} assigned`)
    } catch (error) {
      toast.error(error.response?.data?.detail || `Could not assign ${scopeType}.`)
    } finally {
      setUpdatingId(null)
    }
  }

  const removeOperationsScope = async (profile, scopeType, objectId) => {
    setUpdatingId(`operations-user-${profile.id}-${scopeType}-${objectId}`)
    try {
      if (scopeType === 'market') await removeOperationsAccessMarket(profile.id, objectId)
      if (scopeType === 'city') await removeOperationsAccessCity(profile.id, objectId)
      if (scopeType === 'area') await removeOperationsAccessArea(profile.id, objectId)
      await refreshOperationsUsers()
      toast.success(`${formatFulfillmentStatus(scopeType)} access removed`)
    } catch (error) {
      toast.error(error.response?.data?.detail || `Could not remove ${scopeType} access.`)
    } finally {
      setUpdatingId(null)
    }
  }

  const submitCurrencySetup = event => {
    event.preventDefault()
    currencySetupMutation.mutate({
      ...currencySetupForm,
      code: currencySetupForm.code.toUpperCase(),
      minor_unit: Number(currencySetupForm.minor_unit || 0),
    })
  }

  const submitMarketSetup = event => {
    event.preventDefault()
    marketSetupMutation.mutate({
      ...marketSetupForm,
      country_code: marketSetupForm.country_code.toUpperCase(),
      default_currency: marketSetupForm.default_currency.toUpperCase(),
    })
  }

  const submitCitySetup = event => {
    event.preventDefault()
    citySetupMutation.mutate({
      ...citySetupForm,
      market: Number(citySetupForm.market),
    })
  }

  const submitAreaSetup = event => {
    event.preventDefault()
    areaSetupMutation.mutate({
      ...areaSetupForm,
      city: Number(areaSetupForm.city),
    })
  }

  if (summaryQuery.isLoading || operationsAccessQuery.isLoading) {
    return <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10 text-gray-500">Loading operations workspace...</div>
  }

  if (summaryQuery.isError || operationsAccessQuery.isError) {
    return <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10 text-red-600">The operations workspace could not be loaded.</div>
  }

  const summary = summaryQuery.data
  const tiles = [
    { label: t('operations.tiles.pendingActions'), staticTotal: true, value: summary.pending_merchants + summary.pending_partners + summary.open_support_tickets + summary.unassigned_deliveries, icon: Clock3, tone: 'text-amber-700 bg-amber-50', view: 'pending-merchants' },
    { label: t('operations.tiles.activeRestaurants'), staticTotal: true, value: summary.active_restaurants, icon: Store, tone: 'text-emerald-700 bg-emerald-50', view: 'restaurants' },
    { label: t('operations.tiles.openOrders'), value: summary.open_orders, icon: PackageCheck, tone: 'text-blue-700 bg-blue-50', view: 'orders' },
    { label: t('operations.tiles.platformRevenue'), value: money(summary.platform_revenue), icon: CircleDollarSign, tone: 'text-brand-700 bg-brand-50', view: 'revenue' },
  ]
  const secondaryTiles = [
    { label: t('operations.tiles.customers'), value: summary.customers, icon: Users, view: 'customers' },
    { label: t('operations.tiles.deliveryPartners'), value: summary.partners, icon: Bike, view: 'partners' },
    { label: t('operations.tiles.merchants'), value: summary.merchants, icon: Store, view: 'merchants' },
    { label: t('operations.tiles.verificationQueue'), value: summary.pending_merchants + summary.pending_partners, icon: ShieldCheck, view: 'verification' },
  ]
  const merchantFilterLocked = activeView === 'pending-merchants'
  const partnerFilterLocked = activeView === 'pending-partners'
  const pendingActionViews = [
    { view: 'pending-merchants', label: t('operations.sections.pendingMerchants'), count: pendingMerchants.length },
    { view: 'pending-partners', label: t('operations.sections.pendingPartners'), count: pendingPartners.length },
    { view: 'open-support', label: t('operations.sections.openSupport'), count: pendingTickets.length },
    { view: 'unassigned-deliveries', label: t('operations.sections.unassignedDeliveries'), count: pendingDispatches.length },
  ]
  const isPendingActionView = pendingActionViews.some(item => item.view === activeView)
  const operationsSections = [
    { view: 'merchant-settlements', label: t('operations.sections.merchantSettlements'), count: merchantPayouts.length, detail: t('operations.details.availableMarkPaid', { count: availableMerchantPayouts.length }), icon: Banknote, onClick: () => setDashboardView('merchant-settlements') },
    { view: 'partner-payouts', label: t('operations.sections.partnerPayouts'), count: partnerPayouts.length, detail: t('operations.details.availableMarkPaid', { count: availablePartnerPayouts.length }), icon: Banknote, onClick: () => setDashboardView('partner-payouts') },
    { view: 'dispatch', label: t('operations.sections.liveDispatch'), count: dispatches.length, detail: t('operations.details.unassignedDeliveries', { count: pendingDispatches.length }), icon: Route, onClick: () => setDashboardView('dispatch') },
    { view: 'support', label: t('operations.sections.customerSupport'), count: tickets.length, detail: t('operations.details.openTickets', { count: pendingTickets.length }), icon: Headphones, onClick: () => setDashboardView('support') },
    { view: 'fulfillment-requests', label: t('operations.sections.fulfillmentRequests'), count: fulfillmentRequests.length, detail: t('operations.details.fulfillment'), icon: FileText, onClick: () => setDashboardView('fulfillment-requests') },
    { view: 'branches', label: t('dashboard.branches'), count: branches.length, detail: t('operations.details.branches', { open: openBranches.length, active: activeBranches.length }), icon: Store, onClick: () => setDashboardView('branches') },
    { view: 'ledger', label: t('dashboard.ledger'), count: ledger?.platform_summary?.ledger_transaction_count || 0, detail: t('operations.details.ledger'), icon: CircleDollarSign, onClick: () => setDashboardView('ledger') },
    { view: 'payment-providers', label: t('dashboard.paymentProviders'), count: paymentProviderConfigs.length, detail: t('operations.details.paymentProviders'), icon: ShieldCheck, onClick: () => setDashboardView('payment-providers') },
    { view: 'promo-codes', label: 'Promo codes', count: operationsOffers.length, detail: 'Create and manage checkout promo codes.', icon: BadgePercent, onClick: () => setDashboardView('promo-codes') },
    { view: 'notifications', label: t('dashboard.notifications'), count: operationsNotificationUnreadCount, detail: t('operations.details.notifications', { count: operationsNotifications.length }), icon: Bell, onClick: () => setDashboardView('notifications') },
    { view: 'operations-users', label: t('dashboard.operationsUsers'), count: canManageOperationsUsers ? operationsUsers.length : 0, detail: canManageOperationsUsers ? t('operations.details.operationsUsers') : t('operations.details.operationsUsersDenied'), icon: Users, onClick: () => setDashboardView('operations-users') },
    { view: 'staff-verification', label: t('dashboard.staffVerification'), count: staffMembers.length, detail: t('operations.details.staffVerification', { count: pendingStaff.length }), icon: Users, onClick: () => setDashboardView('staff-verification') },
    { view: 'review-photo-moderation', label: t('dashboard.reviewPhotos'), count: pendingReviewPhotos.length, detail: t('operations.details.reviewPhotos', { count: reviewPhotos.length }), icon: ImagePlus, onClick: () => setDashboardView('review-photo-moderation') },
    { view: 'merchant-applications', label: t('operations.sections.merchantApplications'), count: merchants.length, detail: t('operations.details.pendingReview', { count: pendingMerchants.length }), icon: Store, onClick: openMerchantApplications },
    { view: 'partner-applications', label: t('operations.sections.partnerApplications'), count: partners.length, detail: t('operations.details.pendingReview', { count: pendingPartners.length }), icon: Bike, onClick: openPartnerApplications },
    { view: 'marketplace-intelligence', label: t('operations.sections.marketplaceIntelligence'), count: operationsInsights?.marketplace_recommendations?.length || 0, detail: t('operations.details.marketplaceIntelligence'), icon: Sparkles, onClick: () => setDashboardView('marketplace-intelligence') },
  ]

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-brand-600 font-medium text-sm mb-2">
            <ShieldCheck size={18} /> T-Food operations
          </div>
          <h1 className="text-2xl font-bold text-gray-950">Marketplace control center</h1>
          <p className="text-gray-500 mt-1">Use this workspace for everyday T-Food operations, reviews, support, dispatch, payouts, and marketplace management.</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
          {activeView !== 'overview' && (
            <button type="button" onClick={() => setDashboardView('overview')} className="btn-secondary inline-flex items-center justify-center text-sm">
              Back to overview
            </button>
          )}
        </div>
      </div>

      {showLegacyCompatibilityWarning && (
        <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="font-semibold">Development Compatibility Mode</p>
          <p className="mt-1">Legacy Django staff compatibility is enabled.</p>
          <ul className="mt-2 list-disc pl-5 space-y-1">
            <li>Migrate every operations user to an OperationsStaffProfile before production.</li>
            <li>Disable legacy compatibility before production.</li>
          </ul>
        </section>
      )}

      <section className="bg-white border border-gray-200 rounded-lg p-4" aria-label="Marketplace time range filter">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-gray-950">Marketplace time range</h2>
            <p className="text-sm text-gray-500 mt-1">
              Filters revenue, orders, customers, merchants, partners, verification, support, settlements, and payouts. Current-state cards stay marked as Current Total.
            </p>
            <p className="text-sm font-medium text-gray-700 mt-2">
              Viewing: <span className="text-brand-700">{actorScopeLabel}</span>
            </p>
            {geographySetupMessage && (
              <p className="text-sm text-amber-700 mt-2">
                {geographySetupMessage} T-Food is running safely in Minimum Configuration Mode.
              </p>
            )}
            <p className="text-xs text-gray-500 mt-2">
              Setup order: country → currency → timezone → market → city → area → payment providers → merchants/branches.
            </p>
          </div>
          <div className="grid sm:grid-cols-2 gap-3 lg:min-w-[460px]">
            {operationsActor.is_global_scope && (
              <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                Scope
                <select
                  value={selectedDashboardScopeKey}
                  onChange={event => {
                    const [type, value = ''] = event.target.value.split(':')
                    setDashboardScope({ type, value })
                  }}
                  className="input-field py-2 bg-white"
                  aria-label="Operations dashboard scope"
                >
                  {dashboardScopeOptions.map(option => (
                    <option key={option.key} value={option.key}>{option.label}</option>
                  ))}
                </select>
              </label>
            )}
            <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
              Time range
              <select
                value={selectedRange}
                onChange={event => setSelectedRange(event.target.value)}
                className="input-field py-2 bg-white"
                aria-label="Marketplace time range"
              >
                {rangeOptions.map(option => (
                  <option key={option.value} value={option.value}>{t(option.labelKey)}</option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </section>

      {geographySetupMessage && (
        <section className="bg-white border border-gray-200 rounded-lg p-5" aria-label="First marketplace setup">
          <button
            type="button"
            onClick={() => setMarketplaceSetupOpen(open => !open)}
            className="w-full text-left"
            aria-expanded={marketplaceSetupOpen}
          >
            <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-700">
                    <Store size={20} />
                  </span>
                  <div>
                    <h2 className="text-lg font-semibold text-gray-950">First marketplace setup</h2>
                    <p className="text-sm text-gray-500 mt-1">
                      Create country, currency, timezone, market, city, and area records here. Start with currency, then market, then city, then area.
                    </p>
                  </div>
                </div>
                <p className="mt-3 max-w-3xl rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  These records power branch filters, operations scopes, local pricing, operating hours, and payment provider setup.
                </p>
              </div>
              <span className="inline-flex w-fit items-center justify-center rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700">
                {marketplaceSetupOpen ? 'Hide setup steps' : 'Open setup steps'}
              </span>
            </div>
          </button>
          <div className="mt-4 flex flex-wrap gap-2 text-xs text-gray-500">
            {['1. Currency', '2. Country / Market', '3. City', '4. Area'].map(step => (
              <span key={step} className="rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1">{step}</span>
            ))}
          </div>
          {marketplaceSetupOpen && (
          <div className="grid xl:grid-cols-4 gap-4 mt-4 border-t border-gray-200 pt-4">
            <form onSubmit={submitCurrencySetup} className="border border-gray-200 rounded-lg p-4 space-y-3">
              <h3 className="font-semibold text-gray-950">1. Currency</h3>
              <input className="input-field" placeholder="Code, e.g. GNF" value={currencySetupForm.code} onChange={event => setCurrencySetupForm(current => ({ ...current, code: event.target.value }))} />
              <input className="input-field" placeholder="Name, e.g. Guinean Franc" value={currencySetupForm.name} onChange={event => setCurrencySetupForm(current => ({ ...current, name: event.target.value }))} />
              <input className="input-field" placeholder="Symbol, e.g. GNF" value={currencySetupForm.symbol} onChange={event => setCurrencySetupForm(current => ({ ...current, symbol: event.target.value }))} />
              <div className="grid grid-cols-2 gap-2">
                <input className="input-field" placeholder="Numeric code" value={currencySetupForm.numeric_code} onChange={event => setCurrencySetupForm(current => ({ ...current, numeric_code: event.target.value }))} />
                <input className="input-field" type="number" min="0" max="6" placeholder="Minor unit" value={currencySetupForm.minor_unit} onChange={event => setCurrencySetupForm(current => ({ ...current, minor_unit: event.target.value }))} />
              </div>
              <button type="submit" disabled={currencySetupSaving} className="btn-primary w-full">{currencySetupSaving ? 'Saving...' : 'Save currency'}</button>
            </form>

            <form onSubmit={submitMarketSetup} className="border border-gray-200 rounded-lg p-4 space-y-3">
              <h3 className="font-semibold text-gray-950">2. Country / Market</h3>
              <input className="input-field" placeholder="Country/market name" value={marketSetupForm.name} onChange={event => setMarketSetupForm(current => ({ ...current, name: event.target.value }))} />
              <input className="input-field" placeholder="Slug" value={marketSetupForm.slug} onChange={event => setMarketSetupForm(current => ({ ...current, slug: event.target.value }))} />
              <div className="grid grid-cols-2 gap-2">
                <input className="input-field" placeholder="Country code" value={marketSetupForm.country_code} onChange={event => setMarketSetupForm(current => ({ ...current, country_code: event.target.value }))} />
                <input className="input-field" placeholder="Phone code" value={marketSetupForm.phone_country_code} onChange={event => setMarketSetupForm(current => ({ ...current, phone_country_code: event.target.value }))} />
              </div>
              <select className="input-field" value={marketSetupForm.default_currency} onChange={event => setMarketSetupForm(current => ({ ...current, default_currency: event.target.value }))}>
                <option value={marketSetupForm.default_currency}>{marketSetupForm.default_currency}</option>
                {setupCurrencies.map(currency => (
                  <option key={currency.id || currency.code} value={currency.code}>{currency.code} - {currency.name}</option>
                ))}
              </select>
              <input className="input-field" placeholder="Timezone" value={marketSetupForm.timezone} onChange={event => setMarketSetupForm(current => ({ ...current, timezone: event.target.value }))} />
              <button type="submit" disabled={marketSetupSaving} className="btn-primary w-full">{marketSetupSaving ? 'Saving...' : 'Save market'}</button>
            </form>

            <form onSubmit={submitCitySetup} className="border border-gray-200 rounded-lg p-4 space-y-3">
              <h3 className="font-semibold text-gray-950">3. City</h3>
              <select className="input-field" required value={citySetupForm.market} onChange={event => setCitySetupForm(current => ({ ...current, market: event.target.value }))}>
                <option value="">{paymentProviderMarkets.length ? 'Choose market' : 'Create market first'}</option>
                {paymentProviderMarkets.map(market => (
                  <option key={market.id} value={market.id}>{market.name} ({market.country_code})</option>
                ))}
              </select>
              <input className="input-field" placeholder="City name" value={citySetupForm.name} onChange={event => setCitySetupForm(current => ({ ...current, name: event.target.value }))} />
              <input className="input-field" placeholder="City slug" value={citySetupForm.slug} onChange={event => setCitySetupForm(current => ({ ...current, slug: event.target.value }))} />
              <button type="submit" disabled={citySetupSaving || !citySetupForm.market} className="btn-primary w-full">{citySetupSaving ? 'Saving...' : 'Save city'}</button>
            </form>

            <form onSubmit={submitAreaSetup} className="border border-gray-200 rounded-lg p-4 space-y-3">
              <h3 className="font-semibold text-gray-950">4. Area</h3>
              <select className="input-field" required value={areaSetupForm.city} onChange={event => setAreaSetupForm(current => ({ ...current, city: event.target.value }))}>
                <option value="">{operationsCities.length ? 'Choose city' : 'Create city first'}</option>
                {operationsCities.map(city => (
                  <option key={city.id} value={city.id}>{city.name} ({city.country_code})</option>
                ))}
              </select>
              <input className="input-field" placeholder="Area name" value={areaSetupForm.name} onChange={event => setAreaSetupForm(current => ({ ...current, name: event.target.value }))} />
              <input className="input-field" placeholder="Area slug" value={areaSetupForm.slug} onChange={event => setAreaSetupForm(current => ({ ...current, slug: event.target.value }))} />
              <input className="input-field" placeholder="Service radius km" value={areaSetupForm.service_radius_km} onChange={event => setAreaSetupForm(current => ({ ...current, service_radius_km: event.target.value }))} />
              <button type="submit" disabled={areaSetupSaving || !areaSetupForm.city} className="btn-primary w-full">{areaSetupSaving ? 'Saving...' : 'Save area'}</button>
            </form>
          </div>
          )}
        </section>
      )}

      <section className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4" aria-label="Marketplace summary">
        {tiles.map(({ label, value, icon: Icon, tone, view, staticTotal }) => (
          <button
            key={label}
            type="button"
            onClick={() => setDashboardView(view)}
            className={`bg-white border rounded-lg p-5 text-left transition-colors hover:border-brand-300 hover:bg-brand-50/30 ${activeView === view ? 'border-brand-400 ring-2 ring-brand-100' : 'border-gray-200'}`}
          >
            <div className={`h-9 w-9 rounded-lg flex items-center justify-center ${tone}`}><Icon size={19} /></div>
            <p className="text-2xl font-bold text-gray-950 mt-4">{value}</p>
            <p className="text-sm text-gray-500 mt-1">{label}</p>
            <p className="text-xs text-gray-400 mt-2">{staticTotal ? t('operations.currentTotal') : t('operations.filteredBy', { range: selectedRangeLabel })}</p>
          </button>
        ))}
      </section>

      <section className="grid sm:grid-cols-4 gap-4 border-y border-gray-200 py-5 text-sm">
        {secondaryTiles.map(({ label, value, icon: Icon, view }) => (
          <button
            key={label}
            type="button"
            onClick={() => setDashboardView(view)}
            className={`flex items-center gap-3 rounded-lg px-3 py-2 text-left hover:bg-gray-50 ${activeView === view ? 'bg-brand-50 text-brand-800' : 'text-gray-700'}`}
          >
            <Icon className={activeView === view ? 'text-brand-600' : 'text-gray-400'} size={20} />
            <span><strong>{value}</strong> {label.toLowerCase()} <span className="text-xs text-gray-400">({t('operations.filteredBy', { range: selectedRangeLabel })})</span></span>
          </button>
        ))}
      </section>

      {activeView === 'overview' && (
        <Suspense fallback={<PanelLoading />}>
          <OperationsOverviewPanel
            operationsSections={operationsSections}
            selectedRangeLabel={selectedRangeLabel}
          />
        </Suspense>
      )}

      {isPendingActionView && (
        <Suspense fallback={<PanelLoading />}>
          <PendingActionQueuesPanel
            activeView={activeView}
            pendingActionViews={pendingActionViews}
            setDashboardView={setDashboardView}
          />
        </Suspense>
      )}

      {showFocusedOverview && (
        <Suspense fallback={<PanelLoading />}>
          <FocusedOverviewPanel
            activeView={activeView}
            activeRestaurants={activeRestaurants}
            openOrders={openOrders}
            revenue={revenue}
            availableMerchantPayouts={availableMerchantPayouts}
            availablePartnerPayouts={availablePartnerPayouts}
            customers={customers}
            merchants={merchants}
            partners={partners}
            pendingMerchants={pendingMerchants}
            pendingPartners={pendingPartners}
            pendingStaff={pendingStaff}
            openPendingMerchants={openPendingMerchants}
            openPendingPartners={openPendingPartners}
            setDashboardView={setDashboardView}
            money={money}
            formatDateTime={formatDateTime}
          />
        </Suspense>
      )}

      {showMarketplaceIntelligence && (
        <Suspense fallback={<PanelLoading />}>
          <OperationsIntelligencePanel
            operationsInsights={operationsInsights}
            operationsInsightsQuery={operationsInsightsQuery}
          />
        </Suspense>
      )}
      {showLedger && (
        <Suspense fallback={<PanelLoading />}>
          <OperationsLedgerPanel
            ledger={ledger}
            ledgerQuery={ledgerQuery}
            formatDateTime={formatDateTime}
          />
        </Suspense>
      )}

      {(showPaymentProviders || showPromoCodes) && (
        <section className="bg-white border border-gray-200 rounded-lg p-5">
          {showPaymentProviders && (
            <>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
            <div>
              <h2 className="text-lg font-semibold text-gray-950 flex items-center gap-2">
                <ShieldCheck size={19} className="text-brand-600" /> Payment Providers
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                Configure provider routing by market, country, currency, and payment method. Raw credentials are not stored here.
              </p>
            </div>
            <button
              type="button"
              onClick={() => paymentProvidersQuery.refetch()}
              disabled={paymentProvidersQuery.isFetching}
              className="btn-secondary text-sm"
            >
              {paymentProvidersQuery.isFetching ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>

          <form onSubmit={saveProviderConfig} className="grid lg:grid-cols-6 gap-3 rounded-lg border border-gray-200 bg-gray-50 p-4">
            <label className="text-sm">
              <span className="block text-xs font-medium text-gray-500 mb-1">Market</span>
              <select
                value={providerForm.market}
                onChange={event => setProviderForm(current => ({ ...current, market: event.target.value }))}
                className="input w-full"
                required
              >
                <option value="">Choose market</option>
                {paymentProviderMarkets.map(market => (
                  <option key={market.id} value={market.id}>{market.name} ({market.country_code}/{market.currency})</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="block text-xs font-medium text-gray-500 mb-1">Provider</span>
              <select
                value={providerForm.provider_code}
                onChange={event => setProviderForm(current => ({ ...current, provider_code: event.target.value }))}
                className="input w-full"
              >
                {paymentProviderCapabilities.map(provider => (
                  <option key={provider.code} value={provider.code}>{provider.display_name}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="block text-xs font-medium text-gray-500 mb-1">Method</span>
              <select
                value={providerForm.payment_method}
                onChange={event => setProviderForm(current => ({ ...current, payment_method: event.target.value }))}
                className="input w-full"
              >
                {paymentProviderMethods.map(method => (
                  <option key={method} value={method}>{method.replaceAll('_', ' ')}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="block text-xs font-medium text-gray-500 mb-1">Priority</span>
              <input
                type="number"
                min="1"
                value={providerForm.priority}
                onChange={event => setProviderForm(current => ({ ...current, priority: event.target.value }))}
                className="input w-full"
              />
            </label>
            <div className="lg:col-span-2 grid sm:grid-cols-3 gap-2">
              {[
                ['is_active', 'Active'],
                ['is_preferred', 'Preferred'],
                ['credentials_present', 'Credentials present'],
              ].map(([field, label]) => (
                <label key={field} className="flex items-center gap-2 rounded-md border border-gray-200 bg-white px-3 py-2 text-sm">
                  <input
                    type="checkbox"
                    checked={Boolean(providerForm[field])}
                    onChange={event => setProviderForm(current => ({ ...current, [field]: event.target.checked }))}
                  />
                  {label}
                </label>
              ))}
            </div>
            <div className="lg:col-span-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <p className="text-xs text-gray-500">
                Selected market sets country and currency automatically. Secrets must live in environment variables or a secrets manager later.
              </p>
              <button
                type="submit"
                disabled={updatingId === 'payment-provider-create'}
                className="btn-primary text-sm"
              >
                {updatingId === 'payment-provider-create' ? 'Saving...' : 'Save provider config'}
              </button>
            </div>
          </form>

          <div className="mt-5 rounded-lg border border-blue-200 bg-blue-50 p-4">
            <p className="text-sm font-semibold text-blue-950">Guinea launch example</p>
            <p className="text-sm text-blue-800 mt-1">
              Country GN, currency GNF, method MOBILE MONEY: Orange Money active and preferred, Wave active priority 2, MTN Mobile Money active priority 3.
            </p>
          </div>
            </>
          )}

          <div className="mt-6 rounded-lg border border-gray-200 bg-gray-50 p-4">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
              <div>
                <h3 className="font-semibold text-gray-950 flex items-center gap-2">
                  <BadgePercent size={18} className="text-brand-600" /> Promo codes
                </h3>
                <p className="text-sm text-gray-500 mt-1">
                  Create checkout promo codes such as TFOOD10. Market-specific codes only apply to restaurants in that market.
                </p>
              </div>
              <button
                type="button"
                onClick={() => operationsOffersQuery.refetch()}
                disabled={operationsOffersQuery.isFetching}
                className="btn-secondary text-sm"
              >
                {operationsOffersQuery.isFetching ? 'Refreshing...' : 'Refresh promos'}
              </button>
            </div>

            <form onSubmit={saveOffer} className="mt-4 grid lg:grid-cols-7 gap-3">
              <label className="text-sm lg:col-span-2">
                <span className="block text-xs font-medium text-gray-500 mb-1">Market</span>
                <select
                  value={offerForm.market}
                  onChange={event => setOfferForm(current => ({ ...current, market: event.target.value }))}
                  className="input w-full"
                >
                  <option value="">Global promo</option>
                  {paymentProviderMarkets.map(market => (
                    <option key={market.id} value={market.id}>{market.name} ({market.country_code}/{market.currency})</option>
                  ))}
                </select>
              </label>
              <label className="text-sm">
                <span className="block text-xs font-medium text-gray-500 mb-1">Code</span>
                <input
                  value={offerForm.code}
                  onChange={event => setOfferForm(current => ({ ...current, code: event.target.value.toUpperCase() }))}
                  className="input w-full"
                  placeholder="TFOOD10"
                  required
                />
              </label>
              <label className="text-sm">
                <span className="block text-xs font-medium text-gray-500 mb-1">Discount %</span>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={offerForm.discount_percent}
                  onChange={event => setOfferForm(current => ({ ...current, discount_percent: event.target.value }))}
                  className="input w-full"
                  required
                />
              </label>
              <label className="text-sm">
                <span className="block text-xs font-medium text-gray-500 mb-1">Min order {selectedOfferMarket?.currency ? `(${selectedOfferMarket.currency})` : ''}</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={offerForm.min_order_amount}
                  onChange={event => setOfferForm(current => ({ ...current, min_order_amount: event.target.value }))}
                  className="input w-full"
                />
              </label>
              <label className="text-sm">
                <span className="block text-xs font-medium text-gray-500 mb-1">Uses/customer</span>
                <input
                  type="number"
                  min="1"
                  value={offerForm.max_uses_per_customer}
                  onChange={event => setOfferForm(current => ({ ...current, max_uses_per_customer: event.target.value }))}
                  className="input w-full"
                />
              </label>
              <label className="text-sm">
                <span className="block text-xs font-medium text-gray-500 mb-1">Total uses</span>
                <input
                  type="number"
                  min="1"
                  value={offerForm.max_uses_total}
                  onChange={event => setOfferForm(current => ({ ...current, max_uses_total: event.target.value }))}
                  className="input w-full"
                  placeholder="No limit"
                />
              </label>
              <div className="lg:col-span-7 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="flex flex-wrap gap-2">
                  <label className="flex items-center gap-2 rounded-md border border-gray-200 bg-white px-3 py-2 text-sm">
                    <input
                      type="checkbox"
                      checked={offerForm.is_active}
                      onChange={event => setOfferForm(current => ({ ...current, is_active: event.target.checked }))}
                    />
                    Active
                  </label>
                  <label className="flex items-center gap-2 rounded-md border border-gray-200 bg-white px-3 py-2 text-sm">
                    <input
                      type="checkbox"
                      checked={offerForm.first_order_only}
                      onChange={event => setOfferForm(current => ({ ...current, first_order_only: event.target.checked }))}
                    />
                    First order only
                  </label>
                </div>
                <button type="submit" disabled={updatingId === 'offer-create'} className="btn-primary text-sm">
                  {updatingId === 'offer-create' ? 'Saving...' : 'Save promo code'}
                </button>
              </div>
            </form>

            <div className="mt-4 divide-y divide-gray-200 border-y border-gray-200 bg-white">
              {operationsOffers.length ? operationsOffers.map(offer => (
                <div key={offer.id} className="py-3 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-gray-950">{offer.code}</p>
                      <span className="rounded-full bg-brand-50 px-2 py-1 text-xs text-brand-700">{offer.discount_percent}% off</span>
                      <span className={`rounded-full px-2 py-1 text-xs ${offer.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                        {offer.is_active ? 'Active' : 'Inactive'}
                      </span>
                      {offer.first_order_only && <span className="rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700">First order</span>}
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      {offer.market_name || 'Global promo'} {offer.market_country_code ? `- ${offer.market_country_code}/${offer.market_currency}` : ''} - minimum {money(offer.min_order_amount, offer.market_currency || selectedOfferMarket?.currency || 'GNF')}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      Uses/customer: {offer.max_uses_per_customer || 'No limit'} - Total uses: {offer.max_uses_total || 'No limit'}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => patchOffer(offer, { is_active: !offer.is_active })}
                    disabled={updatingId === `offer-${offer.id}`}
                    className="btn-secondary text-sm"
                  >
                    {offer.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                </div>
              )) : (
                <div className="py-8 text-center text-gray-500">
                  No promo codes yet. Create TFOOD10 above, then customers can apply it at checkout.
                </div>
              )}
            </div>
          </div>

          {showPaymentProviders && (
          <div className="mt-6 divide-y divide-gray-200 border-y border-gray-200">
            {paymentProviderConfigs.length ? paymentProviderConfigs.map(config => {
              const capability = providerCapability(config.provider_code)
              return (
                <div key={config.id} className="py-4">
                  <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-4">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold text-gray-950">{config.provider_display_name}</p>
                        <span className="rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-600">{config.payment_method.replaceAll('_', ' ')}</span>
                        <span className={`rounded-full px-2 py-1 text-xs ${config.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                          {config.is_active ? 'Active' : 'Inactive'}
                        </span>
                        {config.is_preferred && <span className="rounded-full bg-brand-50 px-2 py-1 text-xs text-brand-700">Preferred</span>}
                      </div>
                      <p className="text-sm text-gray-500 mt-1">
                        {config.market_name} - {config.country_code}/{config.currency} - priority {config.priority}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        Supports: {(capability.supported_countries || []).join(', ') || 'No countries'} - {(capability.supported_currencies || []).join(', ') || 'No currencies'} - {(capability.supported_payment_methods || []).join(', ') || 'No methods'}
                      </p>
                      <p className={`text-xs mt-1 ${config.credentials_present ? 'text-emerald-700' : 'text-amber-700'}`}>
                        Credentials: {config.credentials_present ? 'present flag set' : 'not configured for live payments'}
                      </p>
                    </div>
                    <div className="grid sm:grid-cols-4 gap-2">
                      <button
                        type="button"
                        onClick={() => patchProviderConfig(config, { is_active: !config.is_active })}
                        disabled={updatingId === `payment-provider-${config.id}`}
                        className="btn-secondary text-sm"
                      >
                        {config.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                      <button
                        type="button"
                        onClick={() => patchProviderConfig(config, { is_preferred: !config.is_preferred })}
                        disabled={updatingId === `payment-provider-${config.id}`}
                        className="btn-secondary text-sm"
                      >
                        {config.is_preferred ? 'Unset preferred' : 'Set preferred'}
                      </button>
                      <button
                        type="button"
                        onClick={() => patchProviderConfig(config, { credentials_present: !config.credentials_present })}
                        disabled={updatingId === `payment-provider-${config.id}`}
                        className="btn-secondary text-sm"
                      >
                        {config.credentials_present ? 'Unset credentials' : 'Mark credentials'}
                      </button>
                      <button
                        type="button"
                        onClick={() => patchProviderConfig(config, { priority: Number(config.priority || 1) + 1 })}
                        disabled={updatingId === `payment-provider-${config.id}`}
                        className="btn-secondary text-sm"
                      >
                        Lower priority
                      </button>
                    </div>
                  </div>
                </div>
              )
            }) : (
              <div className="py-12 text-center text-gray-500">
                No provider configs yet. Defaults still keep COD active and Razorpay active for India.
              </div>
            )}
          </div>
          )}
        </section>
      )}

      {showOperationsNotifications && (
        <section className="bg-white border border-gray-200 rounded-lg p-5">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
            <div>
              <h2 className="text-lg font-semibold text-gray-950 flex items-center gap-2">
                <Bell size={19} className="text-brand-600" /> Notifications
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                Scoped operations inbox for alerts, verification, support, dispatch, payment, and system events.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={readAllOperationNotifications}
                disabled={updatingId === 'operations-notifications-read-all' || !operationsNotificationUnreadCount}
                className="btn-secondary text-sm"
              >
                Mark all read
              </button>
              <button
                type="button"
                onClick={() => operationsNotificationsQuery.refetch()}
                disabled={operationsNotificationsQuery.isFetching}
                className="btn-secondary text-sm"
              >
                {operationsNotificationsQuery.isFetching ? 'Refreshing...' : 'Refresh'}
              </button>
            </div>
          </div>

          <div className="grid sm:grid-cols-3 gap-3 mb-5">
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Unread</p>
              <p className="text-2xl font-bold text-brand-700 mt-1">{operationsNotificationUnreadCount}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Visible in scope</p>
              <p className="text-2xl font-bold text-gray-950 mt-1">{operationsNotifications.length}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Viewing</p>
              <p className="text-lg font-semibold text-gray-950 mt-1">{actorScopeLabel}</p>
            </div>
          </div>

          <div className="grid md:grid-cols-5 gap-3 rounded-lg border border-gray-200 bg-gray-50 p-4 mb-5">
            <label className="text-sm">
              <span className="block text-xs font-medium text-gray-500 mb-1">Status</span>
              <select
                value={notificationFilters.status}
                onChange={event => setNotificationFilters(current => ({ ...current, status: event.target.value }))}
                className="input-field py-2 bg-white"
              >
                <option value="">Active</option>
                {['UNREAD', 'READ', 'ARCHIVED', 'DISMISSED'].map(option => (
                  <option key={option} value={option}>{formatFulfillmentStatus(option)}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="block text-xs font-medium text-gray-500 mb-1">Category</span>
              <select
                value={notificationFilters.category}
                onChange={event => setNotificationFilters(current => ({ ...current, category: event.target.value }))}
                className="input-field py-2 bg-white"
              >
                <option value="">All categories</option>
                {['ORDER', 'PAYMENT', 'DELIVERY', 'MERCHANT', 'STAFF', 'RIDER', 'SUPPORT', 'VERIFICATION', 'DISPATCH', 'INTELLIGENCE', 'SYSTEM'].map(option => (
                  <option key={option} value={option}>{formatFulfillmentStatus(option)}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="block text-xs font-medium text-gray-500 mb-1">Priority</span>
              <select
                value={notificationFilters.priority}
                onChange={event => setNotificationFilters(current => ({ ...current, priority: event.target.value }))}
                className="input-field py-2 bg-white"
              >
                <option value="">All priorities</option>
                {['LOW', 'NORMAL', 'HIGH', 'CRITICAL'].map(option => (
                  <option key={option} value={option}>{formatFulfillmentStatus(option)}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="block text-xs font-medium text-gray-500 mb-1">Unread</span>
              <select
                value={notificationFilters.unread}
                onChange={event => setNotificationFilters(current => ({ ...current, unread: event.target.value }))}
                className="input-field py-2 bg-white"
              >
                <option value="">Any</option>
                <option value="true">Unread only</option>
                <option value="false">Read only</option>
              </select>
            </label>
            <label className="text-sm">
              <span className="block text-xs font-medium text-gray-500 mb-1">Event type</span>
              <input
                value={notificationFilters.event_type}
                onChange={event => setNotificationFilters(current => ({ ...current, event_type: event.target.value }))}
                className="input-field py-2 bg-white"
                placeholder="tfood.staff.verified"
              />
            </label>
          </div>

          {operationsNotificationsQuery.isError && (
            <p className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              Operations notifications could not be loaded for this scope.
            </p>
          )}

          {!operationsNotifications.length && !operationsNotificationsQuery.isLoading ? (
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-8 text-center">
              <Bell size={24} className="mx-auto text-gray-400" />
              <p className="mt-3 font-semibold text-gray-950">No operations notifications yet.</p>
              <p className="mt-1 text-sm text-gray-500">
                In-app and realtime notifications are active. External email, SMS, WhatsApp, push, and Telegram providers remain inactive until configured later.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200 border-y border-gray-200">
              {operationsNotifications.map(notification => {
                const isUnread = notification.status === 'UNREAD' || !notification.is_read
                return (
                  <article key={notification.id} className="py-4">
                    <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`rounded-full border px-2 py-1 text-xs font-medium ${fulfillmentStatusClass(notification.priority)}`}>
                            {formatFulfillmentStatus(notification.priority)}
                          </span>
                          <span className="rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-600">
                            {formatFulfillmentStatus(notification.category)}
                          </span>
                          <span className={`rounded-full px-2 py-1 text-xs ${isUnread ? 'bg-brand-50 text-brand-700' : 'bg-gray-100 text-gray-500'}`}>
                            {formatFulfillmentStatus(notification.status)}
                          </span>
                        </div>
                        <h3 className="mt-3 font-semibold text-gray-950">{notification.title}</h3>
                        <p className="mt-1 text-sm text-gray-600">{notification.message}</p>
                        <p className="mt-2 text-xs text-gray-500">
                          {notification.event_type || 'system'} · {notification.market_name || notification.country_code || actorScopeLabel} · {notification.branch_name || 'No branch'} · {formatDateTime(notification.created_at)}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2 xl:justify-end">
                        {notification.action_url && (
                          <a href={notification.action_url} className="btn-secondary text-sm">
                            Open
                          </a>
                        )}
                        <button
                          type="button"
                          onClick={() => updateOperationNotification(notification, 'read')}
                          disabled={!isUnread || updatingId === `operations-notification-${notification.id}-read`}
                          className="btn-secondary text-sm"
                        >
                          Read
                        </button>
                        <button
                          type="button"
                          onClick={() => updateOperationNotification(notification, 'archive')}
                          disabled={updatingId === `operations-notification-${notification.id}-archive`}
                          className="btn-secondary text-sm"
                        >
                          Archive
                        </button>
                        <button
                          type="button"
                          onClick={() => updateOperationNotification(notification, 'dismiss')}
                          disabled={updatingId === `operations-notification-${notification.id}-dismiss`}
                          className="btn-secondary text-sm"
                        >
                          Dismiss
                        </button>
                      </div>
                    </div>
                  </article>
                )
              })}
            </div>
          )}
        </section>
      )}

      {showReviewPhotoModeration && (
        <section className="bg-white border border-gray-200 rounded-lg p-5">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
            <div>
              <h2 className="text-lg font-semibold text-gray-950 flex items-center gap-2">
                <ImagePlus size={19} className="text-brand-600" /> Review Photo Moderation
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                Operations-only queue for customer review photos. Merchants cannot approve, reject, hide, or delete customer review photos.
              </p>
            </div>
            <button
              type="button"
              onClick={() => reviewPhotosQuery.refetch()}
              disabled={reviewPhotosQuery.isFetching}
              className="btn-secondary text-sm"
            >
              {reviewPhotosQuery.isFetching ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>

          <div className="grid sm:grid-cols-3 gap-3 mb-5">
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Pending photos</p>
              <p className="text-2xl font-bold text-amber-700 mt-1">{pendingReviewPhotos.length}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Visible in scope</p>
              <p className="text-2xl font-bold text-gray-950 mt-1">{reviewPhotos.length}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <p className="text-sm text-gray-500">Viewing</p>
              <p className="text-lg font-semibold text-gray-950 mt-1">{actorScopeLabel}</p>
            </div>
          </div>

          <div className="grid md:grid-cols-5 gap-3 rounded-lg border border-gray-200 bg-gray-50 p-4 mb-5">
            <label className="text-sm">
              <span className="block text-xs font-medium text-gray-500 mb-1">Status</span>
              <select
                value={reviewPhotoFilters.status}
                onChange={event => setReviewPhotoFilters(current => ({ ...current, status: event.target.value }))}
                className="input-field py-2 bg-white"
              >
                <option value="">All statuses</option>
                {['PENDING', 'APPROVED', 'REJECTED', 'HIDDEN'].map(option => (
                  <option key={option} value={option}>{formatFulfillmentStatus(option)}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="block text-xs font-medium text-gray-500 mb-1">Branch</span>
              <select
                value={reviewPhotoFilters.restaurant}
                onChange={event => setReviewPhotoFilters(current => ({ ...current, restaurant: event.target.value }))}
                className="input-field py-2 bg-white"
              >
                <option value="">All branches</option>
                {branchFilterOptions.map(branch => (
                  <option key={branch.id} value={branch.id}>{branch.label}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="block text-xs font-medium text-gray-500 mb-1">Customer ID</span>
              <input
                value={reviewPhotoFilters.customer}
                onChange={event => setReviewPhotoFilters(current => ({ ...current, customer: event.target.value }))}
                className="input-field py-2 bg-white"
                placeholder="T-Food customer ID"
              />
            </label>
            <label className="text-sm">
              <span className="block text-xs font-medium text-gray-500 mb-1">From</span>
              <input
                type="date"
                value={reviewPhotoFilters.date_from}
                onChange={event => setReviewPhotoFilters(current => ({ ...current, date_from: event.target.value }))}
                className="input-field py-2 bg-white"
              />
            </label>
            <label className="text-sm">
              <span className="block text-xs font-medium text-gray-500 mb-1">To</span>
              <input
                type="date"
                value={reviewPhotoFilters.date_to}
                onChange={event => setReviewPhotoFilters(current => ({ ...current, date_to: event.target.value }))}
                className="input-field py-2 bg-white"
              />
            </label>
          </div>

          {!reviewPhotos.length ? (
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-8 text-center">
              <ImagePlus size={24} className="mx-auto text-gray-400" />
              <p className="mt-3 font-semibold text-gray-950">No review photos need moderation.</p>
              <p className="mt-1 text-sm text-gray-500">
                Pending queue is empty for this scope. Minimum Configuration Mode is supported; missing market, city, area, or branch data will not break this queue.
              </p>
            </div>
          ) : (
            <div className="grid lg:grid-cols-2 gap-4">
              {reviewPhotos.map(photo => (
                <article key={photo.id} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex gap-4">
                    <div className="h-28 w-28 rounded-lg bg-gray-100 overflow-hidden flex-shrink-0">
                      {photo.image_preview_url
                        ? <PrivateImage src={photo.image_preview_url} alt="" className="h-full w-full object-cover" />
                        : <div className="h-full w-full flex items-center justify-center text-gray-400"><ImagePlus size={24} /></div>}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full border px-2 py-1 text-xs font-medium ${fulfillmentStatusClass(photo.status)}`}>
                          {formatFulfillmentStatus(photo.status)}
                        </span>
                        <span className="rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-600">
                          Review #{photo.review_id}
                        </span>
                        <span className="rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-600">
                          Order #{photo.order_id}
                        </span>
                      </div>
                      <p className="mt-3 text-sm font-medium text-gray-950">{photo.customer?.name || photo.customer?.username || 'Customer'}</p>
                      <p className="mt-1 text-sm text-gray-600 line-clamp-2">{photo.comment || 'No review comment.'}</p>
                      <p className="mt-2 text-xs text-gray-500">
                        Rating {photo.rating}/5 · {photo.branch?.name || 'No branch'} · {photo.merchant_company?.business_name || 'No merchant'} · {formatDateTime(photo.created_at)}
                      </p>
                      {photo.caption && <p className="mt-2 text-sm text-gray-700">Caption: {photo.caption}</p>}
                      {photo.moderation_reason && <p className="mt-2 text-sm text-red-700">Reason: {photo.moderation_reason}</p>}
                      {photo.reviewed_at && (
                        <p className="mt-2 text-xs text-gray-500">
                          Reviewed by {photo.reviewed_by?.name || photo.reviewed_by?.username || 'Operations'} · {formatDateTime(photo.reviewed_at)}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="mt-4">
                    <input
                      className="input-field text-sm"
                      placeholder="T-Food moderation reason"
                      value={reviewPhotoReasons[photo.id] || ''}
                      onChange={event => setReviewPhotoReasons(current => ({ ...current, [photo.id]: event.target.value }))}
                    />
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => updateReviewPhotoModeration(photo, 'APPROVE')}
                        disabled={updatingId === `review-photo-${photo.id}-APPROVE` || photo.status === 'APPROVED'}
                        className="btn-secondary inline-flex items-center gap-2 text-sm"
                      >
                        <CheckCircle2 size={15} /> Approve
                      </button>
                      <button
                        type="button"
                        onClick={() => updateReviewPhotoModeration(photo, 'REJECT')}
                        disabled={updatingId === `review-photo-${photo.id}-REJECT`}
                        className="btn-secondary inline-flex items-center gap-2 text-sm text-red-600"
                      >
                        <XCircle size={15} /> Reject
                      </button>
                      <button
                        type="button"
                        onClick={() => updateReviewPhotoModeration(photo, 'HIDE')}
                        disabled={updatingId === `review-photo-${photo.id}-HIDE`}
                        className="btn-secondary inline-flex items-center gap-2 text-sm"
                      >
                        <XCircle size={15} /> Hide
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {showOperationsUsers && (
        <section className="bg-white border border-gray-200 rounded-lg p-5">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-5">
            <div>
              <h2 className="text-lg font-semibold text-gray-950 flex items-center gap-2">
                <Users size={19} className="text-brand-600" /> Operations Users
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                Manage T-Food operations access across global, country, city, and area scopes. Passwords and provider credentials are never shown.
              </p>
            </div>
            <button
              type="button"
              onClick={() => operationsUsersQuery.refetch()}
              disabled={!canManageOperationsUsers || operationsUsersQuery.isFetching}
              className="btn-secondary text-sm"
            >
              {operationsUsersQuery.isFetching ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>

          {!canManageOperationsUsers ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
              Your operations profile does not include MANAGE_OPERATIONS_USERS. Existing dashboard views remain available within your assigned scope.
            </div>
          ) : (
            <div className="space-y-6">
              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="border border-gray-200 rounded-lg p-4">
                  <p className="text-sm text-gray-500">Operations profiles</p>
                  <p className="text-2xl font-bold text-gray-950 mt-1">{operationsUsers.length}</p>
                </div>
                <div className="border border-gray-200 rounded-lg p-4">
                  <p className="text-sm text-gray-500">Active</p>
                  <p className="text-2xl font-bold text-emerald-700 mt-1">{operationsUsers.filter(profile => profile.status === 'ACTIVE').length}</p>
                </div>
                <div className="border border-gray-200 rounded-lg p-4">
                  <p className="text-sm text-gray-500">Suspended</p>
                  <p className="text-2xl font-bold text-red-700 mt-1">{operationsUsers.filter(profile => profile.status === 'SUSPENDED').length}</p>
                </div>
                <div className="border border-gray-200 rounded-lg p-4">
                  <p className="text-sm text-gray-500">Global scope</p>
                  <p className="text-2xl font-bold text-brand-700 mt-1">{operationsUsers.filter(profile => profile.is_global_scope).length}</p>
                </div>
              </div>

              <form onSubmit={createOperationsUser} className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <h3 className="font-semibold text-gray-950">Create operations profile</h3>
                <p className="text-sm text-gray-500 mt-1">
                  For T-Food internal admins and support staff only. This creates the operations access profile; set the real password through the normal account/password flow.
                </p>
                <div className="mt-4 grid md:grid-cols-2 xl:grid-cols-4 gap-3">
                  <input
                    required
                    className="input-field"
                    placeholder="tfood.ops.admin"
                    value={operationsUserForm.username}
                    onChange={event => setOperationsUserForm(current => ({ ...current, username: event.target.value }))}
                  />
                  <input
                    type="email"
                    className="input-field"
                    placeholder="ops@tfoodglobal.com"
                    value={operationsUserForm.email}
                    onChange={event => setOperationsUserForm(current => ({ ...current, email: event.target.value }))}
                  />
                  <input
                    className="input-field"
                    placeholder="T-Food"
                    value={operationsUserForm.first_name}
                    onChange={event => setOperationsUserForm(current => ({ ...current, first_name: event.target.value }))}
                  />
                  <input
                    className="input-field"
                    placeholder="Admin"
                    value={operationsUserForm.last_name}
                    onChange={event => setOperationsUserForm(current => ({ ...current, last_name: event.target.value }))}
                  />
                  <select
                    className="input-field bg-white"
                    value={operationsUserForm.role}
                    onChange={event => setOperationsUserForm(current => ({ ...current, role: event.target.value }))}
                  >
                    {operationsRoleOptions.map(role => (
                      <option key={role} value={role}>{formatFulfillmentStatus(role)}</option>
                    ))}
                  </select>
                  <select
                    className="input-field bg-white"
                    value={operationsUserForm.status}
                    onChange={event => setOperationsUserForm(current => ({ ...current, status: event.target.value }))}
                  >
                    {operationsStatusOptions.map(statusOption => (
                      <option key={statusOption} value={statusOption}>{formatFulfillmentStatus(statusOption)}</option>
                    ))}
                  </select>
                  <button
                    type="submit"
                    disabled={updatingId === 'operations-user-create'}
                    className="btn-primary md:col-span-2 xl:col-span-2 text-sm"
                  >
                    {updatingId === 'operations-user-create' ? 'Creating...' : 'Create operations profile'}
                  </button>
                </div>
                {!paymentProviderMarkets.length && !operationsCities.length && !operationsAreas.length && (
                  <p className="mt-3 text-sm text-gray-500">
                    No markets, cities, or areas are configured yet. Global Admin can still create operations profiles; scope assignment can happen later.
                  </p>
                )}
              </form>

              {operationsUsersQuery.isError && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                  Operations users could not be loaded for this account.
                </div>
              )}

              {!operationsUsers.length && !operationsUsersQuery.isError ? (
                <div className="border border-dashed border-gray-300 rounded-lg py-12 text-center text-gray-500">
                  No operations users yet.
                </div>
              ) : (
                <div className="space-y-4">
                  {operationsUsers.map(profile => {
                    const scopeSelection = operationsScopeSelections[profile.id] || {}
                    return (
                      <article key={profile.id} className="border border-gray-200 rounded-lg p-5">
                        <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-5">
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <h3 className="font-semibold text-gray-950">{profile.user?.name || profile.user?.username}</h3>
                              <span className={`rounded-full px-2 py-1 text-xs font-medium ${profile.status === 'ACTIVE' ? 'bg-emerald-50 text-emerald-700' : profile.status === 'SUSPENDED' ? 'bg-red-50 text-red-700' : 'bg-gray-100 text-gray-600'}`}>
                                {formatFulfillmentStatus(profile.status)}
                              </span>
                              <span className="rounded-full bg-brand-50 px-2 py-1 text-xs font-medium text-brand-700">
                                {formatFulfillmentStatus(profile.role)}
                              </span>
                              {profile.is_global_scope && (
                                <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">Global scope</span>
                              )}
                            </div>
                            <p className="text-sm text-gray-500 mt-1">
                              @{profile.user?.username} - {profile.user?.email || 'No email'} - Created {formatDateTime(profile.created_at)}
                            </p>
                            <p className="text-xs text-gray-500 mt-2">
                              Permissions: {(profile.effective_permissions || []).slice(0, 8).map(formatFulfillmentStatus).join(', ') || 'No active permissions'}
                              {(profile.effective_permissions || []).length > 8 ? ` +${profile.effective_permissions.length - 8} more` : ''}
                            </p>

                            <div className="mt-4 grid lg:grid-cols-3 gap-4">
                              {[
                                ['market', 'Markets', profile.assigned_markets || [], paymentProviderMarkets, 'name'],
                                ['city', 'Cities', profile.assigned_cities || [], operationsCities, 'name'],
                                ['area', 'Areas', profile.assigned_areas || [], operationsAreas, 'name'],
                              ].map(([scopeType, title, assigned, options, labelField]) => {
                                const scopedOptions = scopedOptionsForProfile(scopeType, profile, options)
                                return (
                                <div key={scopeType} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                                  <p className="text-sm font-semibold text-gray-950">{title}</p>
                                  <div className="mt-2 flex flex-wrap gap-2">
                                    {assigned.map(item => (
                                      <button
                                        key={item.id}
                                        type="button"
                                        onClick={() => removeOperationsScope(profile, scopeType, item.id)}
                                        disabled={updatingId === `operations-user-${profile.id}-${scopeType}-${item.id}`}
                                        className="rounded-full border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600 hover:border-red-200 hover:text-red-600"
                                        title={`Remove ${scopeType} access`}
                                      >
                                        {item[labelField] || item.name} x
                                      </button>
                                    ))}
                                    {!assigned.length && <span className="text-xs text-gray-500">No {scopeType} access assigned.</span>}
                                  </div>
                                  <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
                                    <select
                                      className="input-field py-2 bg-white text-sm"
                                      value={scopeSelection[scopeType] || ''}
                                      onChange={event => setOperationsScopeSelections(current => ({
                                        ...current,
                                        [profile.id]: { ...(current[profile.id] || {}), [scopeType]: event.target.value },
                                      }))}
                                    >
                                      <option value="">Assign {scopeType}</option>
                                      {scopedOptions.map(option => (
                                        <option key={option.id} value={option.id}>
                                          {option.name} {option.country_code ? `(${option.country_code})` : ''}
                                        </option>
                                      ))}
                                    </select>
                                    <button
                                      type="button"
                                      onClick={() => assignOperationsScope(profile, scopeType)}
                                      disabled={!scopeSelection[scopeType] || updatingId === `operations-user-${profile.id}-${scopeType}`}
                                      className="btn-secondary px-3 py-2 text-sm"
                                    >
                                      Add
                                    </button>
                                  </div>
                                  {!scopedOptions.length && (
                                    <p className="mt-2 text-xs text-gray-500">No {scopeType} records configured yet.</p>
                                  )}
                                </div>
                              )})}
                            </div>
                          </div>

                          <div className="xl:w-72 space-y-3">
                            <label className="text-sm font-medium text-gray-700">
                              Role
                              <select
                                className="input-field mt-1 bg-white"
                                value={profile.role}
                                onChange={event => patchOperationsUser(profile, { role: event.target.value })}
                                disabled={updatingId === `operations-user-${profile.id}`}
                              >
                                {operationsRoleOptions.map(role => (
                                  <option key={role} value={role}>{formatFulfillmentStatus(role)}</option>
                                ))}
                              </select>
                            </label>
                            <label className="text-sm font-medium text-gray-700">
                              Status
                              <select
                                className="input-field mt-1 bg-white"
                                value={profile.status}
                                onChange={event => patchOperationsUser(profile, { status: event.target.value })}
                                disabled={updatingId === `operations-user-${profile.id}`}
                              >
                                {operationsStatusOptions.map(statusOption => (
                                  <option key={statusOption} value={statusOption}>{formatFulfillmentStatus(statusOption)}</option>
                                ))}
                              </select>
                            </label>
                            <div className="grid grid-cols-3 gap-2">
                              <button type="button" onClick={() => patchOperationsUser(profile, { status: 'ACTIVE' })} className="btn-secondary px-2 py-2 text-xs">Activate</button>
                              <button type="button" onClick={() => patchOperationsUser(profile, { status: 'INACTIVE' })} className="btn-secondary px-2 py-2 text-xs">Deactivate</button>
                              <button type="button" onClick={() => patchOperationsUser(profile, { status: 'SUSPENDED' })} className="btn-secondary px-2 py-2 text-xs text-red-600">Suspend</button>
                            </div>
                            <p className="text-xs text-gray-500">
                              Scoped admins can only assign scopes they already control. Global Admin promotion is restricted by the backend.
                            </p>
                          </div>
                        </div>
                      </article>
                    )
                  })}
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {showBranches && (
        <section>
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-950 flex items-center gap-2">
                <Store size={19} className="text-brand-600" /> Branches
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                Branch / storefront controls for food, grocery, pharmacy, retail, courier, and local commerce locations.
              </p>
            </div>
            <span className="text-sm font-medium text-gray-600">
              {branches.length} branches · Current Total
            </span>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <div className="border border-gray-200 rounded-lg p-4 bg-white">
              <p className="text-sm text-gray-500">Total branches</p>
              <p className="text-2xl font-bold text-gray-950 mt-1">{branches.length}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4 bg-white">
              <p className="text-sm text-gray-500">Active</p>
              <p className="text-2xl font-bold text-emerald-700 mt-1">{activeBranches.length}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4 bg-white">
              <p className="text-sm text-gray-500">Open</p>
              <p className="text-2xl font-bold text-blue-700 mt-1">{openBranches.length}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4 bg-white">
              <p className="text-sm text-gray-500">Closed or inactive</p>
              <p className="text-2xl font-bold text-amber-700 mt-1">{branches.filter(branch => !branch.is_open || !branch.is_active).length}</p>
            </div>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <div className="border border-gray-200 rounded-lg p-4 bg-white">
              <p className="text-sm text-gray-500">Filtered branch revenue</p>
              <p className="text-2xl font-bold text-emerald-700 mt-1">{money(branchAnalytics.revenue)}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4 bg-white">
              <p className="text-sm text-gray-500">Filtered branch orders</p>
              <p className="text-2xl font-bold text-gray-950 mt-1">{branchAnalytics.orders}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4 bg-white">
              <p className="text-sm text-gray-500">Branch riders</p>
              <p className="text-2xl font-bold text-gray-950 mt-1">{branchAnalytics.riders}</p>
            </div>
            <div className="border border-gray-200 rounded-lg p-4 bg-white">
              <p className="text-sm text-gray-500">Rider utilization</p>
              <p className="text-2xl font-bold text-blue-700 mt-1">{branchRiderUtilization}%</p>
            </div>
          </div>

          <div className="grid lg:grid-cols-2 gap-4 mb-4">
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <h3 className="font-semibold text-gray-950">Top branches</h3>
              <div className="mt-3 divide-y divide-gray-200">
                {topBranches.map(branch => (
                  <div key={branch.branch_id} className="py-3 flex items-center justify-between gap-3">
                    <span className="text-sm text-gray-700">{branch.branch_name || branch.rest_name}</span>
                    <span className="text-sm font-medium">{money(branch.analytics?.revenue ?? branch.revenue_summary?.gross_sales)} · {branch.analytics?.orders ?? branch.order_count ?? 0} orders</span>
                  </div>
                ))}
                {!topBranches.length && <p className="py-3 text-sm text-gray-500">No branch revenue yet.</p>}
              </div>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <h3 className="font-semibold text-gray-950">Underperforming branches</h3>
              <div className="mt-3 divide-y divide-gray-200">
                {underperformingBranches.map(branch => (
                  <div key={branch.branch_id} className="py-3 flex items-center justify-between gap-3">
                    <span className="text-sm text-gray-700">{branch.branch_name || branch.rest_name}</span>
                    <span className="text-sm font-medium">{branch.analytics?.performance_label || 'Needs attention'}</span>
                  </div>
                ))}
                {!underperformingBranches.length && <p className="py-3 text-sm text-gray-500">No underperforming branches in the current filters.</p>}
              </div>
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4">
            <div className="grid md:grid-cols-2 xl:grid-cols-4 gap-3">
              {showGeographyFilters && (
                <>
                  <label className="text-sm font-medium text-gray-700">
                    Country
                    <input
                      value={branchFilters.country_code}
                      onChange={event => setBranchFilters(current => ({
                        ...current,
                        country_code: event.target.value.toUpperCase(),
                        market: '',
                        city: '',
                        area: '',
                      }))}
                      className="input-field mt-1"
                      placeholder="GN"
                    />
                  </label>
                  <label className="text-sm font-medium text-gray-700">
                    Market
                    <select
                      value={branchFilters.market}
                      onChange={event => {
                        const market = branchMarketOptions.find(option => String(option.slug || option.id) === event.target.value)
                        setBranchFilters(current => ({
                          ...current,
                          market: event.target.value,
                          country_code: market?.country_code || current.country_code,
                          city: '',
                          area: '',
                        }))
                      }}
                      className="input-field mt-1"
                    >
                      <option value="">{branchMarketOptions.length ? 'All markets' : 'No markets configured'}</option>
                      {branchMarketOptions.map(market => (
                        <option key={market.id} value={market.slug || market.id}>
                          {market.name} ({market.country_code})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-sm font-medium text-gray-700">
                    City
                    <select
                      value={branchFilters.city}
                      onChange={event => setBranchFilters(current => ({ ...current, city: event.target.value, area: '' }))}
                      className="input-field mt-1"
                      disabled={!cities.length}
                    >
                      <option value="">{cities.length ? 'All cities' : selectedBranchCountry ? `No cities for ${selectedBranchCountry}` : 'No cities configured'}</option>
                      {cities.map(city => (
                        <option key={city.id || city.slug || city.name} value={city.slug || city.name}>
                          {city.name}{city.country_code ? ` (${city.country_code})` : ''}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="text-sm font-medium text-gray-700">
                    Area
                    <select
                      value={branchFilters.area}
                      onChange={event => setBranchFilters(current => ({ ...current, area: event.target.value }))}
                      className="input-field mt-1"
                      disabled={!areas.length}
                    >
                      <option value="">{areas.length ? 'All areas' : branchFilters.city ? 'No areas for selected city' : 'Choose a city to filter areas'}</option>
                      {areas.map(area => (
                        <option key={area.id || area.slug || area.name} value={area.slug || area.name}>
                          {area.name}
                        </option>
                      ))}
                    </select>
                  </label>
                </>
              )}
              <label className="text-sm font-medium text-gray-700">
                Branch type
                <select
                  value={branchFilters.branch_type}
                  onChange={event => setBranchFilters(current => ({ ...current, branch_type: event.target.value }))}
                  className="input-field mt-1"
                >
                  <option value="">All branch types</option>
                  <option value="FOOD">Food</option>
                  <option value="GROCERY">Grocery</option>
                  <option value="PHARMACY">Pharmacy</option>
                  <option value="RETAIL">Retail</option>
                  <option value="COURIER">Courier</option>
                  <option value="LOCAL_COMMERCE">Local commerce</option>
                </select>
              </label>
              <label className="text-sm font-medium text-gray-700">
                Status
                <select
                  value={branchFilters.status}
                  onChange={event => setBranchFilters(current => ({ ...current, status: event.target.value }))}
                  className="input-field mt-1"
                >
                  <option value="">All statuses</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="open">Open</option>
                  <option value="closed">Closed</option>
                </select>
              </label>
              <label className="text-sm font-medium text-gray-700">
                Merchant
                <select
                  value={branchFilters.merchant_id}
                  onChange={event => setBranchFilters(current => ({ ...current, merchant_id: event.target.value }))}
                  className="input-field mt-1"
                >
                  <option value="">All merchants</option>
                  {merchants.map(merchant => (
                    <option key={merchant.id} value={merchant.id}>
                      {merchant.business_name || merchant.owner_name || merchant.username}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-medium text-gray-700">
                Branch
                <select
                  value={branchFilters.branch_id}
                  onChange={event => setBranchFilters(current => ({ ...current, branch_id: event.target.value }))}
                  className="input-field mt-1"
                >
                  <option value="">All branches</option>
                  {branchFilterOptions.map(branch => (
                    <option key={branch.id} value={branch.id}>
                      {branch.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="flex items-end">
                <button
                  type="button"
                  onClick={() => setBranchFilters({
                    country_code: '',
                    market: '',
                    city: '',
                    area: '',
                    branch_type: '',
                    status: '',
                    merchant_id: '',
                    branch_id: '',
                  })}
                  className="btn-secondary w-full text-sm"
                >
                  Reset filters
                </button>
              </div>
            </div>
            {branchGeographyMessage && (
              <p className="mt-3 text-sm text-gray-500">{branchGeographyMessage}</p>
            )}
          </div>

          {!branches.length ? (
            <div className="border border-dashed border-gray-300 rounded-lg py-12 text-center text-gray-500">
              No branches match the current filters.
            </div>
          ) : (
            <div className="space-y-3">
              {branches.map(branch => {
                const merchantVerified = branch.merchant_verification_status?.is_verified
                const branchName = branch.branch_name || branch.rest_name
                const acceptingOrders = branch.accepting_orders ?? branch.is_open
                const customerStatus = branch.is_open
                  ? acceptingOrders ? 'Accepting now' : 'Closed by hours'
                  : 'Orders paused'
                return (
                  <article key={branch.branch_id} className="bg-white border border-gray-200 rounded-lg p-5">
                    <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-5">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="font-semibold text-gray-950">{branchName}</h3>
                          <span className="text-xs font-medium px-2 py-1 rounded-full bg-gray-100 text-gray-700">
                            {branch.branch_type?.replaceAll('_', ' ') || 'Branch'}
                          </span>
                          <span className={`text-xs font-medium px-2 py-1 rounded-full ${branch.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'}`}>
                            {branch.is_active ? 'Active' : 'Inactive'}
                          </span>
                          <span className={`text-xs font-medium px-2 py-1 rounded-full ${acceptingOrders ? 'bg-blue-50 text-blue-700' : 'bg-gray-100 text-gray-600'}`}>
                            {customerStatus}
                          </span>
                          <span className={`text-xs font-medium px-2 py-1 rounded-full ${merchantVerified ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                            Merchant {merchantVerified ? 'verified' : 'pending'}
                          </span>
                        </div>
                        <p className="text-sm text-gray-500 mt-2">
                          {branch.merchant_company?.business_name || branch.merchant_company?.username || 'Merchant not set'} · {branch.rest_name}
                        </p>
                        <p className="text-sm text-gray-500 mt-1">
                          Country: {branch.country || branch.country_code || branch.market?.country_code || 'Not set'} · City: {branch.city?.name || branch.city || 'Not set'} · Area: {branch.area?.name || branch.area || 'Not set'}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          Market: {branch.market?.name || branch.market_name || 'Not set'}
                        </p>
                        <p className="text-sm text-gray-600 mt-2">{branch.address || 'Address not set'}</p>
                        <p className="text-xs text-gray-500 mt-2">
                          Radius {branch.delivery_radius_km || 0} km · Menu {branch.menu_count || 0} · Riders {branch.rider_count || 0} · Available {branch.available_rider_count || 0} · Verified {branch.verified_rider_count || 0} · Orders {branch.order_count || 0}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          Location: {branch.location?.latitude || 'not set'}, {branch.location?.longitude || 'not set'} · Created {formatDateTime(branch.created_at)}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">
                          Revenue: gross {money(branch.revenue_summary?.gross_sales)} · platform {money(branch.revenue_summary?.platform_fee)} · merchant {money(branch.revenue_summary?.merchant_payout)}
                        </p>
                        {!!branch.branch_riders?.length && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {branch.branch_riders.slice(0, 5).map(rider => (
                              <span key={rider.id} className="rounded-full border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-600">
                                {rider.name} · {rider.is_verified ? 'verified' : 'pending'} · {rider.is_available ? 'available' : 'offline'}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="grid sm:grid-cols-2 xl:grid-cols-1 gap-2 xl:min-w-[220px]">
                        <button
                          type="button"
                          onClick={() => updateBranchStatus(branch, { is_active: !branch.is_active })}
                          disabled={updatingId === `branch-${branch.branch_id}`}
                          className="btn-secondary text-sm"
                        >
                          {branch.is_active ? 'Deactivate branch' : 'Activate branch'}
                        </button>
                        <button
                          type="button"
                          onClick={() => updateBranchStatus(branch, { is_open: !branch.is_open })}
                          disabled={updatingId === `branch-${branch.branch_id}`}
                          className="btn-secondary text-sm"
                        >
                          {branch.is_open ? 'Close branch' : 'Open branch'}
                        </button>
                        <button type="button" onClick={() => setDashboardView('merchants')} className="btn-secondary text-sm">
                          View merchant
                        </button>
                        <button type="button" onClick={() => setDashboardView('orders')} className="btn-secondary text-sm">
                          View orders
                        </button>
                        <button type="button" onClick={() => toast('Menu management remains in the merchant dashboard for now.')} className="btn-secondary text-sm">
                          View menu
                        </button>
                      </div>
                    </div>
                  </article>
                )
              })}
            </div>
          )}
        </section>
      )}

      {showMerchantSettlements && (
      <section>
        <div className="flex items-center justify-between gap-4 mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-950 flex items-center gap-2"><Banknote size={19} className="text-brand-600" /> Merchant settlements</h2>
            <p className="text-sm text-gray-500 mt-1">Net food revenue after platform adjustments and discounts.</p>
          </div>
          <span className="text-sm font-semibold text-emerald-700">{money(availableMerchantPayoutTotal)} available · Filtered by: {selectedRangeLabel}</span>
        </div>
        {!merchantPayouts.length ? (
          <div className="border border-dashed border-gray-300 rounded-lg py-12 text-center text-gray-500">No merchant settlement records yet.</div>
        ) : (
          <div className="divide-y divide-gray-200 border-y border-gray-200">
            {merchantPayouts.slice(0, 15).map(payout => (
              <div key={payout.id} className="py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <p className="font-medium text-gray-950">{payout.merchant_name} (@{payout.merchant_username}) · Order #{payout.id}</p>
                  <p className="text-sm text-gray-500 mt-1">{money(payout.merchant_payout)} · {payout.merchant_payout_status}</p>
                </div>
                {payout.merchant_payout_status === 'AVAILABLE' ? (
                  <button type="button" disabled={updatingId === `merchant-payout-${payout.id}`} onClick={() => payMerchant(payout)} className="btn-primary text-sm">Mark paid</button>
                ) : (
                  <span className="text-sm text-emerald-700">Paid {payout.merchant_paid_at ? new Date(payout.merchant_paid_at).toLocaleDateString('en-IN') : ''}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
      )}

      {showPartnerPayouts && (
      <section>
        <div className="flex items-center justify-between gap-4 mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-950 flex items-center gap-2"><Banknote size={19} className="text-brand-600" /> Partner payouts</h2>
            <p className="text-sm text-gray-500 mt-1">Delivery earnings become payable only after completion.</p>
          </div>
          <span className="text-sm font-semibold text-emerald-700">{money(availablePartnerPayoutTotal)} available · Filtered by: {selectedRangeLabel}</span>
        </div>
        {!partnerPayouts.length ? (
          <div className="border border-dashed border-gray-300 rounded-lg py-12 text-center text-gray-500">No partner payout records yet.</div>
        ) : (
          <div className="divide-y divide-gray-200 border-y border-gray-200">
            {partnerPayouts.slice(0, 15).map(payout => (
              <div key={payout.id} className="py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                  <p className="font-medium text-gray-950">{payout.partner_name} (@{payout.partner_username}) · Order #{payout.order_id}</p>
                  <p className="text-sm text-gray-500 mt-1">{money(payout.partner_fee)} · {payout.payout_status}</p>
                </div>
                {payout.payout_status === 'AVAILABLE' ? (
                  <button type="button" disabled={updatingId === `payout-${payout.id}`} onClick={() => payPartner(payout)} className="btn-primary text-sm">Mark paid</button>
                ) : (
                  <span className="text-sm text-emerald-700">Paid {payout.paid_at ? new Date(payout.paid_at).toLocaleDateString('en-IN') : ''}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
      )}

      {showDispatchSection && (
      <section>
        <div className="flex items-center justify-between gap-4 mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-950 flex items-center gap-2"><Route size={19} className="text-brand-600" /> {activeView === 'unassigned-deliveries' ? 'Unassigned deliveries' : 'Live dispatch'}</h2>
            <p className="text-sm text-gray-500 mt-1">{activeView === 'unassigned-deliveries' ? 'Deliveries that still need an operator or partner assignment.' : 'Dispatch records with available orders, assigned partners, and delivery status.'}</p>
          </div>
          <span className="text-sm font-medium text-gray-600">{visibleDispatches.length} records · Filtered by: {selectedRangeLabel}</span>
        </div>
        {!visibleDispatches.length ? (
          <div className="border border-dashed border-gray-300 rounded-lg py-12 text-center text-gray-500">
            {activeView === 'unassigned-deliveries' ? 'No unassigned deliveries need action right now.' : 'No orders are waiting for pickup.'}
          </div>
        ) : (
          <div className="space-y-3">
            {visibleDispatches.map(delivery => (
              <article key={delivery.id} className="bg-white border border-gray-200 rounded-lg p-5 grid lg:grid-cols-[1fr_auto] gap-5 lg:items-center">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold text-gray-950">Order #{delivery.order_id} · {delivery.restaurant_name}</h3>
                    <span className={`text-xs font-medium px-2 py-1 rounded-md ${delivery.partner_id ? 'bg-blue-50 text-blue-700' : 'bg-amber-50 text-amber-700'}`}>
                      {delivery.partner_id ? `Assigned to @${delivery.partner_username}` : 'Waiting for partner'}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 mt-2">{delivery.customer_name} · {delivery.delivery_address} · {money(delivery.total_amount)}</p>
                </div>
                <div className="flex flex-col sm:flex-row gap-2 min-w-0 lg:min-w-[360px]">
                  <select
                    value={dispatchSelections[delivery.id] || ''}
                    onChange={event => setDispatchSelections(current => ({ ...current, [delivery.id]: event.target.value }))}
                    className="input-field py-2"
                  >
                    <option value="">{delivery.partner_id ? 'Reassign partner' : 'Choose partner'}</option>
                    {partners.filter(partner => partner.is_verified && partner.is_available).map(partner => (
                      <option key={partner.id} value={partner.id}>{partner.partner_name} (@{partner.username})</option>
                    ))}
                  </select>
                  <button type="button" disabled={updatingId === `dispatch-${delivery.id}`} onClick={() => assignDelivery(delivery)} className="btn-primary text-sm whitespace-nowrap">
                    {delivery.partner_id ? 'Reassign' : 'Assign'}
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
      )}

      {showSupportSection && (
      <section>
        <div className="flex items-center justify-between gap-4 mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-950 flex items-center gap-2"><Headphones size={19} className="text-brand-600" /> {activeView === 'open-support' ? 'Open support tickets' : 'Customer support'}</h2>
            <p className="text-sm text-gray-500 mt-1">{activeView === 'open-support' ? 'Support tickets that are still open or in review.' : 'All support ticket records with available operator actions.'}</p>
          </div>
          <span className="text-sm font-medium text-gray-600">{visibleTickets.length} records · Filtered by: {selectedRangeLabel}</span>
        </div>
        {!visibleTickets.length ? (
          <div className="border border-dashed border-gray-300 rounded-lg py-12 text-center text-gray-500">
            {activeView === 'open-support' ? 'No open support tickets need action right now.' : 'No support tickets.'}
          </div>
        ) : (
          <div className="space-y-3">
            {visibleTickets.slice(0, 10).map(ticket => {
              const active = ['OPEN', 'IN_REVIEW'].includes(ticket.status)
              return (
                <article key={ticket.id} className="bg-white border border-gray-200 rounded-lg p-5">
                  <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-semibold text-gray-950">Ticket #{ticket.id} · Order #{ticket.order_id}</h3>
                        <span className="text-xs font-medium bg-gray-100 text-gray-700 px-2 py-1 rounded-md">{ticket.status.replaceAll('_', ' ')}</span>
                        {ticket.refund_status === 'REQUESTED' && <span className="text-xs font-medium bg-amber-50 text-amber-700 px-2 py-1 rounded-md">Refund requested</span>}
                      </div>
                      <p className="text-sm text-gray-500 mt-1">{ticket.customer_name} · {ticket.customer_email || 'No email'} · {money(ticket.order_total)} · {ticket.payment_method} {ticket.payment_status}</p>
                      <p className="text-sm text-gray-700 mt-3"><strong>{ticket.category.replaceAll('_', ' ')}:</strong> {ticket.description}</p>
                      {ticket.fulfillment_context?.has_fulfillment_request && (
                        <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
                          <p className="font-semibold">Internal fulfillment context - do not disclose to customer.</p>
                          <div className="mt-3 grid gap-2 md:grid-cols-2">
                            <p><span className="font-medium">Request:</span> #{ticket.fulfillment_context.fulfillment_request_id}</p>
                            <p><span className="font-medium">Settlement preview:</span> {ticket.fulfillment_context.settlement_preview_status?.replaceAll('_', ' ') || 'Not available'}</p>
                            <p><span className="font-medium">Requesting merchant:</span> {ticket.fulfillment_context.requesting_merchant?.business_name || ticket.fulfillment_context.requesting_merchant?.username || 'Unknown'}</p>
                            <p><span className="font-medium">Fulfilling merchant:</span> {ticket.fulfillment_context.fulfilling_merchant?.business_name || ticket.fulfillment_context.fulfilling_merchant?.username || 'Unknown'}</p>
                            <p><span className="font-medium">Request status:</span> {ticket.fulfillment_context.fulfillment_status?.replaceAll('_', ' ')}</p>
                            <p><span className="font-medium">Internal status:</span> {ticket.fulfillment_context.internal_status?.replaceAll('_', ' ')}</p>
                          </div>
                          {ticket.fulfillment_context.operations_note && (
                            <p className="mt-3 border-t border-amber-200 pt-3"><span className="font-medium">Operations note:</span> {ticket.fulfillment_context.operations_note}</p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  {active ? (
                    <div className="mt-4 border-t border-gray-100 pt-4">
                      <textarea
                        value={ticketNotes[ticket.id] || ''}
                        onChange={event => setTicketNotes(current => ({ ...current, [ticket.id]: event.target.value }))}
                        rows={2}
                        maxLength={2000}
                        className="input-field resize-none"
                        placeholder="T-Food support response"
                      />
                      <div className="flex flex-wrap gap-2 mt-3">
                        {ticket.status === 'OPEN' && <button type="button" onClick={() => resolveTicket(ticket, 'IN_REVIEW')} className="btn-secondary text-sm">Mark in review</button>}
                        <button type="button" onClick={() => resolveTicket(ticket, 'RESOLVED')} className="btn-secondary text-sm text-emerald-700">Resolve</button>
                        <button type="button" onClick={() => resolveTicket(ticket, 'REJECTED')} className="btn-secondary text-sm text-red-600">Reject</button>
                        <button type="button" disabled={updatingId === `ticket-${ticket.id}`} onClick={() => resolveTicket(ticket, 'RESOLVED', true)} className="btn-primary text-sm">Resolve with full refund</button>
                      </div>
                    </div>
                  ) : ticket.resolution && (
                    <p className="text-sm text-gray-600 mt-4 border-l-2 border-brand-400 pl-3">{ticket.resolution}</p>
                  )}
                </article>
              )
            })}
          </div>
        )}
      </section>
      )}

      {showFulfillmentRequests && (
      <section>
        <div className="flex items-center justify-between gap-4 mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-950 flex items-center gap-2"><FileText size={19} className="text-brand-600" /> Fulfillment requests</h2>
            <p className="text-sm text-gray-500 mt-1">Safe operations control for merchant-to-merchant fulfillment coordination.</p>
          </div>
          <span className="text-sm font-medium text-gray-600">{fulfillmentRequests.length} records · Filtered by: {selectedRangeLabel}</span>
        </div>
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm font-medium text-amber-900">
          Internal only - customer-facing order status and payout are unchanged.
        </div>
        {!fulfillmentRequests.length ? (
          <div className="border border-dashed border-gray-300 rounded-lg py-12 text-center text-gray-500">No fulfillment requests found.</div>
        ) : (
          <div className="space-y-4">
            {fulfillmentRequests.map(request => (
              <article key={request.id} className="bg-white border border-gray-200 rounded-lg p-5">
                <div className="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-5">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold text-gray-950">Request #{request.id} · Order #{request.order_id}</h3>
                      <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${fulfillmentStatusClass(request.status)}`}>
                        Request: {formatFulfillmentStatus(request.status)}
                      </span>
                      <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${fulfillmentStatusClass(request.internal_status)}`}>
                        Internal: {formatFulfillmentStatus(request.internal_status)}
                      </span>
                    </div>
                    <p className="text-sm text-gray-500 mt-2">
                      {request.requesting_merchant?.business_name || request.requesting_merchant?.username || 'Requesting merchant'}
                      {' '}→{' '}
                      {request.fulfilling_merchant?.business_name || request.fulfilling_merchant?.username || 'Fulfilling merchant'}
                    </p>
                    {request.notes && <p className="text-sm text-gray-700 mt-3">{request.notes}</p>}
                    {request.operations_note && <p className="text-sm text-gray-700 mt-3 whitespace-pre-line"><strong>Operations note:</strong> {request.operations_note}</p>}
                    <SettlementPreviewPanel
                      preview={request.settlement_preview}
                      label={request.settlement_preview_label}
                    />
                    <FulfillmentTimeline events={request.events || []} />
                  </div>
                  <div className="xl:w-80 space-y-4">
                    <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-600">
                    <p>Requested {formatDateTime(request.requested_at)}</p>
                    <p>By {request.requested_by?.name || request.requested_by?.username || 'Unknown'}</p>
                    <p className="mt-2">Responded {formatDateTime(request.responded_at)}</p>
                    <p>By {request.responded_by?.name || request.responded_by?.username || 'Not responded yet'}</p>
                      <p className="mt-2">Resolved {formatDateTime(request.resolved_at)}</p>
                      <p>Cancelled {formatDateTime(request.cancelled_at)}</p>
                    </div>
                    <textarea
                      className="input-field resize-none"
                      rows={3}
                      placeholder="T-Food internal operations note"
                      value={fulfillmentNotes[request.id] || ''}
                      onChange={event => setFulfillmentNotes(current => ({ ...current, [request.id]: event.target.value }))}
                    />
                    <button
                      type="button"
                      disabled={!fulfillmentNotes[request.id]?.trim() || updatingId === `fulfillment-${request.id}-ADD_NOTE`}
                      onClick={() => updateFulfillmentRequest(request, 'ADD_NOTE')}
                      className="btn-secondary w-full text-sm"
                    >
                      {updatingId === `fulfillment-${request.id}-ADD_NOTE` ? 'Saving...' : 'Add note'}
                    </button>
                    <div className="rounded-lg border border-gray-200 p-3">
                      <label className="text-sm font-medium text-gray-700">
                        Override internal status
                        <select
                          className="input-field mt-1 bg-white"
                          value={fulfillmentOverrideStatuses[request.id] || request.internal_status || 'REQUESTED'}
                          onChange={event => setFulfillmentOverrideStatuses(current => ({ ...current, [request.id]: event.target.value }))}
                        >
                          {operationsFulfillmentStatuses.map(option => (
                            <option key={option} value={option}>{formatFulfillmentStatus(option)}</option>
                          ))}
                        </select>
                      </label>
                      <button
                        type="button"
                        disabled={updatingId === `fulfillment-${request.id}-OVERRIDE_STATUS`}
                        onClick={() => updateFulfillmentRequest(request, 'OVERRIDE_STATUS')}
                        className="btn-secondary mt-3 w-full text-sm"
                      >
                        {updatingId === `fulfillment-${request.id}-OVERRIDE_STATUS` ? 'Saving...' : 'Override status'}
                      </button>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        disabled={!operationsFulfillmentActionEnabled(request, 'RESOLVE') || updatingId === `fulfillment-${request.id}-RESOLVE`}
                        onClick={() => updateFulfillmentRequest(request, 'RESOLVE')}
                        className="btn-secondary text-sm text-emerald-700"
                      >
                        {updatingId === `fulfillment-${request.id}-RESOLVE` ? 'Saving...' : 'Resolve'}
                      </button>
                      <button
                        type="button"
                        disabled={!operationsFulfillmentActionEnabled(request, 'CANCEL') || updatingId === `fulfillment-${request.id}-CANCEL`}
                        onClick={() => updateFulfillmentRequest(request, 'CANCEL')}
                        className="btn-secondary text-sm text-red-600"
                      >
                        {updatingId === `fulfillment-${request.id}-CANCEL` ? 'Saving...' : 'Cancel'}
                      </button>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
      )}

      {showStaffVerification && (
      <section>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-950 flex items-center gap-2">
              <Users size={19} className="text-brand-600" /> Staff Verification
            </h2>
            <p className="text-sm text-gray-500 mt-1">Operations-only identity review for merchant staff. Merchants cannot approve, reject, suspend, or override verification.</p>
          </div>
          <span className="text-sm font-medium text-gray-600">{staffMembers.length} staff records</span>
        </div>

        {!staffMembers.length ? (
          <div className="border border-dashed border-gray-300 rounded-lg py-12 text-center text-gray-500">No merchant staff records found.</div>
        ) : (
          <div className="space-y-4">
            {staffMembers.map(staff => {
              const documentsPayload = staffDocumentsQuery.data?.[staff.id]
              const documents = documentsPayload?.results || documentsPayload || []
              const requirements = staffDocumentRequirements(staff)
              const isVerified = staff.verification_status === 'VERIFIED'
              const auditItems = [
                staff.submitted_at && { label: 'Submitted', value: staff.submitted_at, actor: staff.name },
                staff.reviewed_at && { label: `Reviewed: ${verificationStatusLabels[staff.verification_status] || formatFulfillmentStatus(staff.verification_status)}`, value: staff.reviewed_at, actor: staff.reviewed_by?.username },
                ...documents
                  .filter(document => document.reviewed_at)
                  .map(document => ({
                    label: `${formatDocumentType(document.document_type)} ${document.status?.toLowerCase() || 'reviewed'}`,
                    value: document.reviewed_at,
                    actor: document.reviewed_by_username,
                  })),
              ].filter(Boolean)
              return (
                <article key={staff.id} className="bg-white border border-gray-200 rounded-lg p-5">
                  <div className="flex flex-col xl:flex-row xl:items-start gap-5">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-semibold text-gray-950">{staff.name}</h3>
                        <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${fulfillmentStatusClass(staff.verification_status)}`}>
                          {verificationStatusLabels[staff.verification_status] || formatFulfillmentStatus(staff.verification_status)}
                        </span>
                        <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${fulfillmentStatusClass(staff.membership_status)}`}>
                          {formatFulfillmentStatus(staff.membership_status)}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500 mt-1">
                        {formatStaffContact(staff)}
                      </p>
                      <p className="text-sm text-gray-600 mt-2">
                        {formatStaffProfile(staff)}
                      </p>
                      <p className="text-sm text-gray-600 mt-2">
                        Merchant: {staff.merchant_company?.business_name || 'Merchant company'} · {staff.merchant_company?.market?.name || 'Market not set'}
                      </p>
                      <p className="text-sm text-gray-600 mt-1">
                        Scope: {staff.is_company_wide ? 'Company-wide' : 'Branch-specific'}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {(staff.assigned_branches || []).map(branch => (
                          <span key={branch.id} className="rounded-full border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-600">
                            {branch.branch_name || branch.name} · {branch.city || 'City not set'}
                          </span>
                        ))}
                        {!staff.is_company_wide && !staff.assigned_branches?.length && (
                          <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-700">
                            Branch assignment required before activation
                          </span>
                        )}
                      </div>

                      <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
                        <p className="text-sm font-semibold text-amber-900">Market document rules</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {requirements.map(requirement => (
                            <span key={requirement} className="rounded-full bg-white/80 px-2 py-1 text-xs text-amber-800">
                              {requirement}
                            </span>
                          ))}
                        </div>
                        {!staff.merchant_company?.market && (
                          <p className="mt-2 text-xs text-amber-800">No market is configured for this merchant company. Use global staff identity requirements until market rules are configured.</p>
                        )}
                      </div>

                      {staff.verification_rejection_reason && (
                        <p className="text-sm text-red-600 mt-3"><strong>Decision reason:</strong> {staff.verification_rejection_reason}</p>
                      )}

                      <VerificationDocuments
                        documentsPayload={documentsPayload}
                        isLoading={staffDocumentsQuery.isLoading}
                        isError={staffDocumentsQuery.isError}
                        onReview={reviewStaffDocument}
                        updatingId={updatingId}
                        rejectionReasons={documentRejectionReasons}
                        setRejectionReasons={setDocumentRejectionReasons}
                      />

                      <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-4">
                        <p className="text-sm font-semibold text-gray-950">Audit timeline</p>
                        {auditItems.length ? (
                          <div className="mt-3 space-y-2">
                            {auditItems.map((item, index) => (
                              <div key={`${item.label}-${index}`} className="border-l-2 border-gray-300 pl-3">
                                <p className="text-sm font-medium text-gray-900">{item.label}</p>
                                <p className="text-xs text-gray-500">{item.actor || 'Operations'} · {formatDateTime(item.value)}</p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="mt-3 text-sm text-gray-500">No verification decisions recorded yet.</p>
                        )}
                      </div>
                    </div>

                    <div className="xl:w-80 space-y-3">
                      <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-600">
                        <p>Submitted {formatDateTime(staff.submitted_at)}</p>
                        <p>Reviewed {formatDateTime(staff.reviewed_at)}</p>
                        <p>Reviewer {staff.reviewed_by?.username || 'Not reviewed yet'}</p>
                        <p className="mt-2">Created {formatDateTime(staff.created_at)}</p>
                        <p>Updated {formatDateTime(staff.updated_at)}</p>
                      </div>
                      <textarea
                        className="input-field resize-none"
                        rows={3}
                        placeholder="T-Food verification decision note"
                        value={staffDecisionReasons[staff.id] || ''}
                        onChange={event => setStaffDecisionReasons(current => ({ ...current, [staff.id]: event.target.value }))}
                      />
                      <button
                        type="button"
                        disabled={updatingId === `staff-${staff.id}-APPROVE` || isVerified}
                        onClick={() => setStaffVerification(staff, 'APPROVE')}
                        className="btn-primary w-full text-sm inline-flex items-center justify-center gap-2"
                      >
                        <CheckCircle2 size={16} /> Approve
                      </button>
                      <div className="grid grid-cols-1 gap-2">
                        <button
                          type="button"
                          disabled={updatingId === `staff-${staff.id}-REJECT`}
                          onClick={() => setStaffVerification(staff, 'REJECT')}
                          className="btn-secondary text-sm text-red-600 inline-flex items-center justify-center gap-2"
                        >
                          <XCircle size={16} /> Reject
                        </button>
                        <button
                          type="button"
                          disabled={updatingId === `staff-${staff.id}-SUSPEND`}
                          onClick={() => setStaffVerification(staff, 'SUSPEND')}
                          className="btn-secondary text-sm text-red-600 inline-flex items-center justify-center gap-2"
                        >
                          <XCircle size={16} /> Suspend
                        </button>
                        <button
                          type="button"
                          disabled={updatingId === `staff-${staff.id}-REQUEST_MORE_INFO`}
                          onClick={() => setStaffVerification(staff, 'REQUEST_MORE_INFO')}
                          className="btn-secondary text-sm inline-flex items-center justify-center gap-2"
                        >
                          <Clock3 size={16} /> Request More Information
                        </button>
                      </div>
                    </div>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </section>
      )}

      {showMerchantApplications && (
      <section>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-950">{merchantFilterLocked ? 'Pending merchants' : 'Merchant applications'}</h2>
            <p className="text-sm text-gray-500">{merchantFilterLocked ? `${visibleMerchants.length} merchants are pending verification or approval.` : 'Approval publishes every storefront owned by the merchant.'}</p>
          </div>
          {!merchantFilterLocked && <div className="inline-flex self-start bg-gray-100 rounded-lg p-1" aria-label="Merchant filter">
            {['pending', 'verified', 'rejected', 'suspended', 'all'].map(option => (
              <button
                key={option}
                type="button"
                onClick={() => setFilter(option)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium capitalize ${filter === option ? 'bg-white text-gray-950 shadow-sm' : 'text-gray-500'}`}
              >
                {option}
              </button>
            ))}
          </div>}
        </div>

        {visibleMerchants.length === 0 ? (
          <div className="border border-dashed border-gray-300 rounded-lg py-12 text-center text-gray-500">No merchants in this queue.</div>
        ) : (
          <div className="space-y-3">
            {visibleMerchants.map(merchant => {
              const requirementsMet = merchantRequirementsMet(merchant.document_summary)
              const documentsPayload = merchantDocumentsQuery.data?.[merchant.id]
              return (
              <article key={merchant.id} className="bg-white border border-gray-200 rounded-lg p-5">
                <div className="flex flex-col lg:flex-row lg:items-start gap-5">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold text-gray-950">{merchant.business_name || merchant.owner_name}</h3>
                    <span className={`text-xs font-medium px-2 py-1 rounded-full ${merchant.is_verified ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                      {merchant.is_verified ? 'Verified' : verificationStatusLabels[merchant.verification_status] || 'Awaiting review'}
                    </span>
                    <span className="text-xs text-gray-500">Merchant</span>
                  </div>
                  <p className="text-sm text-gray-500 mt-1">{formatMerchantContact(merchant)}</p>
                  <p className="text-sm text-gray-600 mt-2">
                    Profile: {merchant.is_verified ? 'Verified merchant' : verificationStatusLabels[merchant.verification_status] || 'Verification pending'} · {merchant.restaurants.length} branches/storefronts
                  </p>
                  <p className="text-sm text-gray-600 mt-2">
                    {merchant.restaurants.length
                      ? merchant.restaurants.map(store => `${store.name}, ${store.city}`).join(' · ')
                      : 'Storefront details not submitted yet'}
                  </p>
                  {merchant.verification_rejection_reason && (
                    <p className="text-sm text-red-600 mt-2">Last rejection: {merchant.verification_rejection_reason}</p>
                  )}
                  <div className="flex flex-wrap gap-2 mt-3">
                    <RequirementPill done={merchant.document_summary?.has_owner_profile_photo} label="Owner photo" />
                    <RequirementPill done={merchant.document_summary?.has_identity_document} label="Identity document" />
                    <RequirementPill done={merchant.document_summary?.has_restaurant_photo} label="Restaurant photo" />
                  </div>
                </div>
                <div className="flex flex-col gap-2 lg:w-72">
                  {!merchant.is_verified && (
                    <input
                      className="input-field"
                          placeholder="T-Food applicant rejection reason"
                      value={merchantRejectionReasons[merchant.id] || ''}
                      onChange={event => setMerchantRejectionReasons(current => ({ ...current, [merchant.id]: event.target.value }))}
                    />
                  )}
                  {merchant.is_verified ? (
                    <button
                      type="button"
                      disabled={updatingId === merchant.id}
                      onClick={() => setVerification(merchant, false)}
                      className="btn-secondary inline-flex items-center gap-2 text-sm text-red-600"
                    ><XCircle size={17} /> Suspend</button>
                  ) : (
                    <div className="grid sm:grid-cols-2 lg:grid-cols-1 gap-2">
                    <button
                      type="button"
                      disabled={updatingId === merchant.id || !requirementsMet}
                      onClick={() => setVerification(merchant, true)}
                      className="btn-primary inline-flex items-center justify-center gap-2 text-sm"
                    ><CheckCircle2 size={17} /> Approve merchant</button>
                    <button
                      type="button"
                      disabled={updatingId === merchant.id}
                      onClick={() => setVerification(merchant, false)}
                      className="btn-secondary inline-flex items-center justify-center gap-2 text-sm text-red-600"
                    ><XCircle size={17} /> Reject merchant</button>
                    {!requirementsMet && <p className="text-xs text-amber-700">Approval blocked: owner photo, identity document, and restaurant photo are required.</p>}
                    </div>
                  )}
                </div>
                </div>
                <VerificationDocuments
                  documentsPayload={documentsPayload}
                  isLoading={merchantDocumentsQuery.isLoading}
                  isError={merchantDocumentsQuery.isError}
                  onReview={reviewDocument}
                  updatingId={updatingId}
                  rejectionReasons={documentRejectionReasons}
                  setRejectionReasons={setDocumentRejectionReasons}
                />
              </article>
              )
            })}
          </div>
        )}
      </section>
      )}

      {showPartnerApplications && (
      <section>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-950">{partnerFilterLocked ? 'Pending partners' : 'Delivery partner applications'}</h2>
            <p className="text-sm text-gray-500">{partnerFilterLocked ? `${visiblePartners.length} delivery partners are pending verification or approval.` : 'Only approved and available partners can receive assignments.'}</p>
          </div>
          {!partnerFilterLocked && <div className="inline-flex self-start bg-gray-100 rounded-lg p-1" aria-label="Partner filter">
            {['pending', 'verified', 'rejected', 'suspended', 'all'].map(option => (
              <button
                key={option}
                type="button"
                onClick={() => setPartnerFilter(option)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium capitalize ${partnerFilter === option ? 'bg-white text-gray-950 shadow-sm' : 'text-gray-500'}`}
              >{option}</button>
            ))}
          </div>}
        </div>

        {visiblePartners.length === 0 ? (
          <div className="border border-dashed border-gray-300 rounded-lg py-12 text-center text-gray-500">No delivery partners in this queue.</div>
        ) : (
          <div className="space-y-3">
            {visiblePartners.map(partner => {
              const requirementsMet = partnerRequirementsMet(partner.document_summary)
              const documentsPayload = partnerDocumentsQuery.data?.[partner.id]
              const hasVehicleDocument = Boolean((documentsPayload?.results || documentsPayload || []).some(document => document.document_type === 'VEHICLE_DOCUMENT'))
              return (
              <article key={partner.id} className="bg-white border border-gray-200 rounded-lg p-5">
                <div className="flex flex-col lg:flex-row lg:items-start gap-5">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold text-gray-950">{partner.partner_name || partner.owner_name}</h3>
                    <span className={`text-xs font-medium px-2 py-1 rounded-full ${partner.is_verified ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                      {partner.is_verified ? 'Verified' : verificationStatusLabels[partner.verification_status] || 'Awaiting review'}
                    </span>
                    <span className="text-xs text-gray-500">Delivery partner</span>
                  </div>
                  <p className="text-sm text-gray-500 mt-1">{formatPartnerContact(partner)}</p>
                  <p className="text-sm text-gray-600 mt-2">{formatPartnerTransport(partner)}</p>
                  {partner.verification_rejection_reason && (
                    <p className="text-sm text-red-600 mt-2">Last rejection: {partner.verification_rejection_reason}</p>
                  )}
                  <div className="flex flex-wrap gap-2 mt-3">
                    <RequirementPill done={partner.document_summary?.has_partner_profile_photo} label="Profile photo" />
                    <RequirementPill done={partner.document_summary?.has_identity_document} label="ID or license" />
                    <RequirementPill done={hasVehicleDocument} label="Vehicle document" optional />
                  </div>
                </div>
                <div className="flex flex-col gap-2 lg:w-72">
                {!partner.is_verified && (
                  <input
                    className="input-field"
                    placeholder="T-Food applicant rejection reason"
                    value={partnerRejectionReasons[partner.id] || ''}
                    onChange={event => setPartnerRejectionReasons(current => ({ ...current, [partner.id]: event.target.value }))}
                  />
                )}
                {partner.is_verified ? (
                  <button
                    type="button"
                    disabled={updatingId === `partner-${partner.id}`}
                    onClick={() => setPartnerVerification(partner, false)}
                    className="btn-secondary inline-flex items-center justify-center gap-2 text-sm text-red-600"
                  ><XCircle size={17} /> Suspend</button>
                ) : (
                  <div className="grid sm:grid-cols-2 lg:grid-cols-1 gap-2">
                  <button
                    type="button"
                    disabled={updatingId === `partner-${partner.id}` || !requirementsMet}
                    onClick={() => setPartnerVerification(partner, true)}
                    className="btn-primary inline-flex items-center justify-center gap-2 text-sm"
                  ><CheckCircle2 size={17} /> Approve partner</button>
                  <button
                    type="button"
                    disabled={updatingId === `partner-${partner.id}`}
                    onClick={() => setPartnerVerification(partner, false)}
                    className="btn-secondary inline-flex items-center justify-center gap-2 text-sm text-red-600"
                  ><XCircle size={17} /> Reject partner</button>
                  {!requirementsMet && <p className="text-xs text-amber-700">Approval blocked: partner profile photo and ID or license document are required.</p>}
                  </div>
                )}
                </div>
                </div>
                <VerificationDocuments
                  documentsPayload={documentsPayload}
                  isLoading={partnerDocumentsQuery.isLoading}
                  isError={partnerDocumentsQuery.isError}
                  onReview={reviewDocument}
                  updatingId={updatingId}
                  rejectionReasons={documentRejectionReasons}
                  setRejectionReasons={setDocumentRejectionReasons}
                />
              </article>
              )
            })}
          </div>
        )}
      </section>
      )}
    </div>
  )
}
