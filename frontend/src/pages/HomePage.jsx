import { useEffect, useMemo, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Camera, Clock, MapPin, Search, ShieldCheck, ShoppingBag, Star, Utensils, Zap } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { getCustomerRecommendations, trackRecommendationEvent } from '../api/intelligence'
import { listRestaurants } from '../api/restaurants'
import { useAuth } from '../context/AuthContext'
import { useLocationContext } from '../context/LocationContext'
import { usePreferences } from '../context/PreferencesContext'
import { formatCurrency } from '../lib/formatters'
import useTitle from '../hooks/useTitle'

const categoryCards = [
  { value: 'Vegetarian', labelKey: 'search.categories.vegetarian', tone: 'bg-emerald-50 text-emerald-700 border-emerald-100' },
  { value: 'Non-Vegetarian', labelKey: 'search.categories.nonVegetarian', tone: 'bg-red-50 text-red-700 border-red-100' },
  { value: 'Beverages', labelKey: 'search.categories.beverages', tone: 'bg-sky-50 text-sky-700 border-sky-100' },
  { value: 'Desserts', labelKey: 'search.categories.desserts', tone: 'bg-fuchsia-50 text-fuchsia-700 border-fuchsia-100' },
]

const recommendationSections = [
  ['recommended_for_you', 'home.recommendations.recommendedForYou'],
  ['nearby_fast', 'home.recommendations.nearbyFast'],
  ['popular_near_you', 'home.recommendations.popularNearYou'],
  ['order_again', 'home.recommendations.orderAgain'],
  ['top_rated', 'home.recommendations.topRated'],
  ['new_to_try', 'home.recommendations.newToTry'],
]

function RestaurantCard({ restaurant, recommendation, sectionKey }) {
  const { t } = useTranslation()
  const { preferences } = usePreferences()
  const hasDistance = restaurant.distance_km !== null && restaurant.distance_km !== undefined
  const deliveryFee = formatCurrency(
    restaurant.delivery_fee,
    restaurant.currency_code || restaurant.currency || 'GNF',
    preferences,
  )
  const handleClick = () => {
    if (!recommendation) return
    trackRecommendationEvent({
      surface: sectionKey || 'home',
      object_type: 'restaurant',
      object_id: String(restaurant.id),
      action: 'click',
      score: recommendation.score,
      reason_codes: recommendation.reason_codes || [],
    }).catch(() => {})
  }
  return (
    <Link
      to={`/restaurants/${restaurant.id}`}
      onClick={handleClick}
      className="card block overflow-hidden hover:shadow-md transition-shadow"
    >
      <div className="h-36 bg-gray-100 flex items-center justify-center border-b border-gray-100 overflow-hidden">
        {restaurant.cover_image
          ? <img src={restaurant.cover_image} alt="" className="h-full w-full object-cover" />
          : <Utensils className="text-brand-500" size={34} />}
      </div>
      <div className="p-4">
        {recommendation?.reason_label && (
          <span className="inline-flex text-xs font-medium bg-brand-50 text-brand-700 px-2 py-1 rounded-md mb-3">
            {recommendation.reason_label}
          </span>
        )}
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold text-gray-900">{restaurant.rest_name}</h3>
            <p className="text-sm text-gray-500 flex items-center gap-1 mt-1">
              <MapPin size={13} /> {restaurant.rest_city}
            </p>
            {restaurant.merchant_verified && (
              <p className="text-xs font-medium text-emerald-700 flex items-center gap-1 mt-1">
                <ShieldCheck size={13} /> {t('search.verifiedMerchant')}
              </p>
            )}
            <p className={`text-xs font-medium mt-1 ${restaurant.is_open ? 'text-emerald-700' : 'text-red-600'}`}>
              {restaurant.is_open ? t('home.openWithDelivery', { fee: deliveryFee }) : t('home.closed')}
            </p>
            {hasDistance && (
              <p className={`text-xs font-medium mt-1 ${restaurant.is_serviceable ? 'text-emerald-700' : 'text-amber-700'}`}>
                {t('search.distanceAway', { distance: Number(restaurant.distance_km).toFixed(1) })}
                {restaurant.is_serviceable === false ? ` - ${t('search.outsideRadius')}` : ''}
              </p>
            )}
          </div>
          <span className="inline-flex items-center gap-1 text-xs font-medium bg-emerald-50 text-emerald-700 px-2 py-1 rounded-md">
            <Star size={12} /> {restaurant.average_rating ? Number(restaurant.average_rating).toFixed(1) : t('home.new')}
          </span>
        </div>
        <p className="text-sm text-gray-500 mt-3 line-clamp-2">{restaurant.rest_address}</p>
        <div className="flex flex-wrap gap-2 mt-4">
          {restaurant.categories.slice(0, 3).map(category => (
            <span key={category} className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-md">{category}</span>
          ))}
        </div>
      </div>
    </Link>
  )
}

function RecommendationSection({ sectionKey, title, items }) {
  const { t } = useTranslation()
  if (!items?.length) return null
  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 pb-9">
      <div className="flex items-center justify-between gap-4 mb-5">
        <h2 className="text-xl font-semibold text-gray-900">{t(title)}</h2>
        <Link to="/search" className="text-sm font-medium text-brand-600 hover:underline">{t('home.viewAll')}</Link>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {items.slice(0, 4).map(item => (
          <RestaurantCard
            key={`${sectionKey}-${item.restaurant.id}`}
            restaurant={item.restaurant}
            recommendation={item}
            sectionKey={sectionKey}
          />
        ))}
      </div>
    </section>
  )
}

export default function HomePage() {
  const { t } = useTranslation()
  useTitle(t('home.title'))
  const { user } = useAuth()
  const { currentLocation } = useLocationContext()
  const navigate = useNavigate()
  const trackedImpressions = useRef(new Set())
  const restaurantParams = useMemo(() => (
    currentLocation ? {
      latitude: currentLocation.latitude,
      longitude: currentLocation.longitude,
    } : undefined
  ), [currentLocation])
  const { data, isLoading, isError } = useQuery({
    queryKey: ['restaurants', 'home', restaurantParams],
    queryFn: async () => (await listRestaurants(restaurantParams)).data,
  })
  const recommendationsQuery = useQuery({
    queryKey: ['customer-recommendations', restaurantParams],
    queryFn: async () => (await getCustomerRecommendations(restaurantParams)).data,
    staleTime: 30 * 1000,
    retry: 1,
  })

  const restaurants = data?.results || data || []
  const recommendations = recommendationsQuery.data || {}
  const visibleRecommendationSections = recommendationSections
    .map(([sectionKey, title]) => ({
      sectionKey,
      title,
      items: recommendations[sectionKey] || [],
    }))
    .filter(section => section.items.length > 0)
  const hasRecommendations = visibleRecommendationSections.length > 0

  useEffect(() => {
    if (!hasRecommendations) return
    visibleRecommendationSections.forEach(section => {
      section.items.slice(0, 4).forEach(item => {
        const key = `${section.sectionKey}:${item.restaurant.id}`
        if (trackedImpressions.current.has(key)) return
        trackedImpressions.current.add(key)
        trackRecommendationEvent({
          surface: section.sectionKey,
          object_type: 'restaurant',
          object_id: String(item.restaurant.id),
          action: 'impression',
          score: item.score,
          reason_codes: item.reason_codes || [],
        }).catch(() => {})
      })
    })
  }, [hasRecommendations, visibleRecommendationSections])

  const handleSearch = e => {
    e.preventDefault()
    const value = new FormData(e.currentTarget).get('search')?.trim()
    navigate(value ? `/search?q=${encodeURIComponent(value)}` : '/search')
  }

  return (
    <div>
      <section className="bg-white border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10 lg:py-14">
          <div className="grid lg:grid-cols-[1.1fr_0.9fr] gap-8 items-center">
            <div>
              <p className="text-sm font-medium text-brand-600 mb-2">{t('home.eyebrow')}</p>
              <h1 className="text-3xl sm:text-4xl font-bold leading-tight text-gray-950">
                {t('home.heroTitle', { name: user?.first_name || t('home.there') })}
              </h1>
              <p className="text-gray-600 mt-3 max-w-xl">
                {t('home.heroSubtitle')}
              </p>
              <form onSubmit={handleSearch} className="mt-6 max-w-xl flex gap-2">
                <div className="relative flex-1">
                  <Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input name="search" className="input-field pl-10" placeholder={t('search.placeholder')} />
                </div>
                <button className="btn-primary px-5">{t('common.search')}</button>
              </form>
              <Link
                to="/search"
                className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-brand-600 hover:text-brand-700"
              >
                <Camera size={16} /> {t('search.searchByImage')}
              </Link>
              <div className="flex flex-wrap gap-3 mt-5 text-sm">
                <span className="inline-flex items-center gap-2 bg-gray-100 text-gray-700 px-3 py-2 rounded-lg"><Clock size={15} /> 20-40 min</span>
                <span className="inline-flex items-center gap-2 bg-gray-100 text-gray-700 px-3 py-2 rounded-lg"><Zap size={15} /> {t('home.fastCheckout')}</span>
              </div>
            </div>
            <div className="bg-gray-950 text-white p-6 rounded-lg">
              <div className="flex items-center gap-3 mb-5">
                <ShoppingBag className="text-brand-400" />
                <div>
                  <p className="font-semibold">{t('home.orderingLive')}</p>
                  <p className="text-sm text-gray-300">{t('home.orderingLiveBody')}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-white/10 rounded-lg p-4">
                  <p className="text-2xl font-bold">{restaurants.length}</p>
                  <p className="text-gray-300">{t('home.restaurants')}</p>
                </div>
                <div className="bg-white/10 rounded-lg p-4">
                  <p className="text-2xl font-bold">{restaurants.reduce((sum, item) => sum + item.item_count, 0)}</p>
                  <p className="text-gray-300">{t('home.menuItems')}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-7xl mx-auto px-4 sm:px-6 py-10">
        <div className="flex items-center justify-between gap-4 mb-5">
          <h2 className="text-xl font-semibold text-gray-900">{t('home.browseByCategory')}</h2>
          <Link to="/search" className="text-sm font-medium text-brand-600 hover:underline">{t('home.viewAll')}</Link>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {categoryCards.map(category => (
            <Link key={category.value} to={`/search?category=${encodeURIComponent(category.value)}`} className={`border ${category.tone} rounded-lg p-5`}>
              <span className="font-medium text-sm">{t(category.labelKey)}</span>
            </Link>
          ))}
        </div>
      </section>

      {hasRecommendations && (
        <div className="pt-10">
          {visibleRecommendationSections.map(section => (
            <RecommendationSection
              key={section.sectionKey}
              sectionKey={section.sectionKey}
              title={section.title}
              items={section.items}
            />
          ))}
        </div>
      )}

      {!recommendationsQuery.isLoading && !recommendationsQuery.isError && !hasRecommendations && restaurants.length === 0 && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 pb-10">
          <div className="card p-8 text-center">
            <Utensils className="mx-auto text-brand-500" size={34} />
            <h2 className="font-semibold text-gray-950 mt-4">{t('home.noRecommendations')}</h2>
            <p className="text-gray-500 mt-1">{t('home.noRecommendationsBody')}</p>
          </div>
        </section>
      )}

      <section className="max-w-7xl mx-auto px-4 sm:px-6 pb-16">
        <div className="flex items-center justify-between gap-4 mb-5">
          <h2 className="text-xl font-semibold text-gray-900">{t('home.openRestaurants')}</h2>
          <Link to="/search" className="text-sm font-medium text-brand-600 hover:underline">{t('home.searchMenus')}</Link>
        </div>
        {isLoading && <p className="text-gray-500">{t('home.loadingRestaurants')}</p>}
        {isError && <p className="text-red-500">{t('home.loadRestaurantsFailed')}</p>}
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {restaurants.map(restaurant => <RestaurantCard key={restaurant.id} restaurant={restaurant} />)}
        </div>
      </section>
    </div>
  )
}
