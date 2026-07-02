import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Camera, ImagePlus, MapPin, Search, ShieldCheck, Utensils, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { trackSearchEvent, visualProductSearch } from '../api/intelligence'
import { listRestaurants } from '../api/restaurants'
import { useLocationContext } from '../context/LocationContext'
import { usePreferences } from '../context/PreferencesContext'
import { formatCurrency, formatNumber } from '../lib/formatters'
import useTitle from '../hooks/useTitle'

const categories = [
  { value: 'All', labelKey: 'search.categories.all' },
  { value: 'Vegetarian', labelKey: 'search.categories.vegetarian' },
  { value: 'Non-Vegetarian', labelKey: 'search.categories.nonVegetarian' },
  { value: 'Beverages', labelKey: 'search.categories.beverages' },
  { value: 'Desserts', labelKey: 'search.categories.desserts' },
]

export default function SearchPage() {
  const { t } = useTranslation()
  useTitle(t('common.search'))
  const { preferences } = usePreferences()
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState(params.get('q') || '')
  const [visualResult, setVisualResult] = useState(null)
  const [visualError, setVisualError] = useState('')
  const [previewUrl, setPreviewUrl] = useState('')
  const trackedSearches = useRef(new Set())
  const imageInputRef = useRef(null)
  const category = params.get('category') || 'All'
  const { currentLocation } = useLocationContext()
  const urlLatitude = params.get('latitude')
  const urlLongitude = params.get('longitude')
  const latitude = urlLatitude || currentLocation?.latitude
  const longitude = urlLongitude || currentLocation?.longitude

  const apiParams = useMemo(() => ({
    search: params.get('q') || undefined,
    category: category === 'All' ? undefined : category,
    latitude: latitude || undefined,
    longitude: longitude || undefined,
  }), [params, category, latitude, longitude])

  const { data, isLoading, isError } = useQuery({
    queryKey: ['restaurants', apiParams],
    queryFn: async () => (await listRestaurants(apiParams)).data,
  })

  const restaurants = data?.results || data || []

  const visualSearchMutation = useMutation({
    mutationFn: async imageFile => {
      const payload = new FormData()
      payload.append('image', imageFile)
      payload.append('provider_code', 'local_mock')
      if (latitude && longitude) {
        payload.append('latitude', latitude)
        payload.append('longitude', longitude)
      }
      if (category !== 'All') payload.append('category', category)
      const response = await visualProductSearch(payload)
      return response.data
    },
    onSuccess: result => {
      setVisualResult(result)
      setVisualError('')
      if (!result?.predicted_labels?.length) {
        setVisualError(t('search.noLabels'))
      }
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
        setPreviewUrl('')
      }
    },
    onError: error => {
      const detail = error?.response?.data
      const message = Array.isArray(detail?.image)
        ? detail.image.join(' ')
        : detail?.detail || t('search.imageFailed')
      setVisualError(message)
      setVisualResult(null)
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
        setPreviewUrl('')
      }
    },
  })

  useEffect(() => {
    setQuery(params.get('q') || '')
  }, [params])

  useEffect(() => {
    if (isLoading || isError || !data) return
    if (!apiParams.search && !apiParams.category) return

    const trackingKey = JSON.stringify({
      query: apiParams.search || '',
      category: apiParams.category || '',
      latitude: apiParams.latitude || '',
      longitude: apiParams.longitude || '',
      result_count: restaurants.length,
    })
    if (trackedSearches.current.has(trackingKey)) return
    trackedSearches.current.add(trackingKey)

    trackSearchEvent({
      query: apiParams.search || '',
      category: apiParams.category || '',
      latitude: apiParams.latitude,
      longitude: apiParams.longitude,
      result_count: restaurants.length,
    }).catch(() => {})
  }, [apiParams, data, isError, isLoading, restaurants.length])

  const submit = e => {
    e.preventDefault()
    const next = new URLSearchParams(params)
    if (query.trim()) next.set('q', query.trim())
    else next.delete('q')
    if (currentLocation?.latitude && currentLocation?.longitude) {
      next.set('latitude', currentLocation.latitude)
      next.set('longitude', currentLocation.longitude)
    }
    setParams(next)
  }

  const setCategory = value => {
    const next = new URLSearchParams(params)
    if (value === 'All') next.delete('category')
    else next.set('category', value)
    setParams(next)
  }

  const runTextSearch = value => {
    const nextQuery = (value || '').trim()
    setQuery(nextQuery)
    const next = new URLSearchParams(params)
    if (nextQuery) next.set('q', nextQuery)
    else next.delete('q')
    if (currentLocation?.latitude && currentLocation?.longitude) {
      next.set('latitude', currentLocation.latitude)
      next.set('longitude', currentLocation.longitude)
    }
    setParams(next)
  }

  const handleImageSelect = event => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setVisualError('')
    setVisualResult(null)
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setVisualError(t('search.unsupportedFile'))
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setVisualError(t('search.fileTooLarge'))
      return
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setPreviewUrl(URL.createObjectURL(file))
    visualSearchMutation.mutate(file)
  }

  const clearVisualSearch = () => {
    setVisualResult(null)
    setVisualError('')
    visualSearchMutation.reset()
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
      setPreviewUrl('')
    }
  }

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-5 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-950">{t('search.title')}</h1>
          <p className="text-gray-500 mt-1">{t('search.subtitle')}</p>
        </div>
        <form onSubmit={submit} className="flex gap-2 md:w-[520px]">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input value={query} onChange={e => setQuery(e.target.value)} className="input-field pl-10" placeholder={t('search.placeholder')} />
          </div>
          <input
            ref={imageInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={handleImageSelect}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => imageInputRef.current?.click()}
            className="btn-secondary px-3 inline-flex items-center gap-2"
            title={t('search.searchByImage')}
            aria-label={t('search.searchByImage')}
          >
            <Camera size={17} />
            <span className="hidden sm:inline">{t('search.searchByImage')}</span>
          </button>
          <button className="btn-primary">{t('common.go')}</button>
        </form>
      </div>

      <div className="flex gap-2 overflow-x-auto pb-4 mb-4">
        {categories.map(item => (
          <button
            key={item.value}
            onClick={() => setCategory(item.value)}
            className={`px-4 py-2 rounded-lg border text-sm font-medium whitespace-nowrap ${category === item.value ? 'bg-brand-500 border-brand-500 text-white' : 'bg-white border-gray-200 text-gray-700'}`}
          >
            {t(item.labelKey)}
          </button>
        ))}
      </div>

      {(visualSearchMutation.isPending || visualError || visualResult || previewUrl) && (
        <section className="border border-gray-200 bg-white rounded-lg p-4 mb-6">
          <div className="flex flex-col lg:flex-row gap-4">
            <div className="flex items-start gap-3 min-w-0 flex-1">
              <div className="h-16 w-16 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center overflow-hidden flex-shrink-0">
                {previewUrl
                  ? <img src={previewUrl} alt="" className="h-full w-full object-cover" />
                  : <ImagePlus size={22} />}
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold text-gray-950">{t('search.searchByImage')}</h2>
                  <button
                    type="button"
                    onClick={clearVisualSearch}
                    className="text-gray-400 hover:text-gray-700"
                    aria-label={t('common.clear')}
                    title={t('common.clear')}
                  >
                    <X size={16} />
                  </button>
                </div>
                {visualSearchMutation.isPending && (
                  <p className="text-sm text-gray-500 mt-1">{t('search.detectingProducts')}</p>
                )}
                {visualError && (
                  <p className="text-sm text-red-600 mt-1">{visualError}</p>
                )}
                {visualResult && (
                  <div className="mt-2 space-y-2">
                    <p className="text-sm text-gray-600">
                      <span className="font-medium text-gray-900">{t('search.detected')}</span>
                      {': '}
                      {visualResult.predicted_labels?.length
                        ? visualResult.predicted_labels.join(', ')
                        : t('search.noLabelsShort')}
                      {typeof visualResult.confidence === 'number' && (
                        <span className="text-gray-400"> - {t('search.confidence', { value: formatNumber(visualResult.confidence * 100, preferences, { maximumFractionDigits: 0 }) })}</span>
                      )}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {visualResult.similar_categories?.map(item => (
                        <span key={item} className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded-md">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
            {visualResult && (
              <div className="lg:w-72">
                <label className="text-xs font-medium text-gray-500 uppercase tracking-wide" htmlFor="visual-normalized-query">
                  {t('search.editSearch')}
                </label>
                <div className="flex gap-2 mt-1">
                  <input
                    id="visual-normalized-query"
                    className="input-field py-2"
                    value={visualResult.normalized_query || ''}
                    onChange={event => setVisualResult(current => ({
                      ...current,
                      normalized_query: event.target.value,
                    }))}
                  />
                  <button
                    type="button"
                    onClick={() => runTextSearch(visualResult.normalized_query || visualResult.fallback_query)}
                    className="btn-primary px-3"
                  >
                    {t('common.go')}
                  </button>
                </div>
              </div>
            )}
          </div>

          {visualResult && (
            <div className="mt-5 grid lg:grid-cols-2 gap-5">
              <div>
                <h3 className="text-sm font-semibold text-gray-950 mb-2">{t('search.similarResults')}</h3>
                {visualResult.matched_items?.length ? (
                  <div className="space-y-2">
                    {visualResult.matched_items.map(item => (
                      <Link
                        key={item.id}
                        to={`/restaurants/${item.branch_id}`}
                        className="block border border-gray-100 rounded-lg p-3 hover:border-brand-200"
                      >
                        <p className="font-medium text-gray-950">{item.name}</p>
                        <p className="text-sm text-gray-500">{item.branch_name} - {item.category}</p>
                        <p className="text-sm text-gray-700 mt-1">{t('search.price', { price: formatCurrency(item.price, item.currency || item.currency_code || 'INR', preferences) })}</p>
                      </Link>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">
                    {t('search.noExactMatch', { query: visualResult.fallback_query || 'product' })}
                  </p>
                )}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-950 mb-2">{t('search.matchedMerchants')}</h3>
                {visualResult.matched_merchants?.length ? (
                  <div className="space-y-2">
                    {visualResult.matched_merchants.map(merchant => (
                      <Link
                        key={merchant.id}
                        to={`/restaurants/${merchant.id}`}
                        className="block border border-gray-100 rounded-lg p-3 hover:border-brand-200"
                      >
                        <p className="font-medium text-gray-950">{merchant.branch_name || merchant.rest_name}</p>
                        <p className="text-sm text-gray-500">{merchant.branch_type} - {merchant.city || t('search.locationPending')}</p>
                        {merchant.distance_km !== null && merchant.distance_km !== undefined && (
                          <p className={`text-sm mt-1 ${merchant.is_serviceable ? 'text-emerald-700' : 'text-amber-700'}`}>
                            {t('search.distanceAway', { distance: formatNumber(merchant.distance_km, preferences, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) })}
                            {merchant.is_serviceable === false ? ` - ${t('search.outsideRadius')}` : ''}
                          </p>
                        )}
                      </Link>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">
                    {t('search.noBranchesMatched')}
                  </p>
                )}
              </div>
            </div>
          )}
        </section>
      )}

      {isLoading && <p className="text-gray-500">{t('search.searching')}</p>}
      {isError && <p className="text-red-500">{t('search.searchFailed')}</p>}
      {!isLoading && restaurants.length === 0 && (
        <div className="border border-dashed border-gray-300 rounded-lg py-12 px-4 text-center">
          <Search size={28} className="mx-auto text-gray-400" />
          <h2 className="font-semibold text-gray-950 mt-4">{t('search.noMatchingRestaurants')}</h2>
          <p className="text-sm text-gray-500 mt-2">
            {t('search.tryAnother')}
          </p>
        </div>
      )}

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {restaurants.map(restaurant => (
          <Link key={restaurant.id} to={`/restaurants/${restaurant.id}`} className="card block p-5 hover:shadow-md transition-shadow">
            <div className="flex items-start gap-4">
              <div className="h-16 w-20 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center flex-shrink-0 overflow-hidden">
                {restaurant.cover_image
                  ? <img src={restaurant.cover_image} alt="" className="h-full w-full object-cover" />
                  : <Utensils size={22} />}
              </div>
              <div className="min-w-0">
                <h2 className="font-semibold text-gray-950">{restaurant.rest_name}</h2>
                <p className="text-sm text-gray-500 flex items-center gap-1 mt-1"><MapPin size={13} /> {restaurant.rest_city}</p>
                {restaurant.merchant_verified && (
                  <p className="text-sm text-emerald-700 flex items-center gap-1 mt-1">
                    <ShieldCheck size={13} /> {t('search.verifiedMerchant')}
                  </p>
                )}
                <p className="text-sm text-gray-500 mt-2">{t('search.menuItems', { count: formatNumber(restaurant.item_count, preferences, { maximumFractionDigits: 0 }) })}</p>
                {restaurant.distance_km !== null && restaurant.distance_km !== undefined && (
                  <p className={`text-sm mt-1 ${restaurant.is_serviceable ? 'text-emerald-700' : 'text-amber-700'}`}>
                    {t('search.distanceAway', { distance: formatNumber(restaurant.distance_km, preferences, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) })}
                    {restaurant.is_serviceable === false ? ` - ${t('search.outsideRadius')}` : ''}
                  </p>
                )}
              </div>
            </div>
            <div className="flex flex-wrap gap-2 mt-4">
              {restaurant.categories.map(item => <span key={item} className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-md">{item}</span>)}
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}
