import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Heart, MapPin, Star, Utensils } from 'lucide-react'
import { listFavoriteRestaurants, toggleFavoriteRestaurant } from '../api/restaurants'
import useTitle from '../hooks/useTitle'

export default function FavoritesPage() {
  useTitle('Favorite restaurants')
  const queryClient = useQueryClient()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['favorite-restaurants'],
    queryFn: async () => (await listFavoriteRestaurants()).data,
  })
  const restaurants = data?.results || data || []

  const removeFavorite = async restaurant => {
    try {
      await toggleFavoriteRestaurant(restaurant.id)
      await queryClient.invalidateQueries({ queryKey: ['favorite-restaurants'] })
      toast.success(`${restaurant.rest_name} removed`)
    } catch {
      toast.error('Could not update favorites.')
    }
  }

  if (isLoading) return <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 text-gray-500">Loading favorites...</div>
  if (isError) return <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 text-red-600">Could not load favorites.</div>

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
      <div className="mb-7">
        <h1 className="text-2xl font-bold text-gray-950">Favorite restaurants</h1>
        <p className="text-gray-500 mt-1">Your saved places, ready when you are.</p>
      </div>
      {!restaurants.length ? (
        <div className="border border-dashed border-gray-300 rounded-lg py-14 text-center">
          <Heart size={36} className="text-gray-300 mx-auto" />
          <h2 className="font-semibold text-gray-900 mt-4">No favorites yet</h2>
          <Link to="/search" className="btn-primary inline-flex mt-5">Explore restaurants</Link>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {restaurants.map(restaurant => (
            <article key={restaurant.id} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
              <Link to={`/restaurants/${restaurant.id}`} className="block h-36 bg-gray-100 overflow-hidden">
                {restaurant.cover_image
                  ? <img src={restaurant.cover_image} alt="" className="h-full w-full object-cover" />
                  : <span className="h-full flex items-center justify-center"><Utensils className="text-brand-500" size={30} /></span>}
              </Link>
              <div className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <Link to={`/restaurants/${restaurant.id}`} className="font-semibold text-gray-950 hover:text-brand-600">{restaurant.rest_name}</Link>
                    <p className="text-sm text-gray-500 flex items-center gap-1 mt-1"><MapPin size={13} /> {restaurant.rest_city}</p>
                  </div>
                  <span className="text-sm flex items-center gap-1 text-amber-600"><Star size={14} /> {restaurant.average_rating ? Number(restaurant.average_rating).toFixed(1) : 'New'}</span>
                </div>
                <div className="flex items-center justify-between mt-4">
                  <span className={`text-sm font-medium ${restaurant.is_open ? 'text-emerald-700' : 'text-red-600'}`}>{restaurant.is_open ? 'Open' : 'Closed'}</span>
                  <button type="button" onClick={() => removeFavorite(restaurant)} className="p-2 text-red-500 hover:bg-red-50 rounded-lg" title="Remove favorite"><Heart size={18} className="fill-red-500" /></button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
