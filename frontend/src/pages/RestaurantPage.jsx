import { useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { ArrowLeft, Heart, ImagePlus, MapPin, Plus, ShieldCheck, Star, Trash2, Utensils, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import {
  createRestaurantReview,
  deleteReviewPhoto,
  getRestaurant,
  listRestaurantReviews,
  toggleFavoriteRestaurant,
  uploadReviewPhoto,
} from '../api/restaurants'
import { useCart } from '../context/CartContext'
import { useAuth } from '../context/AuthContext'
import { usePreferences } from '../context/PreferencesContext'
import { formatCurrency, formatDate, formatNumber } from '../lib/formatters'
import useTitle from '../hooks/useTitle'

const MAX_REVIEW_PHOTO_SIZE = 5 * 1024 * 1024
const REVIEW_PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const reviewPhotoStatusLabelKeys = {
  PENDING: 'restaurant.reviewPhotos.pending',
  APPROVED: 'restaurant.reviewPhotos.approved',
  REJECTED: 'restaurant.reviewPhotos.rejected',
  HIDDEN: 'restaurant.reviewPhotos.hidden',
}

const reviewPhotoStatusClass = status => ({
  PENDING: 'bg-amber-50 text-amber-700 border-amber-200',
  APPROVED: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  REJECTED: 'bg-red-50 text-red-700 border-red-200',
  HIDDEN: 'bg-gray-100 text-gray-700 border-gray-200',
}[status] || 'bg-gray-100 text-gray-700 border-gray-200')

const validateReviewPhotoFile = file => {
  if (!REVIEW_PHOTO_TYPES.includes(file.type)) {
    return 'Use a JPEG, PNG, or WebP image.'
  }
  if (file.size > MAX_REVIEW_PHOTO_SIZE) {
    return 'Review photos must be 5 MB or smaller.'
  }
  return ''
}

export default function RestaurantPage() {
  const { t } = useTranslation()
  const { id } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const reviewOrder = searchParams.get('reviewOrder')
  const queryClient = useQueryClient()
  const [rating, setRating] = useState(5)
  const [comment, setComment] = useState('')
  const [submittingReview, setSubmittingReview] = useState(false)
  const [selectedReviewPhotos, setSelectedReviewPhotos] = useState([])
  const [uploadedReviewPhotos, setUploadedReviewPhotos] = useState([])
  const [submittedReviewId, setSubmittedReviewId] = useState(null)
  const [deletingPhotoId, setDeletingPhotoId] = useState(null)
  const selectedReviewPhotosRef = useRef([])
  const [customizing, setCustomizing] = useState(null)
  const [selectedOptionIds, setSelectedOptionIds] = useState([])
  const { addItem } = useCart()
  const { user, role } = useAuth()
  const { preferences } = usePreferences()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['restaurant', id],
    queryFn: async () => (await getRestaurant(id)).data,
  })
  const { data: reviewData, isLoading: reviewsLoading } = useQuery({
    queryKey: ['restaurant-reviews', id],
    queryFn: async () => (await listRestaurantReviews(id)).data,
  })

  useTitle(data?.rest_name || 'Restaurant')

  const reviews = reviewData?.results || reviewData || []

  useEffect(() => {
    selectedReviewPhotosRef.current = selectedReviewPhotos
  }, [selectedReviewPhotos])

  useEffect(() => () => {
    selectedReviewPhotosRef.current.forEach(photo => URL.revokeObjectURL(photo.previewUrl))
  }, [])

  const startAdd = item => {
    const groups = item.option_groups || []
    if (!groups.length) {
      addItem(item, data.id)
      return
    }
    setCustomizing(item)
    setSelectedOptionIds([])
  }

  const toggleOption = (group, optionId) => {
    const groupIds = group.options.map(option => option.id)
    setSelectedOptionIds(current => {
      if (group.max_select === 1) {
        return [...current.filter(id => !groupIds.includes(id)), optionId]
      }
      if (current.includes(optionId)) return current.filter(id => id !== optionId)
      const selectedInGroup = current.filter(id => groupIds.includes(id)).length
      if (selectedInGroup >= group.max_select) {
        toast.error(`Choose up to ${group.max_select} for ${group.name}`)
        return current
      }
      return [...current, optionId]
    })
  }

  const addCustomizedItem = () => {
    const groups = customizing.option_groups || []
    for (const group of groups) {
      const groupIds = group.options.filter(option => option.is_available).map(option => option.id)
      const count = selectedOptionIds.filter(id => groupIds.includes(id)).length
      if (count < group.min_select) {
        toast.error(`Select at least ${group.min_select} for ${group.name}`)
        return
      }
    }
    const selected = groups.flatMap(group => group.options
      .filter(option => selectedOptionIds.includes(option.id))
      .map(option => ({ ...option, group: group.name })))
    if (addItem(customizing, data.id, selected)) setCustomizing(null)
  }

  const toggleFavorite = async () => {
    if (!user) {
      toast.error('Sign in to save favorites')
      return
    }
    if (role !== 'customer') return
    try {
      const response = await toggleFavoriteRestaurant(id)
      queryClient.setQueryData(['restaurant', id], current => ({
        ...current,
        is_favorite: response.data.is_favorite,
      }))
      await queryClient.invalidateQueries({ queryKey: ['favorite-restaurants'] })
      toast.success(response.data.is_favorite ? 'Added to favorites' : 'Removed from favorites')
    } catch {
      toast.error('Could not update favorites.')
    }
  }

  const addReviewPhotos = event => {
    const files = Array.from(event.target.files || [])
    if (!files.length) return
    const nextPhotos = []
    files.forEach(file => {
      const error = validateReviewPhotoFile(file)
      if (error) {
        toast.error(`${file.name}: ${error}`)
        return
      }
      nextPhotos.push({
        id: `${file.name}-${file.lastModified}-${Math.random().toString(36).slice(2)}`,
        file,
        caption: '',
        previewUrl: URL.createObjectURL(file),
        progress: 0,
      })
    })
    if (nextPhotos.length) {
      setSelectedReviewPhotos(current => [...current, ...nextPhotos])
    }
    event.target.value = ''
  }

  const updateSelectedPhotoCaption = (photoId, caption) => {
    setSelectedReviewPhotos(current => current.map(photo => (
      photo.id === photoId ? { ...photo, caption } : photo
    )))
  }

  const removeSelectedPhoto = photoId => {
    setSelectedReviewPhotos(current => {
      const removed = current.find(photo => photo.id === photoId)
      if (removed) URL.revokeObjectURL(removed.previewUrl)
      return current.filter(photo => photo.id !== photoId)
    })
  }

  const uploadSelectedPhotos = async reviewId => {
    const uploaded = []
    const failed = []
    for (const photo of selectedReviewPhotos) {
      try {
        const response = await uploadReviewPhoto(id, reviewId, photo.file, photo.caption, {
          onUploadProgress: progressEvent => {
            const total = progressEvent.total || photo.file.size || 1
            const progress = Math.round((progressEvent.loaded / total) * 100)
            setSelectedReviewPhotos(current => current.map(item => (
              item.id === photo.id ? { ...item, progress } : item
            )))
          },
        })
        uploaded.push(response.data)
      } catch (error) {
        const response = error.response?.data
        failed.push(response?.image?.[0] || response?.detail || `${photo.file.name} could not be uploaded.`)
      }
    }
    selectedReviewPhotos.forEach(photo => URL.revokeObjectURL(photo.previewUrl))
    setSelectedReviewPhotos([])
    if (uploaded.length) setUploadedReviewPhotos(uploaded)
    if (failed.length) {
      failed.forEach(message => toast.error(message))
    }
    return uploaded
  }

  const deleteUploadedPhoto = async photoId => {
    if (!submittedReviewId) return
    setDeletingPhotoId(photoId)
    try {
      await deleteReviewPhoto(id, submittedReviewId, photoId)
      setUploadedReviewPhotos(current => current.filter(photo => photo.id !== photoId))
      toast.success('Photo removed.')
    } catch (error) {
      toast.error(error.response?.data?.status?.[0] || error.response?.data?.detail || 'Could not delete this photo.')
    } finally {
      setDeletingPhotoId(null)
    }
  }

  const submitReview = async event => {
    event.preventDefault()
    setSubmittingReview(true)
    try {
      const response = await createRestaurantReview(id, {
        order_id: Number(reviewOrder),
        rating,
        comment,
      })
      const createdReview = response.data
      setSubmittedReviewId(createdReview.id)
      setUploadedReviewPhotos([])
      let uploadedPhotos = []
      if (selectedReviewPhotos.length) {
        uploadedPhotos = await uploadSelectedPhotos(createdReview.id)
      }
      toast.success(uploadedPhotos.length ? t('restaurant.reviewThanksPhotos') : t('restaurant.reviewThanks'))
      setSearchParams({})
      setComment('')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['restaurant', id] }),
        queryClient.invalidateQueries({ queryKey: ['restaurant-reviews', id] }),
        queryClient.invalidateQueries({ queryKey: ['orders'] }),
      ])
    } catch (error) {
      const response = error.response?.data
      const message = response?.order_id?.[0]
        || response?.non_field_errors?.[0]
        || t('restaurant.reviewFailed')
      toast.error(message)
    } finally {
      setSubmittingReview(false)
    }
  }

  if (isLoading) return <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10 text-gray-500">{t('restaurant.loadingMenu')}</div>
  if (isError || !data) return <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10 text-red-500">{t('restaurant.loadFailed')}</div>

  return (
    <div>
      <section className="bg-white border-b border-gray-100">
        {data.cover_image && (
          <div className="h-52 sm:h-72 w-full overflow-hidden">
            <img src={data.cover_image} alt="" className="h-full w-full object-cover" />
          </div>
        )}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
          <Link to="/search" className="inline-flex items-center gap-2 text-sm text-brand-600 font-medium mb-5">
            <ArrowLeft size={16} /> {t('restaurant.backToSearch')}
          </Link>
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-5">
            <div>
              <h1 className="text-3xl font-bold text-gray-950">{data.rest_name}</h1>
              {data.merchant_verified && (
                <p className="text-sm text-emerald-700 font-medium flex items-center gap-2 mt-2">
                  <ShieldCheck size={16} /> {t('restaurant.verifiedMerchant')}
                </p>
              )}
              <p className="text-gray-500 mt-2 flex items-center gap-2"><MapPin size={16} /> {data.rest_address}, {data.rest_city}</p>
              <p className="text-sm text-gray-600 mt-2 flex items-center gap-2">
                <Star size={15} className="text-amber-500" />
                {data.average_rating ? formatNumber(data.average_rating, preferences, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : 'New'}
                <span className="text-gray-400">({t('restaurant.reviewCount', { count: formatNumber(data.review_count, preferences, { maximumFractionDigits: 0 }) })})</span>
              </p>
              <p className={`text-sm font-medium mt-2 ${data.is_open ? 'text-emerald-700' : 'text-red-600'}`}>
                {data.is_open ? t('restaurant.openDetails', {
                  fee: formatCurrency(data.delivery_fee, data.currency || data.currency_code || 'INR', preferences),
                  radius: formatNumber(data.delivery_radius_km, preferences, { maximumFractionDigits: 1 }),
                  minutes: formatNumber(Number(data.estimated_prep_minutes) + 15, preferences, { maximumFractionDigits: 0 }),
                }) : t('restaurant.currentlyClosed')}
              </p>
              {data.operating_hours?.length > 0 && (
                <details className="mt-3 text-sm text-gray-600">
                  <summary className="cursor-pointer font-medium text-gray-700">{t('restaurant.weeklyHours')}</summary>
                  <div className="mt-2 grid grid-cols-[100px_1fr] gap-x-4 gap-y-1">
                    {data.operating_hours.map(entry => (
                      <div key={entry.day_of_week} className="contents">
                        <span>{entry.day_display}</span>
                        <span>{entry.is_closed ? 'Closed' : `${entry.opens_at.slice(0, 5)}–${entry.closes_at.slice(0, 5)}`}</span>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {role === 'customer' && (
                <button
                  type="button"
                  onClick={toggleFavorite}
                  className="btn-secondary inline-flex items-center gap-2 text-sm"
                  aria-label={data.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
                >
                  <Heart size={17} className={data.is_favorite ? 'fill-red-500 text-red-500' : ''} />
                  {data.is_favorite ? t('restaurant.saved') : t('common.save')}
                </button>
              )}
              {data.categories.map(category => (
                <span key={category} className="text-sm bg-gray-100 text-gray-700 px-3 py-2 rounded-lg">{category}</span>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
        <h2 className="text-xl font-semibold text-gray-900 mb-5">{t('dashboard.menu')}</h2>
        <div className="grid lg:grid-cols-2 gap-4">
          {data.food_items.map(item => (
            <div key={item.id} className="card p-5 flex gap-4">
              <div className="h-20 w-24 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center flex-shrink-0 overflow-hidden">
                {item.image
                  ? <img src={item.image} alt="" className="h-full w-full object-cover" />
                  : <Utensils size={24} />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold text-gray-950">{item.food_name}</h3>
                    <p className="text-xs text-gray-500 mt-1">{item.food_categ}</p>
                  </div>
                  <p className="font-semibold text-gray-950">{formatCurrency(item.food_price, item.currency || item.currency_code || data.currency || data.currency_code || 'INR', preferences)}</p>
                </div>
                {item.food_desc && <p className="text-sm text-gray-500 mt-2">{item.food_desc}</p>}
                <button disabled={!data.is_open || !item.is_available} onClick={() => startAdd(item)} className="btn-primary mt-4 inline-flex items-center gap-2 py-2 px-4 text-sm">
                  <Plus size={15} /> {data.is_open && item.is_available ? (item.option_groups?.length ? t('restaurant.customize') : t('restaurant.add')) : t('restaurant.unavailable')}
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {customizing && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-0 sm:p-4" role="dialog" aria-modal="true" aria-label={t('restaurant.customizeItem', { name: customizing.food_name })}>
          <div className="bg-white w-full sm:max-w-lg max-h-[90vh] overflow-y-auto rounded-t-lg sm:rounded-lg">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-5 py-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-950">{customizing.food_name}</h2>
                <p className="text-sm text-gray-500 mt-1">Choose how you want it prepared.</p>
              </div>
              <button type="button" onClick={() => setCustomizing(null)} className="p-2 rounded-lg hover:bg-gray-100" aria-label="Close"><X size={19} /></button>
            </div>
            <div className="divide-y divide-gray-200">
              {customizing.option_groups.map(group => (
                <fieldset key={group.id} className="p-5">
                  <legend className="font-semibold text-gray-900">{group.name}</legend>
                  <p className="text-xs text-gray-500 mt-1 mb-3">
                    {group.min_select > 0 ? 'Required' : 'Optional'} · Choose {group.min_select === group.max_select ? group.max_select : `${group.min_select}-${group.max_select}`}
                  </p>
                  <div className="space-y-2">
                    {group.options.filter(option => option.is_available).map(option => (
                      <label key={option.id} className="flex items-center justify-between gap-4 py-2 cursor-pointer">
                        <span className="flex items-center gap-3 text-sm text-gray-800">
                          <input
                            type={group.max_select === 1 ? 'radio' : 'checkbox'}
                            name={`option-group-${group.id}`}
                            checked={selectedOptionIds.includes(option.id)}
                            onChange={() => toggleOption(group, option.id)}
                          />
                          {option.name}
                        </span>
                        <span className="text-sm text-gray-600">{Number(option.price_delta) ? `+ ${formatCurrency(option.price_delta, data.currency || data.currency_code || 'INR', preferences)}` : 'Included'}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              ))}
            </div>
            <div className="sticky bottom-0 bg-white border-t border-gray-200 p-4">
              <button type="button" onClick={addCustomizedItem} className="btn-primary w-full">{t('restaurant.addToCart')}</button>
            </div>
          </div>
        </div>
      )}

      <section className="border-t border-gray-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
          <h2 className="text-xl font-semibold text-gray-900">{t('restaurant.customerReviews')}</h2>

          {reviewOrder && (
            <form onSubmit={submitReview} className="mt-5 max-w-2xl border border-gray-200 rounded-lg p-5">
              <h3 className="font-semibold text-gray-950">{t('restaurant.rateOrder', { id: reviewOrder })}</h3>
              <div className="flex gap-1 mt-3" aria-label="Rating">
                {[1, 2, 3, 4, 5].map(value => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setRating(value)}
                    className="p-1"
                    aria-label={`${value} star rating`}
                  >
                    <Star
                      size={24}
                      className={value <= rating ? 'text-amber-500 fill-amber-500' : 'text-gray-300'}
                    />
                  </button>
                ))}
              </div>
              <textarea
                value={comment}
                onChange={event => setComment(event.target.value)}
                maxLength={1000}
                rows={3}
                className="input-field resize-none mt-3"
                placeholder={t('restaurant.reviewPlaceholder')}
              />
              <div className="mt-4">
                <div className="flex flex-wrap items-center gap-3">
                  <label className="btn-secondary inline-flex items-center gap-2 text-sm cursor-pointer">
                    <ImagePlus size={16} /> {t('restaurant.addPhotos')}
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      multiple
                      className="sr-only"
                      onChange={addReviewPhotos}
                    />
                  </label>
                  <p className="text-xs text-gray-500">JPEG, PNG, or WebP. 5 MB max each.</p>
                </div>
                <p className="text-xs text-amber-700 mt-2">{t('restaurant.reviewPhotos.pendingPublic')}</p>
                {selectedReviewPhotos.length > 0 && (
                  <div className="grid sm:grid-cols-2 gap-3 mt-3">
                    {selectedReviewPhotos.map(photo => (
                      <div key={photo.id} className="border border-gray-200 rounded-lg p-3">
                        <div className="flex gap-3">
                          <img src={photo.previewUrl} alt="" className="h-20 w-20 rounded-lg object-cover bg-gray-100" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900 truncate">{photo.file.name}</p>
                            <p className="text-xs text-gray-500 mt-1">{Math.max(1, Math.round(photo.file.size / 1024))} KB</p>
                            <p className="text-xs text-gray-500 mt-1">{photo.progress ? `${photo.progress}% uploaded` : 'Ready to upload'}</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => removeSelectedPhoto(photo.id)}
                            className="h-9 w-9 inline-flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-500"
                            aria-label="Remove selected photo"
                          >
                            <X size={16} />
                          </button>
                        </div>
                        <input
                          type="text"
                          value={photo.caption}
                          onChange={event => updateSelectedPhotoCaption(photo.id, event.target.value)}
                          maxLength={240}
                          className="input-field mt-3 text-sm"
                          placeholder="T-Food review photo caption"
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <button type="submit" disabled={submittingReview} className="btn-primary mt-3">
                {submittingReview ? t('restaurant.submitting') : t('restaurant.submitReview')}
              </button>
            </form>
          )}

          {uploadedReviewPhotos.length > 0 && (
            <div className="mt-5 max-w-2xl border border-amber-200 bg-amber-50 rounded-lg p-5">
              <h3 className="font-semibold text-gray-950">Your review photos</h3>
              <p className="text-sm text-amber-800 mt-1">{t('restaurant.reviewPhotos.pendingPublic')}</p>
              <div className="space-y-3 mt-4">
                {uploadedReviewPhotos.map(photo => (
                  <div key={photo.id} className="flex items-center justify-between gap-3 bg-white border border-amber-100 rounded-lg p-3">
                    <div>
                      <span className={`inline-flex items-center rounded-full border px-2 py-1 text-xs font-medium ${reviewPhotoStatusClass(photo.status)}`}>
                        {reviewPhotoStatusLabelKeys[photo.status] ? t(reviewPhotoStatusLabelKeys[photo.status]) : photo.status}
                      </span>
                      {photo.caption && <p className="text-sm text-gray-700 mt-2">{photo.caption}</p>}
                    </div>
                    {photo.status === 'PENDING' && (
                      <button
                        type="button"
                        onClick={() => deleteUploadedPhoto(photo.id)}
                        disabled={deletingPhotoId === photo.id}
                        className="btn-secondary inline-flex items-center gap-2 text-sm"
                      >
                        <Trash2 size={15} /> {deletingPhotoId === photo.id ? 'Deleting...' : 'Delete'}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {reviewsLoading && <p className="text-gray-500 mt-5">{t('restaurant.loadingReviews')}</p>}
          {!reviewsLoading && !reviews.length && (
            <p className="text-gray-500 mt-5">{t('restaurant.noReviews')}</p>
          )}
          <div className="grid md:grid-cols-2 gap-4 mt-5">
            {reviews.map(review => (
              <article key={review.id} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium text-gray-900">{review.customer_name}</p>
                  <span className="flex items-center gap-1 text-sm text-amber-600">
                    <Star size={14} className="fill-amber-500" /> {review.rating}
                  </span>
                </div>
                {review.comment && <p className="text-sm text-gray-600 mt-3">{review.comment}</p>}
                {review.photos?.length > 0 && (
                  <div className="grid grid-cols-3 gap-2 mt-3">
                    {review.photos.filter(photo => photo.image_url).map(photo => (
                      <img
                        key={photo.id}
                        src={photo.image_url}
                        alt={photo.caption || 'Approved review photo'}
                        className="aspect-square w-full rounded-lg object-cover bg-gray-100"
                      />
                    ))}
                  </div>
                )}
                <p className="text-xs text-gray-400 mt-3">
                  {formatDate(review.created_at, preferences)}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
