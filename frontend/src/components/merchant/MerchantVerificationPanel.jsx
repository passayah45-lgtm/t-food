import {
  CheckCircle2,
  FileText,
  ShieldCheck,
  Trash2,
  UploadCloud,
  XCircle,
} from 'lucide-react'
import { openPrivateMedia } from '../../api/media'

const ChecklistItem = ({ done, label, help }) => (
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

export default function MerchantVerificationPanel({
  profile,
  documentsQuery,
  form,
  setForm,
  onUpload,
  uploading,
  onDelete,
  deletingId,
  identityDocumentTypes,
  merchantDocumentTypes,
  verificationStatusLabels,
  documentStatusClass,
  formatDocumentType,
  formatDateTime,
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
        <ChecklistItem done={hasOwnerProfilePhoto} label="Owner profile photo" help="A clear photo of the restaurant owner." />
        <ChecklistItem done={hasIdentityDocument} label="One identity document" help="National ID, Passport, or Voter Card." />
        <ChecklistItem done={hasRestaurantPhoto} label="Restaurant photo" help="A real photo of the storefront, kitchen, or counter." />
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
