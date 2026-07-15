import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Bike, CheckCircle2, CircleDollarSign, Clock, Copy, FileText, LocateFixed, MapPin, Navigation, Package, Phone, ShieldCheck, Trash2, UploadCloud, XCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { claimAvailableDelivery, getPartnerEarnings, listAvailableDeliveries, listPartnerDeliveries, listPartnerMerchantInvites, updateAvailabilityLocation, updateDeliveryLocation, updateDeliveryStatus } from '../api/delivery'
import { getPartnerProfile, updatePartnerProfile } from '../api/auth'
import {
  deletePartnerVerificationDocument,
  listPartnerVerificationDocuments,
  uploadPartnerVerificationDocument,
} from '../api/verifications'
import { openPrivateMedia } from '../api/media'
import { usePreferences } from '../context/PreferencesContext'
import { formatCurrency } from '../lib/formatters'
import { statusLabel } from '../lib/statusLabels'
import useRealtime from '../hooks/useRealtime'
import useTitle from '../hooks/useTitle'

const nextActions = {
  ASSIGNED: { status: 'PICKED_UP', labelKey: 'partner.actions.confirmPickup' },
  PICKED_UP: { status: 'ON_THE_WAY', labelKey: 'partner.actions.startTrip' },
  ON_THE_WAY: { status: 'DELIVERED', labelKey: 'partner.actions.confirmDelivery' },
}

const partnerDocumentTypes = [
  { value: 'PARTNER_PROFILE_PHOTO', labelKey: 'partner.verification.partnerProfilePhoto' },
  { value: 'NATIONAL_ID', labelKey: 'partner.verification.nationalId' },
  { value: 'PASSPORT', labelKey: 'partner.verification.passport' },
  { value: 'DRIVING_LICENSE', labelKey: 'partner.verification.drivingLicense' },
  { value: 'VEHICLE_DOCUMENT', labelKey: 'partner.verification.vehicleDocumentOptional' },
]
const partnerIdentityDocumentTypes = ['NATIONAL_ID', 'PASSPORT', 'DRIVING_LICENSE']
const verificationStatusLabels = {
  PENDING: 'statuses.common.PENDING',
  SUBMITTED: 'statuses.verification.SUBMITTED',
  APPROVED: 'statuses.verification.VERIFIED',
  REJECTED: 'statuses.verification.REJECTED',
  SUSPENDED: 'statuses.verification.SUSPENDED',
}
const emptyVerificationForm = {
  document_type: 'PARTNER_PROFILE_PHOTO',
  file: null,
  notes: '',
}
const emptyContactForm = {
  partner_phone: '',
  transport_details: '',
}

const formatDocumentType = (value, t) => (
  t(partnerDocumentTypes.find(type => type.value === value)?.labelKey || 'partner.verification.document')
)

const formatDateTime = value => {
  if (!value) return ''
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

const merchantRiderInvitationLink = token => {
  if (!token) return ''
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  return `${origin}/register?role=partner&rider_invite=${encodeURIComponent(token)}`
}

const pickupMapsUrl = delivery => {
  if (delivery.pickup_latitude && delivery.pickup_longitude) {
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${delivery.pickup_latitude},${delivery.pickup_longitude}`)}`
  }
  if (delivery.pickup_address) {
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(delivery.pickup_address)}`
  }
  return ''
}

function PickupDetails({ delivery, compact = false }) {
  const { t } = useTranslation()
  const mapsUrl = pickupMapsUrl(delivery)
  const pickupName = delivery.pickup_branch_name || delivery.restaurant_name || t('partner.pickupBranchUnavailable')
  const distance = delivery.pickup_distance_km

  return (
    <div className={`rounded-lg border border-gray-200 bg-gray-50 ${compact ? 'mt-3 p-3' : 'mt-4 p-4'}`}>
      <p className="text-xs font-semibold uppercase text-gray-500">{t('partner.pickupFrom')}</p>
      <p className="mt-1 font-semibold text-gray-950">{pickupName}</p>
      {delivery.pickup_address && (
        <p className="mt-2 flex items-start gap-2 text-sm text-gray-600">
          <MapPin size={15} className="mt-0.5 flex-shrink-0 text-brand-600" />
          <span>{delivery.pickup_address}</span>
        </p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-2.5 py-1 text-gray-700">
          <Navigation size={14} className="text-brand-600" />
          {distance == null
            ? t('partner.pickupDistanceUnavailable')
            : t('partner.kmToPickup', { distance })}
        </span>
        {delivery.pickup_phone ? (
          <a
            href={`tel:${delivery.pickup_phone}`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-2.5 py-1 font-medium text-brand-700 hover:bg-brand-50"
          >
            <Phone size={14} />
            {delivery.pickup_phone}
          </a>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1 text-amber-700">
            <Phone size={14} />
            {t('partner.pickupPhoneUnavailable')}
          </span>
        )}
        {mapsUrl && (
          <a
            href={mapsUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-2.5 py-1 font-medium text-brand-700 hover:bg-brand-50"
          >
            <MapPin size={14} />
            {t('partner.openInMaps')}
          </a>
        )}
      </div>
    </div>
  )
}

const documentStatusClass = status => {
  if (status === 'APPROVED') return 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (status === 'REJECTED') return 'bg-red-50 text-red-700 border-red-200'
  if (status === 'SUBMITTED' || status === 'PENDING') return 'bg-amber-50 text-amber-700 border-amber-200'
  return 'bg-gray-50 text-gray-700 border-gray-200'
}

function ChecklistItem({ done, label, help, optional = false }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-gray-200 p-3">
      {done
        ? <CheckCircle2 size={18} className="mt-0.5 flex-shrink-0 text-emerald-600" />
        : optional
          ? <Clock size={18} className="mt-0.5 flex-shrink-0 text-gray-400" />
          : <XCircle size={18} className="mt-0.5 flex-shrink-0 text-amber-600" />}
      <div>
        <p className="text-sm font-medium text-gray-900">{label}</p>
        <p className="text-xs text-gray-500 mt-1">{help}</p>
      </div>
    </div>
  )
}

function PartnerStatCard({ label, value, accent = 'text-gray-950', onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="border border-gray-200 rounded-lg p-4 text-left transition hover:border-brand-300 hover:bg-brand-50/40 focus:outline-none focus:ring-2 focus:ring-brand-500"
    >
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-xl font-bold mt-1 ${accent}`}>{value}</p>
    </button>
  )
}

function PartnerSectionCard({ active, icon: Icon, label, value, detail, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg border p-4 text-left transition focus:outline-none focus:ring-2 focus:ring-brand-500 ${
        active
          ? 'border-brand-500 bg-brand-50 shadow-sm'
          : 'border-gray-200 bg-white hover:border-brand-300 hover:bg-brand-50/40'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-gray-950">{label}</p>
          <p className="mt-2 text-2xl font-bold text-gray-950">{value}</p>
          {detail && <p className="mt-1 text-xs text-gray-500">{detail}</p>}
        </div>
        <Icon size={18} className={active ? 'text-brand-700' : 'text-brand-600'} />
      </div>
    </button>
  )
}

function PartnerVerificationPanel({
  profile,
  documentsQuery,
  contactForm,
  setContactForm,
  onSaveContact,
  savingContact,
  form,
  setForm,
  onUpload,
  uploading,
  onDelete,
  deletingId,
}) {
  const { t } = useTranslation()
  const documentsPayload = documentsQuery.data
  const documents = documentsPayload?.results || documentsPayload || []
  const summary = documentsPayload?.summary || {}
  const uploadedTypes = new Set(documents.map(document => document.document_type))
  const hasProfilePhoto = summary.has_partner_profile_photo ?? uploadedTypes.has('PARTNER_PROFILE_PHOTO')
  const hasIdentityDocument = summary.has_identity_document ?? partnerIdentityDocumentTypes.some(type => uploadedTypes.has(type))
  const hasVehicleDocument = uploadedTypes.has('VEHICLE_DOCUMENT')
  const status = profile?.verification_status || (profile?.is_verified ? 'APPROVED' : 'PENDING')
  const statusText = t(verificationStatusLabels[status] || 'statuses.common.PENDING')
  const missing = [
    !hasProfilePhoto && t('partner.verification.partnerProfilePhoto'),
    !hasIdentityDocument && t('partner.verification.identityOrLicense'),
  ].filter(Boolean)

  return (
    <section className="mb-8 border-b border-gray-200 pb-6">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5 mb-5">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck size={20} className="text-brand-600" />
            <h2 className="text-xl font-semibold text-gray-950">{t('partner.verification.title')}</h2>
          </div>
          <p className="text-sm text-gray-500 mt-2 max-w-2xl">
            {t('partner.verification.description')}
          </p>
        </div>
        <span className={`inline-flex w-fit items-center rounded-full border px-3 py-1 text-sm font-medium ${documentStatusClass(status)}`}>
          {statusText}
        </span>
      </div>

      {profile?.verification_rejection_reason && (
        <div className="mb-5 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <p className="font-medium">{t('partner.verification.reviewNote')}</p>
          <p className="mt-1">{profile.verification_rejection_reason}</p>
        </div>
      )}

      {!profile?.is_verified && (
        <div className="mb-5 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <p className="font-medium text-amber-950">{t('partner.verification.missingTitle')}</p>
          {missing.length ? (
            <p className="mt-1">{t('partner.verification.uploadMissing', { items: missing.join(', ') })}</p>
          ) : (
            <p className="mt-1">{t('partner.verification.requiredUploaded')}</p>
          )}
        </div>
      )}

      <form onSubmit={onSaveContact} className="mb-6 rounded-lg border border-gray-200 p-4">
        <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3 mb-4">
          <div>
            <h3 className="font-semibold text-gray-950">{t('partner.verification.contactTitle')}</h3>
            <p className="text-sm text-gray-500 mt-1">{t('partner.verification.contactDescription')}</p>
          </div>
          <span className="rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs font-medium text-gray-600">
            {profile?.user?.email || t('partner.verification.emailMissing')}
          </span>
        </div>
        <div className="grid md:grid-cols-[1fr_1fr_auto] gap-3 items-end">
          <label className="text-sm font-medium text-gray-700">
            {t('partner.verification.phone')}
            <input
              className="input-field mt-1"
              value={contactForm.partner_phone}
              placeholder="+224 620 00 00 00"
              onChange={event => setContactForm(current => ({ ...current, partner_phone: event.target.value }))}
            />
          </label>
          <label className="text-sm font-medium text-gray-700">
            {t('partner.verification.transportDetails')}
            <input
              className="input-field mt-1"
              value={contactForm.transport_details}
              placeholder={t('partner.verification.transportPlaceholder')}
              onChange={event => setContactForm(current => ({ ...current, transport_details: event.target.value }))}
            />
          </label>
          <button type="submit" disabled={savingContact} className="btn-secondary px-4 py-2">
            {savingContact ? t('common.saving') : t('common.save')}
          </button>
        </div>
        {(!profile?.partner_phone || !profile?.transport_details) && (
          <p className="mt-3 text-xs text-amber-700">{t('partner.verification.contactSetupGap')}</p>
        )}
      </form>

      <div className="grid lg:grid-cols-3 gap-3 mb-6">
        <ChecklistItem
          done={hasProfilePhoto}
          label={t('partner.verification.partnerProfilePhoto')}
          help={t('partner.verification.partnerProfilePhotoHelp')}
        />
        <ChecklistItem
          done={hasIdentityDocument}
          label={t('partner.verification.identityOrLicense')}
          help={t('partner.verification.identityOrLicenseHelp')}
        />
        <ChecklistItem
          done={hasVehicleDocument}
          label={t('partner.verification.vehicleDocument')}
          help={t('partner.verification.vehicleDocumentHelp')}
          optional
        />
      </div>

      <form onSubmit={onUpload} className="grid lg:grid-cols-[220px_1fr_1fr_auto] gap-3 items-end rounded-lg border border-gray-200 p-4 mb-6">
        <label className="text-sm font-medium text-gray-700">
          {t('partner.verification.documentType')}
          <select
            className="input-field mt-1"
            value={form.document_type}
            onChange={event => setForm(current => ({ ...current, document_type: event.target.value }))}
          >
            {partnerDocumentTypes.map(type => <option key={type.value} value={type.value}>{t(type.labelKey)}</option>)}
          </select>
        </label>
        <label className="text-sm font-medium text-gray-700">
          {t('partner.verification.uploadFile')}
          <span className="mt-1 flex min-h-[42px] items-center gap-2 rounded-lg border border-dashed border-gray-300 px-3 text-sm text-gray-600 cursor-pointer hover:bg-gray-50">
            <UploadCloud size={16} className="text-brand-600" />
            <span className="truncate">{form.file?.name || t('partner.verification.chooseImageOrDocument')}</span>
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
          {t('partner.verification.noteForReviewer')}
          <input
            className="input-field mt-1"
            placeholder={t('partner.verification.notePlaceholder')}
            value={form.notes}
            onChange={event => setForm(current => ({ ...current, notes: event.target.value }))}
          />
        </label>
        <button type="submit" disabled={uploading} className="btn-primary inline-flex items-center justify-center gap-2">
          <UploadCloud size={16} /> {uploading ? t('partner.verification.uploading') : t('partner.verification.upload')}
        </button>
      </form>

      <div className="rounded-lg border border-gray-200 divide-y divide-gray-200">
        {documentsQuery.isLoading && <p className="p-4 text-sm text-gray-500">{t('partner.verification.loadingDocuments')}</p>}
        {documentsQuery.isError && <p className="p-4 text-sm text-red-600">{t('partner.verification.loadDocumentsFailed')}</p>}
        {!documentsQuery.isLoading && !documents.length && (
          <p className="p-4 text-sm text-gray-500">{t('partner.verification.noDocuments')}</p>
        )}
        {documents.map(document => {
          const canDelete = document.status === 'PENDING' || document.status === 'REJECTED'
          return (
            <div key={document.id} className="p-4 flex flex-col md:flex-row md:items-start md:justify-between gap-3">
              <div className="flex items-start gap-3">
                <FileText size={18} className="mt-1 flex-shrink-0 text-brand-600" />
                <div>
                  <p className="font-medium text-gray-950">{formatDocumentType(document.document_type, t)}</p>
                  <p className="text-xs text-gray-500 mt-1">{t('partner.verification.uploadedAt', { date: formatDateTime(document.created_at) })}</p>
                  {document.rejection_reason && (
                    <p className="mt-2 text-sm text-red-600">{t('partner.verification.rejectedReason', { reason: document.rejection_reason })}</p>
                  )}
                  {document.file_url && (
                    <button type="button" onClick={() => openPrivateMedia(document.file_url)} className="mt-2 inline-block text-left text-sm font-medium text-brand-700 hover:underline">
                      {t('partner.verification.viewUploadedFile')}
                    </button>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${documentStatusClass(document.status)}`}>
                  {statusLabel(document.status, t, 'verification')}
                </span>
                {canDelete && (
                  <button
                    type="button"
                    onClick={() => onDelete(document)}
                    disabled={deletingId === document.id}
                    className="p-2 text-red-500 hover:bg-red-50 rounded-lg"
                    title={t('partner.verification.deleteDocument')}
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

function MerchantInvitationPanel({ invites, onCopyLink }) {
  if (!invites.length) return null

  return (
    <section className="mb-8 rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-950">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Merchant invitations</h2>
          <p className="mt-1 text-sm text-amber-800">
            A merchant invited you to deliver for their storefront. Open the invitation link and confirm the details; T-Food Operations will approve the merchant rider relationship before it becomes active.
          </p>
        </div>
        <span className="w-fit rounded-full border border-amber-300 bg-white px-3 py-1 text-xs font-semibold text-amber-800">
          {invites.length} pending
        </span>
      </div>
      <div className="mt-4 space-y-3">
        {invites.map(invite => {
          const branch = invite.home_restaurant_detail
          const merchantName = invite.merchant?.business_name || 'T-Food merchant'
          const link = merchantRiderInvitationLink(invite.invite_token)
          return (
            <article key={invite.id} className="rounded-lg border border-amber-200 bg-white p-4">
              <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
                <div>
                  <p className="font-semibold text-gray-950">Invitation from {merchantName}</p>
                  <p className="mt-1 text-sm text-gray-600">
                    {branch?.branch_name || branch?.name || 'Storefront not selected yet'}
                    {branch?.city ? ` · ${branch.city}` : ''}
                    {branch?.area ? ` · ${branch.area}` : ''}
                  </p>
                  <p className="mt-2 text-sm text-gray-600">
                    Your platform rider approval remains active. This merchant assignment still needs your confirmation and T-Food Operations approval.
                  </p>
                  {invite.expires_at && (
                    <p className="mt-2 text-xs text-gray-500">Expires {formatDateTime(invite.expires_at)}</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => onCopyLink(link)}
                  className="btn-secondary inline-flex items-center justify-center gap-2"
                >
                  <Copy size={16} /> Copy invitation link
                </button>
              </div>
              <p className="mt-3 break-all rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600">
                {link}
              </p>
            </article>
          )
        })}
      </div>
    </section>
  )
}

export default function PartnerDashboardPage() {
  const { t } = useTranslation()
  useTitle(t('partner.title'))
  const queryClient = useQueryClient()
  const { preferences } = usePreferences()
  const [trackingId, setTrackingId] = useState(null)
  const [updatingDeliveryId, setUpdatingDeliveryId] = useState(null)
  const [confirmationCodes, setConfirmationCodes] = useState({})
  const [updatingAvailabilityLocation, setUpdatingAvailabilityLocation] = useState(false)
  const [verificationForm, setVerificationForm] = useState(emptyVerificationForm)
  const [contactForm, setContactForm] = useState(emptyContactForm)
  const [uploadingVerification, setUploadingVerification] = useState(false)
  const [savingContact, setSavingContact] = useState(false)
  const [deletingVerificationId, setDeletingVerificationId] = useState(null)
  const [activeSection, setActiveSection] = useState('pickups')
  const watchId = useRef(null)
  const lastLocationSent = useRef(0)
  const deliveryHistoryRef = useRef(null)
  const profileQuery = useQuery({
    queryKey: ['partner-profile'],
    queryFn: async () => (await getPartnerProfile()).data,
    refetchInterval: 5000,
  })
  const { data, isLoading, isError } = useQuery({
    queryKey: ['partner-deliveries'],
    queryFn: async () => (await listPartnerDeliveries()).data,
    enabled: profileQuery.data?.is_verified === true,
    refetchInterval: 5000,
  })
  const availableQuery = useQuery({
    queryKey: ['available-deliveries'],
    queryFn: async () => (await listAvailableDeliveries()).data,
    enabled: profileQuery.data?.is_verified === true,
    refetchInterval: 5000,
  })
  const earningsQuery = useQuery({
    queryKey: ['partner-earnings'],
    queryFn: async () => (await getPartnerEarnings()).data,
    enabled: profileQuery.data?.is_verified === true,
    refetchInterval: 5000,
  })
  const partnerVerificationQuery = useQuery({
    queryKey: ['partner-verification-documents'],
    queryFn: async () => (await listPartnerVerificationDocuments()).data,
    enabled: profileQuery.isSuccess,
  })
  const merchantInvitesQuery = useQuery({
    queryKey: ['partner-merchant-invites'],
    queryFn: async () => (await listPartnerMerchantInvites()).data,
    enabled: profileQuery.isSuccess,
    refetchInterval: 10000,
  })

  const deliveries = data?.results || data || []
  const merchantInvites = merchantInvitesQuery.data?.results || merchantInvitesQuery.data || []
  const availableDeliveries = [...(availableQuery.data?.results || availableQuery.data || [])].sort((left, right) => (
    (left.pickup_distance_km ?? Number.POSITIVE_INFINITY) - (right.pickup_distance_km ?? Number.POSITIVE_INFINITY)
  ))
  const activeDeliveries = deliveries.filter(delivery => delivery.status !== 'DELIVERED')
  const completedDeliveries = deliveries.filter(delivery => delivery.status === 'DELIVERED')
  const partnerCurrency = earningsQuery.data?.currency || earningsQuery.data?.currency_code || 'GNF'
  const money = (value, currency = partnerCurrency) => formatCurrency(value, currency || 'GNF', preferences)
  const profile = profileQuery.data
  const verificationStatus = profile?.verification_status || (profile?.is_verified ? 'APPROVED' : 'PENDING')
  const verificationText = t(verificationStatusLabels[verificationStatus] || 'statuses.common.PENDING')
  const availabilityText = profile?.is_available ? t('partner.availableForAssignment') : t('partner.activeDeliveryInProgress')
  const activeSectionCards = [
    {
      key: 'verification',
      icon: ShieldCheck,
      label: t('partner.verification.title'),
      value: verificationText,
      detail: profile?.partner_phone || profile?.transport_details || profile?.user?.email,
    },
    {
      key: 'earnings',
      icon: CircleDollarSign,
      label: t('partner.earnings'),
      value: money(earningsQuery.data?.available_earnings || 0),
      detail: t('partner.completedJobs') + ': ' + (earningsQuery.data?.completed_deliveries || 0),
    },
    {
      key: 'pickups',
      icon: Package,
      label: t('partner.availablePickups'),
      value: availableDeliveries.length,
      detail: t('partner.sharedQueue'),
    },
    {
      key: 'active',
      icon: Bike,
      label: t('partner.activeDelivery'),
      value: activeDeliveries.length,
      detail: availabilityText,
    },
    {
      key: 'history',
      icon: CheckCircle2,
      label: t('partner.deliveryHistory'),
      value: completedDeliveries.length,
      detail: t('partner.completedJobs'),
    },
  ]
  const refreshPartnerDeliveries = () => queryClient.invalidateQueries({ queryKey: ['partner-deliveries'] })
  const refreshAvailableDeliveries = () => queryClient.invalidateQueries({ queryKey: ['available-deliveries'] })
  const refreshPartnerProfile = () => queryClient.invalidateQueries({ queryKey: ['partner-profile'] })
  const refreshPartnerEarnings = () => queryClient.invalidateQueries({ queryKey: ['partner-earnings'] })
  const refreshVerification = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: ['partner-verification-documents'] }),
    queryClient.invalidateQueries({ queryKey: ['partner-profile'] }),
  ])
  const realtime = useRealtime({
    enabled: profileQuery.data?.is_verified === true,
    onMessage: message => {
      if (message?.type === 'delivery.available_changed') {
        refreshAvailableDeliveries()
      }
      if (message?.type === 'delivery.status_changed') {
        refreshPartnerDeliveries()
        refreshPartnerProfile()
        refreshPartnerEarnings()
      }
    },
  })

  useEffect(() => () => {
    if (watchId.current != null) navigator.geolocation.clearWatch(watchId.current)
  }, [])

  useEffect(() => {
    if (!profileQuery.data) return
    setContactForm({
      partner_phone: profileQuery.data.partner_phone || '',
      transport_details: profileQuery.data.transport_details || '',
    })
  }, [profileQuery.data?.id, profileQuery.data?.partner_phone, profileQuery.data?.transport_details])

  useEffect(() => {
    if (activeDeliveries.length && activeSection === 'pickups') {
      setActiveSection('active')
    }
  }, [activeDeliveries.length, activeSection])

  const stopLiveTracking = () => {
    if (watchId.current != null) navigator.geolocation.clearWatch(watchId.current)
    watchId.current = null
    setTrackingId(null)
  }

  const startLiveTracking = deliveryId => {
    if (!navigator.geolocation) {
      toast.error(t('checkout.locationUnsupported'))
      return
    }
    stopLiveTracking()
    setTrackingId(deliveryId)
    watchId.current = navigator.geolocation.watchPosition(
      async position => {
        if (Date.now() - lastLocationSent.current < 5000) return
        lastLocationSent.current = Date.now()
        try {
          await updateDeliveryLocation(deliveryId, {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          })
          queryClient.invalidateQueries({ queryKey: ['partner-deliveries'] })
        } catch {
          stopLiveTracking()
          toast.error(t('partner.liveLocationStopped'))
        }
      },
      () => {
        stopLiveTracking()
        toast.error(t('checkout.locationFailed'))
      },
      { enableHighAccuracy: true, maximumAge: 3000, timeout: 10000 },
    )
    toast.success(t('partner.liveLocationStarted'))
  }

  const advanceDelivery = async (deliveryId, nextStatus) => {
    const confirmationCode = confirmationCodes[deliveryId] || ''
    if (nextStatus === 'DELIVERED' && !/^\d{6}$/.test(confirmationCode)) {
      toast.error('Enter the customer’s six-digit handoff code.')
      return
    }
    if (
      nextStatus === 'DELIVERED'
      && !window.confirm('Confirm that the order was handed to the customer? This completes the delivery.')
    ) return
    setUpdatingDeliveryId(deliveryId)
    try {
      await updateDeliveryStatus(deliveryId, nextStatus, confirmationCode)
      await queryClient.invalidateQueries({ queryKey: ['partner-deliveries'] })
      await queryClient.invalidateQueries({ queryKey: ['available-deliveries'] })
      await queryClient.invalidateQueries({ queryKey: ['partner-earnings'] })
      if (nextStatus === 'DELIVERED' && trackingId === deliveryId) stopLiveTracking()
      if (nextStatus === 'DELIVERED') {
        setConfirmationCodes(current => ({ ...current, [deliveryId]: '' }))
      }
      toast.success(
        nextStatus === 'PICKED_UP'
          ? t('partner.pickupConfirmed')
          : nextStatus === 'ON_THE_WAY' ? t('partner.tripStarted') : t('partner.deliveryCompleted')
      )
    } catch (error) {
      toast.error(
        error.response?.data?.confirmation_code?.[0]
        || error.response?.data?.status?.[0]
        || t('partner.updateDeliveryFailed')
      )
    } finally {
      setUpdatingDeliveryId(null)
    }
  }

  const claimDelivery = async deliveryId => {
    try {
      await claimAvailableDelivery(deliveryId)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['partner-deliveries'] }),
        queryClient.invalidateQueries({ queryKey: ['available-deliveries'] }),
        queryClient.invalidateQueries({ queryKey: ['partner-profile'] }),
      ])
      toast.success(t('partner.deliveryAccepted'))
    } catch (error) {
      toast.error(error.response?.data?.detail || t('partner.deliveryUnavailable'))
    }
  }

  const updateAvailability = () => {
    if (!navigator.geolocation) {
      toast.error(t('checkout.locationUnsupported'))
      return
    }
    setUpdatingAvailabilityLocation(true)
    navigator.geolocation.getCurrentPosition(
      async position => {
        try {
          await updateAvailabilityLocation({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          })
          await Promise.all([
            queryClient.invalidateQueries({ queryKey: ['partner-profile'] }),
            queryClient.invalidateQueries({ queryKey: ['available-deliveries'] }),
          ])
          toast.success(t('partner.availabilityUpdated'))
        } catch {
          toast.error(t('partner.availabilityUpdateFailed'))
        } finally {
          setUpdatingAvailabilityLocation(false)
        }
      },
      () => {
        setUpdatingAvailabilityLocation(false)
        toast.error(t('checkout.locationFailed'))
      },
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  const saveVerificationContact = async event => {
    event.preventDefault()
    setSavingContact(true)
    try {
      await updatePartnerProfile({
        partner_phone: contactForm.partner_phone.trim(),
        transport_details: contactForm.transport_details.trim(),
      })
      await refreshPartnerProfile()
      toast.success(t('partner.verification.contactSaved'))
    } catch (error) {
      toast.error(error.response?.data?.partner_phone?.[0] || error.response?.data?.transport_details?.[0] || t('partner.verification.contactSaveFailed'))
    } finally {
      setSavingContact(false)
    }
  }

  const uploadVerification = async event => {
    event.preventDefault()
    if (!verificationForm.file) {
      toast.error(t('partner.chooseVerificationFile'))
      return
    }
    setUploadingVerification(true)
    try {
      const form = new FormData()
      form.append('document_type', verificationForm.document_type)
      form.append('file', verificationForm.file)
      if (verificationForm.notes) form.append('notes', verificationForm.notes)
      await uploadPartnerVerificationDocument(form)
      setVerificationForm(emptyVerificationForm)
      await refreshVerification()
      toast.success(t('partner.verificationUploaded'))
    } catch (error) {
      toast.error(error.response?.data?.document_type?.[0] || error.response?.data?.file?.[0] || t('partner.verificationUploadFailed'))
    } finally {
      setUploadingVerification(false)
    }
  }

  const deleteVerification = async document => {
    setDeletingVerificationId(document.id)
    try {
      await deletePartnerVerificationDocument(document.id)
      await refreshVerification()
      toast.success(t('partner.verificationRemoved'))
    } catch (error) {
      toast.error(error.response?.data?.detail || t('partner.verificationDeleteFailed'))
    } finally {
      setDeletingVerificationId(null)
    }
  }

  const copyMerchantInviteLink = async link => {
    if (!link) {
      toast.error('No invitation link available yet.')
      return
    }
    try {
      await navigator.clipboard.writeText(link)
      toast.success('Invitation link copied')
    } catch {
      toast.error('Could not copy invitation link.')
    }
  }

  if (profileQuery.isLoading || (profileQuery.data?.is_verified && isLoading)) {
    return <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 text-gray-500">{t('partner.loadingDeliveries')}</div>
  }
  if (profileQuery.data && !profileQuery.data.is_verified) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-12">
        <div className="border border-amber-200 bg-amber-50 rounded-lg p-6">
          <Clock size={28} className="text-amber-700 mb-4" />
          <h1 className="text-xl font-semibold text-amber-950">{t('partner.approvalPending')}</h1>
          <p className="text-amber-800 mt-2">{t('partner.approvalPendingBody')}</p>
        </div>
        <div className="mt-8">
          <PartnerVerificationPanel
            profile={profileQuery.data}
            documentsQuery={partnerVerificationQuery}
            contactForm={contactForm}
            setContactForm={setContactForm}
            onSaveContact={saveVerificationContact}
            savingContact={savingContact}
            form={verificationForm}
            setForm={setVerificationForm}
            onUpload={uploadVerification}
            uploading={uploadingVerification}
            onDelete={deleteVerification}
            deletingId={deletingVerificationId}
          />
          <MerchantInvitationPanel invites={merchantInvites} onCopyLink={copyMerchantInviteLink} />
        </div>
      </div>
    )
  }
  if (isError) {
    return <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10 text-red-500">{t('partner.loadDeliveriesFailed')}</div>
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-950">{t('partner.title')}</h1>
        <p className="text-gray-500 mt-1">
          {t('partner.signedInAs')} <strong className="text-gray-700">{profileQuery.data?.partner_name}</strong>
          {' '}(@{profileQuery.data?.user?.username})
        </p>
        <p className="text-xs text-gray-400 mt-2">
          {realtime.isConnected ? t('tracking.liveConnected') : t('tracking.autoRefresh')}
        </p>
        <div className="flex flex-wrap items-center gap-2 mt-3">
          <span className={`inline-flex text-xs font-medium px-2 py-1 rounded-md ${profileQuery.data?.is_available ? 'bg-emerald-50 text-emerald-700' : 'bg-blue-50 text-blue-700'}`}>
            {profileQuery.data?.is_available ? t('partner.availableForAssignment') : t('partner.activeDeliveryInProgress')}
          </span>
          <button type="button" onClick={updateAvailability} disabled={updatingAvailabilityLocation} className="btn-secondary py-1.5 px-3 text-xs inline-flex items-center gap-1.5">
            <LocateFixed size={14} /> {updatingAvailabilityLocation ? t('account.updating') : t('partner.updateAvailabilityLocation')}
          </button>
          {profileQuery.data?.location_updated_at && <span className="text-xs text-gray-400">{t('partner.locationUpdated', { time: new Date(profileQuery.data.location_updated_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) })}</span>}
        </div>
      </div>

      <section className="mb-8">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {activeSectionCards.map(section => (
            <PartnerSectionCard
              key={section.key}
              active={activeSection === section.key}
              icon={section.icon}
              label={section.label}
              value={section.value}
              detail={section.detail}
              onClick={() => setActiveSection(section.key)}
            />
          ))}
        </div>
      </section>

      {activeSection === 'verification' && (
        <>
          <PartnerVerificationPanel
            profile={profileQuery.data}
            documentsQuery={partnerVerificationQuery}
            contactForm={contactForm}
            setContactForm={setContactForm}
            onSaveContact={saveVerificationContact}
            savingContact={savingContact}
            form={verificationForm}
            setForm={setVerificationForm}
            onUpload={uploadVerification}
            uploading={uploadingVerification}
            onDelete={deleteVerification}
            deletingId={deletingVerificationId}
          />

          <MerchantInvitationPanel invites={merchantInvites} onCopyLink={copyMerchantInviteLink} />
        </>
      )}

      {activeSection === 'earnings' && (
      <section className="mb-8">
        <h2 className="text-lg font-semibold text-gray-950 mb-3">{t('partner.earnings')}</h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <PartnerStatCard label={t('partner.availablePayout')} value={money(earningsQuery.data?.available_earnings || 0)} accent="text-emerald-700" onClick={() => setActiveSection('history')} />
          <PartnerStatCard label={t('partner.paidEarnings')} value={money(earningsQuery.data?.paid_earnings || 0)} onClick={() => setActiveSection('history')} />
          <PartnerStatCard label={t('partner.lifetimeEarnings')} value={money(earningsQuery.data?.lifetime_earnings || 0)} onClick={() => setActiveSection('history')} />
          <PartnerStatCard label={t('partner.completedJobs')} value={earningsQuery.data?.completed_deliveries || 0} onClick={() => setActiveSection('history')} />
        </div>
      </section>
      )}

      {activeSection === 'pickups' && (
      <section className="mb-8">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-gray-950">{t('partner.availablePickups')}</h2>
          <span className="text-sm text-gray-500">{t('partner.sharedQueue')}</span>
        </div>
        {!availableDeliveries.length ? (
          <p className="text-sm text-gray-500 mt-3 border border-dashed border-gray-300 rounded-lg p-4">
            {t('partner.noPickupWaiting')}
          </p>
        ) : (
          <div className="grid md:grid-cols-2 gap-3 mt-3">
            {availableDeliveries.map(delivery => (
              <article key={delivery.id} className="bg-white border border-amber-200 rounded-lg p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-gray-950">Order #{delivery.order_id} · {delivery.restaurant_name}</p>
                    <PickupDetails delivery={delivery} compact />
                    <p className="text-sm text-gray-600 mt-1"><strong>Drop-off:</strong> {delivery.delivery_address}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {delivery.offer_radius_km == null ? t('partner.openFallbackOffer') : t('partner.offerWave', { distance: delivery.offer_radius_km })}
                    </p>
                    <div className="text-sm text-gray-500 mt-2">{delivery.items.map(item => <p key={`${delivery.id}-${item.name}`}>{item.name} x {item.quantity}{item.selected_options?.length ? ` · ${item.selected_options.map(option => option.name).join(', ')}` : ''}</p>)}</div>
                  </div>
                  <p className="font-semibold whitespace-nowrap">{money(delivery.total_amount, delivery.currency || delivery.currency_code || partnerCurrency)}</p>
                </div>
                <button type="button" onClick={() => claimDelivery(delivery.id)} className="btn-primary w-full mt-4">{t('partner.acceptDelivery')}</button>
              </article>
            ))}
          </div>
        )}
      </section>
      )}

      {activeSection === 'active' && (
      <section>
        <h2 className="text-lg font-semibold text-gray-950 mb-3">{t('partner.activeDelivery')}</h2>
      {!activeDeliveries.length ? (
        <div className="py-12 text-center border border-dashed border-gray-300 rounded-lg">
          <Bike size={42} className="text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900">{t('partner.noActiveDelivery')}</h3>
          <p className="text-gray-500 mt-2">{t('partner.assignedOnly', { username: profileQuery.data?.user?.username })}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {activeDeliveries.map(delivery => {
            const action = nextActions[delivery.status]
            return (
              <article key={delivery.id} className="card p-5">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <Package size={18} className="text-brand-600" />
                      <h2 className="font-semibold text-gray-950">Order #{delivery.order_id}</h2>
                    </div>
                    <p className="text-sm text-gray-500 mt-2">{t('partner.customerValue', { customer: delivery.customer_name })}</p>
                    <div className="text-sm text-gray-500 mt-1">
                      {delivery.items.map(item => <p key={`${delivery.id}-${item.name}`}>{item.name} x {item.quantity}{item.selected_options?.length ? ` · ${item.selected_options.map(option => option.name).join(', ')}` : ''}</p>)}
                    </div>
                    <PickupDetails delivery={delivery} />
                    {delivery.delivery_address && (
                      <p className="text-sm text-gray-500 mt-3">
                        <strong>{t('partner.dropoff')}:</strong> {delivery.delivery_address}
                      </p>
                    )}
                    {delivery.payment_method === 'COD' && delivery.payment_status === 'PENDING' && (
                      <p className="text-sm font-semibold text-amber-700 mt-2">
                        {t('partner.collectCash', { amount: money(delivery.total_amount, delivery.currency || delivery.currency_code || partnerCurrency) })}
                      </p>
                    )}
                    <p className="text-sm font-medium text-emerald-700 mt-2 flex items-center gap-1.5"><CircleDollarSign size={15} /> {t('partner.deliveryEarning', { amount: money(delivery.partner_fee, delivery.currency || delivery.currency_code || partnerCurrency) })}</p>
                  </div>
                  <div className="sm:text-right">
                    <span className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-brand-50 text-brand-700 text-sm font-medium">
                      {delivery.status === 'DELIVERED' ? <CheckCircle2 size={14} /> : <Clock size={14} />}
                      {statusLabel(delivery.status, t, 'delivery')}
                    </span>
                    <p className="font-semibold text-gray-950 mt-2">
                      {money(delivery.total_amount, delivery.currency || delivery.currency_code || partnerCurrency)}
                    </p>
                  </div>
                </div>

                {action && (
                  <div className="border-t border-gray-100 mt-4 pt-4 flex flex-wrap justify-end gap-2">
                    {delivery.status === 'ON_THE_WAY' && (
                      <input
                        value={confirmationCodes[delivery.id] || ''}
                        onChange={event => setConfirmationCodes(current => ({
                          ...current,
                          [delivery.id]: event.target.value.replace(/\D/g, '').slice(0, 6),
                        }))}
                        inputMode="numeric"
                        autoComplete="one-time-code"
                        placeholder={t('partner.handoffCodePlaceholder')}
                        aria-label={t('partner.customerHandoffCode')}
                        className="input-field w-full sm:w-52"
                      />
                    )}
                    <button
                      onClick={() => trackingId === delivery.id ? stopLiveTracking() : startLiveTracking(delivery.id)}
                      className="btn-secondary inline-flex items-center gap-2"
                    >
                      <LocateFixed size={16} /> {trackingId === delivery.id ? t('partner.stopLiveLocation') : t('partner.startLiveLocation')}
                    </button>
                    <button
                      onClick={() => advanceDelivery(delivery.id, action.status)}
                      disabled={updatingDeliveryId === delivery.id}
                      className="btn-primary"
                    >
                      {updatingDeliveryId === delivery.id ? t('account.updating') : t(action.labelKey)}
                    </button>
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}
      </section>
      )}

      {activeSection === 'history' && (
      <section ref={deliveryHistoryRef} className="mt-8 scroll-mt-24">
        <h2 className="text-lg font-semibold text-gray-950 mb-3">{t('partner.deliveryHistory')}</h2>
        {!completedDeliveries.length ? (
          <p className="text-sm text-gray-500">{t('partner.noCompletedDeliveries')}</p>
        ) : (
          <div className="divide-y divide-gray-200 border-y border-gray-200">
            {completedDeliveries.map(delivery => (
              <div key={delivery.id} className="py-4 flex items-center justify-between gap-4">
                <div>
                  <p className="font-medium text-gray-900">Order #{delivery.order_id} · {delivery.restaurant_name}</p>
                  <p className="text-sm text-gray-500 mt-1">{t('partner.customerValue', { customer: delivery.customer_name })}</p>
                  <p className="text-sm text-gray-500 mt-1">{t('partner.earningLine', { amount: money(delivery.partner_fee, delivery.currency || delivery.currency_code || partnerCurrency), status: statusLabel(delivery.payout_status, t, 'payouts') })}</p>
                </div>
                <span className="inline-flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 size={16} /> {statusLabel('DELIVERED', t, 'delivery')}</span>
              </div>
            ))}
          </div>
        )}
      </section>
      )}
    </div>
  )
}
