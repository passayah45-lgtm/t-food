import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Bike, CheckCircle2, CircleDollarSign, Clock, FileText, LocateFixed, Package, ShieldCheck, Trash2, UploadCloud, XCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { claimAvailableDelivery, getPartnerEarnings, listAvailableDeliveries, listPartnerDeliveries, updateAvailabilityLocation, updateDeliveryLocation, updateDeliveryStatus } from '../api/delivery'
import { getPartnerProfile } from '../api/auth'
import {
  deletePartnerVerificationDocument,
  listPartnerVerificationDocuments,
  uploadPartnerVerificationDocument,
} from '../api/verifications'
import { openPrivateMedia } from '../api/media'
import { statusLabel } from '../lib/statusLabels'
import useRealtime from '../hooks/useRealtime'
import useTitle from '../hooks/useTitle'

const nextActions = {
  ASSIGNED: { status: 'PICKED_UP', labelKey: 'partner.actions.confirmPickup' },
  PICKED_UP: { status: 'ON_THE_WAY', labelKey: 'partner.actions.startTrip' },
  ON_THE_WAY: { status: 'DELIVERED', labelKey: 'partner.actions.confirmDelivery' },
}

const partnerDocumentTypes = [
  { value: 'PARTNER_PROFILE_PHOTO', label: 'Partner profile photo' },
  { value: 'NATIONAL_ID', label: 'National ID' },
  { value: 'PASSPORT', label: 'Passport' },
  { value: 'DRIVING_LICENSE', label: 'Driving license' },
  { value: 'VEHICLE_DOCUMENT', label: 'Vehicle document (optional)' },
]
const partnerIdentityDocumentTypes = ['NATIONAL_ID', 'PASSPORT', 'DRIVING_LICENSE']
const verificationStatusLabels = {
  PENDING: 'Pending',
  SUBMITTED: 'Submitted',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  SUSPENDED: 'Suspended',
}
const emptyVerificationForm = {
  document_type: 'PARTNER_PROFILE_PHOTO',
  file: null,
  notes: '',
}

const formatDocumentType = value => (
  partnerDocumentTypes.find(type => type.value === value)?.label || value?.replaceAll('_', ' ') || 'Document'
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

function PartnerVerificationPanel({
  profile,
  documentsQuery,
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
  const statusText = verificationStatusLabels[status] || status?.replaceAll('_', ' ') || 'Pending'
  const missing = [
    !hasProfilePhoto && 'Partner profile photo',
    !hasIdentityDocument && 'National ID, Passport, or Driving License',
  ].filter(Boolean)

  return (
    <section className="mb-8 border-b border-gray-200 pb-6">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-5 mb-5">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck size={20} className="text-brand-600" />
            <h2 className="text-xl font-semibold text-gray-950">Partner verification</h2>
          </div>
          <p className="text-sm text-gray-500 mt-2 max-w-2xl">
            T-Food verifies rider identity before pickup access is enabled. Upload your partner profile photo and identity or license document here; operations will approve the account or share a rejection reason.
          </p>
        </div>
        <span className={`inline-flex w-fit items-center rounded-full border px-3 py-1 text-sm font-medium ${documentStatusClass(status)}`}>
          {statusText}
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
            <p className="mt-1">Required documents are uploaded. T-Food operations will review them before activating delivery access.</p>
          )}
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-3 mb-6">
        <ChecklistItem
          done={hasProfilePhoto}
          label="Partner profile photo"
          help="A clear face photo for account review."
        />
        <ChecklistItem
          done={hasIdentityDocument}
          label="Identity or license document"
          help="National ID, Passport, or Driving License."
        />
        <ChecklistItem
          done={hasVehicleDocument}
          label="Vehicle document"
          help="Optional now, useful when a bike or scooter is used."
          optional
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
            {partnerDocumentTypes.map(type => <option key={type.value} value={type.value}>{type.label}</option>)}
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
                  {statusLabel(document.status, t, 'verification')}
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

export default function PartnerDashboardPage() {
  const { t } = useTranslation()
  useTitle(t('partner.title'))
  const queryClient = useQueryClient()
  const [trackingId, setTrackingId] = useState(null)
  const [updatingDeliveryId, setUpdatingDeliveryId] = useState(null)
  const [confirmationCodes, setConfirmationCodes] = useState({})
  const [updatingAvailabilityLocation, setUpdatingAvailabilityLocation] = useState(false)
  const [verificationForm, setVerificationForm] = useState(emptyVerificationForm)
  const [uploadingVerification, setUploadingVerification] = useState(false)
  const [deletingVerificationId, setDeletingVerificationId] = useState(null)
  const watchId = useRef(null)
  const lastLocationSent = useRef(0)
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

  const deliveries = data?.results || data || []
  const availableDeliveries = [...(availableQuery.data?.results || availableQuery.data || [])].sort((left, right) => (
    (left.pickup_distance_km ?? Number.POSITIVE_INFINITY) - (right.pickup_distance_km ?? Number.POSITIVE_INFINITY)
  ))
  const activeDeliveries = deliveries.filter(delivery => delivery.status !== 'DELIVERED')
  const completedDeliveries = deliveries.filter(delivery => delivery.status === 'DELIVERED')
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
            form={verificationForm}
            setForm={setVerificationForm}
            onUpload={uploadVerification}
            uploading={uploadingVerification}
            onDelete={deleteVerification}
            deletingId={deletingVerificationId}
          />
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

      <PartnerVerificationPanel
        profile={profileQuery.data}
        documentsQuery={partnerVerificationQuery}
        form={verificationForm}
        setForm={setVerificationForm}
        onUpload={uploadVerification}
        uploading={uploadingVerification}
        onDelete={deleteVerification}
        deletingId={deletingVerificationId}
      />

      <section className="mb-8">
        <h2 className="text-lg font-semibold text-gray-950 mb-3">Earnings</h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="border border-gray-200 rounded-lg p-4"><p className="text-xs text-gray-500">Available payout</p><p className="text-xl font-bold text-emerald-700 mt-1">Rs. {Number(earningsQuery.data?.available_earnings || 0).toFixed(2)}</p></div>
          <div className="border border-gray-200 rounded-lg p-4"><p className="text-xs text-gray-500">Paid earnings</p><p className="text-xl font-bold mt-1">Rs. {Number(earningsQuery.data?.paid_earnings || 0).toFixed(2)}</p></div>
          <div className="border border-gray-200 rounded-lg p-4"><p className="text-xs text-gray-500">Lifetime earnings</p><p className="text-xl font-bold mt-1">Rs. {Number(earningsQuery.data?.lifetime_earnings || 0).toFixed(2)}</p></div>
          <div className="border border-gray-200 rounded-lg p-4"><p className="text-xs text-gray-500">Completed jobs</p><p className="text-xl font-bold mt-1">{earningsQuery.data?.completed_deliveries || 0}</p></div>
        </div>
      </section>

      <section className="mb-8">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-gray-950">Available pickups</h2>
          <span className="text-sm text-gray-500">Shared queue</span>
        </div>
        {!availableDeliveries.length ? (
          <p className="text-sm text-gray-500 mt-3 border border-dashed border-gray-300 rounded-lg p-4">
            No pickup is waiting in the shared queue. An order disappears here after a partner accepts or is assigned to it.
          </p>
        ) : (
          <div className="grid md:grid-cols-2 gap-3 mt-3">
            {availableDeliveries.map(delivery => (
              <article key={delivery.id} className="bg-white border border-amber-200 rounded-lg p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-gray-950">Order #{delivery.order_id} · {delivery.restaurant_name}</p>
                    <p className="text-sm text-gray-600 mt-2"><strong>Pickup:</strong> {delivery.pickup_address}</p>
                    <p className="text-sm text-gray-600 mt-1"><strong>Drop-off:</strong> {delivery.delivery_address}</p>
                    <p className="text-sm font-medium text-brand-700 mt-2">
                      {delivery.pickup_distance_km == null ? 'Pickup distance unavailable' : `${delivery.pickup_distance_km} km to pickup`}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {delivery.offer_radius_km == null ? 'Open fallback offer' : `${delivery.offer_radius_km} km offer wave`}
                    </p>
                    <div className="text-sm text-gray-500 mt-2">{delivery.items.map(item => <p key={`${delivery.id}-${item.name}`}>{item.name} x {item.quantity}{item.selected_options?.length ? ` · ${item.selected_options.map(option => option.name).join(', ')}` : ''}</p>)}</div>
                  </div>
                  <p className="font-semibold whitespace-nowrap">Rs. {Number(delivery.total_amount).toFixed(2)}</p>
                </div>
                <button type="button" onClick={() => claimDelivery(delivery.id)} className="btn-primary w-full mt-4">Accept delivery</button>
              </article>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="text-lg font-semibold text-gray-950 mb-3">Active delivery</h2>
      {!activeDeliveries.length ? (
        <div className="py-12 text-center border border-dashed border-gray-300 rounded-lg">
          <Bike size={42} className="text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900">No active delivery for this account</h3>
          <p className="text-gray-500 mt-2">Only orders assigned to @{profileQuery.data?.user?.username} appear here.</p>
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
                    <p className="text-sm text-gray-500 mt-2">Customer: {delivery.customer_name}</p>
                    <div className="text-sm text-gray-500 mt-1">
                      {delivery.items.map(item => <p key={`${delivery.id}-${item.name}`}>{item.name} x {item.quantity}{item.selected_options?.length ? ` · ${item.selected_options.map(option => option.name).join(', ')}` : ''}</p>)}
                    </div>
                    {delivery.payment_method === 'COD' && delivery.payment_status === 'PENDING' && (
                      <p className="text-sm font-semibold text-amber-700 mt-2">
                        Collect Rs. {Number(delivery.total_amount).toFixed(2)} cash
                      </p>
                    )}
                    <p className="text-sm font-medium text-emerald-700 mt-2 flex items-center gap-1.5"><CircleDollarSign size={15} /> Delivery earning: Rs. {Number(delivery.partner_fee).toFixed(2)}</p>
                  </div>
                  <div className="sm:text-right">
                    <span className="inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-brand-50 text-brand-700 text-sm font-medium">
                      {delivery.status === 'DELIVERED' ? <CheckCircle2 size={14} /> : <Clock size={14} />}
                      {statusLabel(delivery.status, t, 'delivery')}
                    </span>
                    <p className="font-semibold text-gray-950 mt-2">
                      Rs. {Number(delivery.total_amount).toFixed(2)}
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
                        placeholder="T-Food 6-digit handoff code"
                        aria-label="Customer handoff code"
                        className="input-field w-full sm:w-52"
                      />
                    )}
                    <button
                      onClick={() => trackingId === delivery.id ? stopLiveTracking() : startLiveTracking(delivery.id)}
                      className="btn-secondary inline-flex items-center gap-2"
                    >
                      <LocateFixed size={16} /> {trackingId === delivery.id ? 'Stop live location' : 'Start live location'}
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

      <section className="mt-8">
        <h2 className="text-lg font-semibold text-gray-950 mb-3">Delivery history</h2>
        {!completedDeliveries.length ? (
          <p className="text-sm text-gray-500">No completed deliveries for this account yet.</p>
        ) : (
          <div className="divide-y divide-gray-200 border-y border-gray-200">
            {completedDeliveries.map(delivery => (
              <div key={delivery.id} className="py-4 flex items-center justify-between gap-4">
                <div>
                  <p className="font-medium text-gray-900">Order #{delivery.order_id} · {delivery.restaurant_name}</p>
                  <p className="text-sm text-gray-500 mt-1">Customer: {delivery.customer_name}</p>
                  <p className="text-sm text-gray-500 mt-1">{t('partner.earningLine', { amount: Number(delivery.partner_fee).toFixed(2), status: statusLabel(delivery.payout_status, t, 'payouts') })}</p>
                </div>
                <span className="inline-flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 size={16} /> Delivered</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
